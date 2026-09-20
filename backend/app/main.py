from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from .models import ProductSearchRequest, LayoutRequest, LayoutEvaluateRequest, GenerateRequest, ExplainRequest, SimulationRequest, ImproveRequest, Design, RoomSpec, CompareDesignsRequest, DesignComparison
from .repository import products, search
from .ai import parse_requirements, explain
from .spatial.validation import validate_layout
from .optimizer.service import generate
from .pdf_export import build_design_pdf

app = FastAPI(title='KOHLER SpatialAI')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://kohler-spatial-ai-eta.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/products')
def get_products():
    return products()

@app.post('/requirements/parse')
def parse(body: dict):
    return parse_requirements(body.get('text', ''))

@app.post('/products/search')
def product_search(body: ProductSearchRequest):
    return search(body.categories, body.keywords, body.style, body.budget_inr)

@app.post('/design/validate')
def validate(body: LayoutRequest):
    return validate_layout(body)

@app.post('/design/evaluate')
def evaluate_design(body: LayoutEvaluateRequest):
    val_res = validate_layout(LayoutRequest(room=body.room, fixtures=body.fixtures, budget_inr=body.budget_inr))
    from .repository import product_by_sku
    from .optimizer.scoring import compute_design_score
    from .models import RequirementSatisfaction

    prods = [product_by_sku(f.sku) for f in body.fixtures]
    valid_prods = [p for p in prods if p is not None]

    score = compute_design_score(
        valid_prods,
        val_res,
        body.budget_inr or 300000,
        body.style,
        body.room.width_mm,
        body.room.depth_mm,
        profile_name=body.design_name,
        fixtures=body.fixtures,
        room=body.room,
    )

    req_sat = []
    seen_cats = set()
    for p in valid_prods:
        if p.category not in seen_cats:
            seen_cats.add(p.category)
            req_sat.append(RequirementSatisfaction(
                requested=p.category,
                satisfied=True,
                selected_category=p.category,
                product_name=p.name,
                sku=p.sku,
            ))

    from .spatial.wash_zone import derive_wash_zone
    return Design(
        name=body.design_name,
        fixtures=body.fixtures,
        products=valid_prods,
        validation=val_res,
        score=score,
        requirements_satisfaction=req_sat,
        room=body.room,
        wash_zone=derive_wash_zone(body.fixtures, valid_prods, body.room),
    )

@app.post('/design/improve')
def improve_design(body: ImproveRequest):
    metric = body.metric.lower()
    design = body.current_design
    room = design.room or RoomSpec(width_mm=1800, depth_mm=2400)
    budget = body.budget_inr or 300000
    style = body.style

    from .repository import products as get_all_products
    all_prods = get_all_products()

    improved_products = list(design.products)
    recommendation_reason = ""

    for i, p in enumerate(improved_products):
        cat_candidates = [item for item in all_prods if item.category == p.category and item.price_inr <= budget]
        if not cat_candidates:
            continue

        if 'style' in metric:
            from .optimizer.scoring import compute_style_match
            baseline, _, _ = compute_style_match(improved_products, style)
            baseline_val = baseline or 0.0
            best_prod = None
            best_val = baseline_val
            for item in cat_candidates:
                if item.sku == p.sku:
                    continue
                trial = list(improved_products); trial[i] = item
                s, _, _ = compute_style_match(trial, style)
                if s is not None and s > best_val:
                    best_val = s
                    best_prod = item
            if best_prod:
                improved_products[i] = best_prod
                recommendation_reason = f"Replaced {p.name} with {best_prod.name} ({best_prod.style or 'matching'} style) to increase style match score from {baseline_val:.0f} to {best_val:.0f}/100."

        elif 'budget' in metric or 'cost' in metric:
            # Step down incrementally: find the next cheapest product just below current price
            cheaper = sorted([item for item in cat_candidates if item.price_inr < p.price_inr], key=lambda item: item.price_inr, reverse=True)
            if cheaper:
                next_cheaper = cheaper[0]  # highest price that is still cheaper than current
                improved_products[i] = next_cheaper
                recommendation_reason = f"Replaced {p.name} (₹{p.price_inr:,}) with {next_cheaper.name} (₹{next_cheaper.price_inr:,}) to reduce cost."

        elif 'fit' in metric or 'spatial' in metric:
            compact = min(cat_candidates, key=lambda item: (item.width_mm or 0) * (item.depth_mm or 0))
            if (compact.width_mm or 0) * (compact.depth_mm or 0) < (p.width_mm or 0) * (p.depth_mm or 0):
                improved_products[i] = compact
                recommendation_reason = f"Replaced {p.name} with more compact {compact.name} to optimize spatial fit."

        elif 'compatibility' in metric:
            from .spatial.compatibility import evaluate_compatibility
            baseline = evaluate_compatibility(improved_products).score or 0.0
            best_prod = None
            best_score = baseline
            for item in cat_candidates:
                if item.sku == p.sku:
                    continue
                trial = list(improved_products); trial[i] = item
                s = evaluate_compatibility(trial).score or 0.0
                if s > best_score:
                    best_score = s
                    best_prod = item
            if best_prod:
                improved_products[i] = best_prod
                recommendation_reason = f"Replaced {p.name} with {best_prod.name} to increase compatibility score from {baseline:.0f} to {best_score:.0f}/100."

    from .optimizer.service import _place_fixtures
    placements = _place_fixtures(improved_products, room.width_mm, room.depth_mm, budget, room)
    if placements is None:
        # Sync old fixture placements to use corresponding new product SKUs
        placements = []
        for f in design.fixtures:
            matching_p = next((p for p in design.products if p.sku == f.sku), None)
            if matching_p:
                new_p = next((np for np in improved_products if np.category == matching_p.category), None)
                if new_p:
                    placements.append(FixturePlacement(sku=new_p.sku, x_mm=f.x_mm, y_mm=f.y_mm, rotation_deg=f.rotation_deg))
                else:
                    placements.append(f)
            else:
                placements.append(f)

    val_res = validate_layout(LayoutRequest(room=room, fixtures=placements, budget_inr=budget))
    from .optimizer.scoring import compute_design_score
    score = compute_design_score(improved_products, val_res, budget, style, room.width_mm, room.depth_mm, profile_name=design.name, fixtures=placements, room=room)

    # Verify metric targeted improvement
    no_improvement = False
    if 'fit' in metric or 'spatial' in metric:
        if not val_res.valid:
            no_improvement = True
            recommendation_reason = "No verified spatial improvement was found without changing your current requirements."
    elif 'budget' in metric or 'cost' in metric:
        if not val_res.valid or val_res.total_price_inr >= design.validation.total_price_inr:
            no_improvement = True
            recommendation_reason = "No lower-cost combination was found that satisfies all spatial and budget constraints."
    elif 'style' in metric:
        if not val_res.valid:
            no_improvement = True
            recommendation_reason = "No valid style variation satisfied all room constraints."
        elif not recommendation_reason and improved_products == list(design.products):
            # Fallback alternative collection swap if products were identical
            for i, p in enumerate(improved_products):
                cat_candidates = [item for item in all_prods if item.category == p.category and item.price_inr <= budget and item.sku != p.sku]
                if cat_candidates:
                    alt_prod = cat_candidates[0]
                    improved_products[i] = alt_prod
                    recommendation_reason = f"Explored style variation: replaced {p.name} with {alt_prod.name}."
                    break
    elif 'compatibility' in metric:
        if not val_res.valid:
            no_improvement = True
            recommendation_reason = "No valid compatibility variation satisfied all room constraints."
        elif not recommendation_reason and improved_products == list(design.products):
            # Fallback alternative compatible swap if products were identical
            for i, p in enumerate(improved_products):
                cat_candidates = [item for item in all_prods if item.category == p.category and item.price_inr <= budget and item.sku != p.sku]
                if cat_candidates:
                    alt_prod = cat_candidates[0]
                    improved_products[i] = alt_prod
                    recommendation_reason = f"Explored compatibility variation: replaced {p.name} with {alt_prod.name}."
                    break

    if no_improvement:
        return {
            'improved_design': None,
            'no_improvement': True,
            'reason': recommendation_reason,
        }

    improved_design = Design(
        name=design.name,
        fixtures=placements,
        products=improved_products,
        validation=val_res,
        score=score,
        requirements_satisfaction=design.requirements_satisfaction,
        room=room,
    )

    return {
        'improved_design': improved_design,
        'no_improvement': False,
        'reason': recommendation_reason or f"Optimized design for improved {metric} score."
    }

@app.post('/design/generate')
def design_generate(body: GenerateRequest):
    try:
        return generate(body)
    except ValueError as e:
        raise HTTPException(422, str(e))

@app.post('/design/explain')
def design_explain(body: ExplainRequest):
    return {'explanation': explain(body.products, body.validation, body.score, body.budget_inr, body.rejected)}

@app.post('/design/compare')
def compare_designs(body: CompareDesignsRequest):
    """Deterministic alternatives summary; the frontend only renders these facts."""
    selected = body.selected
    comparisons=[]
    for alternative in body.alternatives:
        cost_delta=alternative.validation.total_price_inr-selected.validation.total_price_inr
        deltas={
            'spatial fit': alternative.score.spatial_fit-selected.score.spatial_fit,
            'budget efficiency': alternative.score.budget_fit-selected.score.budget_fit,
            'style alignment': (alternative.score.style_match or 0)-(selected.score.style_match or 0),
            'compatibility': (alternative.score.compatibility or 0)-(selected.score.compatibility or 0),
        }
        strongest=max(deltas,key=deltas.get)
        if cost_delta > 0 and alternative.score.total <= selected.score.total:
            reason, headline='budget_tradeoff', 'Higher cost for limited additional benefit'
        elif cost_delta < 0:
            reason, headline='cost_efficiency_tradeoff', 'Lower cost with a different performance trade-off'
        else:
            reason, headline='profile_tradeoff', f'Different profile prioritizes {strongest}'
        comparisons.append(DesignComparison(
            design=alternative.name,primary_reason=reason,headline=headline,
            details=[f"Cost {'+' if cost_delta >= 0 else '-'}₹{abs(cost_delta):,} versus selected design", f"{strongest.title()} {'+' if deltas[strongest] >= 0 else ''}{deltas[strongest]:.1f} points", f"Overall score {alternative.score.total}/100 versus {selected.score.total}/100"]
        ))
    return comparisons

@app.post('/design/simulate')
def simulate(body: SimulationRequest):
    try:
        before = generate(body.before)
        after = generate(body.modified)
    except ValueError as e:
        raise HTTPException(422, str(e))
    diff = round(after[0].score.total - before[0].score.total, 1)
    cost_diff = after[0].validation.total_price_inr - before[0].validation.total_price_inr
    if diff > 0:
        trade_off_msg = f"Simulated option increases score by +{diff} pts (from {before[0].score.total} to {after[0].score.total}) with cost change of ₹{cost_diff:+,}."
    elif diff < 0:
        trade_off_msg = f"Simulated option reduces score by {diff} pts (from {before[0].score.total} to {after[0].score.total}) with cost change of ₹{cost_diff:+,}."
    else:
        trade_off_msg = f"Score remains {before[0].score.total}/100 with cost change of ₹{cost_diff:+,}."

    return {
        'before': before,
        'after': after,
        'trade_off': trade_off_msg
    }

@app.post('/design/export/pdf')
def export_pdf(body: Design):
    return Response(
        content=build_design_pdf(body),
        media_type='application/pdf',
        headers={'Content-Disposition': 'attachment; filename=kohler-spatialai-design.pdf'}
    )

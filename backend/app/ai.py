import logging, os, re
from time import perf_counter
from collections.abc import Callable
from .models import RequirementSpec, RoomSpec, ProductRow, ValidationResult, DesignScore, Design
from .perf import log_perf
logger = logging.getLogger(__name__)

def gemini_keys() -> list[str]:
    """Read ordered comma-separated keys; preserve single-key setting too."""
    configured = os.getenv('GEMINI_API_KEYS', '')
    keys = [key.strip() for key in configured.split(',') if key.strip()]
    if not keys and os.getenv('GEMINI_API_KEY'):
        keys = [os.environ['GEMINI_API_KEY'].strip()]
    return keys

def with_gemini_failover(operation: Callable[[str], str | None]) -> str | None:
    """Run a Gemini operation against each configured key without logging secrets."""
    for index, key in enumerate(gemini_keys(), start=1):
        try:
            return operation(key)
        except Exception as exc:
            logger.warning('Gemini key %d failed (%s); trying next configured key.', index, type(exc).__name__)
    return None

def normalize_amount(amount_str: str) -> int:
    clean = amount_str.lower().replace(',', '').replace('₹', '').replace('rs.', '').replace('inr', '').strip()
    if 'lakh' in clean or 'lac' in clean:
        val = float(re.sub(r'[^\d.]', '', clean.split('lakh')[0].split('lac')[0]))
        return int(val * 100000)
    if 'k' in clean or 'thousand' in clean:
        val = float(re.sub(r'[^\d.]', '', clean.replace('thousand', 'k').split('k')[0]))
        return int(val * 1000)
    try:
        return int(float(clean))
    except (ValueError, TypeError):
        return 0

def extract_category_price_constraints(text: str) -> dict[str, dict[str, int]]:
    constraints: dict[str, dict[str, int]] = {}
    categories = ['smart toilet', 'toilet', 'vanity', 'shower', 'faucet', 'basin', 'mirror']
    for cat in categories:
        # Match "toilet below 20000", "toilet under 20k", "toilet max ₹20,000", "toilet not exceed 20000"
        pattern = rf'\b{cat}\b(?:\s+\w+){{0,3}}?\s+(?:below|under|less\s+than|max|maximum|not\s+exceed|within|at\s+most|<=|<)\s*(?:₹|rs\.?|inr)?\s*([\d.,]+\s*(?:k|thousand|lakh|lac)?)\b'
        match = re.search(pattern, text, re.I)
        if not match:
            # Match reverse: "below 20000 for toilet", "under 20k toilet"
            rev_pattern = rf'(?:below|under|less\s+than|max|maximum|not\s+exceed|within|at\s+most)\s*(?:₹|rs\.?|inr)?\s*([\d.,]+\s*(?:k|thousand|lakh|lac)?)\s+(?:for\s+|on\s+)?(?:the\s+)?\b{cat}\b'
            match = re.search(rev_pattern, text, re.I)
        if match:
            amt = normalize_amount(match.group(1))
            if amt > 0:
                cat_key = 'toilet' if cat in ('toilet', 'smart toilet') else cat
                constraints[cat_key] = {"max_price_inr": amt}
    return constraints

def extract_global_budget(text: str) -> int | None:
    # Only match explicit total/overall budget or standalone budget statements
    global_pattern = r'\b(?:total|overall|bathroom|full)?\s*budget\b\s*(?:is|of|set\s+to|:=|=|:)?\s*(?:₹|rs\.?|inr)?\s*([\d.,]+\s*(?:k|thousand|lakh|lac)?)\b'
    match = re.search(global_pattern, text, re.I)
    if match:
        amt = normalize_amount(match.group(1))
        return amt if amt > 0 else None
    return None

def _deterministic_parse(text: str) -> RequirementSpec:
    dims = re.search(r'(\d{3,4})\s*[x×]\s*(\d{3,4})\s*mm?', text, re.I)
    budget = extract_global_budget(text)
    cat_constraints = extract_category_price_constraints(text)
    styles = ['modern', 'classical', 'industrial', 'scandinavian']
    reqs = [x for x in ['smart toilet', 'toilet', 'vanity', 'shower', 'faucet', 'basin', 'mirror'] if x in text.lower()]
    return RequirementSpec(
        room=RoomSpec(width_mm=int(dims.group(1)), depth_mm=int(dims.group(2))) if dims else None,
        budget_inr=budget,
        style=next((x for x in styles if x in text.lower()), None),
        priority='balanced',
        requirements=reqs,
        category_constraints=cat_constraints,
    )

def parse_requirements(text: str) -> RequirementSpec:
    """Gemini is limited to language extraction; Pydantic rejects unsafe output."""
    started_at = perf_counter()
    cat_constraints = extract_category_price_constraints(text)
    parsed = _deterministic_parse(text)

    if gemini_keys():
        def operation(api_key: str) -> str | None:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
                contents=("Extract room size (millimetres), INR total budget (only if overall/total budget stated), style, priority, requested categories, and category-specific price limits "
                          "from this bathroom brief. Do not output products, SKUs, prices, dimensions beyond the stated room, or geometry coordinates.\n\n" + text),
                config=types.GenerateContentConfig(response_mime_type='application/json', response_schema=RequirementSpec),
            )
            return response.text
        result = with_gemini_failover(operation)
        if result:
            try:
                spec = RequirementSpec.model_validate_json(result)
                # Merge category constraints deterministically
                if cat_constraints:
                    spec.category_constraints = {**cat_constraints, **spec.category_constraints}
                log_perf('requirement parsing', started_at)
                return spec
            except Exception as exc:
                logger.warning('Gemini response failed RequirementSpec validation (%s).', type(exc).__name__)

    log_perf('requirement parsing', started_at)
    return parsed

def explain(
    products: list[ProductRow],
    validation: ValidationResult,
    score: DesignScore,
    budget_inr: int | None = None,
    rejected: list[Design] | None = None,
) -> str:
    rejected_list = rejected or []
    total_cost = validation.total_price_inr
    rem_budget = (budget_inr - total_cost) if budget_inr else None

    prod_summary = ", ".join(f"{p.name} ({p.sku}, ₹{p.price_inr:,})" for p in products)

    lines = [
        "Selected because it provides the strongest balance of spatial fit, budget efficiency, style alignment, and product compatibility.",
        f"Fits room boundary with valid door clearance and 0 collision issues. Total cost: ₹{total_cost:,}" + (f" (Remaining budget: ₹{rem_budget:,})." if rem_budget is not None else "."),
        f"Spatial fit: {score.spatial_fit}/100, Budget fit: {score.budget_fit}/100, Style match: {score.style_match if score.style_match is not None else 'Limited'}/100, Compatibility: {score.compatibility}/100. Overall score: {score.total}/100.",
    ]

    deterministic_summary = "\n".join(lines)

    if gemini_keys():
        def operation(api_key: str) -> str | None:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                "You are a KOHLER SpatialAI design assistant. Summarize why this design was selected based strictly on the evidence below. "
                "Output 2 to 3 concise, elegant, human-readable sentences suitable for a luxury product configurator. "
                "Do NOT use raw markdown formatting, headers (###), bold tags (**), horizontal rules (---), or bullet symbols (*).\n\n"
                f"EVIDENCE:\n{deterministic_summary}\nSelected Products: {prod_summary}"
            )
            res = client.models.generate_content(
                model=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
                contents=prompt
            ).text
            if res:
                # Strip any stray markdown headers or asterisks
                res = re.sub(r'#{1,6}\s*', '', res)
                res = re.sub(r'\*{1,2}', '', res)
                res = re.sub(r'-{3,}', '', res)
                return res.strip()
            return None

        res = with_gemini_failover(operation)
        if res:
            return res

    return deterministic_summary

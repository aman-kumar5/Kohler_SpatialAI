from pathlib import Path
import pandas as pd
from .models import ProductRow

CSV_PATH = Path(__file__).parent / 'data' / 'kohler_products.csv'

_cache: list[ProductRow] | None = None
_sku_cache: dict[str, ProductRow] | None = None


def _load() -> list[ProductRow]:
    global _cache, _sku_cache
    if _cache is not None:
        return _cache
    df = pd.read_csv(CSV_PATH)
    rows = []
    for row in df.to_dict('records'):
        cleaned = {k: (None if (isinstance(v, float) and pd.isna(v)) else v)
                   for k, v in row.items()}
        try:
            rows.append(ProductRow.from_csv_row(cleaned))
        except Exception:
            pass  # Skip malformed rows; never fabricate
    _cache = rows
    _sku_cache = {product.sku: product for product in rows}
    return _cache


def products() -> list[ProductRow]:
    return _load()


def product_by_sku(sku: str) -> ProductRow | None:
    _load()
    return (_sku_cache or {}).get(sku)


def search(
    categories: list[str],
    keywords: list[str],
    style: str | None,
    budget: int | None,
    max_price: int | None = None,
) -> list[ProductRow]:
    from .optimizer.scoring import compute_style_match
    hits = []
    for p in _load():
        if categories and p.category not in categories:
            continue
        if budget is not None and p.price_inr > budget:
            continue
        if max_price is not None and p.price_inr > max_price:
            continue
        text = f'{p.name} {p.keywords or ""}'.lower()
        rank = sum(k.lower() in text for k in keywords)
        # Soft style bonus using catalog style matching engine
        style_bonus = 0.0
        if style:
            s_score, _, _ = compute_style_match([p], style)
            if s_score is not None:
                style_bonus = s_score / 10.0
        hits.append((rank * 10 + style_bonus, p))
    return [p for _, p in sorted(hits, key=lambda x: (-x[0], x[1].price_inr, x[1].sku))]

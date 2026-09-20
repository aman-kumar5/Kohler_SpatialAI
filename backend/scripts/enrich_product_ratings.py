import pandas as pd
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / 'app' / 'data' / 'kohler_products.csv'

def calculate_ratings(row):
    name = str(row.get('product_name', '')).lower()
    cat = str(row.get('category', '')).lower()
    inst = str(row.get('installation_type', '')).lower()
    feat = str(row.get('features', '')).lower()
    coll = str(row.get('collection', '')).lower()

    # Accessibility Heuristic
    acc = 75.0
    if 'wall-hung' in inst or 'wall-hung' in name or 'wall' in feat:
        acc = 85.0
    if 'smart' in cat or 'veil' in name or 'eir' in name or 'innate' in name or 'bidet' in feat or 'touchless' in feat:
        acc = 92.0
    elif cat == 'shower':
        w = float(row.get('width_mm', 0) or 0)
        acc = 88.0 if w >= 900 else 72.0
    elif cat == 'faucet':
        acc = 86.0 if 'sensor' in feat or 'single-lever' in feat or 'touchless' in feat else 80.0
    elif cat == 'vanity':
        acc = 82.0 if 'wall-hung' in inst else 70.0

    # Sustainability Heuristic
    sust = 72.0
    if 'dual-flush' in feat or 'dual flush' in feat or 'eco' in feat or 'water-saving' in feat:
        sust = 90.0
    elif 'smart' in cat or 'veil' in name or 'eir' in name:
        sust = 88.0
    elif cat == 'faucet':
        sust = 84.0 if 'eco' in feat or 'aerator' in feat or 'flow' in feat else 78.0
    elif cat == 'shower':
        sust = 82.0 if 'eco' in feat or 'air-induction' in feat or 'catalyst' in feat else 76.0
    elif cat in ('toilet', 'smart_toilet'):
        sust = 80.0
    elif cat in ('basin', 'vanity'):
        sust = 74.0

    return pd.Series([
        acc,
        sust,
        "Estimated planning score based on installation type, dimensions and spatial planning characteristics.",
        "Estimated planning score based on available catalog features such as water-use information, product type and installation characteristics.",
        "estimated_from_catalog"
    ])

def main():
    df = pd.read_csv(CSV_PATH)
    cols = ['accessibility_rating', 'sustainability_rating', 'accessibility_basis', 'sustainability_basis', 'rating_provenance']
    df[cols] = df.apply(calculate_ratings, axis=1)
    df.to_csv(CSV_PATH, index=False)
    print(f"Successfully enriched {len(df)} products in {CSV_PATH}")

if __name__ == '__main__':
    main()

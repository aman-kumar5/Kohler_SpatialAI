import sys
from pathlib import Path
import pandas as pd

CSV_PATH = Path(__file__).parent.parent / 'app' / 'data' / 'kohler_products.csv'

def validate():
    if not CSV_PATH.exists():
        print(f"ERROR: CSV file not found at {CSV_PATH}")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH)
    total_products = len(df)
    errors = []

    # 1. Unique SKU check
    if df['sku'].duplicated().any():
        dups = df[df['sku'].duplicated()]['sku'].tolist()
        errors.append(f"Duplicate SKUs found: {dups}")

    # 2. Product Name & Category existence
    missing_names = df[df['product_name'].isna() | (df['product_name'].astype(str).str.strip() == '')]
    if not missing_names.empty:
        errors.append(f"{len(missing_names)} products missing product_name")

    missing_cats = df[df['category'].isna() | (df['category'].astype(str).str.strip() == '')]
    if not missing_cats.empty:
        errors.append(f"{len(missing_cats)} products missing category")

    # 3. Price INR > 0 check
    invalid_prices = df[df['price_inr'].isna() | (df['price_inr'] <= 0)]
    if not invalid_prices.empty:
        errors.append(f"{len(invalid_prices)} products with price_inr <= 0 (SKUs: {invalid_prices['sku'].tolist()})")

    # 4. Spatial Dimensions > 0
    invalid_dims = df[
        df['width_mm'].isna() | (df['width_mm'] <= 0) |
        df['depth_mm'].isna() | (df['depth_mm'] <= 0) |
        df['height_mm'].isna() | (df['height_mm'] <= 0)
    ]
    if not invalid_dims.empty:
        errors.append(f"{len(invalid_dims)} products with invalid dimensions (SKUs: {invalid_dims['sku'].tolist()})")

    # 5. Accessibility & Sustainability ratings within 0–100
    invalid_acc = df[df['accessibility_rating'].isna() | (df['accessibility_rating'] < 0) | (df['accessibility_rating'] > 100)]
    if not invalid_acc.empty:
        errors.append(f"{len(invalid_acc)} products with accessibility_rating outside 0–100")

    invalid_sust = df[df['sustainability_rating'].isna() | (df['sustainability_rating'] < 0) | (df['sustainability_rating'] > 100)]
    if not invalid_sust.empty:
        errors.append(f"{len(invalid_sust)} products with sustainability_rating outside 0–100")

    # 6. Provenance check
    missing_prov = df[df['rating_provenance'].isna() | (df['rating_provenance'].astype(str).str.strip() == '')]
    if not missing_prov.empty:
        errors.append(f"{len(missing_prov)} products missing rating_provenance")

    print("==================================================")
    print("PRODUCT DATA VALIDATION REPORT")
    print("==================================================")
    print(f"Total Products Analyzed: {total_products}")
    print(f"Valid Products:          {total_products - len(invalid_prices)}")
    print(f"Prices (>0 INR):         {total_products - len(invalid_prices)}/{total_products} valid")
    print(f"Spatial Dimensions:      {total_products - len(invalid_dims)}/{total_products} valid")
    print(f"Accessibility Ratings:   {total_products - len(invalid_acc)}/{total_products} populated")
    print(f"Sustainability Ratings:  {total_products - len(invalid_sust)}/{total_products} populated")
    print(f"Data Provenance:         {total_products - len(missing_prov)}/{total_products} populated")
    print("==================================================")

    if errors:
        print("\nVALIDATION FAILED WITH ERRORS:")
        for err in errors:
            print(f"[ERROR] {err}")
        sys.exit(1)
    else:
        print("SUCCESS: ALL PRODUCT DATA INTEGRITY CHECKS PASSED PERFECTLY!")
        sys.exit(0)

if __name__ == '__main__':
    validate()

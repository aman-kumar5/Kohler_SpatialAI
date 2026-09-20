
import json
import re
import html as html_lib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# KOHLER SPATIAL AI - MVP PRODUCT SCRAPER
# ============================================================
# Purpose:
# Collect ONLY the product information needed for:
#   1. AI product recommendation
#   2. Budget filtering
#   3. Spatial constraint checking
#   4. 2D bathroom layout
#   5. 3D bathroom visualization
#
# Intentionally NOT collecting:
#   - flush rate
#   - water flow
#   - water-efficiency scores
#   - compactness scores
#   - detailed material data
#   - MRP
#   - electrical requirements
#   - OCR
# ============================================================


BASE_URL = "https://www.kohler.co.in"

OUTPUT_CSV = "kohler_products.csv"
OUTPUT_XLSX = "kohler_products.xlsx"

PDF_DIR = Path("kohler_spec_sheets")

# Prototype target: collect enough diversity for the AI recommender and
# deterministic 2D/3D spatial engine. These are ACCEPTED product targets,
# not merely discovered URLs. The scraper may inspect more URLs because
# some pages are filtered as accessories, duplicates, or wrong sub-types.
CATEGORY_TARGETS = {
    "smart_toilet": 15,
    "toilet": 20,
    "faucet": 20,
    "shower": 20,
    "basin": 20,
    "vanity": 15,
}

# Discover a larger candidate pool so filters do not leave a category short.
DISCOVERY_MULTIPLIER = 3

HEADLESS = True

PAGE_TIMEOUT = 60000
PAGE_WAIT_MS = 1200


# ------------------------------------------------------------
# CATEGORY PAGES
# ------------------------------------------------------------

CATEGORY_URLS = {
    "toilet": f"{BASE_URL}/p/toilets/shop-toilets",
    "smart_toilet": f"{BASE_URL}/p/smart-toilets/shop-smart-toilets",
    "faucet": f"{BASE_URL}/p/faucets/shop-faucets",
    "shower": f"{BASE_URL}/p/showers/shop-showers",
    "basin": f"{BASE_URL}/p/washbasins/shop-washbasins",
    "vanity": f"{BASE_URL}/p/bathroom-vanity/shop-bathroom-vanities",
}

# Some KOHLER India catalogs place products under a different path than the
# top-level category page. These are discovery-only roots.
DISCOVERY_ROOTS = {
    "faucet": [
        f"{BASE_URL}/p/faucets/shop-faucets",
        f"{BASE_URL}/p/washbasins",
    ],
    "vanity": [
        f"{BASE_URL}/p/bathroom-vanity/shop-bathroom-vanities",
    ],
}

# Product types that do NOT belong in the spatial bathroom fixture dataset.
EXCLUDED_PRODUCT_TERMS = {
    "toilet": [
        "toilet tank",
        "tank only",
        "tank; requires bowl",
        "requires bowl and seat",
        "flush tank",
    ],
    "faucet": [
        "bath spout",
        "mounting block",
        "mounting base",
        "handle trim",
        "trim",
        "cartridge",
        "diverter",
        "repair",
        "replacement",
        "rough-in",
        "component",
    ],
}

# KOHLER smart-toilet product pages observed during testing
# resolve under /p/toilets/, so smart_toilet discovery uses
# the normal toilet product path.
CATEGORY_PATH = {
    "toilet": "/p/toilets/",
    "smart_toilet": "/p/toilets/",
    "faucet": "/p/faucets/",
    "shower": "/p/showers/",
    "basin": "/p/washbasins/",
    "vanity": "/p/bathroom-vanity/",
}


BAD_SLUGS = {
    "shop-toilets",
    "shop-smart-toilets",
    "shop-faucets",
    "shop-showers",
    "shop-washbasins",
    "shop-bathroom-furniture",
    "shop-bathroom-furniture-1",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def money_to_float(value):
    if value is None:
        return None

    s = clean(value).replace(",", "")

    match = re.search(r"\d+(?:\.\d+)?", s)
    return float(match.group()) if match else None


def normalize_sku(value):
    """Return the complete KOHLER product code in a stable format."""
    value = clean(value)
    if not value:
        return ""
    value = re.sub(r"\s+", "", value).upper()
    if not value.startswith("K-"):
        value = "K-" + value
    return value


def unique_urls(urls):
    result = []
    seen = set()

    for url in urls:
        if not url:
            continue

        url = url.split("#")[0].split("?")[0].rstrip("/")

        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


# ============================================================
# PRODUCT URL DETECTION
# ============================================================

def is_product_url(url, category):
    """
    KOHLER product URLs vary in naming, so we do NOT require
    a particular SKU pattern.

    We only require:
      - KOHLER India /p/ URL
      - expected category path
      - non-listing slug
    """

    if not url:
        return False

    url = url.split("#")[0].split("?")[0].rstrip("/")

    if not url.startswith(BASE_URL + "/p/"):
        return False

    path = urlparse(url).path.lower()

    expected_path = CATEGORY_PATH.get(category, "")

    if category == "faucet":
        if not ("/p/faucets/" in path or "/p/washbasins/" in path):
            return False
    elif expected_path and expected_path not in path:
        return False

    slug = path.split("/")[-1]

    if not slug:
        return False

    if slug in BAD_SLUGS or slug.startswith("shop-"):
        return False

    if len(slug) < 5:
        return False

    # KOHLER product slugs normally contain a model/SKU number. This
    # prevents category landing pages such as shop-single-control-faucets
    # from entering the product dataset.
    if not re.search(r"\d{3,}", slug):
        return False

    bad_parts = [
        "/search",
        "/compare",
        "/cart",
        "/account",
        "/offers",
        "/promotions",
        "/sale",
        "/learn",
        "/about",
    ]

    if any(part in path for part in bad_parts):
        return False

    return True


# ============================================================
# DIMENSION EXTRACTION
# ============================================================

def parse_dimensions(text):
    """
    Returns:
        width_mm, depth_mm, height_mm

    Supported examples:
        719 x 619 x 432 mm
        60 x 39.6 x 11.9 cm
        W 719 mm D 619 mm H 432 mm
    """

    text = clean(text)

    patterns = [
        (
            r"(\d+(?:\.\d+)?)\s*[x×]\s*"
            r"(\d+(?:\.\d+)?)\s*[x×]\s*"
            r"(\d+(?:\.\d+)?)\s*mm",
            1,
        ),
        (
            r"(\d+(?:\.\d+)?)\s*[x×]\s*"
            r"(\d+(?:\.\d+)?)\s*[x×]\s*"
            r"(\d+(?:\.\d+)?)\s*cm",
            10,
        ),
        (
            r"W\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm.*?"
            r"D\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm.*?"
            r"H\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm",
            1,
        ),
        (
            r"Width\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm.*?"
            r"Depth\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm.*?"
            r"Height\s*[:=]?\s*(\d+(?:\.\d+)?)\s*mm",
            1,
        ),
    ]

    for pattern, multiplier in patterns:
        match = re.search(pattern, text, re.I | re.S)

        if match:
            values = [float(x) * multiplier for x in match.groups()]
            return tuple(values)

    return None, None, None


def extract_dimensions(text):
    """
    Try the most reliable dimension formats found on KOHLER pages/PDFs.
    """

    if not text:
        return None, None, None

    # Standard W x D x H
    width, depth, height = parse_dimensions(text)

    if width is not None:
        return width, depth, height

    # Sometimes dimensions are written as:
    # 600 mm x 395 mm x 133 mm
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*mm\s*[x×]\s*"
        r"(\d+(?:\.\d+)?)\s*mm\s*[x×]\s*"
        r"(\d+(?:\.\d+)?)\s*mm",
        text,
        re.I,
    )

    if match:
        return tuple(float(x) for x in match.groups())

    return None, None, None


def validate_dimensions(width, depth, height, category):
    """Reject missing or obviously impossible dimensions before they enter the dataset."""
    values = [width, depth, height]
    if any(v is None for v in values):
        return False
    if any(v <= 0 or v > 3000 for v in values):
        return False

    # Product-category sanity limits. These are conservative engineering
    # filters for the prototype, not manufacturer installation requirements.
    # Conservative bounds for a prototype spatial model. These are
    # data-quality filters, NOT manufacturer installation requirements.
    bounds = {
        "toilet": ((250, 1000), (300, 1200), (250, 1000)),
        "smart_toilet": ((250, 1000), (300, 1200), (250, 1000)),
        "faucet": ((20, 500), (20, 500), (20, 800)),
        "shower": ((20, 1000), (20, 1000), (20, 1000)),
        "basin": ((200, 2000), (150, 1000), (50, 800)),
        "vanity": ((300, 3000), (200, 1200), (300, 1500)),
    }
    ranges = bounds.get(category)
    if not ranges:
        return True
    return all(lo <= value <= hi for value, (lo, hi) in zip(values, ranges))


# ============================================================
# KOHLER DATA-LAYER EXTRACTION
# ============================================================

def parse_data_layer(page):
    """
    Extract the PRODUCT-SPECIFIC KOHLER data-layer object.

    The previous version recursively merged every matching object on
    the page. That can lose/overwrite product values.

    We now:
      1. Prefer an object containing productID + productName.
      2. Decode HTML entities when necessary.
      3. Fall back to JSON-LD for SKU/name/image.
    """

    candidates = []

    try:
        nodes = page.locator("[data-gbh-data-layer-custom]").all()

        for node in nodes:
            raw = node.get_attribute("data-gbh-data-layer-custom")

            if not raw:
                continue

            raw = html_lib.unescape(raw).strip()

            # React can sometimes serialize an object as this string.
            if raw == "[object Object]":
                continue

            try:
                obj = json.loads(raw)
            except Exception:
                continue

            stack = [obj]

            while stack:
                current = stack.pop()

                if isinstance(current, dict):
                    # Product objects have a very distinctive combination.
                    if (
                        current.get("productID")
                        and current.get("productName")
                    ):
                        candidates.append(current)

                    stack.extend(current.values())

                elif isinstance(current, list):
                    stack.extend(current)

    except Exception:
        pass

    # Pick the first genuine product object.
    if candidates:
        return candidates[0]

    # JSON-LD fallback. This exists on KOHLER PDP pages even when the
    # custom data-layer attribute is not exposed as JSON.
    result = {}

    try:
        scripts = page.locator(
            "script[type='application/ld+json']"
        ).all()

        for script in scripts:
            raw = script.inner_text()

            try:
                obj = json.loads(raw)
            except Exception:
                continue

            objects = obj if isinstance(obj, list) else [obj]

            for item in objects:
                if not isinstance(item, dict):
                    continue

                if str(item.get("@type", "")).lower() == "product":
                    if item.get("sku"):
                        result["productID"] = item["sku"]

                    if item.get("name"):
                        result["productName"] = item["name"]

                    if item.get("image"):
                        result["defaultImageName"] = item["image"]

                    if result:
                        return result

    except Exception:
        pass

    return result


def find_value(data, keys):
    for key in keys:
        value = data.get(key)

        if value not in (None, ""):
            return value

    return ""



# ============================================================
# COLLECTION
# ============================================================

def extract_collection(data, product_name=""):
    """Return only an explicitly supplied KOHLER collection.

    Never substitute product_name: a product title is not necessarily
    the collection name. If KOHLER does not expose a collection, leave blank.
    """
    value = find_value(
        data,
        [
            "productCollectionsName",
            "productCollectionName",
            "collection",
        ],
    )
    return clean(value)



# ============================================================
# ADDITIONAL INFORMATION / SPATIAL DATA
# ============================================================

def open_additional_information(page):
    """
    Open KOHLER's Additional Information accordion ONLY when it is
    currently closed.

    This is important because the inspection showed that Reach was
    already open before our test clicked it, so the test accidentally
    CLOSED it. The scraper must inspect aria-expanded first.
    """

    selectors = [
        "[data-testid='product-accordion-Additional Information'] "
        "[role='button']",
        "[data-testid='product-accordion-Additional Information'] "
        ".Collapsible__trigger",
    ]

    for selector in selectors:
        try:
            trigger = page.locator(selector).first

            if not trigger.is_visible(timeout=1500):
                continue

            expanded = trigger.get_attribute("aria-expanded")

            if str(expanded).lower() == "true":
                return True

            trigger.scroll_into_view_if_needed()
            trigger.click(timeout=5000)

            page.wait_for_timeout(600)

            expanded_after = trigger.get_attribute("aria-expanded")

            if str(expanded_after).lower() == "true":
                return True

        except Exception:
            continue

    return False


def extract_additional_information(page):
    """
    Read the structured key/value pairs inside KOHLER's
    Additional Information accordion.

    Returns a dictionary such as:
        {
            "Product Code": "...",
            "Item Length, Width, Height (cm)": "73.6 × 52.1 × 62.4",
            ...
        }
    """

    info = {}

    try:
        open_additional_information(page)

        root = page.locator(
            "[data-testid='product-accordion-Additional Information']"
        ).first

        if not root.is_visible(timeout=2000):
            return info

        items = root.locator("li").all()

        for item in items:
            try:
                title = clean(
                    item.locator(
                        ".pdp-spec-detail__title"
                    ).first.inner_text()
                )

                value = clean(
                    item.locator(
                        ".pdp-features-technologies__list-item"
                    ).first.inner_text()
                )

                if title and value:
                    info[title] = value

            except Exception:
                continue

    except Exception:
        pass

    return info


def extract_dimension_label_from_text(text):
    """
    Extract KOHLER's stable human-readable Additional Information row.

    Example:
        Item Length, Width, Height (cm)
        18.7 × 40 × 38.9

    This is intentionally label-anchored. We do NOT take arbitrary
    three-number sequences from a page because product pages contain
    many unrelated measurements.
    """
    text = clean(text)
    if not text:
        return None, None, None

    # Normalize common multiplication symbols / spacing.
    label_patterns = [
        r"Item\s+Length\s*,?\s*Width\s*,?\s*Height\s*\(\s*cm\s*\)",
        r"Item\s+Length\s*,?\s*Width\s*,?\s*Height",
        r"Length\s*,?\s*Width\s*,?\s*Height\s*\(\s*cm\s*\)",
    ]

    number_triplet = (
        r"([0-9]+(?:\.[0-9]+)?)\s*[x×]\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*[x×]\s*"
        r"([0-9]+(?:\.[0-9]+)?)"
    )

    for label in label_patterns:
        match = re.search(
            label + r"\s*[:\-]?\s*" + number_triplet,
            text,
            re.I,
        )
        if match:
            # KOHLER order = Length, Width, Height.
            # Our schema = width, depth, height.
            length_cm, width_cm, height_cm = map(float, match.groups())
            return width_cm * 10, length_cm * 10, height_cm * 10

    return None, None, None


def extract_dimensions_from_additional_info(page):
    """
    Robust dimension extraction for KOHLER India PDPs.

    Source priority:
      1. Structured Additional Information key/value rows
      2. Rendered BODY TEXT containing the labelled dimension row
      3. Raw HTML text fallback

    This specifically fixes pages such as Odeon where the dimensions are
    visible to a human but the internal accordion selector differs.
    """

    # 1) Structured key/value extraction.
    info = extract_additional_information(page)

    for key, value in info.items():
        key_clean = clean(key).lower()

        if (
            "length" in key_clean
            and "width" in key_clean
            and "height" in key_clean
        ):
            width, depth, height = extract_dimension_label_from_text(
                f"{key} {value}"
            )

            if width is not None:
                return width, depth, height

            # Some structured values omit the unit because the key supplies it.
            raw_match = re.search(
                r"([0-9]+(?:\.[0-9]+)?)\s*[x×]\s*"
                r"([0-9]+(?:\.[0-9]+)?)\s*[x×]\s*"
                r"([0-9]+(?:\.[0-9]+)?)",
                clean(value),
            )

            if raw_match:
                length_cm, width_cm, height_cm = map(
                    float, raw_match.groups()
                )
                return width_cm * 10, length_cm * 10, height_cm * 10

    # 2) Rendered body text — the critical fallback.
    try:
        body = page.locator("body").inner_text()
    except Exception:
        body = ""

    width, depth, height = extract_dimension_label_from_text(body)
    if width is not None:
        return width, depth, height

    # 3) Raw HTML fallback. This catches text rendered in an element that
    # inner_text() may omit or expose differently.
    try:
        raw_html = page.content()
    except Exception:
        raw_html = ""

    raw_html_text = clean(re.sub(r"<[^>]+>", " ", raw_html))
    width, depth, height = extract_dimension_label_from_text(raw_html_text)

    if width is not None:
        return width, depth, height

    return None, None, None

def extract_sku_from_additional_info(page):
    info = extract_additional_information(page)

    for key, value in info.items():
        if key.lower() in {"product code", "sku", "product sku"}:
            return normalize_sku(value)

    return ""



# ============================================================
# INSTALLATION
# ============================================================

def extract_installation(page):
    """
    Only capture actual installation types useful to the
    spatial engine.

    Avoid generic text such as:
        "Shower arm sold separately"
        "Mounting hardware included"
    """

    try:
        body = page.locator("body").inner_text()
    except Exception:
        return ""

    body = clean(body)

    patterns = [
        r"Installation\s*[:\-]?\s*(Vessel)",
        r"Installation\s*[:\-]?\s*(Wall-hung)",
        r"Installation\s*[:\-]?\s*(Floor-mount(?:ed)?)",
        r"Installation\s*[:\-]?\s*(Deck-mount)",
        r"Installation\s*[:\-]?\s*(Wall-mount)",
        r"Installation\s*[:\-]?\s*(Pedestal)",
        r"Installation\s*[:\-]?\s*(Undermount)",
        r"Installation\s*[:\-]?\s*(Drop-in)",
        r"Installation\s*[:\-]?\s*(Freestanding)",
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.I)

        if match:
            return clean(match.group(1))

    # Toilet fallback
    if re.search(r"wall[- ]hung", body, re.I):
        return "Wall-hung"

    if re.search(r"floor[- ]mount", body, re.I):
        return "Floor-mount"

    return ""


# ============================================================
# ROUGH-IN
# ============================================================

def extract_rough_in(text):
    if not text:
        return None

    patterns = [
        r"(\d+(?:\.\d+)?)\s*mm\s*rough[- ]?in",
        r"(\d+(?:\.\d+)?)\s*inch\s*"
        r"\((\d+(?:\.\d+)?)\s*mm\)\s*rough[- ]?in",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            groups = match.groups()

            if len(groups) == 1:
                return float(groups[0])

            return float(groups[1])

    return None


# ============================================================
# FEATURES
# ============================================================

def extract_features(page):
    """
    Keep a SMALL set of useful human-readable product features.

    These are for:
        - recommendation explanation
        - product cards
        - AI "why this product?"
    """

    candidates = []

    selectors = [
        "[data-testid*='feature']",
        "[class*='feature']",
        "[class*='Feature']",
        "li",
        "p",
    ]

    useful_words = [
        "design",
        "modern",
        "contemporary",
        "minimal",
        "integrated",
        "automatic",
        "touchless",
        "skirted",
        "vessel",
        "round",
        "rectangular",
        "elongated",
        "wall-hung",
        "compact",
        "one-piece",
    ]

    for selector in selectors:
        try:
            elements = page.locator(selector).all()

            for element in elements[:100]:
                text = clean(element.inner_text())

                if not (25 <= len(text) <= 220):
                    continue

                lower = text.lower()

                if any(word in lower for word in useful_words):
                    if text not in candidates:
                        candidates.append(text)

        except Exception:
            continue

    return " | ".join(candidates[:5])


# ============================================================
# SMART PRODUCT DETECTION
# ============================================================

def classify_smart(product_name, url, data, features):
    text = " ".join(
        [
            clean(product_name),
            clean(url),
            clean(features),
            clean(data.get("productCategory")),
        ]
    ).lower()

    smart_terms = [
        "smart toilet",
        "smart-toilet",
        "touchless",
        "integrated personal cleansing",
        "automatic flush",
    ]

    return any(term in text for term in smart_terms)


# ============================================================
# SPECIFICATION PDF
# ============================================================

def find_spec_pdfs(html, sku):
    """
    Return ranked KOHLER PDF candidates, not just one PDF.

    Some PDPs expose multiple technical PDFs. A single 'best' URL can be
    a document without dimensions, so v7 tries several relevant candidates
    until a candidate actually yields usable dimensions.
    """
    if not html:
        return []

    urls = []

    # Absolute URLs.
    urls.extend(
        re.findall(
            r'https?://[^"\'<>\\\s]+?\.pdf(?:\?[^"\'<>\\\s]*)?',
            html,
            re.I,
        )
    )

    # Relative URLs.
    urls.extend(
        urljoin(BASE_URL, value)
        for value in re.findall(
            r'["\']([^"\']+?\.pdf(?:\?[^"\']*)?)["\']',
            html,
            re.I,
        )
    )

    urls = unique_urls(urls)

    if not urls:
        return []

    normalized_sku = normalize_sku(sku).lower()
    sku_compact = re.sub(r"[^a-z0-9]", "", normalized_sku)

    scored = []

    for url in urls:
        lower = url.lower()
        compact = re.sub(r"[^a-z0-9]", "", lower)

        score = 0

        # Strong preference for KOHLER technical specification documents.
        if "techcomm.kohler.com" in lower:
            score += 40

        if "_spec_" in lower or "spec_" in lower:
            score += 80

        if "specification" in lower or "specifications" in lower:
            score += 50

        if "dimension" in lower:
            score += 40

        if sku_compact and sku_compact in compact:
            score += 70

        # The accessibility label PDF is not a product spec.
        if "literature.aria" in lower:
            score -= 300

        scored.append((score, url))

    scored.sort(key=lambda item: item[0], reverse=True)

    # Keep a few strong candidates. This avoids downloading every unrelated
    # PDF linked on a PDP while still handling pages with multiple documents.
    return [url for score, url in scored if score > 0][:5]


def find_spec_pdf(html, sku):
    """Backward-compatible helper returning the best ranked candidate."""
    candidates = find_spec_pdfs(html, sku)
    return candidates[0] if candidates else ""

def download_pdf_text(url, filename):
    if not url:
        return ""

    PDF_DIR.mkdir(exist_ok=True)

    path = PDF_DIR / filename

    try:
        if not path.exists():
            response = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            path.write_bytes(response.content)

        # Modern PyMuPDF API
        try:
            import pymupdf

            document = pymupdf.open(str(path))

            text = "\n".join(
                page.get_text()
                for page in document
            )

            document.close()

            return text

        except Exception:
            pass

        # Compatibility fallback
        try:
            import fitz

            document = fitz.open(str(path))

            text = "\n".join(
                page.get_text()
                for page in document
            )

            document.close()

            return text

        except Exception:
            return ""

    except Exception:
        return ""


# ============================================================
# SCRAPER
# ============================================================

class KohlerScraper:

    def __init__(self, page):
        self.page = page

    # --------------------------------------------------------
    # DISCOVERY
    # --------------------------------------------------------

    def discover(self, category):
        """Discover actual KOHLER PDPs for the requested spatial category."""
        discovery_category = "toilet" if category == "smart_toilet" else category

        print()
        print("=" * 70)
        print(f"DISCOVERING: {category}")
        print("=" * 70)

        roots = DISCOVERY_ROOTS.get(category, [CATEGORY_URLS[category]])
        all_links = []

        def get_links(url):
            try:
                self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )
                self.page.wait_for_timeout(PAGE_WAIT_MS)
            except Exception:
                pass

            # Lazy-load product grids.
            for _ in range(16):
                try:
                    self.page.mouse.wheel(0, 1800)
                    self.page.wait_for_timeout(350)
                except Exception:
                    break

            try:
                hrefs = []
                for a in self.page.locator("a[href]").all():
                    href = a.get_attribute("href")
                    if href:
                        hrefs.append(urljoin(BASE_URL, href))
                return unique_urls(hrefs)
            except Exception:
                return []

        # First pass: collect links from all roots.
        for root in roots:
            all_links.extend(get_links(root))

        all_links = unique_urls(all_links)

        # Visit relevant subcategory pages. This is especially important
        # for faucets because actual bathroom sink faucet PDPs can live under
        # /p/washbasins/ rather than /p/faucets/.
        subpages = []
        for u in all_links:
            path = urlparse(u).path.lower()
            slug = path.rstrip("/").split("/")[-1]

            if not slug or slug in BAD_SLUGS:
                continue

            if category == "faucet":
                if (
                    ("/p/faucets/" in path or "/p/washbasins/" in path)
                    and (
                        slug.startswith("shop-")
                        or "faucet" in slug
                        or "tall" in slug
                        or "single" in slug
                        or "widespread" in slug
                        or "wall" in slug
                    )
                ):
                    subpages.append(u)

            elif category == "vanity":
                if "/p/bathroom-vanity/" in path and slug.startswith("shop-"):
                    subpages.append(u)

            elif category not in {"toilet", "smart_toilet"}:
                expected = CATEGORY_PATH.get(discovery_category, "")
                if expected and path.startswith(expected) and slug.startswith("shop-"):
                    subpages.append(u)

        for sub in unique_urls(subpages)[:30]:
            all_links.extend(get_links(sub))

        all_links = unique_urls(all_links)

        # Filter to individual PDPs.
        candidates = []
        for u in all_links:
            if is_product_url(u, discovery_category):
                candidates.append(u)

        candidates = unique_urls(candidates)

        # Faucet PDPs may live under /p/washbasins/.
        if category == "faucet":
            candidates = [
                u for u in candidates
                if (
                    "/p/washbasins/" in urlparse(u).path.lower()
                    or "/p/faucets/" in urlparse(u).path.lower()
                )
            ]

        print(f"Rendered links found: {len(all_links)}")
        target = CATEGORY_TARGETS.get(category, 15)
        discovery_limit = target * DISCOVERY_MULTIPLIER

        print(f"Candidate product URLs: {len(candidates)}")
        print(f"Candidate scan limit: {discovery_limit}")
        for url in candidates[:discovery_limit]:
            print(" ", url)

        return candidates[:discovery_limit]

    # --------------------------------------------------------
    # PRODUCT
    # --------------------------------------------------------

    def scrape_product(self, url, requested_category):
        print()
        print("-" * 70)
        print("OPENING")
        print(url)

        try:
            self.page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT,
            )

            self.page.wait_for_timeout(PAGE_WAIT_MS)

        except PlaywrightTimeoutError:
            print("Product page timeout; using loaded content.")

        except Exception as error:
            print("Product page error:", error)
            return None

        # ----------------------------------------------------
        # DATA LAYER
        # ----------------------------------------------------

        data = parse_data_layer(self.page)

        # ----------------------------------------------------
        # NAME
        # ----------------------------------------------------

        h1 = ""

        try:
            h1 = clean(
                self.page.locator("h1").first.inner_text()
            )
        except Exception:
            pass

        # H1 is the canonical customer-facing product title on KOHLER PDPs.
        # The data layer can contain normalized/lowercase collection labels
        # rather than the actual display name.
        name = h1 or clean(
            find_value(
                data,
                [
                    "productName",
                    "name",
                ],
            )
        )

        # ----------------------------------------------------
        # SKU
        # ----------------------------------------------------

        # Additional Information Product Code is the most reliable SKU source.
        sku = extract_sku_from_additional_info(self.page)

        # Data-layer / JSON-LD fallback.
        if not sku:
            sku = normalize_sku(
                find_value(
                    data,
                    [
                        "productID",
                        "sku",
                        "productSku",
                    ],
                )
            )

        # URL fallback
        if not sku:
            match = re.search(
                r"(?:K[- ]?)?"
                r"(\d{3,8}[A-Z]{0,3}"
                r"(?:-[A-Z0-9]+)?)",
                url,
                re.I,
            )

            if match:
                sku = normalize_sku(match.group(1))

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        price = money_to_float(
            find_value(
                data,
                [
                    "productSalePrice",
                    "salePrice",
                    "price",
                ],
            )
        )

        # Visible PDP price fallback when the custom data layer is absent.
        if price is None:
            try:
                body_for_price = self.page.locator("body").inner_text()

                price_match = re.search(
                    r"₹\s*([0-9][0-9,]*(?:\.\d+)?)"
                    r"\s*Inclusive of all taxes",
                    body_for_price,
                    re.I,
                )

                if price_match:
                    price = money_to_float(price_match.group(1))

            except Exception:
                pass

        # ----------------------------------------------------
        # COLLECTION
        # ----------------------------------------------------

        collection = extract_collection(
            data,
            name,
        )

        # ----------------------------------------------------
        # FINISH
        # ----------------------------------------------------

        finish = clean(
            find_value(
                data,
                [
                    "productColor",
                    "color",
                    "finish",
                ],
            )
        )

        # ----------------------------------------------------
        # BODY
        # ----------------------------------------------------

        try:
            body = self.page.locator("body").inner_text()
        except Exception:
            body = ""

        body_clean = clean(body)

        # ----------------------------------------------------
        # ADDITIONAL INFORMATION
        # ----------------------------------------------------
        # This is the most reliable PDP source for:
        #   Item Length, Width, Height (cm)
        #   Product Code
        #
        # The inspection confirmed this structure on KOHLER pages.

        info = extract_additional_information(
            self.page
        )

        # ----------------------------------------------------
        # DIMENSIONS — PRIMARY SOURCE
        # ----------------------------------------------------

        width, depth, height = (
            extract_dimensions_from_additional_info(
                self.page
            )
        )

        dimension_source = (
            "additional_information"
            if width is not None
            else ""
        )

        # ----------------------------------------------------
        # DIMENSIONS — BODY TEXT FALLBACK
        # ----------------------------------------------------

        if width is None:
            width, depth, height = extract_dimensions(
                body_clean
            )

            if width is not None:
                dimension_source = "product_page"

        # ----------------------------------------------------
        # DIMENSION VALIDATION
        # ----------------------------------------------------

        if not validate_dimensions(width, depth, height, requested_category):
            width, depth, height = None, None, None
            dimension_source = ""

        # ----------------------------------------------------
        # ROUGH-IN
        # ----------------------------------------------------

        rough_in = extract_rough_in(
            body_clean
        )

        # Product-code fallback from Additional Information.
        if not sku:
            sku = extract_sku_from_additional_info(
                self.page
            )

        # ----------------------------------------------------
        # INSTALLATION
        # ----------------------------------------------------

        installation = clean(
            find_value(
                data,
                ["installationType", "installation", "productInstallationType"],
            )
        )
        if not installation:
            installation = extract_installation(self.page)

        # ----------------------------------------------------
        # FEATURES
        # ----------------------------------------------------

        features = extract_features(
            self.page
        )

        # ----------------------------------------------------
        # PRODUCT-ROLE FILTERING
        # ----------------------------------------------------
        # Do not contaminate the fixture dataset with accessories/components.
        combined_product_text = " ".join(
            [
                clean(name),
                clean(url),
                clean(features),
            ]
        ).lower()

        excluded_terms = EXCLUDED_PRODUCT_TERMS.get(
            requested_category,
            [],
        )

        if any(term in combined_product_text for term in excluded_terms):
            return None

        # A toilet tank is a component, not a complete toilet fixture.
        # It must never enter the spatial toilet optimizer.
        if requested_category == "toilet":
            tank_only_markers = [
                "toilet tank",
                "tank only",
                "requires bowl and seat",
                "tank; requires bowl",
            ]
            if any(marker in combined_product_text for marker in tank_only_markers):
                return None

        if requested_category == "faucet":
            # Keep bathroom sink faucets only. Bath spouts and hardware are
            # useful catalog items but not the faucet fixture we need.
            faucet_markers = [
                "bathroom sink faucet",
                "sink faucet",
                "basin faucet",
                "tall faucet",
                "single-handle bathroom faucet",
                "widespread faucet",
            ]
            if not any(marker in combined_product_text for marker in faucet_markers):
                return None

        # ----------------------------------------------------
        # SMART
        # ----------------------------------------------------

        smart = classify_smart(
            name,
            url,
            data,
            features,
        )

        # ----------------------------------------------------
        # PDF FALLBACK
        # ----------------------------------------------------
        # Only download a PDF when a spatial field is missing.

        if (
            width is None
            or rough_in is None
        ):
            try:
                html = self.page.content()
            except Exception:
                html = ""

            pdf_candidates = find_spec_pdfs(
                html,
                sku,
            )

            # Try several strong candidates. A PDP may expose installation
            # literature before the actual specification sheet.
            for pdf_index, pdf_url in enumerate(pdf_candidates, start=1):
                pdf_filename = re.sub(
                    r"[^A-Za-z0-9_.-]",
                    "_",
                    (sku or "product") + f"_{pdf_index}.pdf",
                )

                pdf_text = download_pdf_text(
                    pdf_url,
                    pdf_filename,
                )

                if not pdf_text:
                    continue

                if width is None:
                    width, depth, height = extract_dimensions(
                        pdf_text
                    )

                    if width is not None:
                        dimension_source = "spec_pdf"

                if rough_in is None:
                    rough_in = extract_rough_in(
                        pdf_text
                    )

                # Stop once the spatial fields we care about are complete.
                if width is not None and depth is not None and height is not None:
                    break

        # ----------------------------------------------------
        # FINAL DIMENSION VALIDATION
        # ----------------------------------------------------
        # PDF fallback can introduce dimensions after the first validation.
        if not validate_dimensions(width, depth, height, requested_category):
            width, depth, height = None, None, None
            dimension_source = ""

        # ----------------------------------------------------
        # CATEGORY FILTERING
        # ----------------------------------------------------

        if requested_category == "smart_toilet":
            if not smart:
                return None

        elif requested_category == "toilet":
            if smart:
                return None

        # ----------------------------------------------------
        # RECORD
        # ----------------------------------------------------

        record = {
            "sku": sku,
            "product_name": name,
            "category": requested_category,
            "price_inr": price,
            "width_mm": width,
            "depth_mm": depth,
            "height_mm": height,
            "installation_type": installation,
            "rough_in_mm": rough_in,
            "finish": finish,
            "collection": collection,
            "features": features,
            "source_url": url,
            "dimension_source": dimension_source,
        }

        print()
        print("EXTRACTED")
        print("-" * 50)

        for key, value in record.items():
            print(f"{key}: {value}")

        if all(
            value is not None
            for value in (
                width,
                depth,
                height,
            )
        ):
            print("DIMENSION STATUS: COMPLETE")
        else:
            print("DIMENSION STATUS: MISSING")

        return record


# ============================================================
# MAIN
# ============================================================

def main():

    rows = []
    seen_skus = set()

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=HEADLESS
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        scraper = KohlerScraper(page)

        try:

            categories = [
                "smart_toilet",
                "toilet",
                "faucet",
                "shower",
                "basin",
                "vanity",
            ]

            for category in categories:

                try:

                    target = CATEGORY_TARGETS.get(category, 15)
                    urls = scraper.discover(category)
                    accepted_for_category = 0

                    for url in urls:

                        # Stop once this category has the required number of
                        # accepted, unique products. We intentionally scan a
                        # larger pool because PDPs can be rejected after
                        # inspection (e.g. toilet tanks, bath spouts,
                        # accessories, smart/non-smart mismatches).
                        if accepted_for_category >= target:
                            break

                        try:

                            record = scraper.scrape_product(
                                url,
                                category,
                            )

                            if not record:
                                continue

                            sku = record.get("sku")

                            if sku and sku in seen_skus:
                                print(
                                    f"Duplicate skipped: {sku}"
                                )
                                continue

                            if sku:
                                seen_skus.add(sku)

                            rows.append(record)
                            accepted_for_category += 1

                        except KeyboardInterrupt:
                            raise

                        except Exception as error:
                            print(
                                "Product error:",
                                error,
                            )

                    print(
                        f"CATEGORY RESULT — {category}: "
                        f"{accepted_for_category}/{target} accepted"
                    )

                except KeyboardInterrupt:
                    raise

                except Exception as error:
                    print(
                        f"Discovery error for {category}:",
                        error,
                    )

        finally:
            browser.close()

    # ========================================================
    # EXPORT
    # ========================================================

    if not rows:
        print()
        print("No products scraped.")
        return

    df = pd.DataFrame(rows)

    # --------------------------------------------------------
    # DATA QUALITY SUMMARY
    # --------------------------------------------------------
    dimension_cols = ["width_mm", "depth_mm", "height_mm"]
    if all(c in df.columns for c in dimension_cols):
        complete_mask = df[dimension_cols].notna().all(axis=1)
        print()
        print("DATA QUALITY SUMMARY")
        print("-" * 70)
        print(f"Total unique products: {len(df)}")
        print(f"Complete 3D dimensions: {int(complete_mask.sum())}/{len(df)} "
              f"({(complete_mask.mean() * 100 if len(df) else 0):.1f}%)")

        for cat in sorted(df["category"].dropna().unique()):
            sub = df[df["category"] == cat]
            cm = sub[dimension_cols].notna().all(axis=1)
            print(
                f"  {cat}: {len(sub)} products, "
                f"{int(cm.sum())}/{len(sub)} dimension-complete "
                f"({(cm.mean() * 100 if len(sub) else 0):.1f}%)"
            )

    if "sku" in df.columns:
        df = df.drop_duplicates(
            subset=["sku"],
            keep="first",
        )

    # Exact final MVP schema. Images intentionally omitted.
    # dimension_source is retained for debugging/credibility.
    columns = [
        "sku",
        "product_name",
        "category",
        "price_inr",
        "width_mm",
        "depth_mm",
        "height_mm",
        "installation_type",
        "rough_in_mm",
        "finish",
        "collection",
        "features",
        "source_url",
        "dimension_source",
    ]

    df = df[
        [
            column
            for column in columns
            if column in df.columns
        ]
    ]

    df.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    try:
        df.to_excel(
            OUTPUT_XLSX,
            index=False,
        )
    except Exception as error:
        print(
            "Excel export skipped:",
            error,
        )

    print()
    print("=" * 70)
    print(
        f"DONE — {len(df)} unique products"
    )
    print(f"CSV: {OUTPUT_CSV}")
    print(f"XLSX: {OUTPUT_XLSX}")
    print("=" * 70)

    print()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()

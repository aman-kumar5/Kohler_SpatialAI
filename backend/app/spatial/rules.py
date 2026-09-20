from pathlib import Path
import json
from functools import lru_cache

RULES_PATH = Path(__file__).parent.parent / 'data' / 'design_rules.json'

@lru_cache(maxsize=1)
def load_design_rules() -> dict:
    if RULES_PATH.exists():
        try:
            with open(RULES_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

@lru_cache(maxsize=512)
def get_installation_envelope_dims(category: str, width_mm: int, depth_mm: int) -> tuple[int, int, str]:
    """Returns (envelope_width_mm, envelope_depth_mm, label) for a category and product dimension."""
    rules = load_design_rules().get("installation_envelopes", {})
    cat_rule = rules.get(category, {})
    min_w = cat_rule.get("min_width_mm", 0)
    min_d = cat_rule.get("min_depth_mm", 0)
    label = cat_rule.get("label", "Installation envelope")
    
    env_w = max(width_mm, min_w)
    env_d = max(depth_mm, min_d)
    return env_w, env_d, label

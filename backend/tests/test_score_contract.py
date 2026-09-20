from app.models import ProductRow, ValidationResult
from app.optimizer.scoring import compute_design_score

def product(sku, style='modern'):
    return ProductRow(sku=sku,name=sku,category='toilet',price_inr=10000,width_mm=400,depth_mm=600,height_mm=400,style=style,keywords=style)

def test_score_exposes_normalized_backend_contract():
    score=compute_design_score([product('one')],ValidationResult(valid=True,total_price_inr=10000),100000,'modern',1800,2400,'Balanced')
    assert score.weights == {'budget_fit':25.0,'spatial_fit':30.0,'style_match':25.0,'compatibility':20.0}
    assert score.normalized_weight_sum == 1.0
    assert round(sum(score.weighted_contributions.values()),1) == score.total

def test_one_missing_style_does_not_hide_supported_style_evidence():
    score=compute_design_score([product('evidence'),product('missing',style=None)],ValidationResult(valid=True,total_price_inr=20000),100000,'modern',1800,2400,'Balanced')
    assert score.style_match is not None

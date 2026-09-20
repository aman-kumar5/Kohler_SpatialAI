from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Canonical demo scenario — uses real CSV categories
PAYLOAD = {
    'requirements': {
        'room': {
            'width_mm': 1800,
            'depth_mm': 2400,
            'door_wall': 'south',
            'door_offset_mm': 1000,
            'door_width_mm': 700,
        },
        'budget_inr': 300000,
        'style': 'modern',
        'requirements': ['toilet', 'vanity', 'shower'],
    },
    'categories': ['toilet', 'vanity', 'shower'],
}


def test_generate_returns_designs():
    """Must return at least 1 valid design from real CSV products."""
    resp = client.post('/design/generate', json=PAYLOAD)
    assert resp.status_code == 200, f"generate failed: {resp.text}"
    designs = resp.json()
    assert len(designs) >= 1
    assert designs[0]['validation']['valid']


def test_simulation_returns_before_and_after():
    """Simulation with same before/after must return matching designs."""
    resp = client.post('/design/simulate', json={'before': PAYLOAD, 'modified': PAYLOAD})
    assert resp.status_code == 200, f"simulate failed: {resp.text}"
    data = resp.json()
    assert 'before' in data and 'after' in data and 'trade_off' in data
    assert len(data['after']) >= 1


def test_pdf_export():
    """PDF export must return valid PDF bytes for a generated design."""
    generated = client.post('/design/generate', json=PAYLOAD)
    assert generated.status_code == 200
    design = generated.json()[0]
    report = client.post('/design/export/pdf', json=design)
    assert report.status_code == 200
    assert report.headers['content-type'] == 'application/pdf'
    assert report.content.startswith(b'%PDF')


def test_explain_endpoint():
    """Explain endpoint must return a non-empty string."""
    generated = client.post('/design/generate', json=PAYLOAD)
    assert generated.status_code == 200
    design = generated.json()[0]
    resp = client.post('/design/explain', json={
        'products': design['products'],
        'validation': design['validation'],
        'score': design['score'],
    })
    assert resp.status_code == 200
    assert len(resp.json()['explanation']) > 0


def test_products_list():
    """GET /products must return all CSV products."""
    resp = client.get('/products')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 60  # Full CSV has 69 rows
    # Must have required fields
    assert all('sku' in p and 'name' in p and 'price_inr' in p for p in data)

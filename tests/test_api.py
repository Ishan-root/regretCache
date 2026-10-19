from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

POLICY_NAMES = {'FIFO', 'LRU', 'Optimal', 'RegretCache'}


def default_run():
    res = client.post('/api/simulate', json={})
    assert res.status_code == 200
    return res.json()


def test_health():
    res = client.get('/api/health')
    assert res.status_code == 200
    assert res.json() == {'status': 'ok'}


def test_default_run():
    data = default_run()
    results = data['results']
    assert set(results.keys()) == POLICY_NAMES
    for r in results.values():
        assert len(r['steps']) == 300
        assert r['hits'] + r['misses'] == 300
    caps = data['sweep']['capacities']
    for rates in data['sweep']['hit_rate'].values():
        assert len(rates) == len(caps)
    opt = results['Optimal']['misses']
    for name, r in results.items():
        assert opt <= r['misses'], name


def test_every_workload():
    for w in ['zipf', 'loop', 'scan_hot', 'shifting']:
        res = client.post('/api/simulate', json={'workload': w, 'n_requests': 50})
        assert res.status_code == 200, w


def test_step_fields():
    data = default_run()
    for step in data['results']['RegretCache']['steps']:
        for key in ('ghost', 'scores', 'regret_rate', 'mistakes'):
            assert key in step
    for step in data['results']['LRU']['steps']:
        assert 'cache' in step
        assert 'ghost' not in step


def test_gap_closed_type():
    g = default_run()['gap_closed']
    assert g is None or isinstance(g, float)


def test_bad_input():
    for body in ({'capacity': 1}, {'workload': 'nope'}, {'n_requests': 10}):
        res = client.post('/api/simulate', json=body)
        assert res.status_code == 422, body


def test_front_page():
    res = client.get('/')
    assert res.status_code == 200
    assert 'RegretCache' in res.text

import pytest
from backend.policies import FIFO, LRU, Optimal, RegretCache
from backend.workloads import generate

WORKLOADS = ['zipf', 'loop', 'scan_hot', 'shifting']


def run(policy, trace):
    hits, evictions = [], []
    for page in trace:
        hit, evicted = policy.access(page)
        hits.append(hit)
        evictions.append(evicted)
    return hits, evictions


def misses(policy, trace):
    hits, _ = run(policy, trace)
    return hits.count(False)


def all_policies(capacity, trace):
    return [FIFO(capacity), LRU(capacity),
            Optimal(capacity, trace), RegretCache(capacity)]


def test_textbook_string():
    trace = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
    assert misses(FIFO(3), trace) == 15
    assert misses(LRU(3), trace) == 12
    assert misses(Optimal(3, trace), trace) == 9


def test_belady_anomaly():
    trace = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    assert misses(FIFO(3), trace) == 9
    assert misses(FIFO(4), trace) == 10


def test_lru_by_hand():
    p = LRU(2)
    hits, ev = run(p, [1, 2, 1, 3])
    assert hits == [False, False, True, False]
    assert ev == [None, None, None, 2]
    assert p.contents() == [1, 3]


def test_fifo_by_hand():
    p = FIFO(2)
    _, ev = run(p, [1, 2, 1, 3])
    assert ev == [None, None, None, 1]
    assert p.contents() == [2, 3]


def test_optimal_by_hand():
    trace = [1, 2, 3, 1, 2]
    hits, ev = run(Optimal(2, trace), trace)
    assert hits == [False, False, False, True, False]
    assert ev == [None, None, 2, None, 1]


def test_optimal_rejects_wrong_page():
    with pytest.raises(ValueError):
        Optimal(2, [1, 2, 3]).access(9)


def test_regretcache_hand_example():
    trace = [1, 2, 3, 1, 4, 5]
    p = RegretCache(2)
    _, ev_first = run(p, trace[:4])
    # t=4: page 1 returns 1 request after eviction, alpha is the warm-up 0.5, so +0.5 / 1
    assert p.score[1] == pytest.approx(0.5)
    assert 2 not in p.score
    assert p.mistakes == 1
    # 2 evictions so far (page 1 marked as a mistake, page 2 not), divided by 10
    assert p.regret_rate() == pytest.approx(0.1)
    assert list(p.ghost) == [2]
    _, ev_rest = run(p, trace[4:])
    assert ev_first + ev_rest == [None, None, 1, 2, 3, 4]
    _, ev_lru = run(LRU(2), trace)
    assert ev_lru == [None, None, 1, 2, 3, 1]


def test_regretcache_ghost_trim():
    p = RegretCache(1, ghost_size=1)
    run(p, [1, 2, 3])
    assert p.mistakes == 0
    assert list(p.ghost) == [2]


def test_alpha_is_half_before_10_evictions():
    p = RegretCache(2)
    assert p.alpha() == 0.5
    # every request from t=3 on is a miss with an eviction: 9 evictions, page 1 is a mistake
    for page in [1, 2, 3, 1, 4, 5, 6, 7, 8, 9, 10]:
        p.access(page)
        if len(p.recent_evictions) < 10:
            assert p.alpha() == 0.5
    assert len(p.recent_evictions) == 9
    assert p.mistakes == 1


@pytest.mark.parametrize('workload', WORKLOADS)
def test_alpha_stays_in_range_after_warmup(workload):
    for c in (2, 8):
        p = RegretCache(c)
        for page in generate(workload, 300, 0):
            p.access(page)
            if len(p.recent_evictions) == 10:
                a = p.alpha()
                assert 0.25 <= a <= 1.0
                assert a == pytest.approx(0.25 + 0.75 * p.regret_rate())


def test_mistake_counted_before_alpha():
    p = RegretCache(1, ghost_size=1)
    run(p, list(range(1, 12)))     # pages 1..11: 10 evictions, none of them mistakes yet
    assert len(p.recent_evictions) == 10
    assert p.regret_rate() == 0.0
    p.access(10)                   # page 10 returns 1 request after its eviction
    assert p.regret_rate() == pytest.approx(0.1)
    # alpha must use the rate that already includes this mistake: 0.25 + 0.75 * 0.1
    assert p.score[10] == pytest.approx(0.325)


@pytest.mark.parametrize('workload', WORKLOADS)
def test_optimal_is_never_worse(workload):
    for c in (2, 4, 8, 16):
        for seed in (1, 2, 3):
            trace = generate(workload, 300, seed)
            opt = misses(Optimal(c, trace), trace)
            for p in (FIFO(c), LRU(c), RegretCache(c)):
                assert opt <= misses(p, trace), (p.name, c, seed)


@pytest.mark.parametrize('workload', ['scan_hot', 'loop'])
def test_capacity_and_ghost_bounds(workload):
    n = 300
    trace = generate(workload, n, 0)
    for p in all_policies(5, trace):
        h = m = 0
        for page in trace:
            hit, _ = p.access(page)
            if hit:
                h += 1
            else:
                m += 1
            assert len(p.cache) <= 5
            if isinstance(p, RegretCache):
                assert len(p.ghost) <= p.ghost_size
        assert h + m == n


def test_determinism():
    a = generate('zipf', 100, 7)
    b = generate('zipf', 100, 7)
    c = generate('zipf', 100, 8)
    assert a == b
    assert a != c
    h1, _ = run(RegretCache(8), a)
    h2, _ = run(RegretCache(8), a)
    assert h1 == h2


def test_workload_shapes():
    n = 200
    for w in WORKLOADS:
        trace = generate(w, n, 1)
        assert len(trace) == n
        assert all(type(x) is int for x in trace)
    assert generate('loop', 24, 0) == [i % 12 for i in range(24)]

    scan = [x for x in generate('scan_hot', n, 1) if x >= 6]
    assert scan == list(range(6, 6 + len(scan)))

    sh = generate('shifting', n, 1)
    noise = set(range(200, 300))
    assert all(x in set(range(0, 6)) or x in noise for x in sh[:100])
    assert all(x in set(range(100, 106)) or x in noise for x in sh[100:])

    with pytest.raises(ValueError):
        generate('nope', 10, 0)


def test_print_comparison():
    print()
    print(f"{'workload':<10} {'FIFO':>6} {'LRU':>6} {'Optimal':>8} {'RegretCache':>12}")
    for w in WORKLOADS:
        trace = generate(w, 300, 42)
        m = [misses(p, trace) for p in all_policies(8, trace)]
        print(f'{w:<10} {m[0]:>6} {m[1]:>6} {m[2]:>8} {m[3]:>12}')

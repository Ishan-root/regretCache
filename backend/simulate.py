from .policies import FIFO, LRU, Optimal, RegretCache

POLICY_ORDER = ['FIFO', 'LRU', 'Optimal', 'RegretCache']
SWEEP_CAPACITIES = [2, 4, 6, 8, 10, 12, 16, 20, 24, 32]


def build_policies(capacity, trace, ghost_size=None, half_life=100.0):
    # returns a dict name -> fresh policy instance, keys exactly as POLICY_ORDER
    return {
        'FIFO': FIFO(capacity),
        'LRU': LRU(capacity),
        'Optimal': Optimal(capacity, trace),
        'RegretCache': RegretCache(capacity, ghost_size=ghost_size, half_life=half_life),
    }


def run_policy(policy, trace, with_steps):
    # runs every request in order and returns a result dict
    hits = 0
    steps = []
    for i, page in enumerate(trace):
        hit, evicted = policy.access(page)
        if hit:
            hits += 1
        if with_steps:
            step = {'t': i + 1, 'page': page, 'hit': hit, 'evicted': evicted}
            step.update(policy.snapshot())
            steps.append(step)
    n = len(trace)
    result = {
        'hits': hits,
        'misses': n - hits,
        'hit_rate': round(hits / n, 4) if n else 0.0,
    }
    if with_steps:
        result['steps'] = steps
    return result


def simulate(trace, capacity, ghost_size, half_life):
    # returns the full response dict
    policies = build_policies(capacity, trace, ghost_size, half_life)
    results = {name: run_policy(policies[name], trace, True) for name in POLICY_ORDER}

    distinct = len(set(trace))
    capacities = sorted({c for c in SWEEP_CAPACITIES if c < distinct} | {capacity})
    sweep_rates = {name: [] for name in POLICY_ORDER}
    for c in capacities:
        fresh = build_policies(c, trace, None, half_life)
        for name in POLICY_ORDER:
            sweep_rates[name].append(run_policy(fresh[name], trace, False)['hit_rate'])

    lru = results['LRU']['misses']
    opt = results['Optimal']['misses']
    rc = results['RegretCache']['misses']
    gap_closed = round((lru - rc) / (lru - opt), 4) if lru - opt > 0 else None

    return {
        'n_requests': len(trace),
        'capacity': capacity,
        'trace': list(trace),
        'gap_closed': gap_closed,
        'results': results,
        'sweep': {'capacities': capacities, 'hit_rate': sweep_rates},
    }

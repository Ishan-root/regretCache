import random


def generate(name, n, seed):
    rng = random.Random(seed)

    if name == 'zipf':
        weights = [1 / ((p + 1) ** 1.1) for p in range(50)]
        return [int(x) for x in rng.choices(range(50), weights=weights, k=n)]

    if name == 'loop':
        return [i % 12 for i in range(n)]

    if name == 'scan_hot':
        trace = []
        scan_i = 0
        for _ in range(n):
            if rng.random() < 0.5:
                trace.append(rng.randrange(6))
            else:
                trace.append(6 + (scan_i % 1000))
                scan_i += 1
        return trace

    if name == 'shifting':
        set_a = list(range(0, 6))
        set_b = list(range(100, 106))
        trace = []
        for i in range(n):
            working = set_a if i < n // 2 else set_b
            if rng.random() < 0.8:
                trace.append(rng.choice(working))
            else:
                trace.append(rng.randrange(200, 300))
        return trace

    raise ValueError(f'unknown workload: {name}')

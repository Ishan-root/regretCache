from collections import OrderedDict, deque
from typing import Optional


class Policy:
    name = 'Base'

    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError('capacity must be at least 1')
        self.capacity = capacity
        self.cache = {}   # any container that supports: in, len, iteration

    def access(self, page: int):
        # Returns a tuple (hit, evicted). hit is a bool.
        # evicted is the page id that was removed, or None.
        raise NotImplementedError

    def contents(self) -> list:
        return sorted(self.cache)

    def snapshot(self) -> dict:
        return {'cache': self.contents()}


class FIFO(Policy):
    name = 'FIFO'

    def __init__(self, capacity: int):
        super().__init__(capacity)
        self.cache = OrderedDict()   # page -> None, insertion order

    def access(self, page: int):
        if page in self.cache:
            return True, None
        evicted = None
        if len(self.cache) >= self.capacity:
            evicted, _ = self.cache.popitem(last=False)
        self.cache[page] = None
        return False, evicted


class LRU(Policy):
    name = 'LRU'

    def __init__(self, capacity: int):
        super().__init__(capacity)
        self.cache = OrderedDict()   # page -> None, least recent first

    def access(self, page: int):
        if page in self.cache:
            self.cache.move_to_end(page)
            return True, None
        evicted = None
        if len(self.cache) >= self.capacity:
            evicted, _ = self.cache.popitem(last=False)
        self.cache[page] = None
        return False, evicted


class Optimal(Policy):
    name = 'Optimal'

    def __init__(self, capacity: int, trace):
        super().__init__(capacity)
        self.trace = list(trace)
        self.i = 0
        self.cache = {}   # page -> next-use index
        INF = float('inf')
        n = len(self.trace)
        next_use = [INF] * n
        last_seen = {}
        for i in range(n - 1, -1, -1):
            next_use[i] = last_seen.get(self.trace[i], INF)
            last_seen[self.trace[i]] = i
        self.next_use = next_use

    def access(self, page: int):
        if self.i >= len(self.trace) or self.trace[self.i] != page:
            raise ValueError('page does not match the trace at this position')
        nxt = self.next_use[self.i]
        self.i += 1
        if page in self.cache:
            self.cache[page] = nxt
            return True, None
        evicted = None
        if len(self.cache) >= self.capacity:
            evicted = max(self.cache, key=lambda p: (self.cache[p], -p))
            del self.cache[evicted]
        self.cache[page] = nxt
        return False, evicted


class RegretCache(Policy):
    name = 'RegretCache'

    def __init__(self, capacity, ghost_size=None, half_life=100.0,
                 alpha_min=0.25, alpha_max=1.0,
                 score_min=-1.0, score_max=5.0, window=10):
        super().__init__(capacity)
        self.ghost_size = ghost_size if ghost_size is not None else capacity
        self.lam = 0.5 ** (1.0 / half_life)   # per-request decay multiplier
        self.alpha_min = alpha_min
        self.alpha_max = alpha_max
        self.alpha_warmup = 0.5          # alpha used until `window` evictions have happened
        self.window = window
        self.score_min = score_min
        self.score_max = score_max
        self.t = 0
        self.cache = {}                  # page -> last_used time
        self.score = {}                  # page -> stored score
        self.score_t = {}                # page -> time the stored score was set
        self.ghost = OrderedDict()       # page -> (t_evict, record), oldest first
        # One record per eviction, newest last. A record is a one-item list:
        # [0] when created, set to [1] if the evicted page returns while on the ghost list.
        self.recent_evictions = deque(maxlen=window)
        self.mistakes = 0                # total mistakes seen

    def eff(self, p, t):
        # decayed score of page p at time t
        s = self.score.get(p, 0.0)
        if s == 0.0:
            return 0.0
        return s * (self.lam ** (t - self.score_t[p]))

    def regret_rate(self):
        # share of the last `window` evictions that turned out to be mistakes
        return sum(r[0] for r in self.recent_evictions) / self.window

    def alpha(self):
        if len(self.recent_evictions) < self.window:
            return self.alpha_warmup
        return self.alpha_min + (self.alpha_max - self.alpha_min) * self.regret_rate()

    def set_score(self, p, value, t):
        self.score[p] = min(self.score_max, max(self.score_min, value))
        self.score_t[p] = t

    def _trim_ghost(self):
        while len(self.ghost) > self.ghost_size:
            old, _ = self.ghost.popitem(last=False)   # oldest entry
            self.score.pop(old, None)
            self.score_t.pop(old, None)

    def access(self, page):
        self.t += 1
        t = self.t

        # Hit: only update last-used time.
        if page in self.cache:
            self.cache[page] = t
            return True, None

        # Step A: a ghost hit means an earlier eviction of this page was a mistake.
        if page in self.ghost:
            t_evict, record = self.ghost.pop(page)
            gap = t - t_evict                       # always at least 1
            record[0] = 1                           # mark the mistake before computing alpha
            self.mistakes += 1
            inc = self.alpha() * (1.0 / gap)        # sooner return means bigger regret
            self.set_score(page, self.eff(page, t) + inc, t)

        # Step B: if the cache is full, evict the lowest score, ties by oldest last use.
        evicted = None
        if len(self.cache) >= self.capacity:
            ranked = sorted(self.cache, key=lambda p: (self.eff(p, t), self.cache[p]))
            evicted = ranked[0]
            del self.cache[evicted]
            record = [0]
            self.recent_evictions.append(record)
            self.ghost[evicted] = (t, record)
            self._trim_ghost()

        # Step C: insert the requested page.
        self.cache[page] = t
        return False, evicted

    def snapshot(self):
        t = self.t
        return {
            'cache': self.contents(),
            'ghost': list(self.ghost),
            'scores': {str(p): round(self.eff(p, t), 3) for p in self.cache},
            'regret_rate': round(self.regret_rate(), 3),
            'mistakes': self.mistakes,
        }

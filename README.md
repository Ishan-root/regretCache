# RegretCache

A cache eviction simulator that runs four policies (FIFO, LRU, Optimal and RegretCache) on the same request sequence and compares their misses.

## The idea

Most caches never find out whether an eviction was a good decision. RegretCache keeps a fixed-length "ghost list" of pages it recently evicted. If an evicted page is requested again while it is still on that list, the eviction was a mistake, and the page's protection score goes up by alpha divided by the gap (the number of requests since it was evicted), so a page that came back sooner gets more protection. The regret rate is the share of the last 10 evictions that turned out to be mistakes. Alpha is 0.5 until 10 evictions have happened, then 0.25 + 0.75 x regret rate, so it always lies between 0.25 and 1.0 and grows when the cache is making more mistakes. Scores decay over time with a configurable half-life. On a miss with a full cache, the page with the lowest decayed score is evicted, with ties broken by least recent use, so when every score is 0 it behaves exactly like LRU.

## Commands

All commands run from the `regretcache/` folder.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn backend.main:app --port 8000
```

Then open `http://localhost:8000` in a browser.

To print the comparison table below, run `pytest -s -k print_comparison`.

## Results

Miss counts with capacity 8, 300 requests, seed 42 (lower is better). These are the real numbers; no parameter was tuned.

| workload | FIFO | LRU | Optimal | RegretCache |
| --- | --- | --- | --- | --- |
| zipf | 172 | 148 | 96 | 133 |
| loop | 300 | 300 | 116 | 300 |
| scan_hot | 230 | 215 | 156 | 164 |
| shifting | 148 | 123 | 79 | 102 |

What this shows:

- **scan_hot:** RegretCache closes about 86% of the LRU to Optimal gap (215 to 164 misses).
- **shifting:** RegretCache beats LRU and FIFO (102 misses against LRU 123), because its scores decay when the working set changes.
- **zipf:** RegretCache beats LRU (133 against 148).
- **loop:** RegretCache does not help. With a 12-page cycle and 8 slots, every page returns exactly 12 requests after it is used, so every policy except Optimal misses on every request. The spec's guess that it might help on `loop` did not hold at these settings.

## Notes

Decisions not fully covered by the spec:

- **LFU removed.** The original spec included an LFU policy. It was removed at the owner's request, so the app compares four policies and every list, table, chart and test uses `FIFO, LRU, Optimal, RegretCache`.
- **RegretCache simplified.** At the owner's request, the original spec's RegretCache was changed: blame on the runner-up page was removed, the ghost list no longer stretches (it has a fixed length of `ghost_size`), the good-call counter was removed, and the regret rate and alpha now follow the rules in "The idea" above. Score decay, the score clamps (-1 to 5) and the eviction rule are unchanged.
- **Alpha parameters.** `alpha_min` (0.25), `alpha_max` (1.0) and `window` (10) remain constructor parameters with those defaults; the warm-up alpha of 0.5 is fixed. Because the warm-up alpha does not depend on them, setting `alpha_min` and `alpha_max` to 0 no longer makes RegretCache identical to LRU, so the original "zero regret equals LRU" test was removed.
- **Lower score clamp.** Without blame, scores never go negative, so the -1 lower clamp is never reached. It is kept as requested.
- **Virtual environment location.** The section 2 commands create `.venv` inside the project folder, and running `pytest` creates `.pytest_cache`. Neither is part of the delivered file tree; both are generated on your machine when you run the commands.
- **Optimal label.** The spec says to append `  (ceiling) ` with irregular spacing. The table shows it as `Optimal (ceiling)`.
- **Range value spans.** Each range input's value `<span>` has the id `<input id>_val` (for example `capacity_val`).
- **Network failures.** `runSimulation` follows the spec code and also catches network errors, showing `Could not reach the server. Is it running?`. The Run button is restored in a `finally` block so it never stays disabled.
- **Chart.js missing.** If the Chart.js CDN cannot be loaded, the page still runs: the summary table and replay work, and only the charts are skipped.
- **Play button.** While playing, its text changes to `Pause`. Pressing Play at the last request restarts from request 1.
- **Switching the replay policy** rebuilds the strip (its hit and miss colors depend on the policy) and keeps the current request index.
- **Test warning.** With the newest Starlette, `TestClient` prints a deprecation warning about `httpx`. It does not affect results, and the spec's `httpx` requirement is kept.

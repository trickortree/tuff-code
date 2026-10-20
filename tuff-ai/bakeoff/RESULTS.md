# Bake-off results

Made by `report.mjs` from `results/`. Every score comes from running the model's code with `tuff.py`.

| Run | Tasks | **All, after 1 retry** | First try | Write | Apps | Fix: fixed | Fix: explained | Passes the checker (first try) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| granite-4.0-1b-guide | 255 | **36%** | 29% | 32% | 7% | 49% | 76% | 47% |
| granite-4.0-1b-lean | 255 | **36%** | 24% | 32% | 7% | 49% | 71% | 47% |
| qwen3.5-2b-guide | 255 | **35%** | 31% | 13% | 27% | 65% | 84% | 58% |
| qwen3.5-2b-lean | 255 | **32%** | 27% | 16% | 13% | 58% | 77% | 49% |

"After 1 retry" is what Tuff AI would show in the app: if the first answer fails `tuff.py --check`, the model gets one more try with the checker's error. "Apps" are only checked, never run. "Explained" means the explanation names the mistake (a rough keyword check). Speed and memory aren't in this table: part of each run used the GPU to save time, and scores don't depend on it. The CPU speed and memory numbers come from `probe.mjs`.

## By category (after 1 retry)

| Category | granite-4.0-1b-guide | granite-4.0-1b-lean | qwen3.5-2b-guide | qwen3.5-2b-lean |
| --- | --- | --- | --- | --- |
| basics | 50% (12) | 50% (12) | 17% (12) | 33% (12) |
| control | 33% (12) | 25% (12) | 8% (12) | 0% (12) |
| fix: error | 47% (60) | 50% (60) | 67% (60) | 65% (60) |
| fix: wrong-output | 53% (40) | 48% (40) | 63% (40) | 48% (40) |
| functions | 18% (17) | 29% (17) | 6% (17) | 6% (17) |
| gui | 7% (30) | 7% (30) | 27% (30) | 13% (30) |
| input | 24% (25) | 28% (25) | 0% (25) | 0% (25) |
| lists | 50% (18) | 50% (18) | 28% (18) | 39% (18) |
| numbers | 46% (13) | 38% (13) | 31% (13) | 31% (13) |
| patterns | 13% (15) | 13% (15) | 13% (15) | 7% (15) |
| text | 31% (13) | 23% (13) | 8% (13) | 23% (13) |

## By level (after 1 retry)

| Level | granite-4.0-1b-guide | granite-4.0-1b-lean | qwen3.5-2b-guide | qwen3.5-2b-lean |
| --- | --- | --- | --- | --- |
| easy | 43% | 41% | 39% | 41% |
| medium | 35% | 36% | 33% | 32% |
| hard | 22% | 24% | 29% | 14% |

## Why first tries failed

- **granite-4.0-1b-guide:** fails the checker 111, runs, wrong output 32, no code block 23, stops with an error when run 11, app is missing a needed part 5
- **granite-4.0-1b-lean:** fails the checker 109, runs, wrong output 46, no code block 27, stops with an error when run 8, app is missing a needed part 4
- **qwen3.5-2b-guide:** fails the checker 99, runs, wrong output 42, stops with an error when run 21, no code block 9, app is missing a needed part 6
- **qwen3.5-2b-lean:** fails the checker 119, runs, wrong output 48, no code block 11, stops with an error when run 7

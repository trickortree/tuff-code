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

## Thinking levels (Pumice 1, 2026-10-20)
Tuff Bench through the app's own Tuff AI code (`run.mjs --app`), Qwen3.5-2B Q4_K_M as Pumice 1: 40 write, 10 app and 30 fix tasks per row on the GPU (Medium (256) used 20/5/15), and 10 tasks per row on the CPU with 4 threads. "Improver" is the request card the app adds before the question; Medium and High also let the model rewrite the request first. Tuff Bench is for scoring only, never training.

**On the GPU** (vulkan):

| Level (thought budget) | Improver | Tasks | **Pass, after 1 retry** | First try | Write | Apps | Fix | Fix: explained | Median s | 90th pct s | Thought tokens (mean) | Cut by the budget | Looping when cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Off | off | 80 | **24%** | 23% | 13% | 10% | 43% | 77% | 2.1 | 4.3 | 0 | – | – |
| Off | on | 80 | **34%** | 31% | 20% | 30% | 53% | 73% | 1.6 | 4.0 | 0 | – | – |
| Low (128) | on | 80 | **38%** | 34% | 28% | 20% | 57% | 80% | 2.9 | 7.2 | 168 | 80 of 80 | 0 |
| Low (128) | on | 80 | **29%** | 26% | 18% | 10% | 50% | 70% | 1.6 | 4.1 | 178 | 80 of 80 | 0 |
| Low (192) | off | 80 | **26%** | 20% | 15% | 20% | 43% | 77% | 3.2 | 7.4 | 264 | 80 of 80 | 3 |
| Low (192) | on | 80 | **39%** | 33% | 30% | 20% | 57% | 73% | 3.5 | 7.5 | 257 | 80 of 80 | 1 |
| Medium (256) | on | 40 | **43%** | 38% | 30% | 20% | 67% | 73% | 4.0 | 7.2 | 346 | 40 of 40 | 1 |
| Medium (512) | off | 80 | **28%** | 25% | 20% | 30% | 37% | 67% | 7.1 | 14.0 | 721 | 80 of 80 | 40 |
| Medium (512) | on | 80 | **35%** | 31% | 23% | 20% | 57% | 60% | 6.8 | 13.9 | 672 | 80 of 80 | 23 |
| High (1024) | off | 39 | **15%** | 15% | 15% | – | – | – | 7.7 | 15.0 | 1202 | 30 of 39 | 24 |

**On the CPU** (4 threads):

| Level (thought budget) | Improver | Tasks | **Pass, after 1 retry** | First try | Write | Apps | Fix | Fix: explained | Median s | 90th pct s | Thought tokens (mean) | Cut by the budget | Looping when cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Off | on | 10 | **20%** | 20% | 17% | 0% | 33% | 67% | 32.7 | 65.7 | 0 | – | – |
| Low (192) | on | 10 | **40%** | 40% | 33% | 0% | 67% | 67% | 50.0 | 76.7 | 211 | 10 of 10 | 0 |

- Low (192) with the improver adds a median of **21.0 s** per answer on the CPU over Off (90th percentile 25.4 s, over the same 10 tasks).

**The improver, task by task** (the same tasks with and without it):

- Off: the improver turned 13 failures into passes and 5 passes into failures.
- Low (192): the improver turned 15 failures into passes and 5 passes into failures.
- Medium (512): the improver turned 13 failures into passes and 7 passes into failures.

**What was chosen** (`LEVELS` in `tuffcode/ai.js`): Off 0, **Low 128 (the default)**, Medium 256 with the rewrite, High 512 with the rewrite. 1024 did worst of all (15% on 39 tasks), because the model loops when it thinks long; High says it's slower and not always better. The improver is always on.
- The run was cut short on purpose to ship sooner: High (1024) stopped at 39 tasks, and High with the improver wasn't run.
- **Read the next section before trusting these numbers:** a rerun with the final 1.0.5 code a few hours later didn't reproduce the gaps.

**Rerun after the 1.0.5 review** (2026-10-21). The second Low (128) row is `results/think/low128-improved-v2-gpu.jsonl`: the app's code after three fixes. The system prompt no longer has the sentence to answer "who are you?" with (Pumice 1 began almost every answer with it: 76 of 80 below, and 58 of the 60 answers in the Medium (256) and CPU rows, which were measured with it). The improver no longer calls "I don't get…" or "should I…?" a fix when a file is open, and knows "make a game where you catch apples" is a tgame game. And tgame's "Games Tuff Engine can edit" section, a section of its own in the guide, no longer goes into console messages (it went into 66 of the 255): 245 of the 255 messages now get the same guide sections as when the 38% row was measured. No task's kind or target changed.

To compare like with like, the same 80 tasks ran on the same day and GPU, through the app's code, as two controls in `results/think/controls/`:

| Run | Pass, after 1 retry | First try | Answers that say who it is, unasked | Median s |
| --- | --- | --- | --- | --- |
| release/1.0.5 as it was (`low128-release-1.0.5-gpu`) | **29%** (23) | 23% | 76 of 80 | 1.8 |
| After the fixes (`low128-improved-v2-gpu`, the row above) | **29%** (23) | 26% | 0 | 1.6 |
| After the fixes, with the identity line the 38% row had (`low128-v2-with-old-identity-line-gpu`) | **28%** (22) | 25% | 0 | 1.8 |

So the fixes don't lower the score. None of the three reaches the 38% row, not even with that row's own identity line, so 38% doesn't reproduce today. It isn't the scoring: its saved replies still score 30 of 80 with today's `tuff.py`. Its run was also almost twice as slow (2.9 s median), so it was probably made under other conditions, maybe like the other rows of that evening; compare new runs with these three rather than with them.

## Thinking levels, rerun with the final 1.0.5 code (2026-10-21)
The same 80 tasks a row on the same GPU, with the code that ships in 1.0.5 (Pumice 1 says who it is only when asked; the improver no longer turns questions with "don't" or "should" into "fix my program"; game requests go to tgame).

**On the GPU** (vulkan):

| Level (thought budget) | Improver | Tasks | **Pass, after 1 retry** | First try | Write | Apps | Fix | Fix: explained | Median s | 90th pct s | Thought tokens (mean) | Cut by the budget | Looping when cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Off | off | 80 | **30%** | 24% | 18% | 20% | 50% | 87% | 1.6 | 2.8 | 0 | – | – |
| Off | on | 80 | **31%** | 29% | 23% | 40% | 40% | 63% | 1.1 | 2.8 | 0 | – | – |
| Low (128) | on | 80 | **33%** | 29% | 20% | 30% | 50% | 67% | 1.6 | 3.8 | 165 | 80 of 80 | 1 |
| Medium (256) | on | 80 | **30%** | 30% | 20% | 10% | 50% | 83% | 2.4 | 4.7 | 333 | 80 of 80 | 6 |

**The improver, task by task** (the same tasks with and without it):

- Off: the improver turned 13 failures into passes and 12 passes into failures.

**What this means:**
- **The earlier gaps don't reproduce.** That evening: Off 24% → 34% with the improver, Low 38%, Medium 43%. This rerun: 30%, 31%, 33%, 30%. On 80 tasks a few tasks either way is noise.
- The fix agent's own control runs agree: the unchanged release code scored 29% at Low the same morning, the same as the fixed code.
- So 1.0.5 doesn't claim a score gain from the levels or the improver. What they do give:
  - **The improver:** the question shown as a clear task, and fewer wrong "fix my program" answers.
  - **Thinking:** visible thinking with a hard cap, so it can't loop.
- **Low stays the default:** it costs about 0.5 s on a graphics card. On a 4-thread laptop CPU it adds about 14–21 s per answer, so Off may be the better default there (an open task).


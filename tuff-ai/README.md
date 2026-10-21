# Tuff AI (work in progress)

Tuff AI is the offline helper built into TuffCode. Since 1.0.4 the app has it as a preview: the Tuff AI tab in Tuff Agents downloads its model and runs it with node-llama-cpp (`tuffcode/ai.js`, `tuffcode/ai-worker.mjs`). Its model is **Pumice 1**, TuffCode's own. For now Pumice 1 is the open Qwen3.5-2B (Apache 2.0) as it is; a fine-tune of it on Tuff comes later. The full plan lives in the project vault (`Plans/Tuff AI.md`).

What the app does around the model:

- **Thinking levels** (the Thinking chip): Off, Low, Medium and High. Off is what 1.0.4 did, no thinking at all. The others let Pumice 1 think, up to a hard budget of thought tokens that node-llama-cpp enforces, so a thinking loop can't run on. Medium and High first have it rewrite the request as a task in one short pass.
- **The improver**: before the model answers, the question becomes a clearer task, the same way every time: what kind of request it is (write, fix, explain, a question, or "who are you?"), a console program or a window, the part of the open file that matters, the last run's error and its line, and what a good answer looks like. The reply shows it, folded.
- **The checker retry**: a ` ```tuff ` block that fails `tuff.py --check` gets one more try with the error.

This folder holds the measuring:

- [`bench/`](bench/README.md): **Tuff Bench**, 255 tasks checked against the real interpreter: 125 "write a program", 30 app windows and 100 "fix this". It's used for scoring only and is never used as training data.
- [`bakeoff/`](bakeoff/): runs a GGUF model on Tuff Bench with node-llama-cpp and scores it with `tuff.py`.
  - `run.mjs`: the bench run. Phase 1's mode runs the model on its own (a short prompt or the whole guide, and one retry with the checker's error). `--app` runs Tuff AI exactly as the app does: it loads `tuffcode/ai.js` with a stand-in for Electron, which starts the real `ai-worker.mjs`, so the levels, the improver and the retry are the app's own code.
  - `probe.mjs`: speed, memory and prompt-reuse measurements.
  - `report.mjs`: turns the results into `RESULTS.md` (`--think` for the thinking levels' tables).

## Running the bake-off
The app depends on node-llama-cpp 3.22.2 now (`tuffcode/package.json`), so after `npm ci` in `tuffcode/` you can pass `--runtime tuffcode` (and `--app` uses it by itself). npm also fetches ~545 MB of CUDA builds (`@node-llama-cpp/win-x64-cuda`, `win-x64-cuda-ext`) that nothing uses; delete them from `tuffcode/node_modules/@node-llama-cpp`. To keep the bake-off separate, install it somewhere outside the repo instead, with only the CPU build:

```bash
mkdir ../llama-runtime
cd ../llama-runtime
npm init -y
npm install @node-llama-cpp/win-x64@3.22.2
npm install node-llama-cpp@3.22.2 --omit=optional --ignore-scripts
```

On a Mac, use `@node-llama-cpp/mac-arm64-metal` or `@node-llama-cpp/mac-x64` instead. Then, from the repo root:

```bash
node tuff-ai/bakeoff/run.mjs --runtime ../llama-runtime --model Qwen3.5-2B-Q4_K_M.gguf --name qwen3.5-2b --mode lean --threads 8
node tuff-ai/bakeoff/probe.mjs --runtime ../llama-runtime --model Qwen3.5-2B-Q4_K_M.gguf --what speed --threads 4 --mmap off
node tuff-ai/bakeoff/report.mjs > tuff-ai/bakeoff/RESULTS.md
```

Tuff AI as the app runs it, one level at a time, with and without the improver (`--gpu auto` picks the graphics card the way the app does; `--gpu cpu --threads 4` is roughly a fast laptop):

```bash
node tuff-ai/bakeoff/run.mjs --app --model Qwen3.5-2B-Q4_K_M.gguf --level low --improve on --sample write:40,gui:10,fix:30
node tuff-ai/bakeoff/run.mjs --app --model Qwen3.5-2B-Q4_K_M.gguf --level off --improve on --gpu cpu --threads 4 --sample write:4,gui:2,fix:4
node tuff-ai/bakeoff/report.mjs --think
```

The model comes from Hugging Face: [`unsloth/Qwen3.5-2B-GGUF`](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF) (Phase 1 also tried [`ibm-granite/granite-4.0-1b-GGUF`](https://huggingface.co/ibm-granite/granite-4.0-1b-GGUF)), both at Q4_K_M.

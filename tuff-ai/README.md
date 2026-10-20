# Tuff AI (work in progress)

Tuff AI is the planned offline helper built into TuffCode. Its model is called **Pumice**, a fine-tune of Qwen3.5-2B. Nothing here ships in the app yet. The full plan lives in the project vault (`Plans/Tuff AI.md`).

This folder holds the Phase 1 work:

- [`bench/`](bench/README.md): **Tuff Bench**, 255 tasks checked against the real interpreter: 125 "write a program", 30 app windows and 100 "fix this". It's used for scoring only and is never used as training data.
- [`bakeoff/`](bakeoff/): runs a GGUF model on Tuff Bench on the CPU with node-llama-cpp and scores it with `tuff.py`.
  - `run.mjs`: the bench run. It supports a short prompt or the whole guide, and gives one retry with the checker's error.
  - `probe.mjs`: speed, memory and prompt-reuse measurements.
  - `report.mjs`: turns the results into `RESULTS.md`.

## Running the bake-off
node-llama-cpp isn't a dependency of the app yet, so install it somewhere outside the repo. Install only the CPU build: npm would otherwise also fetch ~570 MB of CUDA files.

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

The models come from Hugging Face: [`unsloth/Qwen3.5-2B-GGUF`](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF) and [`ibm-granite/granite-4.0-1b-GGUF`](https://huggingface.co/ibm-granite/granite-4.0-1b-GGUF), both at Q4_K_M.

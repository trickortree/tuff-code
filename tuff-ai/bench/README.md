# Tuff Bench

A test set for [Tuff AI](../README.md). Models are scored on it, and **nothing in here is ever used as training data.** Tuff Bench was written with Claude, and Anthropic's terms forbid training models on Claude's answers. Keeping it out of training also keeps the scores honest.

Every task is checked against the real interpreter (`tuff.py`). Expected outputs come from running the reference code, never from typing them by hand:

```bash
node tuff-ai/bench/verify.mjs tuff-ai/bench/write.jsonl --fill   # run references, store real outputs
node tuff-ai/bench/verify.mjs tuff-ai/bench/write.jsonl          # check that everything still matches
```

## Files
One JSON object per line.

### `write.jsonl`: "make a program that…"
```json
{"id": "lists-007", "type": "write", "cat": "lists", "level": "easy",
 "task": "Make a list of the numbers 3, 8 and 5, then say the biggest one.",
 "tests": [{"stdin": "", "stdout": "8"}],
 "solution": "nums = [3, 8, 5]\nsay max(nums)\n"}
```
- `cat` is one of `basics`, `numbers`, `text`, `control`, `lists`, `functions`, `input` or `patterns`. `level` is `easy`, `medium` or `hard`.
- `task` is worded the way a beginner would ask. It states the **exact** text to show, including any `input` question, so a correct program gives the same output.
- `tests[].stdin` holds the typed answers, one per line. `stdout` is what a real run prints. With piped input, `input` questions print with no newline, so `Name? Hi Sam` is normal.
- **Scoring:** the model's program must pass `--check`, and every test's output must match exactly (trailing spaces and blank lines are ignored).

### `gui.jsonl`: app windows (tgui / mtgui)
```json
{"id": "gui-003", "type": "gui", "cat": "gui", "level": "easy",
 "task": "Make a window titled Counter with a button that counts clicks.",
 "needs": ["mention tgui", ":button"],
 "solution": "..."}
```
- These are never run, because they open windows.
- **Scoring:** the model's program must pass `--check` and contain every `needs` string. `needs` lists only things that **any** correct answer must contain.

### `fix.jsonl`: "this doesn't work, fix it"
```json
{"id": "fix-012", "type": "fix", "kind": "error", "mistake": "python-print", "level": "easy",
 "task": "It should say Hello three times.",
 "broken": "...", "error": "Tuff error on line 1: ...",
 "fixed": "...", "tests": [{"stdin": "", "stdout": "..."}],
 "explain_words": ["say"]}
```
- `kind: "error"`: `broken` stops with the `error` shown. `kind: "wrong-output"`: `broken` runs, but prints `got` instead of the right output.
- `mistake` is a short tag for the kind of beginner mistake, like `python-print`, `missing-colon` or `text-plus-number`.
- **Scoring:**
  - **fixed:** the model's program passes `tests`, like a write task.
  - **explained:** the model's explanation mentions at least one of `explain_words` (case-insensitive). This is a rough signal only.

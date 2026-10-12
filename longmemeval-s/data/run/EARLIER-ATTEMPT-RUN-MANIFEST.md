# Architecture 0008 full-500 fresh run

Run bundle: `full500-audit-20260731T002635Z`

Started: 2026-07-31 05:56 IST / 2026-07-31T00:26:35Z

## Frozen pipeline

1. GPT-5.6 Luna low facet planning
2. Fresh local BM25 over notes, USER, ASSISTANT, and combined views
3. Fresh GPT-5.6 Luna low v1-style admission into a maximum-12 opaque bag
4. Fresh GPT-5.4 Nano low per-session Arm 3 extraction
5. Fresh deterministic balanced raw-turn package
6. Fresh GPT-5.6 Luna high `answer-v8-preference` answer
7. Fresh pinned GPT-4o canonical judgment

All model-visible session IDs use per-question opaque `memory_###` handles.

## Execution policy

- Dataset: all 500 LongMemEval-S questions, including 30 abstentions
- Cache/resume: disabled; every model-dependent stage is called again
- Query-time token budget: 1,900,000 reserved tokens per rolling 60 seconds
- Query-time request concurrency: 192
- Judge concurrency: 64
- Existing frozen session notes are treated as the already-built memory index
- Exact prompts and structured responses are retained where the provider API
  exposes them; private hidden reasoning is not exposed by the API

## Artifact map

- `hop-full500-v1.json`: exact ordered evaluation slice
- `hybrid-retrieval.json`: aggregate and per-case retrieval results
- `retrieval-cases/<qid>.json`: durable per-case retrieval trace and model I/O
- `logs/`: complete command stdout/stderr logs
- downstream run:
  `runs/arch0008-full500-fresh-20260731T002635Z-3`
- downstream `agent-artifacts/cases/<qid>/context-package.json`
- downstream `agent-artifacts/cases/<qid>/intermediate.json`
- downstream `agent-artifacts/cases/<qid>/model-io.json`
- downstream `predictions.jsonl`, `judgments.jsonl`, and `report.json`
- downstream `judge-artifacts/<qid>.json`: exact canonical judge prompt,
  response, usage, request ID, latency, and retry count
- `AUDIT.json` and `SUMMARY.md`: generated after completion

## Commands

```bash
pnpm --dir src/agents/current exec node --import tsx \
  src/scripts/buildHopFull500.ts \
  --out runs/full500-audit-20260731T002635Z/hop-full500-v1.json

pnpm --dir src/agents/current exec node --import tsx \
  src/scripts/hopArchitectureScreen.ts \
  --arm hybrid \
  --ids runs/full500-audit-20260731T002635Z/hop-full500-v1.json \
  --annotations runs/local-archive/backbone/session-annotations-v1 \
  --model gpt-5.6-luna --reasoning low \
  --concurrency 192 --token-budget 1900000 --window-seconds 60 \
  --case-artifacts runs/full500-audit-20260731T002635Z/retrieval-cases \
  --out runs/full500-audit-20260731T002635Z/hybrid-retrieval.json

pnpm --dir src/agents/current exec node --import tsx \
  src/scripts/hopBagDownstreamGate.ts \
  --hop-run runs/full500-audit-20260731T002635Z/hybrid-retrieval.json \
  --out-prefix arch0008-full500-fresh-20260731T002635Z \
  --arms 3 \
  --reader-model gpt-5.4-nano-2026-03-17 --reader-reasoning low \
  --answer-model gpt-5.6-luna --answer-reasoning high \
  --concurrency 192 --token-budget 1900000 \
  --opaque-session-ids true --capture-model-io true

uv run python src/longmemeval/tools/judge_parallel.py \
  --run arch0008-full500-fresh-20260731T002635Z-3 \
  --concurrency 64

uv run memorybench report \
  --run arch0008-full500-fresh-20260731T002635Z-3
```

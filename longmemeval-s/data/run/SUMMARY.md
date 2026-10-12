# Architecture 0008 — fresh all-500 result

The complete no-reuse pipeline scored **457/500 (91.40%)**. All 19,195
sessions were freshly annotated, all 500 questions completed retrieval and
downstream answering, and all 500 answers were judged with the pinned
GPT-4o evaluator.

## Architecture

1. `gpt-5.4-nano-2026-03-17` storer, USER turns only
2. `gpt-5.6-luna` low: parallel multi-view discovery plus v1 admission
3. `gpt-5.4-nano-2026-03-17` low: Arm 3 per-session claim extraction
4. `gpt-5.6-luna` high: final answer
5. `gpt-4o-2024-08-06`, temperature 0: exact pinned judge

The storer, retrieval, and downstream stages used concurrency 256 with a
1.95M-token rolling 60-second budget. The judge used concurrency 64.

## Final accuracy

| Slice | Correct | Accuracy |
|---|---:|---:|
| All | 457/500 | 91.40% |
| Answerable | 431/470 | 91.70% |
| Abstention | 26/30 | 86.67% |
| Knowledge update | 74/78 | 94.87% |
| Multi-session | 116/133 | 87.22% |
| Single-session assistant | 56/56 | 100.00% |
| Single-session preference | 27/30 | 90.00% |
| Single-session user | 68/70 | 97.14% |
| Temporal reasoning | 116/133 | 87.22% |

Task-averaged accuracy is 92.74%.

## Retrieval

- Candidate pool full-gold: 494/500 (98.80%)
- Final bag full-gold: 471/500 (94.20%)
- Mean candidate-pool gold recall: 99.43%
- Mean final-bag gold recall: 97.36%
- Mean pool size: 23.89 sessions
- Mean bag size: 2.09 sessions

Of the 43 wrong final answers, **35 already had a full-gold bag** and only
8 lacked one or more gold sessions. The largest remaining loss is therefore
after retrieval, especially on multi-session and temporal reasoning, although
retrieval still accounts for a smaller residual.

## Cost and time

| Stage | Estimated cost | Measured elapsed |
|---|---:|---:|
| Fresh storer | $11.582 | 18.39 min |
| Hybrid retrieval | $6.900 | 4.30 min |
| Extraction + answer | $4.901 | 7.25 min |
| Judge | $0.235 | 10.8 sec |
| Core total | **$23.618** | **30.12 min** |

The separate two-session preflight smoke cost about $0.002. Total operational
cost including it was approximately **$23.619**. Core model usage was
34,421,676 tokens across 23,240 API calls.

## Certification

- No prior annotation cache or prior query-time model output was reused.
- All 19,195 raw session IDs were checked against every model-visible storer
  prompt and all 500 retrieval and downstream prompt sets: zero leaks.
- Exact model prompts, outputs, request IDs, usage, latency, and retry counts
  are retained at each model-dependent stage.
- Storer, retrieval, downstream, and judge each finished with zero unresolved
  failures.
- One malformed Unicode surrogate from provider output was normalized to
  U+FFFD in the strict-valid merged retrieval JSON.
- Typecheck, all 59 tests, targeted TypeScript lint, Python Ruff, and Python
  compile checks passed. Repository-wide lint still reports 13 pre-existing
  findings in unrelated files; none are in the changed files.

Primary machine-readable results are in `AUDIT.json`,
`hybrid-retrieval-complete.json`, and the downstream run
`runs/arch0008-full500-from-scratch-20260731T004831Z-3/report.json`.

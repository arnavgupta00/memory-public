# Architecture 0008 full-500 from-scratch run

Run bundle: `full500-from-scratch-20260731T004831Z`

Started: 2026-07-31 06:18 IST / 2026-07-31T00:48:31Z

## No-reuse boundary

This run does not read the prior answerable135 annotation directory or any
output from `full500-audit-20260731T002635Z`.

Fresh model-dependent stages:

1. Annotate all unique sessions across all 500 questions.
2. Build a new notes index from those annotations.
3. Run opaque hybrid candidate discovery and v1 admission.
4. Run Nano-low Arm 3 extraction.
5. Run Luna-high final answering.
6. Run the pinned GPT-4o canonical judge.

The immutable raw LongMemEval dataset and prompt source files are inputs, not
cached model outputs.

## Models and limits

- Storer: `gpt-5.4-nano-2026-03-17`
- Retrieval planner/admission: `gpt-5.6-luna`, low reasoning
- Arm 3 extractor: `gpt-5.4-nano-2026-03-17`, low reasoning
- Final answerer: `gpt-5.6-luna`, high reasoning
- Judge: `gpt-4o-2024-08-06`, temperature 0
- Query-time/storer concurrency: 256
- Rolling query-time/storer token reservation: 1,950,000 per 60 seconds
- Judge concurrency: 64

Every model-visible storer source ID and retrieval/downstream session ID is
opaque. Exact prompts, structured outputs, request IDs, usage, latency, and
retry counts are retained where exposed by the provider API.

## Primary artifacts

- `hop-full500-v1.json`
- `session-annotations-v1/`
- `storer-audit/`
- `storer-repair-audit/`
- `hybrid-retrieval.json` (initial pass)
- `hybrid-retrieval-repair1.json` and `hybrid-retrieval-repair2.json`
- `hybrid-retrieval-complete.json` (certified merged input to downstream)
- `retrieval-cases/`
- `logs/`
- downstream run:
  `runs/arch0008-full500-from-scratch-20260731T004831Z-3`
- final `AUDIT.json`, `SUMMARY.md`, `SHA256SUMS`, and
  `code-changes-final.patch`

## Completion

- Status: complete
- Fresh annotations: 19,195/19,195 sessions
- Retrieval: 500/500 cases, zero errors
- Downstream: 500/500 cases, zero errors
- Judge: 500/500 cases
- Final score: 457/500 (91.40%)
- Finished: 2026-07-31T01:25:08Z

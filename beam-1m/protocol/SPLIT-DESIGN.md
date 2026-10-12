> Excerpt of the internal design note for the BEAM-1M split, written 31 Jul–1 Aug 2026 (the allocation note at the top
> was added on 24 Sep). The sections on implementation are omitted. The split files themselves are in
> `../data/questions/partition-files/`.

# BEAM-1M canary design

**2026-09-24 allocation update:** The user authorized allocating the 13
final-blind histories to a new 75-question development cohort. Their complete
260-question histories are no longer an independent holdout. Canary B and its
four expansion histories remain protected. The original manifests below remain
historical snapshots; see the allocation record
`../data/questions/partition-files/beam-1m-holdout-allocation-20260924.json` for current status.

**Status:** frozen / Canary A measured / structurally validated / dual-benchmark runner implemented
**Source:** BEAM commit `3e12035532eb85768f1a7cd779832b650c4b2ef9`
**Selection seed:** `20260731`

## Decision

BEAM-1M is partitioned at the complete-conversation boundary. Questions from
one conversation never cross development and certification partitions.

| Partition | Conversations | Questions | Intended use |
|---|---:|---:|---|
| Canary A | 5 | 100 | Development, debugging, and permitted tuning |
| Canary B | 13 | 260 | Sealed score prediction after architecture freeze |
| Blind reserve | 17 | 340 | Variance-only expansion and final confirmation |

Every conversation has exactly two questions for each of the ten BEAM
abilities, so both canaries are exactly ability-balanced.

## Frozen conversation partition

- Canary A: `3, 8, 18, 25, 29`
- Canary B: `1, 2, 9, 10, 12, 14, 17, 22, 24, 26, 27, 30, 35`
- Expansion to 15: `16, 21`
- Expansion to 17: `7, 34`
- Final blind confirmation: `4, 5, 6, 11, 13, 15, 19, 20, 23, 28, 31, 32, 33`

The expansion order is fixed before model inference. Expansion is allowed only
when the conversation-level finite-population 95% confidence interval has a
half-width above five percentage points. The observed point score must never
influence expansion.

## Selection isolation

The optimizer used:

- topic category;
- message, pair, turn-group, character, and time-anchor counts;
- difficulty labels;
- anonymous source-ID counts and normalized source positions;
- event-ordering, summarization, and multi-session evidence breadth.

It did not use question text, ideal answers, rubric content, model outputs, or
Architecture 0008 results. Session/message IDs remain host-only evaluation
metadata.

Canary A deliberately emphasizes diagnostic diversity and may be inspected.
Canary B and the reserve must stay sealed until the architecture, prompts,
models, caps, and scorer are frozen. Tuning after Canary B is unsealed retires
that certification result.

## Structural fit of Canary B

| Statistic | Full 700 | Canary B 260 |
|---|---:|---:|
| Mean source pairs | 6.7071 | 6.7962 |
| Median source pairs | 3 | 3 |
| P90 source pairs | 25 | 25 |
| Maximum source pairs | 48 | 48 |
| Exceeds bag-12 | 107 (15.29%) | 39 (15.00%) |
| Exceeds 20 pairs | 82 (11.71%) | 30 (11.54%) |
| Exceeds pool-24 | 71 (10.14%) | 27 (10.38%) |

Across the normalized selection features, Canary B has RMS standardized mean
difference `0.0792` and maximum absolute difference `0.1768`. Its two omitted
rare categories—Education & Learning and Relationship & Family—each represent
only one of the 35 conversations; keeping proportional Coding and Math coverage
produced the lower aggregate imbalance.

## Reliability contract

Primary metric: official BEAM macro score across the ten abilities.

- Target uncertainty: conversation-level 95% interval half-width at most `0.05`.
- Published reference points: RAG `0.302`; LIGHT `0.336`.
- Green: lower confidence bound exceeds `0.336`.
- Promising: point estimate exceeds `0.302`, but the interval overlaps `0.336`.
- Red: upper confidence bound is below `0.302`.

Canary A is measured; Canary B remains sealed. The canary design is still
**empirically provisional** for full-700 score prediction.
The upstream repository does not contain published per-conversation baseline
outputs, so retrospective score-prediction backtesting is unavailable. Canary B
becomes empirically certified only after its prediction is compared with one
paired, unchanged full-700 run.

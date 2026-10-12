# Comparison with published BEAM-1M results

Sources were retrieved on **12 Oct 2026**. Vendor numbers are self-reported unless marked otherwise. Different scorers
give very different numbers for the same answers: our own answers score between 76.83 and 82.23 depending on the basis.
**A comparison is only meaningful on the same basis,** so each row below states its basis.

## 1. What has been published, and on what basis
| System | BEAM-1M score | Basis (judge) | Answer model | Source |
|---|---:|---|---|---|
| BEAM paper, best system (LIGHT) | 33.6 | BEAM's own evaluation | Llama-4-Maverick / GPT-4.1-nano | arXiv 2510.27246, Table 1 |
| ReMe | 65.0 graded (60.9 binary) | BEAM rubric judge, "longmemeval-version prompt" (judge model not named) | not named | reme.agentscope.io/en/benchmarks/beam |
| Mem0 (managed platform) | 64.1 | Rubric item mean with half credit for every ability, event ordering included (Mem0's judge configuration; default model not named) | — | docs.mem0.ai/core-concepts/memory-evaluation; code: github.com/mem0ai/memory-benchmarks |
| Honcho | 63.1 | not stated | not stated | Hindsight's table (hindsight.vectorize.io/blog/2026/04/02/beam-sota) |
| Hindsight | 73.9 | Vectorize AMB rubric mean (`score_result`); judge gemini-2.5-flash-lite | gemini-3.1-pro-preview | AMB results file (below) and the Hindsight blog |
| HydraDB | 82 | "the same answer-generation and evaluation configuration as Hindsight's" (AMB) | not named | benchmarks.hydradb.com/beam-1m |
| **Ours (R9)** | **76.83** | **BEAM's official evaluator, unmodified (gpt-4.1-mini)** | DeepSeek V4.1 Flash | this package |
| Ours, on Hindsight/HydraDB's basis | 78.18 | AMB `score_result`, judge gemini-3.5-flash-lite | DeepSeek V4.1 Flash | `data/comparison/` |
| Ours, on Mem0's basis | 82.23 | Rubric item mean with half credit, event ordering by rubric (BEAM's judge, gpt-4.1-mini) | DeepSeek V4.1 Flash | `data/scores/scores.csv` |

Other self-reported BEAM results exist, for example Exabase's July 2026 press release. We could not examine their
scoring, so they are left out.

## 2. Like for like
**Official evaluator.**
- We know of no vendor that publishes BEAM's official score. The only official-method numbers we found are the paper's.
- Our 76.83 is the only official-evaluator result for a complete memory system on all 700 questions that we know of.

**Vectorize/AMB basis (Hindsight 73.9, HydraDB 82): ours is 78.18.**
- **What Hindsight's 73.9 actually is.** We downloaded Hindsight's own published results file from AMB's repository
  (commit `20751fa0`, `outputs/beam/hindsight/single-query/1m.json.gz`, sha256 `95e87a30…`). Its headline "accuracy",
  0.7386, is the mean per-item rubric score, which AMB's `score_result` computes. It is not the pass rate: the same file
  marks 585 of 700 correct, which is 83.6%. HydraDB states that it used the same configuration. Facts drawn from that
  file are in `data/comparison/hindsight-published-results-summary.json`.
- **How we matched it.** We ran AMB's `score_result` unchanged on our 700 answers.
- **Where it differs:**
  - **Judge model.** Hindsight's judge, gemini-2.5-flash-lite, now returns "no longer available to new users" (HTTP 404).
    We used gemini-3.5-flash-lite, the closest available model. The judge moves the score, so this comparison is close,
    not exact.
  - **Answers.** In AMB's runs, each memory provider supplies retrieved memories and AMB answers with a fixed prompt on
    Gemini 3.1 Pro. Ours are our system's own answers, written by DeepSeek V4.1 Flash, a low-cost Flash-tier model.

**Mem0 basis (Mem0 64.1): ours is 82.23.**
- Same convention: the mean of rubric items, half credit counted, and event ordering by its rubric.
- Different judges: ours is BEAM's own (gpt-4.1-mini); Mem0 uses its own judge configuration. Mem0 notes a ±1 point
  variation from judge inconsistency.

## 3. By ability on the AMB basis
Our scores use gemini-3.5-flash-lite on all 700. Hindsight's are recomputed from its published results file. HydraDB's
are from its page.

| Ability | Ours | Hindsight | HydraDB |
|---|---:|---:|---:|
| Abstention | 68.6 | 90.0 | 89 |
| Contradiction resolution | 67.5 | 59.5 | 66 |
| Event ordering | 71.3 | 80.9 | 92 |
| Information extraction | 92.0 | 61.3 | 80 |
| Instruction following | 97.7 | 93.3 | 92 |
| Knowledge update | 86.4 | 66.4 | 63 |
| Multi-session reasoning | 73.9 | 46.2 | 60 |
| Preference following | 91.1 | 97.0 | 96 |
| Summarization | 79.0 | 84.5 | 88 |
| Temporal reasoning | 54.3 | 59.6 | 91 |
| **Overall** | **78.18** | **73.86** | **82** |

**Where we lead on this basis:** information extraction, knowledge update, multi-session reasoning and contradiction
resolution.

**Where we trail:**
- Abstention.
- Event ordering.
- Temporal reasoning, where HydraDB reports 91 against our 54.3. Temporal reasoning is also our weakest ability on BEAM's
  own judge.

## 4. Event ordering is scored two ways
BEAM's evaluator computes two scores for event ordering:
- `tau_norm`, an order score over lines matched to hidden reference labels, which the official report uses;
- `llm_judge_score`, which asks whether the answer mentions each reference item.

Mem0, Hindsight and HydraDB all publish rubric-style numbers. On the official order score we get 28.7; the paper's own
best system gets about 20 at 1M (our offline replay of the official scorer). On the rubric we get 77.0, against Mem0's 53.6. So the published
event-ordering numbers of 80–92 are not comparable with an official event-ordering score.

## 5. Caveats
- Vendor numbers are self-reported and could not be re-run by us. We checked Hindsight's only through its published
  results file.
- Judges differ between rows, and the judge alone moves a score by several points. The same answers (our earlier run
  R8, Canary A) score 87.7 as a rubric average with BEAM's judge, and 80.1 with AMB's scorer (a Gemini judge with
  Mem0's prompt).
- AMB evaluates a memory provider with a fixed strong answerer (Gemini 3.1 Pro). We evaluate a whole system whose
  answerer is a low-cost model.
- Our development sets are part of our 700. On the unseen 340 alone, our numbers are 76.00 official, 78.00 on the AMB
  basis and 81.74 on the Mem0 basis.

# Results

All numbers are recomputed from `data/judge/` by `verify/verify.py` (checks 8–11), or from `data/scores/*.csv`. Scores are
on a 0–100 scale. "Official" means BEAM's pinned evaluator (`3e12035`) exactly as it reports; the other bases are defined
in [METHOD.md](METHOD.md) §4.

## 1. Headline
**BEAM-1M, all 700 questions, official evaluator: 76.83.** On the 340 questions sealed until their run: **76.00.**

| Set | Questions | Official | + half-credit fix | Rubric average (BEAM judge) | Vectorize/AMB scorer |
|---|---:|---:|---:|---:|---:|
| **All 700** | 700 | **76.83** | 77.39 | 82.23 | 78.18 |
| Canary A (development) | 100 | 77.71 | 78.19 | 83.28 | 79.51 |
| Fresh75 histories (development) | 260 | 77.58 | 78.00 | 82.46 | 77.91 |
| Canary B (sealed) | 260 | 75.97 | 76.49 | 81.19 | 77.48 |
| Expansion (sealed) | 80 | 76.09 | 77.37 | 83.50 | 79.71 |
| Development total (A + Fresh75) | 360 | 77.61 | 78.05 | 82.69 | 78.36 |
| **Unseen total (B + expansion)** | 340 | **76.00** | 76.70 | 81.74 | 78.00 |

The sealed questions score 1.6 points below the development questions on the official basis, and 0.4 below on the
Vectorize basis. That is about the size of one run's sampling variation (§4).

## 2. By ability (official)
Each cell is the mean over that set's questions of the ability: 10 for Canary A, 26 for Fresh75 and for Canary B, 8 for
expansion, and 70 in the All 700 column.

| Ability | Canary A | Fresh75 h. | Canary B | Expansion | Development | Unseen | **All 700** |
|---|---:|---:|---:|---:|---:|---:|---:|
| Instruction following | 100.0 | 100.0 | 96.2 | 100.0 | 100.0 | 97.1 | **98.6** |
| Preference following | 100.0 | 93.6 | 92.6 | 90.6 | 95.4 | 92.2 | **93.8** |
| Information extraction | 88.3 | 89.8 | 92.3 | 85.0 | 89.4 | 90.6 | **90.0** |
| Abstention | 80.0 | 86.5 | 80.8 | 87.5 | 84.7 | 82.4 | **83.6** |
| Knowledge update | 95.0 | 75.0 | 84.6 | 87.5 | 80.6 | 85.3 | **82.9** |
| Summarization | 78.6 | 83.5 | 81.8 | 82.0 | 82.1 | 81.8 | **82.0** |
| Contradiction resolution | 77.5 | 84.6 | 78.8 | 81.2 | 82.6 | 79.4 | **81.1** |
| Multi-session reasoning | 82.5 | 82.6 | 69.6 | 82.4 | 82.6 | 72.6 | **77.7** |
| Temporal reasoning | 50.0 | 50.0 | 51.9 | 43.8 | 50.0 | 50.0 | **50.0** |
| Event ordering | 25.2 | 30.1 | 31.1 | 21.0 | 28.7 | 28.7 | **28.7** |
| **Overall** | 77.71 | 77.58 | 75.97 | 76.09 | 77.61 | 76.00 | **76.83** |

**By ability on the four bases (all 700):**

| Ability | Official | + half credit | Rubric average | Vectorize/AMB |
|---|---:|---:|---:|---:|
| Abstention | 83.6 | 83.6 | 83.6 | 68.6 |
| Contradiction resolution | 81.1 | 81.1 | 81.1 | 67.5 |
| Event ordering | 28.7 | 28.7 | 77.0 | 71.3 |
| Information extraction | 90.0 | 90.7 | 90.7 | 92.0 |
| Instruction following | 98.6 | 98.9 | 98.9 | 97.7 |
| Knowledge update | 82.9 | 82.9 | 82.9 | 86.4 |
| Multi-session reasoning | 77.7 | 79.4 | 79.4 | 73.9 |
| Preference following | 93.8 | 94.5 | 94.5 | 91.1 |
| Summarization | 82.0 | 83.8 | 83.8 | 79.0 |
| Temporal reasoning | 50.0 | 50.4 | 50.4 | 54.3 |
| **Overall** | **76.83** | **77.39** | **82.23** | **78.18** |

How to read these:
- **Event ordering** is the only ability where the official and rubric bases differ widely: 28.7 against 77.0. The answers
  mention about three quarters of the reference events, which is what the rubric measures. The official order score
  credits a line only when an LLM matcher equates it with one of the reference's own short labels
  ([LIMITATIONS.md](LIMITATIONS.md) §5).
- **Temporal reasoning (50.0)** is the weakest ability on every basis. On the development sets, most lost temporal points
  traced to answer keys that the conversations contradict (internal loss analysis); the rest are real errors, such as choosing the wrong
  one of two dates.
- **Multi-session reasoning** fell on Canary B (69.6 against 82–83 on the development sets). The Canary B post-mortem
  (internal) traces most of it to the planner.
- **Abstention and contradiction resolution score lower on Vectorize's scorer** (68.6 and 67.5) than on BEAM's judge.
  The Gemini judge with Mem0's per-item prompt is stricter on those rubrics.

## 3. By conversation (official and Vectorize)
| Conversation | Set | Official | Vectorize |
|---:|---|---:|---:|
| 1 | Canary B (sealed) | 72.76 | 71.10 |
| 2 | Canary B (sealed) | 73.01 | 74.16 |
| 3 | Canary A (development) | 79.51 | 69.33 |
| 4 | Fresh75 history (development) | 77.01 | 80.17 |
| 5 | Fresh75 history (development) | 82.02 | 80.11 |
| 6 | Fresh75 history (development) | 74.72 | 75.50 |
| 7 | Expansion (sealed) | 61.11 | 71.45 |
| 8 | Canary A (development) | 71.10 | 79.54 |
| 9 | Canary B (sealed) | 72.28 | 72.92 |
| 10 | Canary B (sealed) | 77.06 | 78.28 |
| 11 | Fresh75 history (development) | 71.80 | 68.38 |
| 12 | Canary B (sealed) | 84.40 | 83.26 |
| 13 | Fresh75 history (development) | 80.99 | 76.13 |
| 14 | Canary B (sealed) | 71.71 | 65.76 |
| 15 | Fresh75 history (development) | 71.93 | 79.42 |
| 16 | Expansion (sealed) | 82.22 | 77.62 |
| 17 | Canary B (sealed) | 76.15 | 77.87 |
| 18 | Canary A (development) | 80.22 | 85.52 |
| 19 | Fresh75 history (development) | 76.05 | 79.97 |
| 20 | Fresh75 history (development) | 82.93 | 85.74 |
| 21 | Expansion (sealed) | 80.79 | 84.46 |
| 22 | Canary B (sealed) | 79.75 | 82.83 |
| 23 | Fresh75 history (development) | 84.52 | 86.57 |
| 24 | Canary B (sealed) | 71.19 | 75.10 |
| 25 | Canary A (development) | 83.22 | 81.74 |
| 26 | Canary B (sealed) | 86.81 | 91.12 |
| 27 | Canary B (sealed) | 78.59 | 76.33 |
| 28 | Fresh75 history (development) | 78.54 | 75.58 |
| 29 | Canary A (development) | 74.49 | 81.41 |
| 30 | Canary B (sealed) | 69.20 | 73.75 |
| 31 | Fresh75 history (development) | 76.43 | 78.48 |
| 32 | Fresh75 history (development) | 82.54 | 80.37 |
| 33 | Fresh75 history (development) | 69.06 | 66.46 |
| 34 | Expansion (sealed) | 80.25 | 85.29 |
| 35 | Canary B (sealed) | 74.70 | 84.73 |

- **Official conversation scores.** Mean 76.83, standard deviation 5.51, range 61.11 (conversation 7) to 86.81
  (conversation 26).
- **Conversation 7** is the one outlier, and it is in the sealed expansion block. Five of its questions scored 0: both
  temporal questions, and one each of abstention, information extraction and knowledge update.

## 4. Reliability: how much these numbers move
- **No sampling over conversations for the full 700.** All 35 conversations are covered, so the 700-question score has
  no sampling error over conversations. What remains is run-to-run variation (the models sample) and judge variation.
- **Run-to-run variation.**
  - Two answer runs of the same configuration on the same Canary A memory packs scored 77.71 and 79.32; 31 of 100
    questions changed.
  - The Canary B post-mortem estimates about ±1 point for one run on 260 questions. On 700 questions, expect less than
    that.
- **Judge variation.** gpt-4.1-mini at temperature 0 is close to deterministic, but re-scoring identical event-ordering
  answers changed 4 of 36 alignments, by 0.8 points on average. Re-judging all 700 should agree within about half a
  point (L3 in [VERIFY.md](VERIFY.md)).
- **The precommitted reliability contract for Canary B.** The finite-population 95% confidence half-width over its 13
  conversation scores, against the 35 in all, is 2.3 points (z = 1.96, as computed in the run; 2.6 with a t quantile).
  The target was at most 5, so the expansion block was not needed for reliability. It was run anyway, as part of the
  full 700.
- **The same half-width for the 17 unseen conversations** (Canary B + expansion) is 2.2 points (z) or 2.4 (t).
- **Pass/fail.** For reference, Vectorize's pass/fail judge (gemini-3.5-flash) marked 275 of 360 answers correct
  (76.4%) on Canary A + B. It was not run on the other 340.

## 5. Run health
| Part | Questions | Answered | Blank answers | Model calls | Judge calls (failed) | Resumes | Amendments |
|---|---:|---:|---:|---:|---:|---:|---|
| Canary A part 1 | 20 | 20 | 0 | 4,219 | 385 (0) | 0 | none |
| Canary A part 2 | 80 | 80 | 0 | 739 | 1,094 (0) | 3 | none (resumed after TypeSafe ran out of credits) |
| Canary B | 260 | 260 | 0 | 13,283 | 3,749 (0) | 13 | 3 (failure paths) |
| Remaining 340 | 340 | 340 | 0 | 17,660 | 4,654 (0) | 5 | 1 (failure path) |
| **Total** | **700** | **700** | **0** | **35,901** | **9,882 (0)** | 21 | 4 |

- Every model call above returned a non-empty reply.
- Transient provider errors were all recovered: 83 HTTP errors (mostly 429 rate limits, a few 5xx, one 408 timeout), 1
  transport error and 3 empty streams. They were retried by the translator, or by the pipeline's own retry for the 408.
- In 650 cases a JSON stage's reply failed its schema check and was asked again.
- See `runs/*/hive-ledger-summary.json`.

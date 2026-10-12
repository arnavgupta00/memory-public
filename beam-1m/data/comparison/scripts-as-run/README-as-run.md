# AMB (Vectorize) judge on our BEAM answers, 12 Oct 2026

## Valid
**Pass/fail judge** (`amb_judge.py`, `results.json`): AMB's per-category correct/incorrect prompts, gemini-3.5-flash,
360 answers, 0 errors.

| Set | Correct |
|---|---|
| Canary A | 78.0% (78/100) |
| Canary B | 75.8% (197/260) |
| **Combined** | **76.4% (275/360)** |

Event ordering is 1 of 36.

## Not valid (all zeros: the calls failed and AMB's code records a failed call as 0)
`INVALID-score-*.json`, the rubric-mean score (`amb_score.py`). Two causes:
- gemini-2.5-flash-lite, the judge in Hindsight's published run, returns HTTP 404: "no longer available to new users".
- gemini-3.5-flash returns HTTP 429: "project has exceeded its monthly spending cap".

## Key finding
Hindsight's published "73.9% accuracy" at 1M is the **mean rubric score** (AMB `score_result`). Their pass/fail rate in
the same results file is 83.6% (585/700).

Their run used:
- answer model gemini-3.1-pro-preview;
- judge gemini-2.5-flash-lite.

HydraDB's 82% and both systems' per-category numbers are on that rubric-mean basis.

## Valid: AMB rubric-mean score (the basis of Hindsight's 73.9 and HydraDB's 82), 12 Oct
`amb_score.py gemini-3.5-flash-lite` → `score-gemini-3.5-flash-lite.json`. 360 answers, 0 failed judge calls (failed
calls are now retried instead of being scored 0).

| Set | AMB score |
|---|---:|
| Canary A | 79.5 |
| Canary B | 77.5 |
| **Combined** | **78.0** |

| Category | Ours (360) | Hindsight (700) | HydraDB (700) |
|---|---:|---:|---:|
| Abstention | 63.9 | 90 | 89 |
| Contradiction resolution | 68.8 | 59 | 66 |
| Event ordering | 67.7 | 81 | 92 |
| Information extraction | 93.8 | 61 | 80 |
| Instruction following | 96.3 | 93 | 92 |
| Knowledge update | 93.1 | 66 | 63 |
| Multi-session reasoning | 71.7 | 46 | 60 |
| Preference following | 88.7 | 97 | 96 |
| Summarization | 80.4 | 84 | 88 |
| Temporal reasoning | 56.2 | 60 | 91 |
| **Overall** | **78.0** | **73.9** | **82** |

**Differences from their setup:**
- **Judge:** gemini-3.5-flash-lite. Hindsight's gemini-2.5-flash-lite is no longer available to new users.
- **Questions:** 360 (Canary A + B), against their 700.
- **Answers:** our own planner/answerer. Theirs use AMB's fixed answer prompt with Gemini 3.1 Pro.

## R8 (Canary A 82.41) and R9's two runs on every basis (12 Oct)
| Basis (Canary A, 100 questions) | R8 | R9 run 1 | R9 run 2 |
|---|---:|---:|---:|
| BEAM official, pinned | 82.4 | 77.7 | 79.3 |
| BEAM official + half-credit fix | 82.7 | 78.2 | 79.4 |
| Rubric average, BEAM judge | 87.7 | 83.3 | 84.9 |
| Vectorize/Hindsight rubric average (3.5 Flash Lite) | **80.1** | **79.5** | **79.8** |
| Vectorize pass/fail (3.5 Flash) | 79.0 | 78.0 | 79.0 |

On an independent judge the three runs are within 0.6 points of each other. R8's lead on BEAM's official judge
(gpt-4.1-mini) mostly does not carry over. That is consistent with doc 27's finding of judge inconsistency on near-identical
answers.

Files: `score-gemini-3.5-flash-lite-r8.json`, `score-gemini-3.5-flash-lite-r9run2.json`, `results-r8.json`, `results-r9run2.json`.

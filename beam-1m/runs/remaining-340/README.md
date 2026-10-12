# BEAM-1M full 700 with the frozen R9 configuration: the remaining 340 questions (12 Oct 2026)

Written before the run started.

## What runs
- **Configuration:** R9, exactly the code that completed Canary B (`runs/canary-b-r9-20261011`).
  - The frozen A6 pipeline with the A2 answer layer (FROZEN.json sha256 `74ae7895…`, including Canary B's three
    failure-path amendments).
  - The Hive translator, sha256 `5be459b1…`, the same file as Canary B's final state.
  - Every GPT call goes to DeepSeek V4.1 Flash on Hive:

    | Stage | Reasoning |
    |---|---|
    | Session notes | none |
    | Router, search, targeted plans | low |
    | Packager's discarded answer | none, real call (no placeholder) |
    | Planner + answerer | max |

  - Unchanged: voyage-context-4, TypeSafe jev-1.13.0, and the official BEAM judge (3e12035, gpt-4.1-mini, temperature 0).
  - **No change of any kind** relative to Canary B. The only run-time setting is `--jev-cap 20`, the spend guard that
    Canary B also used.
- **Questions (`scripts/questions.json`, 340):** all 20 questions of each of the 17 conversations not in Canary A or
  Canary B.
  - The 13 Fresh75 histories (4, 5, 6, 11, 13, 15, 19, 20, 23, 28, 31, 32, 33) are a development set: seen.
  - The 4 expansion histories (7, 16, 21, 34) are sealed.
- **Fully fresh:** these histories share nothing with earlier runs.

## Rules
- One answer per question. No reruns and no selection by score.
- Failed calls are redone through `--resume`. Finished answers are never redone.

## Final BEAM-1M score
- **700 questions:** Canary A (R9, original answer run: `runs/a6/canary-a-screen20-hive-r9` + `canary-a-other80-hive-r9`),
  Canary B (`runs/canary-b-r9-20261011`) and these 340.
- **Headline:** the official pinned score.
- **Also reported, labelled:** official with the half-credit fix, the rubric average, and the Vectorize/Hindsight scorer.
- **The clean unseen estimate stays separate:** Canary B, plus the 80 expansion questions here.

## Amendment, 02:45 (during the run)
- **What happened:** the run stopped at stage 2 (Voyage index). 16 of 17 history indexes were built. The 17th history sent one
  embedding batch of 120,372 tokens, against Voyage's limit of 120,000 per batch, because the local token estimate that sizes
  the batches ran slightly low. Every resume rebuilt the same batch and failed the same way.
- **Change (failure path only):** in `src/retrieval/semanticProviders.ts`, a batch Voyage refuses with
  `TOO_MANY_TOKENS_IN_BATCH` is split in two by whole documents and each half embedded.
  - Voyage contextualizes a chunk within its own document, so the vectors are the same as for the unsplit batch.
  - Accepted batches are byte-identical. Canary A and Canary B never hit this path.
- **Record:** `FROZEN.json` → `amendments`. `run.mjs verify` passes.
- **Resume:** the run continued with `--resume`, and the 16 finished indexes and all session notes were reused.

## Result (04:19, 12 Oct 2026)
**BEAM-1M, all 700 questions, frozen R9 configuration, official evaluator (pinned 3e12035): 76.83.**

| Set | n | Official | + half credit | Rubric avg (BEAM judge) | Vectorize/Hindsight rubric avg (Gemini 3.5 Flash Lite) |
|---|---:|---:|---:|---:|---:|
| Canary A (dev) | 100 | 77.71 | 78.19 | 83.28 | 79.5 |
| Canary B (sealed) | 260 | 75.97 | 76.49 | 81.19 | 77.5 |
| Remaining 340 (this run) | 340 | 77.23 | 77.85 | 82.70 | 78.3 |
| Expansion 80 (sealed) | 80 | 76.09 | 77.37 | 83.50 | — |
| **Unseen: Canary B + expansion** | 340 | **76.00** | 76.70 | 81.74 | 78.0 |
| **ALL 700** | 700 | **76.83** | **77.39** | **82.23** | **78.18** |

**By ability, all 700 (official / rubric):**

| Ability | Official | Rubric |
|---|---:|---:|
| Abstention | 83.6 | 83.6 |
| Contradiction resolution | 81.1 | 81.1 |
| Event ordering | 28.7 | 77.0 |
| Information extraction | 90.0 | 90.7 |
| Instruction following | 98.6 | 98.9 |
| Knowledge update | 82.9 | 82.9 |
| Multi-session reasoning | 77.7 | 79.4 |
| Preference following | 93.8 | 94.5 |
| Summarization | 82.0 | 83.8 |
| Temporal reasoning | 50.0 | 50.4 |

- **Conversations:** all 35 covered; per-conversation scores have mean 76.83, SD 5.52, range 61.1–86.8.
- **This run (340 questions):**
  - 340/340 answered, 0 blank answers.
  - 17,660 Hive calls, $80.17 at list price (about $42 billed). TypeSafe about $6. Judge about $1.
  - One failure-path amendment (Voyage batch split), described above.
  - Translator trim fallback never used. 0 JEV refusals.

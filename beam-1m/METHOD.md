# Method

## 1. The benchmark
**BEAM** ("Beyond a Million Tokens"; Tavakoli et al., arXiv 2510.27246, https://github.com/mohammadtavakoli78/BEAM, MIT
licence) tests long-term memory over very long conversations between a user and an assistant.

- **The 1M tier.** It has 35 conversations of about one million tokens each: 1.03–1.09 million on average by our
  tokenizer. Each has 20 probing questions, 2 for each of 10 abilities: abstention, contradiction resolution, event ordering,
  information extraction, instruction following, knowledge update, multi-session reasoning, preference following,
  summarization and temporal reasoning.
- **Question files.** Each question comes with a reference answer and a rubric: a list of points a good answer must
  contain.
- **Our data.** The data is pinned to BEAM commit `3e12035`. Each file matches BEAM's git tree at that commit (check 6).

## 2. The system (the R9 configuration)
One pipeline answers every question. It reads only the conversation, the question and the question's date. Stage 1
writes the answer-key sessions to an `oracle.json` file for recall reporting. No inference stage reads it, and rubrics are
read only by the judge. These guarantees are listed in the pipeline's README, which is withheld with the code and can be
checked by an auditor.

| # | Stage | What it does | Model in R9 | Reasoning |
|---|---|---|---|---|
| 1 | Dataset | Loads the pinned BEAM files and checks them | none | — |
| 2a | Session notes, once per history | One short structured note per session (about 840 sessions per history) | DeepSeek V4.1 Flash | none |
| 2b | Notes index | Contextual vector index of the notes | voyage-context-4, 1024 dims | — |
| 3 | Memory notebook | Labels each user message as an instruction, preference, fact, relationship or goal; flagged messages kept verbatim and dated | TypeSafe jev-1.13.0 | — |
| 5 | Router | Flags the question as broad, a conflict check or a duration question, from the question text only | DeepSeek V4.1 Flash | low |
| 6 | Search | Plans queries, then BM25 + vector search, with one targeted follow-up round | DeepSeek V4.1 Flash (plans), voyage-context-4 (query vectors) | low |
| 7 | Fusion | Rank fusion with diversity (MMR 0.85), up to 180 sessions | none | — |
| 8 | Relevance filter | Scores each candidate session's relevance; keeps those at or above 0.50 | TypeSafe jev-1.13.0 | — |
| 9 | Routed extras | Broad questions get a timeline of relevant session notes. Conflict and duration questions get statements for and against, or event dates | DeepSeek V4.1 Flash (plans), TypeSafe jev-1.13.0 (checks) | low |
| 10 | Memory pack | Kept sessions oldest first, dated and role-marked, plus the notebook and extras; broad packs trimmed to 130K tokens | none | — |
| 10a | (discarded) | The packager also writes an old-style answer that nothing downstream reads | DeepSeek V4.1 Flash | none |
| 11 | Answer layer "A2" | A planner reads the whole memory pack and writes a structured answer plan. The answerer writes the final answer from the plan and the pack | DeepSeek V4.1 Flash | **max** |
| 12 | Judge | BEAM's official evaluator (Section 4) | gpt-4.1-mini (OpenAI), temperature 0 | — |

- **Hash locking.** The pipeline (`src/pipeline/a6`, 123 files) is hash-locked by `FROZEN.json`.
  - Every start and resume refuses to run if any locked file differs from its recorded hash (`run.mjs`, `checkFrozen`),
    and it writes the hash of the locked file list into the run manifest.
  - Before each run, `run.mjs verify` also checks that the frozen code rebuilds earlier runs' requests byte for byte.
    The output is in `runs/<part>/frozen-verify.txt`.
- **The 700 answers come from one configuration (R9).** All its prompts, models and thresholds were frozen on 11 Oct in
  tag `r9-freeze-20261011`.

### 2.1 Why the stages ask for OpenAI model names
The pipeline was built and frozen on OpenAI models (gpt-5.4-nano for notes; gpt-5.6-luna for the rest). To run it
unchanged on DeepSeek, every one of its OpenAI calls goes to a local **translator**
(withheld with the code; sha256 `5be459b1…`). The translator looks like OpenAI's Responses API to the pipeline and calls
DeepSeek V4.1 Flash on Hive (`deepseek-ai/deepseek-v4.1-flash`).
- **Reasoning effort per stage:**
  - session notes: none (`HIVE_EFFORT_NOTES`);
  - stages the pipeline runs at low: low (`HIVE_EFFORT_LOW`);
  - the planner and answerer: max;
  - the discarded answer: none.
- **Structured replies.** For JSON stages, the schema goes into the prompt, Hive's JSON mode is used, and every reply is
  parsed and checked against the schema. An invalid reply is asked again, up to 5 asks in all.
- **Failures and limits.**
  - Blank replies (0 output tokens) are retried; this fix was added on 11 Oct after R7.
  - Rate-limit and server errors back off and retry.
  - One rate gate is set at 4.8 requests per second.
  - A spend cap stops everything if it is reached.
- **Logging.** Every attempt is logged with tokens, latency and cost. These ledgers are in `bulk/*/hive-ledger.redacted.jsonl.gz`, with the prompt text removed.
- **What does not go through the translator.** Voyage, TypeSafe and the judge call their own providers directly.

## 3. Evaluation protocol
- **Split.** The split was fixed in advance (`data/questions/partition.json`).

  | Set | Histories | Questions | Status at run time |
  |---|---|---:|---|
  | Canary A | 3, 8, 18, 25, 29 | 100 | development (studied question by question) |
  | Fresh75 histories | 4, 5, 6, 11, 13, 15, 19, 20, 23, 28, 31, 32, 33 | 260 | development (75 studied; the 185 siblings are not independent) |
  | Canary B | 1, 2, 9, 10, 12, 14, 17, 22, 24, 26, 27, 30, 35 | 260 | **sealed** until 11 Oct |
  | Expansion | 7, 16, 21, 34 | 80 | **sealed** until 12 Oct |

  The Fresh75 histories were "final-blind" in the 1 Aug plan and were reallocated to development on 24 Sep. Canary B
  and the expansion block were never reallocated.
- **Runs.** Four run parts produced the 700 answers, all with the same configuration:

  | Part | Questions | Started (UTC) | Code state at start |
  |---|---:|---|---|
  | Canary A part 1 (screen 20) | 20 | 2026-10-10 19:44 | public freeze |
  | Canary A part 2 (other 80) | 80 | 2026-10-10 20:32 | public freeze |
  | Canary B | 260 | 2026-10-11 12:21 | public freeze |
  | Remaining 340 (Fresh75 histories + expansion) | 340 | 2026-10-11 19:53 | freeze + Canary B's amendments |

  - Canary A part 2 reused part 1's session notes and their index, because notes are made once per history and do not
    depend on the question (`runs/canary-a-part2/pipeline-run/SEEDED-FROM.json`).
  - Every per-question stage ran fresh in every part.
  - The Canary A parts ran on 10 Oct (UTC), before the tag was made. Their locked files and translator were byte-identical
    to the tag's: the same frozen-file hash `fb2baea…`, and translator sha256 `b136610e…` in both
    (`runs/canary-a-part*/sha256.txt`).
- **One answer per question.** A failed call is redone by `--resume`, which repeats only unfinished calls and reuses only
  this run's own results. No answer is ever regenerated to get a better one (check 18).
- **Amendments.** If a run stopped on a failure, the fix could touch only the failure path: a request that had already
  succeeded had to be unaffected. Each fix was recorded in `FROZEN.json` → `amendments` before the resume
  ([AMENDMENTS.md](AMENDMENTS.md)).
- **Judging.** The judge ran after each run, on real OpenAI, through `verify/judge-wrapper/.../judgeExpertReview.py`, which is published and matches its hash in `FROZEN.json`. That
  wrapper runs BEAM's `compute_metrics.py` unchanged; it only adds a call log and a spend guard.

## 4. Scoring definitions
For each question, the official evaluator calls gpt-4.1-mini at temperature 0. Every result is in `data/judge/`.
- **Ordinary abilities (all but event ordering).** One call per rubric item. The judge returns a score of 1, 0.5 or 0
  with a reason, and these are stored as `llm_judge_responses`.
- **Event ordering.** The answer is split into lines, and each line is matched by an LLM equivalence check against the
  reference events. The order of the matched events is compared with the reference order, which gives Kendall's tau,
  normalised to [0, 1] as `tau_norm`. A rubric-style score, `llm_judge_score` ("does the answer mention each reference
  item?"), is computed too.

| Basis | Ordinary question | Event-ordering question | Total |
|---|---|---|---|
| **Official (headline)** | mean over items of `int(score)`: half credit counts 0 at the pinned commit | `tau_norm` | mean over the 700 questions × 100 |
| Official + half-credit fix | mean of `float(score)`, as in BEAM's later commit `b2da22e` | `tau_norm` | same |
| Rubric average, BEAM's judge | mean of `float(score)` | `llm_judge_score` | same |
| Vectorize/AMB scorer | AMB `score_result`: Mem0's per-item prompt scored by gemini-3.5-flash-lite, 0/0.5/1 per item, mean per question | the same, with items framed as "should mention" | same |

- **Totals.** Every ability has 70 questions, so the question mean equals the mean of the ten ability scores.
- **Per-conversation scores** (20 questions each) are in `data/scores/conversations.csv`.
- **Two choices in the official arithmetic matter a lot, and we report under both.**
  - Event ordering is scored by line order against hidden reference labels. We score 28.7 on that and 77.0 on its own
    rubric.
  - Half credit counts as zero.

## 5. Models and versions
| Role | Model | Provider | Where pinned |
|---|---|---|---|
| Every generation stage (2a, 5, 6, 9, 10a, 11) | deepseek-ai/deepseek-v4.1-flash | Hive (thehive.ai) | translator default; ledgers record the model and effort used for every call |
| Embeddings | voyage-context-4 (1024 dims) | Voyage AI | `FROZEN.json` → models |
| Notebook, relevance filter, timeline checks | jev-1.13.0 | TypeSafe | `FROZEN.json` → models; responses record the model |
| Official judge | gpt-4.1-mini, temperature 0 | OpenAI | BEAM's `src/llm.py` at `3e12035`; verified by the wrapper |
| Comparison scorer only | gemini-3.5-flash-lite (rubric), gemini-3.5-flash (pass/fail) | Google | `data/comparison/scripts-as-run/` |

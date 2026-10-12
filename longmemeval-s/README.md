# LongMemEval-S: 91.40% (457/500), judged with LongMemEval's own evaluator. Proof package

**The claim.** An earlier version of our long-term memory system, Architecture 0008 (July 2026), answered all 500 questions
of LongMemEval-S in one fresh run on 31 Jul 2026.
- **Judging.** gpt-4o-2024-08-06 at temperature 0, with LongMemEval's own prompts.
- **Result.** 457 answers are correct: **91.40%**. Task-averaged accuracy is 92.74%.

LongMemEval (Wu et al., ICLR 2025; [arXiv:2410.10813](https://arxiv.org/abs/2410.10813)) gives each question a chat history of
about 115,000 tokens (about 50 sessions). The questions test six abilities, and 30 of them should be declined.

## The numbers

| | Correct | Accuracy |
|---|---:|---:|
| **All 500 questions** | **457/500** | **91.40%** |
| Questions never named in development (227) | 206/227 | 90.75% |
| Questions named in development subsets (273) | 251/273 | 91.94% |

| Question type | Correct |
|---|---:|
| Single-session, user facts | 68/70 (97.14%) |
| Single-session, assistant facts | 56/56 (100.00%) |
| Single-session, preferences | 27/30 (90.00%) |
| Knowledge update | 74/78 (94.87%) |
| Temporal reasoning | 116/133 (87.22%) |
| Multi-session reasoning | 116/133 (87.22%) |

The 30 abstention questions are spread across these types; 26 of them were declined correctly.

## Check it yourself in one minute
```
python3 verify/verify.py            # 9 checks, offline: integrity, provenance, every number recomputed
python3 verify/verify.py --online   # 13 checks: also the dataset and evaluator against their official sources, all 500 judge
                                    # prompts rebuilt from LongMemEval's own code, and the Wayback Machine's copy of GitHub's log
```
Expected output: `9/9 checks passed`, and `13/13` with `--online`. It needs only Python 3.

## Why it holds up
1. **Official data.** The run recorded the sha256 of LongMemEval's dataset files, and they equal Hugging Face's own content
   hashes for those files (check 10).
2. **Official evaluator.**
   - The judge prompts come from LongMemEval's `evaluate_qa.py`, pinned by sha256 (`ecce9c4c…`, the file at commit
     `d6dc8b5`) (check 11).
   - All 500 prompts the judge received are rebuilt exactly from that code, the official questions and the published
     answers (check 12).
3. **The judge as configured.**
   - Every record shows gpt-4o-2024-08-06 at temperature 0.
   - Every label follows the judge's reply ("yes" means correct), and every prompt contains the published answer (check 5).
4. **Untouched records.** The answers, judgments, report and all 500 judge records are byte-identical to the checksum file
   the run wrote when it finished, at 01:30 UTC on 31 Jul (check 3).
5. **On GitHub within minutes.**
   - The judge finished at 2026-07-31T01:25:02Z. The commit that records 457/500 reached GitHub at 2026-07-31T01:35:40Z, according to GitHub's
     own server log.
   - The Wayback Machine keeps a copy of that log (checks 9 and 13).
6. **The score recomputes** from the judgments, overall, by type and by development exposure (checks 6 and 7).

## Cost, speed and latency
A memory system has two kinds of latency.
- **Pre-processing** builds the memory before any question arrives. In live use, each session is noted when it ends.
- **Query time** is what a question costs once its memory exists: retrieval builds the context, then the answer is written.

| | Median | 90th percentile |
|---|---:|---:|
| **Pre-processing, before any question** | | |
| Per new session: its note | 3.2 s | 5.4 s |
| A whole history from cold: about 48 sessions, notes in parallel | 8.0 s | 13.7 s |
| **Query time, per question, memory already built** | | |
| Retrieval: facet planning, admission, per-session extraction | 17.2 s | 26.0 s |
| Answer | 4.5 s | 8.3 s |
| **Query total** | **22.0 s** | **33.8 s** |
| **Cold start: a new history, then its first question** | 31.4 s | 43.6 s |

| | |
|---|---|
| Whole benchmark, end to end: notes for 19,195 sessions, retrieval, answers, judging | **30.1 minutes**, with 256 requests in flight; the notes alone took 18.4 min |
| Cost at list prices, from logged tokens | **$23.62** in all; **$0.047 per question** |
| Context given to the answerer | about 4,182 tokens per question, from a history of about 115,000 |

- **Model time.** These are provider-measured times on each call:
  - a history is ready when its slowest note is done;
  - a question's retrieval is the two planning and admission calls, one after another, plus the slowest of its parallel
    extraction calls.
- **Sources.** Every session's note time is in `data/note-latency-per-session.csv`, and every question's times are in
  `data/latency-per-question.csv`. Check 8 recomputes every figure here.

## How the system worked (Architecture 0008)
1. **Notes.** gpt-5.4-nano writes notes for every session, from the user's turns.
2. **Retrieval.**
   - gpt-5.6-luna, at low reasoning, plans keyword searches over four views of the history: notes, user turns, assistant
     turns, and all turns.
   - It then admits up to 12 sessions from a pool of up to 24. Session ids are replaced with opaque handles, so no id can
     hint at the answer.
3. **Extraction.** gpt-5.4-nano, at low reasoning, pulls the claims relevant to the question from each admitted session,
   in parallel.
4. **Answer.** gpt-5.6-luna, at high reasoning, answers from a balanced package of those claims and the raw turns around them.

**Retrieval quality.**
- For 471 of the 500 questions, retrieval admitted every session that holds the answer.
- 35 of the 43 wrong answers had every one of those sessions.

**This is not the configuration behind the BEAM result.** That one is R9 (October 2026, DeepSeek V4.1 Flash, see
`../beam-1m/`). The BEAM system grew from this one.

## Published results on LongMemEval
These are self-reported results, collected on 13 Oct 2026. Answer models differ, so the comparison is approximate.

| System | Answer model | Score | Source |
|---|---|---:|---|
| Mastra Observational Memory | gpt-5-mini | 94.87% | [Mastra](https://mastra.ai/blog/observational-memory) |
| Mem0 (managed platform) | not stated | 94.4 | [Mem0 docs](https://docs.mem0.ai/core-concepts/memory-evaluation) |
| Mastra Observational Memory | gemini-3-pro-preview | 93.27% | Mastra |
| **Ours, Architecture 0008** | **gpt-5.6-luna** | **91.40%** | **this package** |
| Hindsight | gemini-3-pro-preview | 91.40% | listed by Mastra |
| Hindsight | GPT-OSS 120B | 89.00% | listed by Mastra |
| EmergenceMem (internal configuration) | gpt-4o | 86.00% | listed by Mastra |
| Supermemory | gemini-3-pro-preview | 85.20% | listed by Mastra |
| Mastra Observational Memory | gpt-4o | 84.23% | Mastra |
| Oracle: only the sessions that hold the answer | gpt-4o | 82.40% | listed by Mastra |
| Supermemory | gpt-4o | 81.60% | listed by Mastra |
| Zep | gpt-4o | 71.20% | [Zep paper](https://arxiv.org/abs/2501.13956), Table 2 |
| Full history in context | gpt-4o | 60.20% | Zep paper, Table 2 |

Zep's paper uses the same judge setup as ours: GPT-4o with LongMemEval's own prompts.

## Limits
- **No held-out set.**
  - All 500 questions were used by retrieval recall sweeps on 25–26 Jul, and 273 were named in answer-level development
    runs (`data/exposure.json`).
  - The 227 never named score 90.75%, against 91.94% for the rest.
- **An earlier attempt.** It started 22 minutes before the final run, ran retrieval for all 500 questions and stopped
  before answering. Nothing from it was judged or reused.
- **One run.** Judging with gpt-4o has some run-to-run variation.
- **Cost basis.**
  - The $23.62 is computed at the run's configured list prices from logged tokens.
  - An earlier project note gives about $15 as the end-to-end bill. The logs cannot reproduce that figure, so this package
    uses the one they do.
- **The code is withheld.** The run's own checksum file commits to every withheld record ([withheld/](withheld/README.md)).

## What is in the package
| Path | Contents |
|---|---|
| `claims.json` | every claimed number |
| `data/run/` | the run's answers in the official format, judgments, report, manifest and audit, plus the manifests of the final run and the earlier attempt |
| `data/judge-artifacts/` | the judge's record for each question: prompt, reply, label, model, temperature, latency |
| `data/questions.json` | the question type of each question |
| `data/dataset-and-evaluator.json` | the dataset's and the evaluator's sources and hashes |
| `data/exposure.json` | which questions development used |
| `data/performance.json`, `data/latency-per-question.csv` | cost, time, tokens and latency |
| `data/timeline.json`, `data/certification-2026-07-31.md` | when the result reached GitHub, and the record committed then |
| `verify/` | the verifier |
| `withheld/` | what is withheld, and the run's own checksum file |
| `tools/` | the script that built this package |
| `MANIFEST.sha256` | sha256 of every file above |

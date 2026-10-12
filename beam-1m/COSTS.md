# Cost, speed and latency

Costs are computed from the logged calls. Hive's figures are at DeepSeek's list price ($0.30 per million input tokens,
$1.20 per million output tokens). Hive billed about 0.53× list in practice. Sources: `runs/*/hive-ledger-summary.json`,
`runs/*/judge-call-log-summary.json` and `runs/*/typesafe-usage-summary.json`.

## Summary: all 700 questions
| Provider | What | Calls | At list price | Billed (approx.) |
|---|---|---:|---:|---:|
| Hive (DeepSeek V4.1 Flash) | every generation stage | 35,901 | $168.39 | about $89 |
| TypeSafe (jev-1.13.0) | notebook, relevance filter, timeline and statement checks | 13,261 | $10.18 | $10.18 |
| OpenAI (gpt-4.1-mini) | official judge | 9,882 | $2.49 | $2.49 |
| Voyage (voyage-context-4) | embeddings | — | not itemised | — |
| **Total** | | | **about $181** | **about $102** |

That is about **$0.15 per question** as billed, for a history of about one million tokens.

The Vectorize re-scoring with Gemini was a comparison only, not part of the system. It cost about a dollar and is not
itemised.

## Hive, by stage and run (list price)
| Stage (reasoning) | Canary A part 1 | Canary A part 2 | Canary B | Remaining 340 | **Total** | Calls |
|---|---:|---:|---:|---:|---:|---:|
| Session notes (none) | $1.73 | — (reused from part 1) | $4.31 | $5.75 | **$11.79** | 29,488 |
| Router, search, targeted plans (low) | $0.96 | $4.03 | $12.90 | $16.43 | **$34.32** | 4,020 |
| Packager's discarded answer (none) | $0.76 | $5.03 | $17.49 | $19.22 | **$42.50** | 990 |
| Planner + answerer (max) | $1.76 | $8.90 | $30.34 | $38.77 | **$79.77** | 1,403 |
| **Run total** | **$5.22** | **$17.96** | **$65.04** | **$80.17** | **$168.39** | 35,901 |

- **A quarter of the Hive spend went on output nothing uses.** The packager's discarded answer is part of the frozen
  pipeline and was kept for that reason. Removing it is the obvious saving for a future version.
- **The planner and answerer used about 120 million input tokens and 37 million output tokens** across 1,403 calls. That
  is the cost of max reasoning over packs of up to about 130K tokens.

## TypeSafe, by stage (list price, $0.042 per million input tokens)
| Stage | Calls | Input tokens | Cost |
|---|---:|---:|---:|
| Notebook (3) | 2,161 | 25.1 M | $1.05 |
| Relevance filter (8) | 6,898 | 175.3 M | $7.36 |
| Timeline (9) | 3,741 | 41.0 M | $1.72 |
| Targeted checks (9) | 461 | 1.0 M | $0.04 |
| **Total** | **13,261** | **242.4 M** | **$10.18** |

- By run: Canary A part 1 $0.39, part 2 $1.23, Canary B $3.73, remaining 340 $4.84. Rounding makes the parts sum to
  $10.19.
- The relevance filter's own accounting (`runs/*/pipeline-run/jev/accounting.json`) gives the same $7.36.
- 35 attempts with no usage recorded (refused or failed) are excluded.

## Latency: pre-processing and query time
A memory system has two kinds of latency.
- **Pre-processing** builds the memory before any question arrives. In live use, each session is noted when it ends.
- **Query time** is what a question costs once its memory exists.
  - Retrieval builds the context from the memory: the router, search, the relevance filter and packaging.
  - The answer is then written from it.

All figures are model time: provider-measured time on each call, matched to its question through the response id the
pipeline logs (`data/performance/`, built by `tools/performance.py`). In these batch runs every question queued behind one
rate gate, so wall time per question was longer. That queueing is a property of the run, not of the system.

| | Median | 90th percentile |
|---|---:|---:|
| **Pre-processing, before any question** | | |
| Per new session: its note | 1.4 s | 2.7 s |
| Per new session: notebook labelling | 0.4 s | 0.4 s |
| A whole history from cold: about 840 sessions, at our 4.8-requests-per-second limit | 3.8 min (measured) | — |
| **Query time, per question, memory already built** | | |
| Retrieval: router, search, relevance filter, packaging | 147.6 s (2.5 min) | 234.1 s (3.9 min) |
| Answer: planner and answerer | 248.2 s (4.1 min) | 442.7 s (7.4 min) |
| **Query total** | **398.7 s (6.6 min)** | **629.6 s (10.5 min)** |
| **Cold start: a new history, then its first question** | about 10.4 min | — |

- **Coverage.** 698 of the 700 questions have every step recorded.
- **Where the history time comes from.** It is measured: notes, index and notebook for five histories took 1,142 s at one
  4.8-requests-per-second gate. With that limit raised, the notes run in parallel and a history takes about as long as its
  slowest few calls.
- **What the settings favour.** Accuracy: the planner and answerer run at maximum reasoning, and the planner alone is more
  than half the query time.
- **Untested.** Lower reasoning on search would cut time; we did not measure what it would cost in accuracy.
- **Dropping the discarded answer** would save 9 s per question and a quarter of the DeepSeek spend.

**Query time, step by step:**

| Step | Median | 90th percentile |
|---|---:|---:|
| Router | 1.7 s | 3.2 s |
| Search: five calls, one after another | 115.3 s | 202.7 s |
| Relevance filter: the slowest of its parallel batches | 20.2 s | 34.8 s |
| Packager's discarded answer (its median, for every question) | 9.1 s | — |
| Planner, maximum reasoning | 214.3 s | 369.6 s |
| Answerer, maximum reasoning | 20.7 s | 90.4 s |

**Why a query takes minutes.** Almost all of it is generation. On its critical path a question generates about 75,000
output tokens, mostly hidden reasoning, and each call waits for the one before it. Hive generated about 200 tokens a
second on these calls.

| Step | Output tokens, median | Hidden reasoning, share of output | Generation speed, median |
|---|---:|---:|---:|
| Planner, maximum reasoning (per call) | 44,396 | 92% | 208 tokens/s |
| Search, all calls of one question | 26,067 | 74% | 201 tokens/s |
| Answerer, maximum reasoning (per call) | 3,457 | 84% | 162 tokens/s |
| Packager's discarded answer (per call) | 1,663 | — | 151 tokens/s |

- **Search is a loop.** A blueprint, a targeted query, a check of what it found, a follow-up query and a final check. Each
  call depends on the one before. The two checks reason about 15,000 tokens each, even at low effort, and take about 67 s
  each.
- **The speed is the provider's.** On 3 Oct the same model on Baseten generated about 500 tokens a second.
- **Sources.** Tokens, reasoning share and speed come from the ledgers in `bulk/` (`usage.completion_tokens`,
  `reasoning_chars`, `content_chars`, `latency_ms`); the search loop's steps come from the retrieval traces, which are
  withheld.

**Per call:**

| Calls | Median | 90th percentile |
|---|---:|---:|
| Session note (29,488 calls) | 1.4 s | 2.7 s |
| TypeSafe relevance batch (6,863) | 6.5 s | 20.0 s |
| TypeSafe notebook and timeline checks | 0.4 s | 0.4 s |
| Official judge, gpt-4.1-mini (9,882) | 0.7 s | 1.4 s |

## Speed
| Run | Questions | Histories | Wall clock (IST) |
|---|---:|---:|---|
| Canary A part 1, fully fresh | 20 | 5 | 11 Oct 01:14 → 01:51 (37 min) |
| Canary A part 2, notes reused | 80 | 5 | 11 Oct 02:02 → 02:40 (38 min) |
| Canary B | 260 | 13 | 11 Oct 17:51 → 21:02 (3 h 11 min, with three stops for amendments) |
| Remaining 340 | 340 | 17 | 12 Oct 01:23 → 04:19 (2 h 56 min, with a 6-minute stop) |

- **What limits throughput.** One gate of 4.8 requests per second to the model provider, with 64 calls in flight for
  Canary A and 100 for the sealed runs. These settings affect speed only.
- **Notes for one history.** Writing the notes for a history of about 840 sessions takes about 4 minutes at that rate.

## Tokens and context size
| Stage | Calls | Prompt tokens | Output tokens |
|---|---:|---:|---:|
| Session notes | 29,488 | 22.9 M | 4.1 M |
| Router, search, targeted plans | 4,020 | 27.5 M | 21.7 M |
| Packager's discarded answer | 990 | 133.5 M | 2.0 M |
| Planner | 703 | 59.5 M | 31.7 M |
| Answerer | 700 | 60.2 M | 4.8 M |

**The memory pack** the planner reads has a median of 80,798 tokens (90th percentile 162,036). That is about a thirteenth of
a history of about a million tokens.

# Claims

Each claim lists its exact definition, the files that hold the evidence, and the checks that test it.
- "Check n" refers to `python3 verify/verify.py` (checks 1–14, offline) or `--deep` (checks 15–19).
- "L2b", "L3" and so on are the levels in [VERIFY.md](VERIFY.md).
- Every number below is also in [claims.json](claims.json). Check 9 recomputes each one from the raw judge outputs.

---

## C1. All 700 BEAM-1M questions were answered, once each
- **Definition.** BEAM's 1M tier has 35 conversations. Each has 2 questions in each of 10 abilities, so 700 questions in
  all. There is one non-empty answer for every question.
- **Evidence.** `data/answers/answers.jsonl`, which gives the answer, its sha256, its partition and the run part that
  produced it.
- **Checks.** 2 (exactly the 700 question IDs, each once) and 4 (hashes match, no empty answer).

## C2. The questions and conversations are BEAM's official files
- **Definition.** All 35 conversations and their question files came from BEAM's repository at commit `3e12035`. Each
  file matches:
  - the git blob hash in BEAM's own tree at that commit, which anyone can read from GitHub's API;
  - the sha256 recorded in our split files when the split was made on 1 Aug.
- **Evidence.** `data/questions/official-source-manifest.json`.
- **Checks.** 6. L2b checks the blob hashes against GitHub, or against a fresh clone of BEAM.

## C3. Every answer was scored by BEAM's official evaluator, unmodified
- **Definition.**
  - The evaluator is BEAM's `compute_metrics.py` and `report_results.py` at commit `3e12035`, with judge gpt-4.1-mini at
    temperature 0.
  - Our wrapper refuses to run unless the checkout is at that exact commit, the six evaluator files are unmodified, and the
    model and temperature settings are present (`verify/judge-wrapper/.../runBeamEvidenceContractEvaluation.py`, `validate_official_repo`).
  - The wrapper adds call logging and a spend guard. It passes BEAM's prompts, model, temperature and scoring through
    unchanged.
- **Evidence.**
  - `data/judge/*.judge.json`. Each file records `official_source_commit`, the sha256 of each evaluator file, the judge
    model and the temperature.
  - The full judge call logs are in `bulk/*/judge-call-log.jsonl.gz`.
- **Checks.**
  - 7: all four judge files used the same commit and identical evaluator file hashes.
  - 15: 9,882 judge calls, every one answered, none failed.
  - L3: re-judge everything yourself.

## C4. Headline: 76.83 on the official evaluator, all 700 questions
- **Definition.** This is the pinned evaluator's own arithmetic. Each question gets a score, and 76.83 is the mean over the
  700 questions × 100.
  - **Event ordering:** `tau_norm`, an order score computed over the answer's lines.
  - **Every other ability:** the mean, over the question's rubric items, of `int(item score)`. The judge gives each item
    1, 0.5 or 0, and at this commit `int()` turns 0.5 into 0.
- **Evidence.** `data/judge/*.judge.json`, which holds the per-item judge verdicts and reasons. Also
  `data/scores/scores.csv`.
- **Checks.**
  - 8: each of the 700 stored scores equals the score recomputed from its raw items.
  - 9: the aggregate.
  - 10: the per-ability scores.
  - 11: the CSV.

## C5. On the 340 questions that were sealed until their run: 76.00
- **Definition.** Canary B (260 questions, 13 conversations) plus the expansion block (80 questions; conversations 7, 16,
  21 and 34). Official scoring as in C4.
  - Canary B alone: 75.97.
  - Expansion alone: 76.09.
- **Evidence.** `data/questions/partition.json`, `data/questions/sealing-audit.json` and `data/scores/scores.csv`.
- **Checks.** 3, 9 and 14. Claim C6 covers the sealing itself.

## C6. The split was fixed in advance, and no sealed history was used before its run
- **Definition.**
  - On 1 Aug 2026 the 35 histories were split with a fixed seed, using metadata only (no question text, answers or
    rubrics):
    - Canary A: 5 histories, development;
    - Canary B: 13 histories, sealed;
    - a reserve of 17 histories: 13 "final-blind" and 4 precommitted expansion.
  - On 24 Sep the 13 final-blind histories were reallocated to development. The Fresh75 set was drawn from them. Canary B
    and the 4 expansion histories stayed sealed.
- **Evidence.**
  - `data/questions/partition-files/`: all seven files that defined or changed the split, including the 24 Sep
    allocation record.
  - `data/questions/partition.json`: the split history, and each file's first commit.
  - `data/questions/github-push-log.json`: GitHub's own server-side log.
  - `data/questions/sealing-audit.json`.
- **What the evidence shows.**
  - **The split was on GitHub by 29 Aug 2026.** That is the first logged push containing the 1 Aug commit, recorded by
    GitHub's servers, six weeks before the sealed runs. The commit's own date, 1 Aug, is self-reported.
  - **The sealing audit found nothing.**
    - It ran a full-text search of every project record (82,322 files that reference a BEAM history, compressed files
      included) for any reference to a sealed history.
    - Outside the sealed runs' own folders, only 5 files mention a sealed history:
      - the two split files;
      - the 8 Aug holdout list, which was never run;
      - an ID list for a gated run that never happened;
      - a unit-test fixture with an invented ID.
- **Checks.** 3, 14, and 20 (`--online`: the Wayback Machine's copies of GitHub's records).
- **Limitation.** The audit can show absence in the records, not that no person ever opened a file
  ([LIMITATIONS.md](LIMITATIONS.md) §2).

## C7. One configuration, frozen and published before the sealed runs, changed only on failure paths
- **Definition.** All 700 answers come from the R9 configuration (see [METHOD.md](METHOD.md)).
  - It was frozen as git tag `r9-freeze-20261011` (commit `595a2e28`).
  - GitHub's server log records that commit's push at **2026-10-11 10:06:21 UTC**. Canary B started at **12:21:10 UTC**.
    The development repository is now private; the Wayback Machine keeps a copy of that log.
  - During the sealed runs, four amendments were made. Each touched only a path taken after a call had already failed, and
    each is recorded with its before and after file hashes ([AMENDMENTS.md](AMENDMENTS.md)).
- **Evidence.**
  - `code/`: the hash commitments: `FROZEN.json` at the freeze and as run last, and the hash chain
    (`code-provenance.json`). The source itself is withheld ([withheld/](withheld/README.md)).
  - `data/questions/independent-archives.json`: the Wayback Machine's copies of the freeze records.
  - `runs/*/pipeline-run/manifest.json`: the code hash recorded at every start and resume.
- **Checks.**
  - 12: the 123 locked files are committed by sha256, and the published judge wrapper matches its hashes.
  - 13: public freeze → each recorded amendment → final code, with every run start and resume (25 in total) on that chain,
    in time order.
  - 14: the timeline.
  - 17: the translator's fallback never fired.
  - 20 (`--online`): the third-party archive copies of the push log, the tag and the freeze-time `FROZEN.json`.

## C8. One answer per question: no reruns, no selection
- **Definition.** Each question's answer is the only one produced.
  - The rules, written in each run's README before the run, allow only `--resume` after a failed call. A resume redoes
    unfinished calls only.
  - For Canary A, we count R9's first answer run (77.71), not its second (79.32). The remaining-340 README states this
    before that run.
- **Evidence.** The model-call ledgers in `bulk/*/hive-ledger.redacted.jsonl.gz`, and `runs/*/README.md`.
- **Checks.**
  - 18: the ledgers contain exactly 700 answer generations and 700 first plans. The only extra calls are 3 planner re-asks
    after a plan failed its JSON schema check.
  - 5: the judged answers are those answers.

## C9. The text that was scored is the text published here
- **Evidence.** `data/answers/predictions-as-judged/` holds the exact files the judge read.
- **Checks.**
  - 5: answers are byte-identical to those files.
  - 16: for all 630 non-ordering questions, the published answer appears in the official judge's own logged prompts.

## C10. Every model call is on record
- **Definition.**
  - 35,901 DeepSeek responses with tokens and cost, and 0 empty replies.
  - 9,882 judge calls, 0 failed.
  - A memory pack and an answer plan for each of the 700 questions (withheld; committed by sha256).
- **Evidence.** `bulk/` (judge call logs, and model-call ledgers with the prompt text removed), the per-run summaries in
  `runs/*/`, and `withheld/memory-pack-and-plan-hashes.json`.
- **Checks.** 15, 17 and 19.

## C11. The same answers on three other scoring bases
| Basis | All 700 | Unseen 340 | Definition |
|---|---:|---:|---|
| Official with BEAM's half-credit fix | 77.39 | 76.70 | The same judge verdicts, with `float()` in place of `int()`, as BEAM's upstream commit `b2da22e` (31 Aug 2026) does. That commit also removes an unused prompt line; the judge was not re-run for that. |
| Rubric average, BEAM's judge | 82.23 | 81.74 | The rubric item mean for every ability. Event ordering uses its rubric judge score (`llm_judge_score`) instead of `tau_norm`. This is the convention Mem0 publishes. |
| Vectorize/Hindsight (AMB) scorer | 78.18 | 78.00 | Vectorize's Agent Memory Benchmark scorer (`score_result`, commit `20751fa0`), run unchanged with judge gemini-3.5-flash-lite. This is the method behind Hindsight's 73.9 and HydraDB's 82. |

- **Evidence.** `data/scores/scores.csv`, `data/comparison/` and `claims.json`.
- **Checks.** 9. L4 re-runs the Vectorize scorer.

## C12. Comparison statements
We claim only the following ([COMPARISON.md](COMPARISON.md)).
- **No vendor publishes the official metric.** The only official-method results we know of are the BEAM paper's (best:
  33.6 at 1M).
- **On Vectorize's scorer we score 78.18,** against Hindsight's published 73.9 and HydraDB's self-reported 82.
  - Hindsight's run used judge gemini-2.5-flash-lite, which is no longer available, so ours used gemini-3.5-flash-lite.
  - Their answers come from AMB's fixed answer prompt with Gemini 3.1 Pro. Ours come from our own system's answerer,
    DeepSeek V4.1 Flash.
- **On Mem0's convention we score 82.23 with BEAM's judge,** against Mem0's self-reported 64.1, which used Mem0's own
  judge configuration.

## C13. Cost
- **Definition.**
  - DeepSeek on Hive: 35,901 responses, **$168.39 at list price**, which is about $89 at the rate Hive billed (about 0.53×
    list).
  - Official judge: $2.49.
  - TypeSafe: $10.18 at list price.
- **Evidence.** `runs/*/hive-ledger-summary.json`, `runs/*/judge-call-log-summary.json` and `runs/*/pipeline-run/jev/accounting.json`.
  Details are in [COSTS.md](COSTS.md).
- **Checks.** 17 (the ledger totals).

---

## What we do not claim
- **That all 700 questions were unseen.** 360 are development data: Canary A (100) and the Fresh75 histories (260). The
  unseen-only score is 76.00 and is always reported next to the headline.
- **That a rerun gives exactly 76.83.** Model sampling and the judge both vary. On 260 questions, one run moves about ±1 point.
- **That our system beats every vendor on an equal footing.** Judges, answer models, prompts and question sets differ,
  and vendor numbers are self-reported.
- **That event ordering is solved.** On the official order metric we score 28.7, while on the rubric metric we score 77.0.
  The official metric is mostly a label-matching artifact ([LIMITATIONS.md](LIMITATIONS.md) §5), but that is our reading
  of it, not BEAM's.
- **That temporal reasoning is good.** At 50.0 it is our weakest real ability.

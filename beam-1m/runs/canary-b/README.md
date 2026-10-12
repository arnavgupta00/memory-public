# Canary B, R9 configuration: the sealed run (11 Oct 2026)

Written before the run started. These rules are fixed in advance.

## What runs
- **Configuration:** R9 exactly, as frozen in `src/agents/current/freezes/R9-20261011` (git tag `r9-freeze-20261011`).
  - The frozen A6 pipeline (FROZEN.json sha256 `518766…53be1`, `run.mjs verify` passes) with the A2 answer layer.
  - Fully fresh: nothing is reused, and Canary B shares no history with any earlier run.
- **Models:** every GPT call goes to DeepSeek V4.1 Flash on Hive through the translator `src/pipeline/a7/hive-proxy.mjs`
  (sha256 `b136610e…a0ac1650`, the same file as R9).

  | Stage | Reasoning effort |
  |---|---|
  | Session notes | none |
  | Router, search, targeted plans | low |
  | Packager's discarded answer | none |
  | Planner + answerer | max |

  Blank replies are retried.
- **Unchanged:** voyage-context-4, TypeSafe jev-1.13.0, and the official BEAM judge (commit 3e12035, gpt-4.1-mini,
  temperature 0) on real OpenAI.
- **Questions:** `eval-slices/beam-1m/beam-1m-canary-b-certification-v1.json`, the 13 base conversations (chat 1, 2, 9, 10, 12,
  14, 17, 22, 24, 26, 27, 30, 35), 260 questions. Never inspected before this run.

## Rules
- **One answer per question.** No reruns, no selection by score.
- **Failed calls:** if a call fails (inference or transport), the pipeline's own `--resume` redoes only the failed calls.
  Finished answers are never redone.
- **Headline:** the official pinned score, the mean over 260 questions with half credit = 0 and event ordering scored by
  tau_norm.
- **Secondary:** the per-item rubric basis, with event ordering by its rubric judge and half credit counted. That is the
  basis Mem0 publishes. Both are reported, labelled.
- **Reliability contract (from the certification file):** the finite-population 95% CI over conversation scores (N = 35).
  If the half-width exceeds 5 points, the precommitted expansion block (chat 16 and 21) is the next step. It needs separate
  approval and is never decided by the point score.

## Budget
Estimates:

| Item | Estimate |
|---|---|
| Hive, at list price | about $63 (about $33 billed at ~0.53×) |
| TypeSafe | about $5 |
| OpenAI judge | about $1 |

Hive spend is capped at $90 at list price.

## Amendment, 19:10 (during the run)
- **What happened:** the run stopped at stage 8 (JEV relevance filter) on the frozen pipeline's spend guard. The guard
  requires 4 × the one-attempt TypeSafe forecast to stay at or under $10. For 260 questions the forecast is $2.62, so
  4 × $2.62 = $10.46.
- **Nothing was lost.** Notes, search and fusion for all 260 questions are saved. The automatic resumes hit the same guard,
  and no TypeSafe filter calls were sent.
- **Change:** `run.mjs` gained `--jev-cap` (default 10, so behaviour is unchanged), which is passed to the guard. This run
  uses `--jev-cap 20`. It is a spend guard only: no prompt, model, request, threshold or result changes.
- **Record:** the change is in `FROZEN.json` → `amendments` (run.mjs sha256 `a2fc26da…` → `6821f881…`). `run.mjs verify`
  still passes (all 75 + 75 saved requests identical).
- **Resume:** the run continued with `--resume`, which redoes nothing that finished.

## Amendment 2, 19:50 (during the run)
- **What happened:** the JEV relevance filter stopped twice on TypeSafe `HTTP 400 max_tokens_exceeded`, for two batches of
  chat-22 sessions.
- **Cause: a glitch in the benchmark data.** One generated assistant reply (chat 22, session ~278) contains a
  21,712-character run of zeros; another in chat 9 contains 11,182 zeros. Canary A and Fresh75 have none.
  - Our local token count, which sizes the batches, treats such a run as a few tokens. TypeSafe counts far more.
  - Batches containing the run went through at about 70K characters (10 calls) and were refused at about 91K (2 calls).
  - The first refusal also halted every other dispatch. 144 of 260 questions were filtered when it stopped.
- **Change (failure path only):**
  - `s07_fusion_jev.mjs`: a batch TypeSafe refuses as too large is split in two, each half is judged, and the answers are
    merged.
  - `recursiveArtifacts.mjs`: that one error no longer halts other dispatches.
  - Requests TypeSafe accepts are byte-identical to before, so all 1,489 completed calls are reused unchanged.
- **Record:** `FROZEN.json` → `amendments`. `run.mjs verify` passes.
- **Resume:** with `--resume`. Only the refused or stopped calls are sent again.

## Amendment 3, 20:35 (during the run)
- **What happened:** stage 10a (package) finished 258 of 260 questions.
  - For chat-01 event ordering 1 and chat-30 summarization 1, the packager's **discarded** v8 answer, which A2 never reads,
    came back from DeepSeek with more than 32 evidence rows after all 5 translator re-asks (up to 104 rows).
  - The packager therefore recorded no package prompt for those 2 questions, and the stage cannot resume over partial output.
- **Change (translator, discarded answer only):** if that discarded answer still breaks a length limit after every re-ask,
  over-long lists and strings are cut to the limit so the packager can record the package. The package prompt, which is
  what A2 uses, does not depend on that answer. Every other call is unchanged.
- **Resume:**
  - The partial packager output was moved to `package/downstream-attempt1-partial`, kept for the record.
  - The stage re-ran: the 258 finished packager calls replay from its cache (identical requests, no new calls), and only the
    2 failed ones are sent again.
- **Outcome:** on the rerun, both re-sent answers met the limits within the re-asks. The trim was **not used** (0 trims in the ledger). The package stage completed 260/260.

## Result (21:02)
**Canary B, official pinned score: 75.97** (260 questions, 13 conversations).
- **Secondary, labelled:** 81.2 on the per-item rubric basis, with event ordering scored by its rubric judge and half
  credit counted. That is the basis Mem0 publishes.
- **Reliability contract:** the finite-population 95% CI half-width over conversation scores is **2.3 points**, below the
  5-point target, so the expansion block is not needed.
- **Per conversation:** 69.2 (chat 30) to 86.8 (chat 26).

| Ability | Official | Rubric basis |
|---|---:|---:|
| Abstention | 80.8 | 80.8 |
| Contradiction resolution | 78.8 | 78.8 |
| Event ordering | 31.1 | 78.2 |
| Information extraction | 92.3 | 92.3 |
| Instruction following | 96.2 | 97.1 |
| Knowledge update | 84.6 | 84.6 |
| Multi-session reasoning | 69.6 | 70.4 |
| Preference following | 92.6 | 93.3 |
| Summarization | 81.8 | 83.6 |
| Temporal reasoning | 51.9 | 52.9 |
| **Overall** | **76.0** | **81.2** |

**Run health:**
- 260/260 answered, 0 blank answers, 0 empty model replies.
- 13,283 Hive calls. 25 transient Hive errors and 1 transport error were all retried.
- Three amendments, all on failure paths, are described above. The trim fallback in amendment 3 was never used.

**Spend:**

| Item | Cost |
|---|---|
| Hive | $65.04 at list price (about $34 billed) |
| TypeSafe | about $5 |
| OpenAI judge | about $1 |

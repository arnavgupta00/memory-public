# Limitations

What this result does not show, and where a careful reader should discount it.

## 1. 360 of the 700 questions are development data
- **Canary A (100 questions).** These were studied question by question while the system was built, and the
  configuration was chosen with them.
- **The 13 Fresh75 histories (260 questions).** 75 of their questions were studied. The other 185 were not inspected one
  by one, but they share histories with the 75, so they are not independent either.
- **Effect.** The headline, 76.83, includes all of these. The sealed 340 score **76.00**, which is 1.6 points below the
  development 360 (77.61). That gap is about the size of one run's sampling variation, so the data shows no sign of heavy
  overfitting, but it cannot rule out a small amount. **Quote 76.00 wherever "unseen" matters.**

## 2. Sealing: what the audit can and cannot show
- **The original plan had more blind data.** The 1 Aug plan kept 17 histories blind: 13 for a final confirmation and 4 as
  a precommitted expansion block.
  - On 24 Sep the 13 final-blind histories were reallocated to development, and the Fresh75 set was drawn from them.
  - This is recorded in `data/questions/partition-files/beam-1m-holdout-allocation-20260924.json`, and the split history
    is in `partition.json`.
  - The full 700 therefore has 340 independent questions, not the 600 the original plan would have kept.
- **The audit shows absence in the records.** It searched every project record (82,322 files that reference a BEAM
  history, compressed files included) and found no use of a sealed history before its run (`sealing-audit.json`). It
  cannot prove that no person ever opened a sealed file by hand.
  - The split files themselves, which contain only question IDs, have been on GitHub since 29 Aug.
  - The policy written into them is: do not inspect sealed questions, references, rubrics or failures before the freeze.
- **An August holdout list includes 10 expansion questions.** The list (`beam-1m-compression-holdout40-v1.json`, 8 Aug)
  was never run; later experiments read it only to exclude its IDs.
- **Two sealed-run question lists exist that never produced runs:**
  - one written for R7's gated Canary B run on 9 Oct; R7 failed its gate, so that run never happened;
  - the actual sealed runs' own lists, written seconds before each run.

## 3. One run, and runs vary
- Each question was answered once. Models sampling at maximum reasoning do not repeat themselves. Two answer runs of R9 on
  the same Canary A memory packs scored 77.71 and 79.32, with 31 of 100 questions changing.
- A rerun of all 700 would give a different number, probably within about ±1 point.

## 4. The judge is inconsistent, and some answer keys are wrong
- **Judge inconsistency.** BEAM's judge (gpt-4.1-mini) sometimes scores near-identical answers differently. Examples are
  in the run ledger (R9 against R8) and the Canary B post-mortem. On a neutral judge, R8's 4.7-point lead over R9 on
  Canary A shrank to 0.6.
- **Answer keys the conversation contradicts.**
  - Examples: a stale percentage when a later message updates it; dates that disagree with the session anchors; a
    statement the key says is absent, but which the user wrote.
  - On the development sets, about a third of all lost points traced to such keys (internal loss analysis).
  - On Canary B, the post-mortem puts key defects and judge errors at 15.6 of the 62.5 lost question-points.
- **Scores were not corrected.** The scores here are as judged; we corrected nothing in our favour. The flip side is that
  the scores carry this noise.

## 5. Event ordering: the official metric mostly measures label matching
- **How the metric works.** The official score splits an answer into lines and asks an LLM matcher whether each line is
  "the same" as one of the reference's hidden short labels. It then scores the order of the matched lines.
- **Our offline replay of the official scorer** (our offline replay of the official scorer) found that this has little to do with ordering:
  - **A ceiling for natural wording.** A list built from the reference's own threads, in our wording and in perfect
    order, scores only about 35.
  - **Short titles score lower** (22.5), because the matcher mostly checks shared words.
  - **A one-line answer can score 0.72** if its single line matches the first reference item.
- **Our numbers.** We score 28.7 on the official basis. On the rubric score, which BEAM's evaluator also computes ("does
  the answer mention each reference item?"), we score 77.0.
- **We did not tune toward the reference's labels or line format,** because that would game the benchmark rather than
  improve memory. This reading of the metric is ours; BEAM's authors may see it differently. The headline uses the
  official metric regardless.

## 6. Temporal reasoning is weak
At 50.0 it is the weakest ability on every basis.
- **Part of it is keys.** On the development sets, 86.7% of lost temporal points traced to keys the conversations
  contradict (internal loss analysis).
- **Part is real.** The answerer sometimes picks the earlier of two dates, or does not state a date range as a range.
- **Competitors are ahead here.** HydraDB reports 91 on Vectorize's basis, against our 54.3.

## 7. Half credit
- **What the pinned evaluator does.** It turns a rubric item's half credit (0.5) into 0 (`int()`). BEAM's authors changed
  this upstream on 31 Aug 2026 (`b2da22e`).
- **Our headline keeps the pinned behaviour** (76.83).
- **77.39 applies the fix to the same judge verdicts.** The same upstream commit also removes an unused prompt line; we did
  not re-judge to include that change.

## 8. Amendments during the sealed runs
- **What changed.** Four small code changes were made mid-run, after a call failed ([AMENDMENTS.md](AMENDMENTS.md)). Each
  changes only what happens after a refusal or failure, and requests that had succeeded were byte-identical before and
  after.
- **What the hash chain proves, and what it does not.** It proves that nothing else changed. It does not prove that a
  rerun from scratch, without the original failures, would reach the same answers. Section 3 applies.
- **One amendment had no effect.** The translator's trim fallback never fired.
- **Logged times are authoritative.** The run README headings give approximate times (19:50, 20:35). The driver logs show
  the relaunches at 19:44 and 20:25 IST.

## 9. Canary B was analysed after its run
- **What happened after Canary B.** We did a question-by-question post-mortem (internal)
  before running the remaining 340.
- **Nothing in the system changed as a result.** The remaining 340 ran on the same code, plus a Voyage batch-size fix
  that applies only after a refusal. Its README, written before the run, says "No change of any kind relative to Canary
  B".
- **Effect on Canary B.** Canary B's questions are no longer unseen for any future system. They stay valid for this
  result, because they were scored before anyone looked.

## 10. The configuration was chosen on development data
- **Earlier runs on Canary A.** Configurations R1–R9 were compared on Canary A. The best single run, R8 at 82.41, was not
  chosen.
  - R9 was frozen because its memory packs were the most complete, it cost about 40% less upstream, and its answer
    quality was statistically tied with R7/R8.
  - The difference in mean was −0.9 points, with a 95% interval of [−5.7, +3.4].
- **The counted Canary A run.** For Canary A, the 700 counts R9's first answer run (77.71), not the better second one
  (79.32).

## 11. The comparisons are approximate
See [COMPARISON.md](COMPARISON.md) §5.
- Judges differ: Hindsight's judge model has been retired.
- Answer models differ: vendors evaluated with Gemini 3.1 Pro; we use DeepSeek V4.1 Flash.
- Answer prompts differ.
- The vendors' numbers are self-reported.

## 12. What rests on our own records
- **Self-recorded.** Run times, resumes and costs come from our run manifests and logs.
- **Independent anchors:**
  - GitHub's server-side push log, which dates the split files and the frozen code, with copies in the Wayback Machine
    (check 20);
  - BEAM's own git tree, for the data;
  - the official evaluator's file hashes.
- **Provider logs are not included.** Hive, OpenAI, TypeSafe and Voyage hold their own account logs, but those are not in
  this package.
- **Model identity.** That Hive served DeepSeek V4.1 Flash rests on the model ID requested and returned (ledgers). We
  cannot see inside the provider.

## 13. Costs are partly estimates
- **Hive.** Costs are computed at DeepSeek's list price from logged tokens. Hive billed about 0.53× list in practice.
- **TypeSafe.** The figure is computed from logged input tokens at its published price.
- **Not itemised.** Voyage and the Gemini comparison scoring ([COSTS.md](COSTS.md)).

## 14. Exact answers cannot be reproduced
- **What can be reproduced exactly:**
  - the requests: the code rebuilds them byte for byte from the same inputs;
  - the scoring of the published answers: Levels L1–L4.
- **What cannot:** the answers themselves. A full rerun gives new answers and a score within run-to-run variation.

## 15. This public copy withholds the code
- **What is withheld.** The source code, prompts, memory packs, answer plans and internal research notes
  ([withheld/](withheld/README.md)). Each is committed by sha256, so it cannot be swapped later without the hashes showing
  it.
- **What the hashes cannot show.** That the withheld code does what [METHOD.md](METHOD.md) describes. An auditor with the
  full copy can check that; a reader of this copy cannot.
- **Reproducing the run.** Re-running the system (VERIFY.md, L5) needs the full copy. Every other level of verification
  works on this copy.

# The journey: July to October 2026

This is how the result was reached, including the dead ends. The detailed internal record (the experiment history, the
run ledger and the analysis notes) stays private with the code.

Dates are India time.

## At a glance
| Period | Phase | What mattered |
|---|---|---|
| 22–31 Jul | LongMemEval architectures 0001–0008 | Architecture 0008, run fresh end to end: **457/500 = 91.40% on LongMemEval-S** (about $15) |
| 31 Jul–1 Aug | Move to BEAM-1M; split the 35 histories | Canary A (development), Canary B (sealed), blind reserve. Committed 1 Aug; on GitHub by 29 Aug |
| Aug | Retrieval and fusion on BEAM | 0008 on Canary A: 62.92% → 64.69%. Whole raw sessions (K81) into the answerer: **74.10% on Canary A**, but the selector was tuned on Canary A |
| 8 Aug–15 Sep | Compression, ingestion-time cards and events, evidence contracts | No durable gain. Generated summaries lost evidence (0/12 complete stories); evidence-contract gates failed twice |
| 19–24 Sep | TypeSafe JEV relevance filtering; Fresh75 set allocated | About 9:1 compression with no reliable accuracy change (Fresh75 60.36 → 63.75, inside noise) |
| 27 Sep–2 Oct | Expert review: noise measured, keys audited, planner architecture | **A6 77.5 and A2 78.0 on Fresh75** (from about 64); pipeline frozen 30 Sep; first fully fresh Canary A: **78.51 (R1)** |
| 2–8 Oct | Answer-model scans; loss attribution | DeepSeek V4.1 Flash as answerer: **80.79 (R3)**. 66% of lost points lie outside the architecture (keys, scorer, model) |
| 8–11 Oct | Whole pipeline on DeepSeek through the Hive translator (R6–R9) | Blank-reply fault found and fixed. R8 82.41 (a judge-favoured draw). R9: the most complete packs at about 40% lower cost |
| 11 Oct | Event-ordering and temporal investigation; scorer study | A8 rejected. The official order score was shown to be mostly label matching. Competitor scoring bases mapped |
| 11 Oct | **Freeze**, then **Canary B** (R10) | Tag pushed 15:36; Canary B run once: **75.97** |
| 12 Oct | **Remaining 340** (R11); proof package | **All 700: 76.83 official; unseen 340: 76.00** |

## 1. LongMemEval first (22–31 July)
- **Starting point.** The project began on LongMemEval, a shorter memory benchmark. Eight architectures in ten days moved
  the canary from 35/60 to 54/60 and tried typed memory updates, graph readers, session-first selection and hybrid
  retrieval.
- **Architecture 0008** combined four-view retrieval with an extractor and a strong final answerer. It scored 457/500
  (91.40%) on the full LongMemEval-S, run fresh from ingestion to judging.
- **Lesson.** A fixed, fresh, end-to-end run is the only result that counts. Several exposed-panel wins did not survive a
  blind rerun.

## 2. BEAM-1M, and a split made on day one (31 July–1 August)
- **Why BEAM.** BEAM's 1M tier is harder: about a million tokens per history, against LongMemEval's roughly 115K.
- **The split, before any BEAM tuning.**
  - A seeded split used metadata only, never question text, answers or rubrics.
  - **Canary A**: 5 histories, for development.
  - **Canary B**: 13 histories, sealed, with a policy of no inspection before the architecture is frozen.
  - **A blind reserve** of 17: 13 for a final confirmation, plus 4 for a variance-triggered expansion.
- **A precommitted reliability contract.** If Canary B's 95% confidence half-width exceeded 5 points, the expansion block
  would be added.

## 3. A long August (1 August–15 September)
- **The first BEAM run.** Architecture 0008 scored 62.92% on Canary A; wider history routing gave 64.69%.
- **The best August result.** Whole raw sessions selected from a sparse + dense union (K81), with a strong answerer:
  74.10% on Canary A. The selector had been tuned on Canary A, and 22 of the 100 predictions were inherited.
- **What did not work:**
  - **Compressing evidence with generated summaries** discarded what mattered: 29/75 atoms and 0/12 complete stories,
    although discovery had found 11/12.
  - **Ingestion-time cards and structured events** produced indexes larger than the raw text, with no demonstrated answer
    gain.
  - **Evidence contracts** (organising or preserving the answer's required content) failed their gates twice; a "preserved"
    arm amplified mistaken requirements.
- **Lesson.** Raw evidence beat generated summaries. Combining individually promising modules did not add up.

## 4. JEV and Fresh75 (19–24 September)
- **TypeSafe's JEV relevance model** scored each candidate session against the question.
  - A first 12-question test kept accuracy (88.39 → 89.09) while cutting final input from about 109K to 44K tokens.
  - On harder questions the accuracy effect was mixed; compression held.
- **Fresh75 (24 Sep).** To stop reusing Canary A, 75 new development questions were drawn from the 13 final-blind reserve
  histories. Those histories became development data. Canary B and the 4 expansion histories stayed sealed.
- **The paired Fresh75 test.**
  - Raw K180 against K180 → JEV: 60.36 against 63.75, with final input 217K against 111K tokens.
  - That is 11 wins, 12 losses and 52 ties: compression, not accuracy.

## 5. The expert review (27 September–2 October)
A full reanalysis took everything back to the primary records.
- **Noise was measured for the first time.** 44 byte-identical answer requests sent twice changed 9 scores, so most
  single-run comparisons sit inside about ±4–7 points.
- **The scorer and the keys were audited:**
  - several answer keys contradicted their own conversations;
  - the event-ordering metric behaved non-monotonically;
  - the pinned evaluator scored half credit as zero (BEAM fixed this upstream on 31 Aug).
- **The answer layer was rebuilt:**
  - **A6**: extractor → planner → answerer, 77.5 on Fresh75;
  - **A2**: a planner reading the full memory, then the answerer, 78.0 on Fresh75 and steadier on fresh contexts.
  - The whole pipeline was hash-locked on 30 Sep.
- **R1 (2 Oct).** The first fully fresh Canary A run of the production configuration (OpenAI models for every generation
  stage) scored 78.51.

## 6. Models and loss attribution (2–8 October)
- **The answer-model scan,** on the same memory packs:
  - DeepSeek V4.1 Flash 80.79 (R3);
  - Gemini 3.8 Flash 78.34;
  - DeepSeek V4 Flash 76.12;
  - Claude Haiku 5.5 stopped at 70.0 on the screen.
- **Loss attribution.** Every lost point on Canary A and Fresh75 was traced to a cause:
  - outside the architecture, 66.2%: answer keys 34.8%, judge and scoring 20.9%, model behaviour 10.5%;
  - planner and answerer, 26.5%;
  - the memory pack, 7.3%.
- **Lesson.** The memory pack was rarely the problem. The planner was the biggest lever we controlled.

## 7. All-DeepSeek through a translator (8–11 October)
- **The translator.** It lets the frozen pipeline run unchanged on DeepSeek V4.1 Flash (Hive). It answers the pipeline's
  OpenAI calls and logs every call.
- **R6** (screen 20, all stages at max) scored 84.8.
- **R7** was precommitted as the final candidate, with a gate: run Canary B only above 80.79.
  - It scored 76.43, so Canary B was not run.
  - Diagnosis: Hive had returned 4 blank answers that passed straight through, costing 3 points. The translator was fixed
    to retry blank replies.
- **R8** reran R7's planner and answerer on R7's packs, with byte-identical requests, and scored **82.41**, the best single
  Canary A run.
  - About 3 points of the gain came from the blank fix; the rest is run-to-run variation.
  - On an independent judge (12 Oct), R8 and R9 were within 0.6 points: much of R8's lead was a judge-favoured draw.
- **R9** cut upstream reasoning: no reasoning for notes, low for router and search, max for the planner and answerer.
  - Its packs were the most complete of any run (309 of 489 needed sessions in full, against 296–298), at about 40%
    lower upstream cost.
  - Two answer runs scored 77.71 and 79.32; the mean, 78.5, is tied with R7/R8's 79.4.

## 8. Event ordering and the scorer (11 October)
- **A8,** a focus timeline plus list-style answers, gave no gain and was rejected.
- **An offline replay of the official scorer** showed what the event-ordering metric rewards:
  - a list of exactly the reference's threads, in natural wording, reaches only about 35;
  - higher scores come from reproducing the reference's hidden labels.
  - We decided not to chase that, because it would game the benchmark rather than improve memory.
- **Vendors publish rubric-based numbers.** Mem0, Hindsight and HydraDB all publish rubric-style numbers, where our event
  ordering is about 80. We decided to report the official metric as the headline, with the others labelled.

## 9. Freeze, Canary B, and the rest (11–12 October)
- **The freeze.** R9 was frozen in its own folder and tag. The push to GitHub is logged by GitHub at 15:36 IST, 11 Oct.
- **Canary B (R10).**
  - It started at 17:51 and ran once.
  - Three failure-path amendments were needed (a spend guard, a TypeSafe batch split, a trim fallback that never fired).
  - **75.97** at 21:02.
  - The 95% half-width was 2.3 points, under the 5-point contract.
- **The post-mortem** split the 62.5 lost question-points:

  | Cause | Question-points |
  |---|---:|
  | Planner | 19.7 |
  | Event-ordering scoring | 17.9 |
  | Key defects and judge errors | 15.6 |
  | Missing pack evidence | 9.0 |
  | Answerer | 0.4 |

  Nothing was changed as a result.
- **Comparison scorers.** Vectorize's AMB scorer (the method behind Hindsight and HydraDB) gave 78.0 on Canary A + B.
  Hindsight's published 73.9 turned out to be a rubric mean, not a pass rate.
- **The remaining 340 (R11),** with "no change of any kind":
  - It started at 01:23 on 12 Oct.
  - One failure-path amendment was needed (a Voyage batch split).
  - It finished at 04:19: **77.23** on the 340.
- **All 700: 76.83 official. Unseen 340: 76.00.**

## The run ledger, R1–R11 (Canary A unless stated)
| Run | Date | What changed | Score |
|---|---|---|---:|
| R1 | 2 Oct | Production: OpenAI models for every generation stage, fully fresh | 78.51 |
| R2 | 3 Oct | Answerer: DeepSeek V4 Flash (R1's packs) | 76.12 |
| R3 | 3 Oct | Answerer: DeepSeek V4.1 Flash (R1's packs) | 80.79 |
| R4 | 8 Oct | Answerer: Gemini 3.8 Flash (R1's packs) | 78.34 |
| R5 | 8 Oct | Answerer: Claude Haiku 5.5 | stopped (screen 70.0) |
| R6 | 9 Oct | Everything DeepSeek V4.1 at max, through the translator (screen 20) | screen 84.8 |
| R7 | 9 Oct | As R6, full Canary A, precommitted with a gate | 76.43 (gate failed) |
| R8 | 11 Oct | R7's planner and answerer rerun on R7's packs, blank-reply fix | 82.41 |
| R9 | 11 Oct | Cheaper upstream reasoning; **the frozen configuration** | 77.71 (run 2: 79.32) |
| R10 | 11 Oct | R9 on **Canary B (sealed, 260)** | 75.97 |
| R11 | 12 Oct | R9 on the **remaining 340** | 77.23 → **all 700: 76.83** |

## What we learned
1. **Fix the evaluation before the system.** Split once, seal early, and publish the freeze before the sealed run.
2. **Measure noise first.** Most gaps under 5 points between single runs were noise. R8's 82.41 is the clearest example.
3. **Read the scorer.** A third of lost points were key defects, and the event-ordering metric rewards label matching.
   Knowing this kept us from "fixing" things that were not broken.
4. **Raw evidence beats generated summaries,** and a planner that reads the whole memory beats an extractor.
5. **Log every call.** The blank-reply fault, the judge's silent zeros in AMB's code, and every amendment were found or
   proved from logs.
6. **Report the number that holds up.** That is the official evaluator, all 700, with the unseen subset beside it. The
   friendlier bases are labelled comparisons, not headlines.

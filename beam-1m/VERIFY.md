# How to verify

There are five levels. Each one checks more, and the later ones need network access, keys or money. Levels 1 and 2 need
only Python 3. A reviewer short on time should run Level 1, read [CLAIMS.md](CLAIMS.md), and spot-check one question by
hand (last section).

| Level | What it establishes | Needs | Time | Cost |
|---|---|---|---|---|
| **L1** | Integrity; provenance; every claimed number recomputed from the raw judge outputs | Python 3 | < 1 min | free |
| **L2** | L1, plus the judge call logs and the model-call ledgers | Python 3, `bulk/` | < 1 min | free |
| **L2b** | Dates against third-party archives of GitHub's records; data against BEAM's repository | network | 5 min | free |
| **L3** | Re-judge all 700 answers yourself with BEAM's official evaluator | network, OpenAI key | 15–20 min | about $2.50 |
| **L4** | Re-score with Vectorize's scorer (the method behind Hindsight and HydraDB) | network, Gemini key | 15 min | about $1 |
| **L5** | Re-run the whole system (auditors only: the code is withheld) | the full copy, 4 provider keys | about 7 hours | about $100 |

---

## L1 and L2: offline (`verify/verify.py`)
Run these from the package folder:
```
python3 verify/verify.py                   # checks 1-14
python3 verify/verify.py --deep            # checks 1-19 (needs bulk/)
python3 verify/verify.py --deep --online   # check 20 as well: the Wayback Machine's copies of GitHub's records
```
Expected result: `14/14 checks passed`, `19/19` with `--deep`, and `20/20` with `--online`. The script uses only the
standard library and reads no keys. Only `--online` uses the network.

| # | Check | What a failure would mean |
|---|---|---|
| 1 | Every file matches `MANIFEST.sha256`. If `bulk/` is absent, the core files are still checked. | A file was changed after the package was built |
| 2 | The answers are exactly the 700 BEAM-1M question IDs, each once | Missing, duplicated or foreign questions |
| 3 | The partition is 100 / 260 / 260 / 80, and the split files match their recorded hashes | The split was misreported |
| 4 | Each answer matches its sha256; none is empty | An answer was edited or left blank |
| 5 | The answers are byte-identical to the prediction files the judge read | The published answers differ from the scored ones |
| 6 | Both files of each of the 35 conversations match BEAM's own git tree at `3e12035` (blob hashes) and the sha256 recorded in the 1 Aug split files | The data is not BEAM's |
| 7 | One completed judge row per question. All four judge files used BEAM `3e12035`, identical evaluator file hashes, gpt-4.1-mini and temperature 0 | A modified or different evaluator |
| 8 | Each stored score equals the score recomputed from its raw rubric verdicts with the evaluator's arithmetic | Scores were edited |
| 9 | Every number in `claims.json` (7 groups × 4 bases) recomputes exactly | A claimed number is wrong |
| 10 | The per-ability scores recompute exactly | As above |
| 11 | `scores.csv` agrees with the judge outputs | As above |
| 12 | The 123 locked files are committed by sha256: `FROZEN.json` agrees with the full package's manifest, and the published judge wrapper (3 files) matches its hashes | The commitment to the code is inconsistent |
| 13 | **Hash chain.** The freeze-time `FROZEN.json` plus each recorded amendment, one file at a time, gives exactly the final `FROZEN.json`. Every run start and resume (25) recorded a state on that chain, in time order, and Canary A and the start of Canary B used the public freeze itself | Unrecorded code changes during the runs |
| 14 | **Timeline.** In GitHub's server log, the split files and the frozen commit were on GitHub before Canary B and the remaining 340 started | The freeze or split came after the runs |
| 15 | Judge call logs: every dispatched call was answered; no failures | Silent judge failures scored as zeros |
| 16 | For all 630 non-ordering questions, the published answer appears in the judge's own logged prompts | The judge saw different text |
| 17 | The ledgers match their summaries; no empty model replies; the translator's trim fallback never fired | Hidden failures or an amendment that changed outputs |
| 18 | The ledgers contain exactly 700 answer generations and 700 first plans; the only extras are 3 schema re-asks of a plan | Best-of-N selection |
| 19 | A memory pack and an answer plan exist for every question, each committed by sha256 (`withheld/`) | Missing evidence |
| 20 | `--online` only. The Wayback Machine's copies of GitHub's push log, the freeze tag and commit, the freeze-time `FROZEN.json` and the five split files match this package byte for byte (`data/questions/independent-archives.json`) | The dates rest only on our own copy of GitHub's log |

**We tested that the script catches tampering.** On copies of the package:
- changing one word of one answer failed checks 1, 4 and 5;
- raising one claimed number by 0.01 failed checks 1 and 9;
- flipping one judge verdict failed checks 1 and 8–11.

Regenerating the manifest after such an edit makes check 1 pass again, but the content checks still fail.

---

## L2b: third-party records (no keys)
The development repository (github.com/arnavgupta00/memory) became private on 12 Oct 2026. Before that, its public records
were saved to the Internet Archive's Wayback Machine. `python3 verify/verify.py --online` downloads the archived copies and
compares them with this package (check 20). You can also open them yourself; the snapshot URLs are in
`data/questions/independent-archives.json`.

1. **GitHub's server-side push log**, as archived. The repository owner cannot edit GitHub's log.
   - Find the push with `after` = `595a2e28228c21cf842378fb9216cacb46478fd3` at `2026-10-11T10:06:21Z`.
   - Canary B started at 12:21:10 UTC (`runs/canary-b/pipeline-run/manifest.json`).
   - The same log shows the split files' commit (`2e1719d3`) reaching GitHub at `2026-08-29T20:45:53Z`.
2. **The freeze tag and commit**, as archived. Tag `r9-freeze-20261011` points at that commit, dated 2026-10-11 10:06:19 UTC.
3. **The freeze-time hash manifest**, as archived.
   - The archived `FROZEN.json` at that commit is byte-identical to `code/public-freeze/.../FROZEN.json` here (sha256
     `518766…`).
   - Its frozen-files hash, `sha256(JSON.stringify(FROZEN.files))`, is `fb2baea2867f…`. Every Canary A run and the start of
     Canary B recorded that hash.
4. **The split files**, as archived at commit `2e1719d3`, and the 24 Sep allocation record at `f3961ce7`. They are
   byte-identical to `data/questions/partition-files/`.
5. **BEAM's data and evaluator.**
   - Without cloning, GitHub's API gives the git blob hash of each data file at the pinned commit:
     ```
     curl -s "https://api.github.com/repos/mohammadtavakoli78/BEAM/contents/chats/1M/26?ref=3e12035532eb85768f1a7cd779832b650c4b2ef9"
     ```
     The `sha` of `chat.json` must equal `beam_tree_chat_blob_sha1` for conversation 26 in
     `data/questions/official-source-manifest.json`. The same applies to `probing_questions/`.
   - With a clone of https://github.com/mohammadtavakoli78/BEAM at that commit, compare the files' sha256 with the same
     manifest. Also compare the six evaluator files with `official_source_hashes` in any `data/judge/*.judge.json`.
6. **For auditors.** Given read access to the private repository, you can also check the live push log, the tag and the
   commit history directly. GitHub keeps them whatever the repository's visibility.

---

## L3: re-judge with the official evaluator (about $2.50)
```
export OPENAI_API_KEY=...        # your own key
sh verify/rejudge_official.sh    # clones BEAM at 3e12035, builds its environment, judges the 700 published answers, compares
```
- **How it runs.** It uses BEAM's own `compute_metrics.py`, through the same wrapper that produced the package's judge
  files. The wrapper refuses a checkout that is not exactly `3e12035` or has modified evaluator files. It logs every call
  to `rejudge/<part>/`.
- **Expected result.** About 76.8. The judge is gpt-4.1-mini at temperature 0, which is close to deterministic but not
  exactly: re-scoring identical inputs changed about 1 in 10 event-ordering alignments in our tests. Expect agreement
  within about half a point. `verify/compare_rejudge.py` prints the difference and the number of questions whose score
  changed.
- **We smoke-tested this level from the package** with a zero spend budget, which stops the first judge call before it is
  sent. The evaluator pin checks passed, the answers loaded, and BEAM's scorer started.

## L4: re-score with Vectorize's scorer (about $1)
```
export GEMINI_API_KEY=...
python3 verify/rescore_vectorize.py --beam-root beam-official/chats/1M --model gemini-3.5-flash-lite
```
- **How it runs.** It downloads AMB's `beam.py` from the pinned commit `20751fa0` and checks its sha256 (AMB has no
  licence, so it is not redistributed here). It then runs AMB's `score_result` unchanged.
- **Failed judge calls are retried, not scored 0.** AMB's own code turns a failed call into a 0. We hit that once, when
  the original judge model returned 404, and discarded that run.
- **Expected result.** About 78.2, plus or minus about a point, because Gemini is not fully reproducible.

## L5: re-run the system (auditors; about $100, about 7 hours)
The source code is withheld from this public copy, so a re-run needs the full copy.
- **What it holds.** The code and an exact recipe: the drivers in `runs/*/run.sh`, the question lists in `runs/*/scripts/`,
  and the translator settings.
- **Expect a different score within about ±1 point, not the same answers.** Sampling at maximum reasoning is not
  deterministic: two answer runs of R9 on Canary A scored 77.71 and 79.32.

---

## Spot-check one question by hand (5 minutes)
1. Pick any ID, for example `beam-1m/chat-26/temporal_reasoning/1`.
2. Read the question, the reference answer and the rubric in BEAM's file:
   `chats/1M/26/probing_questions/probing_questions.json` → `temporal_reasoning[0]`.
3. Read our answer in `data/answers/answers.jsonl`.
4. Find the row in `data/judge/canary-b.judge.json`:
   - `official_result.llm_judge_responses` holds the judge's verdict and reason for each rubric item;
   - `score` is what counts.
5. Recompute the score yourself.
   - Event ordering: the score is `official_result.tau_norm`.
   - Every other ability: average `int(score)` over the items.
6. The memory pack the answer was written from is withheld; its sha256 is in
   `withheld/memory-pack-and-plan-hashes.json`.

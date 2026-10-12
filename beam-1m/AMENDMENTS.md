# Amendments during the sealed runs

**The rule.** The frozen configuration could change in only one way. If a run stopped on a failure, the fix could touch
only what happens after that failure, so a request that had already succeeded had to be unaffected. Every such change was
recorded in `FROZEN.json` → `amendments` before the run resumed. The pipeline refuses to start or resume if any locked file
differs from `FROZEN.json` (`run.mjs`, `checkFrozen`).

There were four amendments: three during Canary B and one during the remaining 340. None was made in response to a score,
because each was made before any answer of its run had been judged.

## The four amendments
Times are IST, from the driver logs (`runs/*/run.log`). The run READMEs give approximate headings (19:10, 19:50, 20:35).
The driver logs are authoritative.

### 1. Spend-guard option (Canary B, relaunched 19:09)
- **What failed.** Stage 8, the TypeSafe relevance filter, refuses to dispatch unless 4 × its one-attempt cost forecast is
  at or under $10. For 260 questions the forecast was $2.62, so the guard tripped at 4 × $2.62 = $10.46. No filter call
  had been sent.
- **Change.** `run.mjs` gained `--jev-cap`. Its default is 10, so behaviour without the flag is unchanged. Canary B and
  the remaining 340 used `--jev-cap 20`.
- **File.** `src/pipeline/a6/run.mjs`: `a2fc26da…` → `6821f881…`.
- **Effect on requests.** None. It is a spend guard only.

### 2. Split a batch TypeSafe refuses as too large (Canary B, relaunched 19:44)
- **What failed.** Stage 8 got TypeSafe `HTTP 400 max_tokens_exceeded` for two batches of conversation 22's sessions, 8
  refused attempts in all.
  - The cause is in BEAM's own data. One generated assistant reply in conversation 22 contains a run of 21,712 zeros, and
    one in conversation 9 contains 11,182.
  - Our local token estimate, which sizes the batches, counts such a run as a few tokens; TypeSafe counts far more.
  - The first refusal also halted every other dispatch (244 calls).
- **Change.**
  - `s07_fusion_jev.mjs`: a batch refused with `max_tokens_exceeded` is split in two, each half is scored, and the answers
    are merged (`askSplitting`).
  - `recursiveArtifacts.mjs`: that one error no longer halts other dispatches.
- **Files.**
  - `src/pipeline/a6/stages/s07_fusion_jev.mjs`: `efce6c79…` → `935ac475…`.
  - `src/jev/recursiveArtifacts.mjs`: `f009b3e8…` → `347dd263…`.
- **Effect on requests.**
  - A batch TypeSafe accepts is sent exactly as before, so all 1,489 calls completed before the stop were reused
    unchanged, from the request-hash cache.
  - Only the refused batches and the halted calls were sent again.

### 3. Trim fallback for the packager's discarded answer (Canary B, relaunched 20:25)
- **What failed.** Stage 10a finished 258 of 260 questions.
  - For two questions (chat-01 event ordering 1 and chat-30 summarization 1), the packager's old-style answer
    (`answer_v1`) came back from DeepSeek with more than its schema's limit of 32 evidence rows (up to 104). That was
    still true after 5 asks.
  - A2 never reads that answer, but without it the packager does not record the package for that question.
- **Change.** In the translator, for that discarded answer only: if it still breaks a length limit after every ask,
  over-long lists and strings are cut to the limit. Every other call is unchanged.
- **File.** `src/pipeline/a7/hive-proxy.mjs`: `b136610e…` → `5be459b1…`. The translator is not one of the 123 locked
  files; its hash is recorded in `runs/*/sha256.txt`.
- **Effect on requests.**
  - None in practice. The stage re-ran with 258 packager calls replayed from cache, and the 2 failed ones were sent again.
  - Both re-sent answers met the limit within the 5 asks. **The trim never fired:** there are 0
    `discarded_answer_trimmed` events in any ledger (check 17).

### 4. Split a batch Voyage refuses as too large (remaining 340, relaunched 02:41 on 12 Oct)
- **What failed.** Stage 2b, the notes index, built 16 of 17 history indexes. The 17th sent one embedding batch of 120,372
  tokens, above Voyage's 120,000-token limit per batch, because the local estimate ran slightly low. Every resume rebuilt
  the same batch.
- **Change.** A batch refused with `TOO_MANY_TOKENS_IN_BATCH` is split in two by whole documents, and each half is
  embedded.
  - Voyage's contextual embeddings depend only on the chunk's own document, so the vectors are the same as for the unsplit
    batch.
  - Accepted batches are byte-identical to before.
- **File.** `src/retrieval/semanticProviders.ts`: `281d2fad…` → `812fbde5…`.
- **Effect on requests.** None for accepted batches. Canary A and Canary B never reached this path.

## The hash chain
`run.mjs` writes `sha256(JSON.stringify(FROZEN.files))` into the run manifest at every start and every resume. Applying
the recorded amendments one file at a time to the public freeze gives this chain. Check 13 recomputes it from the two
`FROZEN.json` files in `code/`, and requires every recorded start and resume to be on it, in time order.

| State | Locked-files hash | Recorded by |
|---|---|---|
| Public freeze, tag `r9-freeze-20261011` | `fb2baea2867f…` | Canary A part 1 start; Canary A part 2 start and its 3 resumes; Canary B start and resumes 1–4 |
| + amendment 1 (`run.mjs`) | `c8f55b6646a3…` | Canary B resumes 5–7 |
| + amendment 2, first file (`s07_fusion_jev.mjs`) | `f205d436becb…` | none (applied together with the second file) |
| + amendment 2, second file (`recursiveArtifacts.mjs`) | `8f117895b4ce…` | Canary B resumes 8–13; remaining-340 start and resumes 1–4 |
| + amendment 4 (`semanticProviders.ts`) | `6ee072cb8521…` | remaining-340 resume 5 (and the final `FROZEN.json`) |

The translator went from `b136610e…` (the public freeze, Canary A, and Canary B until 20:25) to `5be459b1…` (Canary B
from 20:25, and the whole remaining 340).

## How to check it yourself
- **The code is withheld in this public copy.** The full copy for auditors holds the diff from the public freeze to the
  final code (205 lines) and the six changed files, as frozen and as run last. Their sha256 are in
  `code/code-provenance.json` → `amendments` and in `withheld/FULL-PACKAGE-MANIFEST.sha256`.
- **The freeze side is archived.** The freeze-time `FROZEN.json` is in the Wayback Machine, and check 20 compares it
  with this package.
- **Run the checks.** `python3 verify/verify.py` (checks 12, 13 and 14), then `--deep` (check 17) and `--online`
  (check 20).

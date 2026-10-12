# What this public copy withholds

The system's source code and its research notes stay private. Everything needed to check the score is public. Each
withheld item is committed by sha256 before release, so an auditor given the full copy can confirm that nothing was swapped.

| Withheld | Why | How it is committed |
|---|---|---|
| Source code of the pipeline (123 locked files) and the translator | the product | `../code/src/agents/current/src/pipeline/a6/FROZEN.json` (a sha256 for every locked file); the translator's sha256 in `../code/code-provenance.json` |
| The prompts | part of the code | in `FROZEN.json`, like every other locked file |
| The four amendments' code and the freeze-to-final diff | code | old and new sha256 in `../code/code-provenance.json` → `amendments` |
| 700 memory packs (what the answerer read) | they expose how the memory is built | `memory-pack-and-plan-hashes.json` |
| 700 answer plans (the planner's output) | they expose the answer layer's design | `memory-pack-and-plan-hashes.json` |
| Search outputs and stage logs | internal | `FULL-PACKAGE-MANIFEST.sha256` |
| Internal research notes (run ledger, loss analysis, post-mortems, experiment history) | research | `FULL-PACKAGE-MANIFEST.sha256` |

`FULL-PACKAGE-MANIFEST.sha256` is the manifest of the full copy: one sha256 for every file in it, public or withheld.
- **Public files.** Every public file at a path that also exists in the full copy is byte-identical to it, with three
  exceptions:
  - the documents, whose references to withheld files are rewritten;
  - the model-call ledgers (`*.redacted.jsonl.gz`), which drop two fields: the first words of each prompt and the names of
    the schema fields a reply broke;
  - the generated `MANIFEST.sha256` itself.
- **What the redaction keeps.** Every count, token total and cost in the ledgers is unchanged.

**What an auditor can check with the full copy:**
1. Its `MANIFEST.sha256` equals `FULL-PACKAGE-MANIFEST.sha256` here.
2. Its code matches `FROZEN.json`; the full copy's `verify.py` runs check 12 against the source itself.
3. Its memory packs and plans hash to the values in `memory-pack-and-plan-hashes.json`.
4. The answers can be regenerated from the code, within run-to-run variation (VERIFY.md, L5).

The scripts that built this public copy are in `../tools/`: `build_package.py` for the full copy, and `build_public.py`,
which lists exactly what is copied, rewritten and left out.

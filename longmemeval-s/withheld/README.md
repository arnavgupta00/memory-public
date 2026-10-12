# What this package withholds

**Withheld.**
- The code and the prompts of Architecture 0008.
- The session notes, retrieval traces and context packages.
- The per-call model inputs and outputs of the answer stage.

**Public.** Everything needed to check the score.

**How the withheld records are committed.** `RUN-SHA256SUMS` is the checksum file the run itself wrote when it finished, at
01:30 UTC on 31 Jul 2026. It lists a sha256 for each of the run's 40,943 files, public and withheld.
- **Public files.** Every file in `../data/run/` and `../data/judge-artifacts/` that also appears in that list is
  byte-identical to it. Check 3 compares them.
- **Withheld files.** An auditor given the run folders can check them against the same list.

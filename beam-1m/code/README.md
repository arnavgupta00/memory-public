# Code commitments

The source code is not public. This folder holds the hashes that pin it.

| File | What it pins |
|---|---|
| `public-freeze/src/agents/current/src/pipeline/a6/FROZEN.json` | The locked pipeline as tagged on 11 Oct 2026 (`r9-freeze-20261011`, commit `595a2e28`): a sha256 for each of its 123 files. The Wayback Machine holds the same file as it was on GitHub (check 20). |
| `src/agents/current/src/pipeline/a6/FROZEN.json` | The locked pipeline as it ran last: the same list after the four recorded amendments. |
| `code-provenance.json` | Each amendment's file, old and new sha256, the hash chain from the first state to the last, which run starts and resumes used each state, and the translator's sha256. |

`verify.py` checks that applying the amendments to the first file gives the second (check 13). It also checks that every
recorded run start and resume used a state on that chain, in time order, and that the published judge wrapper
(`../verify/judge-wrapper/`) matches its hashes (check 12).

"""Compare a fresh official re-judge (rejudge/<part>/judge.json) with the judge outputs in this package.

The official judge (gpt-4.1-mini at temperature 0) is close to deterministic but not exactly: in our checks, re-scoring
identical inputs changed about 1 in 10 event-ordering alignments. Expect the 700-question total to agree within about half
a point."""
import json, pathlib, statistics as st, sys
PKG = pathlib.Path(__file__).resolve().parents[1]; NEW = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'rejudge')
old, new = {}, {}
for part in ['canary-a-part1', 'canary-a-part2', 'canary-b', 'remaining-340']:
    old.update({r['question_id']: r['score'] for r in json.loads((PKG / f'data/judge/{part}.judge.json').read_text())['rows']})
    new.update({r['question_id']: r['score'] for r in json.loads((NEW / part / 'judge.json').read_text())['rows']})
qs = sorted(set(old) & set(new)); d = [new[q] - old[q] for q in qs]
print(f'questions compared: {len(qs)}')
print(f'package official score: {100 * st.mean(old[q] for q in qs):.2f}   fresh re-judge: {100 * st.mean(new[q] for q in qs):.2f}   difference {100 * st.mean(d):+.2f}')
print(f'questions whose score changed: {sum(abs(x) > 1e-9 for x in d)}')

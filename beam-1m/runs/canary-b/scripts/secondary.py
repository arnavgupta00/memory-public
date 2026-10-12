"""Secondary basis (labelled, not the headline): per-item rubric scores with half credit for every category, event ordering
by its rubric judge (official llm_judge_score). This is the basis Mem0 publishes for BEAM."""
import json, statistics as st, collections
rows = json.load(open('/Users/arnav/programming/projects/memory/runs/canary-b-r9-20261011/canary-b/judge/judge.json'))['rows']
def nugget(r):
    o = r['official_result']
    if r['ability'] == 'event_ordering': return o['llm_judge_score']
    items = o.get('llm_judge_responses') or []
    return st.mean(float(x['score']) for x in items) if items else r['score']
by = collections.defaultdict(lambda: ([], []))
for r in rows: by[r['ability']][0].append(r['score']); by[r['ability']][1].append(nugget(r))
print(f"{'ability':26} {'official':>9} {'rubric basis':>13}")
for a, (o, n) in sorted(by.items()): print(f'{a:26} {100*st.mean(o):9.1f} {100*st.mean(n):13.1f}')
print(f"{'OVERALL':26} {100*st.mean(r['score'] for r in rows):9.1f} {100*st.mean(nugget(r) for r in rows):13.1f}   (n={len(rows)})")

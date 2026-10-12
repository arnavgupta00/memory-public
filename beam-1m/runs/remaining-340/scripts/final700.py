"""Final BEAM-1M score over all 700 questions, frozen R9 configuration: Canary A (R9 original answer run), Canary B, and the
remaining 340. Official pinned score is the headline; also official with the half-credit fix and the rubric average."""
import json, statistics as st, collections
R = '/Users/arnav/programming/projects/memory/runs'
parts = {'Canary A (100, dev)': ['a6/canary-a-screen20-hive-r9', 'a6/canary-a-other80-hive-r9'], 'Canary B (260, sealed)': ['canary-b-r9-20261011/canary-b'],
         'Remaining 340': ['final-700-r9-20261012/remaining-340']}
rows = {k: [r for p in v for r in json.load(open(f'{R}/{p}/judge/judge.json'))['rows']] for k, v in parts.items()}
allr = [r for v in rows.values() for r in v]; assert len({r['question_id'] for r in allr}) == 700, len(allr)
items = lambda r: [float(x['score']) for x in (r['official_result'].get('llm_judge_responses') or [])]
pinned = lambda r: r['score']
fixed = lambda r: r['official_result']['tau_norm'] if r['ability'] == 'event_ordering' else (st.mean(items(r)) if items(r) else r['score'])
nug = lambda r: r['official_result']['llm_judge_score'] if r['ability'] == 'event_ordering' else (st.mean(items(r)) if items(r) else r['score'])
exp = [r for r in rows['Remaining 340'] if int(r['question_id'].split('/')[1].split('-')[1]) in (7, 16, 21, 34)]
groups = {**rows, 'Expansion 80 (sealed, in remaining)': exp, 'Unseen total: Canary B + expansion (340)': rows['Canary B (260, sealed)'] + exp, 'ALL 700': allr}
print(f"{'set':42} {'n':>4} {'official':>9} {'+half credit':>13} {'rubric avg':>11}")
for k, v in groups.items(): print(f"{k:42} {len(v):4} {100*st.mean(map(pinned, v)):9.2f} {100*st.mean(map(fixed, v)):13.2f} {100*st.mean(map(nug, v)):11.2f}")
by = collections.defaultdict(list)
for r in allr: by[r['ability']].append(r)
print('\nALL 700 by ability (official / rubric):')
for a, v in sorted(by.items()): print(f'   {a:26} {100*st.mean(map(pinned, v)):6.1f} / {100*st.mean(map(nug, v)):6.1f}  (n={len(v)})')
conv = collections.defaultdict(list)
for r in allr: conv[r['question_id'].split('/')[1]].append(r['score'])
cs = [100 * st.mean(v) for v in conv.values()]
print(f'\nconversation scores: n={len(cs)}, mean {st.mean(cs):.2f}, sd {st.stdev(cs):.2f}, min {min(cs):.1f}, max {max(cs):.1f}')

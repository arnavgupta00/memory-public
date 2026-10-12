#!/usr/bin/env python3
"""Verify the LongMemEval-S proof package. Python 3 standard library only.

    python3 verify/verify.py            # checks 1-9, offline: integrity, provenance, every claimed number recomputed
    python3 verify/verify.py --online   # checks 10-13 as well: dataset, evaluator and prompts against their official sources,
                                        # and the Wayback Machine's copy of GitHub's push log

Every check prints PASS or FAIL. The script exits 0 only if every check passes. Only --online uses the network.
"""
import csv, gzip, hashlib, json, pathlib, statistics as st, sys

PKG = pathlib.Path(__file__).resolve().parents[1]
ONLINE = '--online' in sys.argv
results = []
def check(name, ok, detail=''):
    results.append(bool(ok)); print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f'  [{detail}]' if detail else ''))
sha = lambda b: hashlib.sha256(b).hexdigest()
load = lambda p: json.loads((PKG / p).read_text())
jsonl = lambda p: [json.loads(l) for l in (PKG / p).read_text().splitlines() if l.strip()]
pct = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]
print(f'LongMemEval-S proof package: {PKG.name}\n')

# 1. every file in the manifest is present and unchanged
man = [l.split('  ', 1) for l in (PKG / 'MANIFEST.sha256').read_text().splitlines() if l.strip()]
bad = [rel for h, rel in man if not (PKG / rel).exists() or sha((PKG / rel).read_bytes()) != h]
check('1. MANIFEST.sha256: every file present and byte-identical', not bad, f'{len(man)} files; changed or missing {len(bad)}')

# 2. 500 answers, the 500 LongMemEval-S questions, once each
preds = jsonl('data/run/official-predictions.jsonl'); P = {r['question_id']: r['hypothesis'] for r in preds}
types = load('data/questions.json')['question_types']
check('2. 500 answers, one for each of the 500 LongMemEval-S questions', len(preds) == 500 and set(P) == set(types) and len(types) == 500)

# 3. the run's own files are byte-identical to the checksums the run wrote on 31 Jul 2026
sums = {}
for line in (PKG / 'withheld/RUN-SHA256SUMS').read_text().splitlines():
    h, path = line.split('  ', 1); sums[path] = h
D = 'runs/arch0008-full500-from-scratch-20260731T004831Z-3'
same = [sha((PKG / 'data/run' / f).read_bytes()) == sums.get(f'{D}/{f}') for f in
        ('official-predictions.jsonl', 'judgments.jsonl', 'report.json', 'manifest.json')]
arts = sorted((PKG / 'data/judge-artifacts').glob('*.json'))
same += [sha(a.read_bytes()) == sums.get(f'{D}/judge-artifacts/{a.name}') for a in arts]
check("3. answers, judgments, report and all 500 judge records match the checksum file the run wrote on 31 Jul", all(same) and len(arts) == 500,
      f'{sum(same)}/{len(same)} files')

# 4. judgments are of the published answers
J = {r['question_id']: r for r in jsonl('data/run/judgments.jsonl')}
check('4. one judgment per question, each of the published answer', set(J) == set(P) and all(J[q]['hypothesis'] == P[q] for q in P))

# 5. the judge: gpt-4o-2024-08-06, temperature 0, label = "yes" in the reply, prompt contains the answer
A = {json.loads(a.read_text())['question_id']: json.loads(a.read_text()) for a in arts}
ok = all(a['model'] == 'gpt-4o-2024-08-06' and a['temperature'] == 0 and (('yes' in a['response'].lower()) == a['label'])
         and a['label'] == J[q]['autoeval_label']['label'] and P[q] in a['prompt'] for q, a in A.items())
check('5. judge records: gpt-4o-2024-08-06 at temperature 0; each label follows the reply; each prompt contains the published answer', ok)

# 6. recompute the score
claims = load('claims.json'); L = {q: J[q]['autoeval_label']['label'] for q in J}
by = {}
for q, t in types.items(): by.setdefault(t, []).append(L[q])
acc = round(100 * sum(L.values()) / 500, 2); task_avg = round(100 * st.mean(sum(v) / len(v) for v in by.values()), 2)
abst = [L[q] for q in L if q.endswith('_abs')]
got = {'correct': sum(L.values()), 'accuracy': acc, 'task_averaged_accuracy': task_avg, 'abstention_correct': sum(abst), 'abstention_count': len(abst),
       'by_type': {t: {'correct': sum(v), 'count': len(v)} for t, v in sorted(by.items())}}
check('6. the score recomputes exactly from the judgments: 457/500 = 91.40%', got == claims['result'], f"{got['correct']}/500 = {acc}%, task-averaged {task_avg}%")

# 7. the split by development exposure
ex = load('data/exposure.json'); dev, never = set(ex['answer_level_development_ids']), set(ex['never_named_ids'])
sub = {'development': [sum(L[q] for q in dev), len(dev)], 'never_named': [sum(L[q] for q in never), len(never)]}
check('7. accuracy on the questions never named in development recomputes: 206/227', dev | never == set(P) and not dev & never and sub == claims['by_exposure'],
      f"never named {sub['never_named'][0]}/{sub['never_named'][1]}; development {sub['development'][0]}/{sub['development'][1]}")

# 8. performance figures recompute from the per-question latency table and the run's audit
perf = load('data/performance.json')
rows = list(csv.DictReader(open(PKG / 'data/latency-per-question.csv')))
t = [float(r['model_time_ms']) / 1000 for r in rows]
lat_ok = len(rows) == 500 and round(pct(t, 50), 1) == perf['per_question_model_time_seconds']['p50'] and round(pct(t, 90), 1) == perf['per_question_model_time_seconds']['p90']
audit = load('data/run/AUDIT.json'); cost = audit['estimated_cost_usd']
cost_ok = round(cost['core_pipeline_total'], 2) == perf['cost']['list_usd_total'] and audit['usage']['core_pipeline']['api_calls'] == perf['tokens']['api_calls']
split = perf['latency_split']; sl = lambda col: [float(r[col]) / 1000 for r in rows]
notes = [float(r['note_ms']) / 1000 for r in csv.DictReader(open(PKG / 'data/note-latency-per-session.csv'))]
for xs, key in ((sl('retrieval_total_ms'), split['query_retrieval_seconds']), (sl('answer_ms'), split['query_answer_seconds']),
                (sl('model_time_ms'), split['query_total_seconds']), (sl('preprocessing_history_ms'), split['preprocessing']['per_history_parallel_seconds']),
                (sl('cold_start_ms'), split['cold_start_seconds']), (notes, split['preprocessing']['per_new_session_note_seconds'])):
    lat_ok &= round(pct(xs, 50), 1) == key['p50'] and round(pct(xs, 90), 1) == key['p90']
lat_ok &= all(float(r['preprocessing_history_ms']) <= max(notes) * 1000 + 1e-6 for r in rows) and len(notes) == 19195
check('8. performance: pre-processing, retrieval, answer and cold-start latency, and cost, recompute from the latency tables and the run audit', lat_ok and cost_ok,
      f"model time p50 {perf['per_question_model_time_seconds']['p50']}s; ${perf['cost']['list_usd_total']} at list price")

# 9. the result was on GitHub minutes after the run
tl = load('data/timeline.json'); push = tl['first_push_containing_result']
check('9. timeline: the result reached GitHub after the run finished (GitHub server log, saved copy)',
      tl['run_completed_utc'] < push['timestamp'] and push['after'] == tl['result_commit'], f"run finished {tl['run_completed_utc']}; on GitHub {push['timestamp']}")

if ONLINE:
    import urllib.request, ast, re
    import time
    def get(u):   # third-party services can be briefly unavailable: retry before giving up
        for i in range(5):
            try: return urllib.request.urlopen(u, timeout=300).read()
            except Exception as e:
                if i == 4: raise
                time.sleep(5 * (i + 1))
    src = load('data/dataset-and-evaluator.json')
    def online(name, fn):   # a service that cannot be reached is a FAIL with the reason, never a crash
        try: ok, detail = fn()
        except Exception as e: ok, detail = False, f'could not fetch it: {e}; try again later'
        check(name, ok, detail)
    # 10. the dataset files are LongMemEval's own (Hugging Face content hashes)
    def c10():
        tree = {e['path']: (e.get('lfs') or {}).get('oid') for e in json.loads(get(src['dataset']['tree_api']))}
        return all(tree.get(f) == h for f, h in src['dataset']['sha256'].items()), ''
    online("10. dataset: Hugging Face's content hashes for the LongMemEval files equal those the run recorded", c10)
    # 11. the evaluator is LongMemEval's evaluate_qa.py
    ev = {}
    def c11():
        ev['src'] = get(src['evaluator']['url']); return sha(ev['src']) == src['evaluator']['sha256'], ''
    online("11. evaluator: LongMemEval's evaluate_qa.py on GitHub has the sha256 the run pinned", c11)
    # 12. every judge prompt is the official one, rebuilt from the evaluator, the official questions and the published answer
    def c12():
        ns = {}
        for node in ast.parse((ev.get('src') or get(src['evaluator']['url'])).decode()).body:
            if isinstance(node, ast.FunctionDef) and node.name == 'get_anscheck_prompt': exec(compile(ast.Module([node], []), 'evaluate_qa', 'exec'), ns)
        oracle = get(src['dataset']['oracle_url']); data = {d['question_id']: d for d in json.loads(oracle)}
        same = sum(ns['get_anscheck_prompt'](data[q]['question_type'], data[q]['question'], data[q]['answer'], P[q], abstention='_abs' in q) == A[q]['prompt'] for q in P)
        return same == 500 and sha(oracle) == src['dataset']['sha256']['longmemeval_oracle.json'], f'{same}/500'
    online('12. every judge prompt is exactly the official LongMemEval prompt for that question and answer', c12)
    # 13. the Wayback Machine's copy of GitHub's push log shows the same push
    try:
        w = tl['wayback_push_log']; b = get(re.sub(r'/web/(\d+)/', r'/web/\1id_/', w)); b = gzip.decompress(b) if b[:2] == b'\x1f\x8b' else b
        check("13. the Wayback Machine's copy of GitHub's push log shows the result's push", any(e.get('after') == push['after'] and e.get('timestamp') == push['timestamp'] for e in json.loads(b)))
    except Exception as e:
        check("13. the Wayback Machine's copy of GitHub's push log shows the result's push", False, f'could not fetch it: {e}; try again later')

n = sum(results); print(f'\n{n}/{len(results)} checks passed.')
sys.exit(0 if all(results) else 1)

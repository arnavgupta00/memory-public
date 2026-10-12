"""Cost, speed and latency of the BEAM-1M runs, computed from the logs (13 Oct 2026).

Writes data/performance/performance.json and data/performance/latency-per-question.csv.

Latency here is model time measured by the provider side of each call (the translator ledger's `latency_ms`), not the
wall time a question spent in the batch run: these runs sent all questions at once through one 4.8-requests-per-second
gate, so wall time per question is mostly queueing. A question's model time is the sum of the calls on its path:
- the router call;
- the search calls, which run one after another;
- the slowest of its relevance-filter batches, which run in parallel;
- the packager call;
- the planner call and the answerer call.
Each call is matched to its question through the response id that the pipeline's own logs record for it. The packager
logs no question id, so its median is used for every question. Routed extras (timeline, statement checks) run for some
questions only and are left out.

Usage (private repository root): python3 proof/BEAM-1M-R9-final-20261012/tools/performance.py
"""
import csv, gzip, json, pathlib, statistics as st, collections, re

ROOT = pathlib.Path(__file__).resolve().parents[3]
PKG = pathlib.Path(__file__).resolve().parents[1]
RUNS = {'canary-a-part1': ROOT / 'runs/a6/canary-a-screen20-hive-r9', 'canary-a-part2': ROOT / 'runs/a6/canary-a-other80-hive-r9',
        'canary-b': ROOT / 'runs/canary-b-r9-20261011/canary-b', 'remaining-340': ROOT / 'runs/final-700-r9-20261012/remaining-340'}
pct = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]
def dist(xs, scale=1000.0, nd=1):
    xs = [x / scale for x in xs]
    return {'n': len(xs), 'p50': round(pct(xs, 50), nd), 'p90': round(pct(xs, 90), nd), 'mean': round(st.mean(xs), nd)}

# ---------- provider-measured latency of every model call (translator ledger) ----------
lat, stage_lat = {}, collections.defaultdict(list)
tokens = collections.defaultdict(lambda: [0, 0, 0])   # stage -> prompt, completion, calls
planner_prompt = []
for part in RUNS:
    for line in gzip.open(PKG / f'bulk/{part}/hive-ledger.jsonl.gz', 'rt'):
        e = json.loads(line)
        if e.get('event') != 'hive_response': continue
        if str(e.get('requested_model', '')).startswith('gpt-5.4-nano'): s = 'session notes'
        elif e['effort_used'] == 'max': s = 'planner' if e['structured'] else 'answerer'
        elif e['effort_used'] == 'low': s = 'router, search, targeted plans'
        else: s = "packager's discarded answer"
        lat[e['resp_id']] = e['latency_ms']; stage_lat[s].append(e['latency_ms'])
        u = e['usage']; tokens[s][0] += u.get('prompt_tokens', 0); tokens[s][1] += u.get('completion_tokens', 0); tokens[s][2] += 1
        if s == 'planner' and e['ask'] == 1 and not e['corrective']: planner_prompt.append(u.get('prompt_tokens', 0))

# ---------- per-question model time ----------
def attempts(path):
    out = {}
    for line in open(path):
        e = json.loads(line)
        if e.get('event') == 'response' and e.get('response_id') in lat: out[e['id']] = lat[e['response_id']]
    return out
rows = {}
for part, run in RUNS.items():
    router, planner, answerer = attempts(run / 'v2/router/attempts.jsonl'), attempts(run / 'plan/attempts.jsonl'), attempts(run / 'answer/attempts.jsonl')
    search = {}
    for f in (run / 'traces/retrieval').rglob('*.json'):
        d = json.loads(f.read_text()); calls = d.get('model_io') or []
        if calls and all(c.get('request_id') in lat for c in calls): search[d['question_id']] = sum(lat[c['request_id']] for c in calls)
    filt = collections.defaultdict(list)
    for f in (run / 'jev/calls').glob('*.json'):
        d = json.loads(f.read_text()); ident = d.get('identity') or {}
        if ident.get('phase') == 'filter' and d.get('elapsedMs') is not None: filt[ident['id']].append(float(d['elapsedMs']))
    for q in planner:
        rows[q] = {'question_id': q, 'run_part': part, 'router_ms': router.get(q), 'search_ms': search.get(q),
                   'filter_slowest_batch_ms': max(filt[q]) if filt.get(q) else None, 'planner_ms': planner[q], 'answerer_ms': answerer.get(q)}
pack_p50 = pct(stage_lat["packager's discarded answer"], 50)
complete = [r for r in rows.values() if all(r[k] is not None for k in ('router_ms', 'search_ms', 'filter_slowest_batch_ms', 'planner_ms', 'answerer_ms'))]
for r in rows.values():   # query time = retrieval (memory -> context) + answer; pre-processing happens before any question
    ret = [r[k] for k in ('router_ms', 'search_ms', 'filter_slowest_batch_ms')]; ans = [r[k] for k in ('planner_ms', 'answerer_ms')]
    r['retrieval_ms'] = round(sum(ret) + pack_p50, 1) if None not in ret else None
    r['answer_ms'] = round(sum(ans), 1) if None not in ans else None
    r['model_time_ms'] = round(r['retrieval_ms'] + r['answer_ms'], 1) if None not in (r['retrieval_ms'], r['answer_ms']) else None
(PKG / 'data/performance').mkdir(parents=True, exist_ok=True)
with open(PKG / 'data/performance/latency-per-question.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['question_id', 'run_part', 'router_ms', 'search_ms', 'filter_slowest_batch_ms', 'planner_ms', 'answerer_ms',
                                      'retrieval_ms', 'answer_ms', 'model_time_ms'])
    w.writeheader(); w.writerows(sorted(rows.values(), key=lambda r: r['question_id']))

# ---------- TypeSafe call latency, cost, wall clock ----------
ts_lat = collections.defaultdict(list)
for run in RUNS.values():
    for stage, d in [('notebook', 'v2/notebook/jev/attempts'), ('relevance filter', 'jev/attempts'), ('timeline', 'v2/view/jev/attempts'), ('targeted checks', 'v2/targeted/jev/attempts')]:
        for f in (run / d).glob('*.json'):
            a = json.loads(f.read_text())
            if a.get('status') == 200 and a.get('latencyMs') is not None: ts_lat[stage].append(float(a['latencyMs']))
judge_lat = []
for part in RUNS:
    for line in gzip.open(PKG / f'bulk/{part}/judge-call-log.jsonl.gz', 'rt'):
        e = json.loads(line)
        if e['event'] == 'response' and e.get('elapsed_seconds') is not None: judge_lat.append(1000 * float(e['elapsed_seconds']))
hive = {p: json.loads((PKG / f'runs/{p}/hive-ledger-summary.json').read_text()) for p in RUNS}
judge = {p: json.loads((PKG / f'runs/{p}/judge-call-log-summary.json').read_text()) for p in RUNS}
ts = {p: json.loads((PKG / f'runs/{p}/typesafe-usage-summary.json').read_text()) for p in RUNS}
hive_list = round(sum(h['list_usd_total'] for h in hive.values()), 2); ts_list = round(sum(t['list_usd_total'] for t in ts.values()), 2)
judge_usd = round(sum(j['cost_usd'] for j in judge.values()), 2)
billed = round(hive_list * 0.53 + ts_list + judge_usd, 2)
def wall(p):   # first start and DONE in the driver log (IST), stops included
    t = re.findall(r'^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]', (PKG / f'runs/{p}/run.log').read_text(), re.M)
    return {'from_ist': t[0], 'to_ist': t[-1]}
perf = {
    'note': 'Computed by tools/performance.py from the logs in this package and the run folders. Latency is provider-measured model '
            'time per call, not batch wall time; see the script header for how a question\'s model time is assembled.',
    'cost': {'hive_list_usd': hive_list, 'hive_billed_usd_approx': round(hive_list * 0.53, 2), 'typesafe_list_usd': ts_list,
             'judge_usd': judge_usd, 'total_billed_usd_approx': billed, 'per_question_billed_usd_approx': round(billed / 700, 3),
             'per_question_list_usd': round((hive_list + ts_list + judge_usd) / 700, 3),
             'one_time_session_notes_list_usd': round(sum(h['by_stage'].get('session_notes (reasoning none)', {}).get('list_usd', 0) for h in hive.values()), 2),
             'note': 'Hive billed about 0.53x list price; TypeSafe and the judge are at list price.'},
    'tokens': {s: {'prompt_tokens': v[0], 'completion_tokens': v[1], 'calls': v[2]} for s, v in tokens.items()},
    'memory_pack_tokens_planner_prompt': dist(planner_prompt, scale=1, nd=0),
    'history_tokens_note': 'BEAM-1M histories are about one million tokens each (1.03-1.09 million on average by the project tokenizer).',
    'model_call_latency_seconds': {s: dist(v) for s, v in stage_lat.items()},
    'typesafe_call_latency_seconds': {s: dist(v) for s, v in ts_lat.items()},
    'judge_call_latency_seconds': dist(judge_lat),
    'per_question_model_time_seconds': {
        'questions_with_every_component': len(complete),
        'router': dist([r['router_ms'] for r in complete]), 'search': dist([r['search_ms'] for r in complete]),
        'relevance_filter_slowest_batch': dist([r['filter_slowest_batch_ms'] for r in complete]),
        'packager_median_used': round(pack_p50 / 1000, 1),
        'planner': dist([r['planner_ms'] for r in complete]), 'answerer': dist([r['answerer_ms'] for r in complete]),
        'total': dist([r['model_time_ms'] for r in complete])},
    'latency_split': {
        'preprocessing': {
            'per_new_session_note_seconds': dist(stage_lat['session notes']),
            'per_new_session_notebook_seconds': dist(ts_lat['notebook']),
            'per_history_cold_minutes': round(sum(json.loads((RUNS['canary-a-part1'] / 'timing.json').read_text())[k] for k in ('ingest', 'notebook')) / 5 / 60, 1),
            'per_history_cold_basis': 'Canary A part 1, fully fresh: notes, index and notebook for 5 histories (4,037 sessions) took '
                                      + str(sum(json.loads((RUNS['canary-a-part1'] / 'timing.json').read_text())[k] for k in ('ingest', 'notebook')))
                                      + ' s at one 4.8-requests-per-second gate; divided by 5.'},
        'query_retrieval_seconds': dist([r['retrieval_ms'] for r in complete]),
        'query_answer_seconds': dist([r['answer_ms'] for r in complete]),
        'query_total_seconds': dist([r['model_time_ms'] for r in complete]),
        'note': 'Pre-processing builds the memory before any question arrives: in live use, a session is noted when it ends. Query time is '
                'what a question costs once its memory exists: retrieval (router, search, relevance filter, packaging) builds the context, '
                'and the planner and answerer write the answer. Cold start, a new history and then its first question, is about the sum.'},
    'wall_clock': {p: wall(p) for p in RUNS},
    'concurrency': {'requests_per_second_to_hive': 4.8, 'max_in_flight': {'canary-a': 64, 'sealed runs': 100}},
}
(PKG / 'data/performance/performance.json').write_text(json.dumps(perf, indent=1) + '\n')
print(json.dumps({k: perf[k] for k in ('cost', 'memory_pack_tokens_planner_prompt', 'per_question_model_time_seconds')}, indent=1))

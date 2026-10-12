"""Build the public LongMemEval-S proof package (memory-public/longmemeval-s/) from the 31 Jul 2026 run (13 Oct 2026).

The run is Architecture 0008's fresh full-500 run on LongMemEval-S. It is kept in the development repository's run
folders, which are not in git:
- runs/full500-from-scratch-20260731T004831Z/: session notes, retrieval, logs, audit, the run's own checksum file;
- runs/arch0008-full500-from-scratch-20260731T004831Z-3/: extraction, answers, judge records.

Published: the answers, the judgments, all 500 judge records (prompt, reply, model, latency), the run's report, manifest
and audit, the per-question latency, the development-exposure analysis, the timeline, and the run's own checksum file.
Withheld, committed by that checksum file: the code, the prompts, the session notes, the retrieval traces, the context
packages and the per-call model I/O.

Usage (private repository root): python3 proof/public/build_longmemeval.py [--out ../memory-public]
"""
import csv, json, pathlib, re, shutil, statistics as st, subprocess, sys, collections, datetime, hashlib, os

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path(sys.argv[sys.argv.index('--out') + 1]).resolve() if '--out' in sys.argv else ROOT.parent / 'memory-public'
PUB = OUT / 'longmemeval-s'
PIPE = ROOT / 'runs/full500-from-scratch-20260731T004831Z'
DOWN = ROOT / 'runs/arch0008-full500-from-scratch-20260731T004831Z-3'
EARLIER = ROOT / 'runs/full500-audit-20260731T002635Z'
CERT = 'src/agents/current/architecture/0008-FULL500-CERTIFICATION-2026-07-31.md'
EVAL_COMMIT = 'd6dc8b50a2d9ac0c99485ea28fa5755c62414c34'
pct = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]
dist = lambda xs, nd=1: {'n': len(xs), 'p50': round(pct(xs, 50), nd), 'p90': round(pct(xs, 90), nd), 'mean': round(st.mean(xs), nd)}
sha = lambda b: hashlib.sha256(b).hexdigest()
def put(rel, data):
    p = PUB / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data if isinstance(data, bytes) else data.encode())
wjson = lambda rel, v: put(rel, json.dumps(v, indent=1, ensure_ascii=False) + '\n')

shutil.rmtree(PUB, ignore_errors=True)

# ---------- the run's own files, byte for byte ----------
for f in ['official-predictions.jsonl', 'judgments.jsonl', 'report.json', 'manifest.json']: put(f'data/run/{f}', (DOWN / f).read_bytes())
for f in ['AUDIT.json', 'SUMMARY.md', 'RUN-MANIFEST.md']: put(f'data/run/{f}', (PIPE / f).read_bytes())
put('data/run/EARLIER-ATTEMPT-RUN-MANIFEST.md', (EARLIER / 'RUN-MANIFEST.md').read_bytes())
for a in sorted((DOWN / 'judge-artifacts').glob('*.json')): put(f'data/judge-artifacts/{a.name}', a.read_bytes())
put('withheld/RUN-SHA256SUMS', (PIPE / 'SHA256SUMS').read_bytes())

# ---------- question types (the internal predictions file carries traces and stays withheld) ----------
types = {}
for line in (DOWN / 'predictions.jsonl').read_text().splitlines():
    r = json.loads(line); types[r['question_id']] = r['question_type']
wjson('data/questions.json', {'note': 'question_id -> question_type for the 500 LongMemEval-S questions; ids ending in _abs are the 30 abstention questions.',
                             'question_types': dict(sorted(types.items()))})

# ---------- dataset and evaluator ----------
man = json.loads((DOWN / 'manifest.json').read_text())
ev_url = f'https://raw.githubusercontent.com/xiaowu0162/LongMemEval/{EVAL_COMMIT}/src/evaluation/evaluate_qa.py'
wjson('data/dataset-and-evaluator.json', {
    'dataset': {'source': 'https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned', 'sha256': man['dataset_hashes'],
                'tree_api': 'https://huggingface.co/api/datasets/xiaowu0162/longmemeval-cleaned/tree/main',
                'oracle_url': 'https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json',
                'licence': 'MIT (github.com/xiaowu0162/LongMemEval)'},
    'evaluator': {'repository': 'https://github.com/xiaowu0162/LongMemEval', 'file': 'src/evaluation/evaluate_qa.py', 'commit': EVAL_COMMIT,
                  'url': ev_url, 'sha256': man['judging']['upstream_evaluator_sha256'],
                  'execution': 'its get_anscheck_prompt prompts, sent unchanged; reply checked with "yes" in reply.lower(), as evaluate_qa.py does'},
    'judge': {'model': man['judging']['model'], 'temperature': man['judging']['temperature'], 'max_tokens': 10}})

# ---------- score, and the split by development exposure ----------
J = {json.loads(l)['question_id']: json.loads(l)['autoeval_label']['label'] for l in (DOWN / 'judgments.jsonl').read_text().splitlines()}
by = collections.defaultdict(list)
for q, t in types.items(): by[t].append(J[q])
abst = [J[q] for q in J if q.endswith('_abs')]
result = {'correct': sum(J.values()), 'accuracy': round(100 * sum(J.values()) / 500, 2), 'task_averaged_accuracy': round(100 * st.mean(sum(v) / len(v) for v in by.values()), 2),
          'abstention_correct': sum(abst), 'abstention_count': len(abst), 'by_type': {t: {'correct': sum(v), 'count': len(v)} for t, v in sorted(by.items())}}
start = datetime.datetime(2026, 7, 31, 0, 48, 31, tzinfo=datetime.timezone.utc).timestamp()   # the final run started
pat = '|'.join(sorted(re.escape(q) for q in J))
out = subprocess.run(['rg', '--no-ignore', '--hidden', '-z', '-o', '-N', '--null', '--no-messages', '-w', '-e', f'(?:{pat})', '-g', '!**/node_modules/**',
                      '-g', '!**/site-packages/**', '-g', '!*full500*', '-g', '!**/*full500*/**', 'runs', 'src'], cwd=ROOT, capture_output=True, text=True).stdout
per = collections.defaultdict(set)
for line in set(out.splitlines()):
    p, _, m = line.partition('\0')
    if m in J: per[p].add(m)
early = {p: v for p, v in per.items() if (ROOT / p).exists() and (ROOT / p).stat().st_mtime < start}
sweeps = sorted(p for p, v in early.items() if len(v) >= 400)
dev = sorted(set().union(*[v for p, v in early.items() if len(v) < 400]))
never = sorted(set(J) - set(dev))
by_exposure = {'development': [sum(J[q] for q in dev), len(dev)], 'never_named': [sum(J[q] for q in never), len(never)]}
wjson('data/exposure.json', {
    'summary': 'LongMemEval-S has no held-out set in this project. All 500 questions were used at the retrieval level by recall sweeps on '
               '25-26 Jul 2026; the questions named in answer-level development subsets before the final run are listed below.',
    'method': 'Full-text search of every project record dated before the final run (2026-07-31T00:48:31Z) for the 500 question ids. Files that name '
              '400 or more ids are whole-benchmark retrieval sweeps; every id named in a smaller file counts as answer-level development.',
    'retrieval_sweeps_over_all_500': [{'file': p, 'modified_utc': datetime.datetime.fromtimestamp((ROOT / p).stat().st_mtime, tz=datetime.timezone.utc).isoformat(timespec='minutes')} for p in sweeps],
    'earlier_attempt': '22 minutes before the final run, an attempt started with the existing session notes and ran retrieval for all 500 questions. '
                       'It stopped before answering; no answer from it was judged. The final run re-built every session note from scratch and reused '
                       'nothing from it (data/run/EARLIER-ATTEMPT-RUN-MANIFEST.md, data/run/RUN-MANIFEST.md).',
    'answer_level_development_ids': dev, 'never_named_ids': never})

# ---------- performance ----------
audit = json.loads((PIPE / 'AUDIT.json').read_text())
rows = []
for f in sorted((PIPE / 'retrieval-cases').glob('*.json')):
    c = json.loads(f.read_text()); q = c['question_id']
    r_ms = sum(float(x.get('latency_ms') or 0) for x in (c.get('model_io') or []))   # facet planning, then admission
    io = json.loads((DOWN / f'agent-artifacts/cases/{q}/model-io.json').read_text())
    ext = [float(x['latency_ms']) for x in io if x['role'] == 'session_extract']   # extraction runs in parallel, one call per session
    ans = [float(x['latency_ms']) for x in io if x['role'] == 'answer']
    rows.append({'question_id': q, 'retrieval_ms': round(r_ms, 1), 'extraction_slowest_ms': round(max(ext), 1) if ext else 0.0,
                 'answer_ms': round(ans[0], 1), 'model_time_ms': round(r_ms + (max(ext) if ext else 0.0) + ans[0], 1)})
# pre-processing: one note per session (logged per session); a question's history is ready when its slowest note is done
note = {}
for folder in ('storer-audit', 'storer-repair-audit'):   # a repaired session's note is the one that was kept
    for f in (PIPE / folder).glob('*.json'):
        d = json.loads(f.read_text())
        if isinstance(d, dict) and d.get('latency_ms') is not None: note[d['session_id']] = float(d['latency_ms'])
with open(PUB / 'data/note-latency-per-session.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['session_id', 'note_ms']); w.writerows(sorted((k, round(v, 1)) for k, v in note.items()))
hist = {d['question_id']: d['haystack_session_ids'] for d in json.loads((ROOT / 'data/raw/longmemeval_s_cleaned.json').read_text())}
assert all(s_ in note for ids in hist.values() for s_ in ids), 'every history session has a logged note'
for r in rows:
    ids = hist[r['question_id']]
    r['retrieval_total_ms'] = round(r['retrieval_ms'] + r['extraction_slowest_ms'], 1)
    r['history_sessions'] = len(ids); r['preprocessing_history_ms'] = round(max(note[x] for x in ids), 1)
    r['cold_start_ms'] = round(r['preprocessing_history_ms'] + r['model_time_ms'], 1)
with open(PUB / 'data/latency-per-question.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
rep = json.loads((DOWN / 'report.json').read_text())
u, c = audit['usage'], audit['estimated_cost_usd']
perf = {
    'note': 'Model time is the provider-measured latency of the calls on a question\'s path: retrieval (facet planning, then admission), the slowest '
            'of its parallel per-session extraction calls, and the answer. It excludes building the session notes, which LongMemEval-S needs '
            'once per question history.',
    'cost': {'list_usd_total': round(c['core_pipeline_total'], 2), 'per_question_list_usd': round(c['core_pipeline_total'] / 500, 3),
             'by_stage_list_usd': {'session notes': round(c['storer'], 2), 'retrieval': round(c['retrieval'], 2),
                                   'extraction and answer': round(c['extraction_and_answer'], 2), 'judge': round(c['judge'], 2)},
             'basis': c['pricing_note'] + ' Computed from logged tokens; provider bills may differ.'},
    'tokens': {'total': u['core_pipeline']['total_tokens'], 'api_calls': u['core_pipeline']['api_calls'],
               'answer_context_tokens_per_question_mean': round(rep['usage']['by_role']['answer']['input_tokens'] / 500)},
    'elapsed_minutes': {'session notes (19,195 sessions)': round(u['storer']['elapsed_ms'] / 60000, 2), 'retrieval': round(u['retrieval']['elapsed_ms'] / 60000, 2),
                        'extraction and answer': round(u['downstream']['elapsed_ms'] / 60000, 2), 'judge': round(u['judge']['elapsed_ms'] / 60000, 2),
                        'total': round(sum(u[k]['elapsed_ms'] for k in ('storer', 'retrieval', 'downstream', 'judge')) / 60000, 1)},
    'concurrency': {'requests_in_flight': 256, 'tokens_per_minute_budget': audit['limits']['model_token_budget_per_60_seconds']},
    'per_question_model_time_seconds': dist([r['model_time_ms'] / 1000 for r in rows]),
    'per_question_components_seconds': {'retrieval': dist([r['retrieval_ms'] / 1000 for r in rows]),
                                         'extraction_slowest_call': dist([r['extraction_slowest_ms'] / 1000 for r in rows]),
                                         'answer': dist([r['answer_ms'] / 1000 for r in rows])},
    'latency_split': {
        'preprocessing': {'per_new_session_note_seconds': dist([v / 1000 for v in note.values()]),
                          'per_history_parallel_seconds': dist([r['preprocessing_history_ms'] / 1000 for r in rows]),
                          'sessions_per_history': dist([r['history_sessions'] for r in rows], nd=0),
                          'all_19195_sessions_minutes': round(u['storer']['elapsed_ms'] / 60000, 2)},
        'query_retrieval_seconds': dist([r['retrieval_total_ms'] / 1000 for r in rows]),
        'query_answer_seconds': dist([r['answer_ms'] / 1000 for r in rows]),
        'query_total_seconds': dist([r['model_time_ms'] / 1000 for r in rows]),
        'cold_start_seconds': dist([r['cold_start_ms'] / 1000 for r in rows]),
        'note': 'Pre-processing writes one note per session before any question; a history is ready when its slowest note is done (notes run '
                'in parallel). Query time is retrieval (facet planning, admission, per-session extraction) plus the answer. Cold start is a '
                'new history and then its first question.'},
    'history_tokens_note': 'LongMemEval-S gives each question a history of about 115,000 tokens (about 50 sessions).'}
wjson('data/performance.json', perf)

# ---------- timeline: the result reached GitHub minutes after the run ----------
commit = subprocess.run(['git', 'log', '--diff-filter=A', '--format=%H', '--', CERT], cwd=ROOT, capture_output=True, text=True).stdout.split()[-1]
log = json.loads((ROOT / 'proof/BEAM-1M-R9-final-20261012/data/questions/github-push-log.json').read_text())['events']
first = next(e for e in sorted(log, key=lambda e: e['timestamp'])
             if subprocess.run(['git', 'merge-base', '--is-ancestor', commit, e['after']], cwd=ROOT, capture_output=True).returncode == 0)
arch = json.loads((ROOT / 'proof/BEAM-1M-R9-final-20261012/data/questions/independent-archives.json').read_text())
wjson('data/timeline.json', {
    'run_started_utc': '2026-07-31T00:48:31Z', 'run_completed_utc': man['completed_at'], 'judging_completed_utc': man['judging']['completed_at'],
    'result_commit': commit, 'result_document': CERT, 'first_push_containing_result': first,
    'wayback_push_log': next(x['snapshot'] for x in arch['archives'] if x['what'] == 'push log'),
    'note': "GitHub's server-side push log (saved copy in ../beam-1m/data/questions/github-push-log.json; a Wayback Machine copy is linked above) "
            'shows the commit that records 457/500 on GitHub minutes after the judge finished.'})
put('data/certification-2026-07-31.md', subprocess.run(['git', 'show', f'{commit}:{CERT}'], cwd=ROOT, capture_output=True, check=True).stdout)

# ---------- claims, documents, verifier, manifest ----------
wjson('claims.json', {'claim': 'LongMemEval-S, all 500 questions, Architecture 0008, one fresh run on 31 Jul 2026, judged by gpt-4o-2024-08-06 with LongMemEval\'s own prompts',
                      'result': result, 'by_exposure': by_exposure, 'performance': {k: perf[k] for k in ('cost', 'per_question_model_time_seconds', 'elapsed_minutes')}})
put('verify/verify.py', (HERE / 'templates/longmemeval-verify.py').read_bytes())
put('verify/LICENSE', (ROOT / 'LICENSE').read_bytes())
put('tools/build_longmemeval.py', pathlib.Path(__file__).read_bytes())
put('withheld/README.md', (HERE / 'templates/longmemeval-withheld.md').read_text())
readme = (HERE / 'templates/longmemeval-README.md').read_text()
L_ = perf['latency_split']
fill = {'__PRE_S50__': f"{L_['preprocessing']['per_new_session_note_seconds']['p50']:.1f}", '__PRE_S90__': f"{L_['preprocessing']['per_new_session_note_seconds']['p90']:.1f}",
        '__PRE_H50__': f"{L_['preprocessing']['per_history_parallel_seconds']['p50']:.1f}", '__PRE_H90__': f"{L_['preprocessing']['per_history_parallel_seconds']['p90']:.1f}",
        '__RET50__': f"{L_['query_retrieval_seconds']['p50']:.1f}", '__RET90__': f"{L_['query_retrieval_seconds']['p90']:.1f}",
        '__ANS50__': f"{L_['query_answer_seconds']['p50']:.1f}", '__ANS90__': f"{L_['query_answer_seconds']['p90']:.1f}",
        '__COLD50__': f"{L_['cold_start_seconds']['p50']:.1f}", '__COLD90__': f"{L_['cold_start_seconds']['p90']:.1f}",
        '__ALLNOTES__': f"{L_['preprocessing']['all_19195_sessions_minutes']:.1f}",
        '__ACC__': f"{result['accuracy']:.2f}", '__CORRECT__': str(result['correct']), '__TASKAVG__': f"{result['task_averaged_accuracy']:.2f}",
        '__NEVER__': f"{by_exposure['never_named'][0]}/{by_exposure['never_named'][1]}",
        '__NEVERPCT__': f"{100 * by_exposure['never_named'][0] / by_exposure['never_named'][1]:.2f}",
        '__DEV__': f"{by_exposure['development'][0]}/{by_exposure['development'][1]}",
        '__DEVPCT__': f"{100 * by_exposure['development'][0] / by_exposure['development'][1]:.2f}",
        '__COST__': f"{perf['cost']['list_usd_total']:.2f}", '__CPQ__': f"{perf['cost']['per_question_list_usd']:.3f}",
        '__P50__': f"{perf['per_question_model_time_seconds']['p50']:.1f}", '__P90__': f"{perf['per_question_model_time_seconds']['p90']:.1f}",
        '__TOTALMIN__': f"{perf['elapsed_minutes']['total']:.1f}", '__CTX__': f"{perf['tokens']['answer_context_tokens_per_question_mean']:,}",
        '__PUSH__': first['timestamp'], '__DONE__': man['judging']['completed_at'][:19] + 'Z'}
for k, v in fill.items():
    assert k in readme, k; readme = readme.replace(k, v)
for t, v in result['by_type'].items():
    readme = readme.replace(f'__T:{t}__', f"{v['correct']}/{v['count']} ({100 * v['correct'] / v['count']:.2f}%)")
assert '__' not in re.sub(r'`[^`]*`', '', readme), 'unfilled placeholder in the README'
put('README.md', readme)
lines = [f'{sha(p.read_bytes())}  {p.relative_to(PUB).as_posix()}' for p in sorted(PUB.rglob('*')) if p.is_file() and p.name != 'MANIFEST.sha256']
put('MANIFEST.sha256', '\n'.join(lines) + '\n')
r = subprocess.run([sys.executable, str(PUB / 'verify/verify.py')], capture_output=True, text=True)
print('\n'.join(l for l in r.stdout.splitlines() if l.startswith(('FAIL', 'LongMem')) or 'checks passed' in l))
sys.exit(r.returncode)

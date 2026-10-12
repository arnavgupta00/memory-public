"""Build the BEAM-1M proof package from the run folders (12 Oct 2026).

This script is included in the package so that every derived file can be traced back to its source. It reads the
project's run folders (`runs/`, mostly git-ignored), extracts the evidence and writes `data/`, `runs/`, `code/` and `bulk/`. It
never edits a source file. The narrative documents (README, CLAIMS, ...) are written separately; `claims.json` and the
results tables are generated here from the data.

Usage (repository root): python3 proof/BEAM-1M-R9-final-20261012/tools/build_package.py
"""
import csv, gzip, hashlib, io, json, os, re, shutil, statistics as st, subprocess, tarfile, collections, pathlib, datetime

ROOT = pathlib.Path('/Users/arnav/programming/projects/memory')
PKG = ROOT / 'proof/BEAM-1M-R9-final-20261012'
RUNS = ROOT / 'runs'
CUR = ROOT / 'src/agents/current'
SLICES = CUR / 'eval-slices/beam-1m'
AMB = RUNS / 'amb-judge-20261012'
ABILITIES = ['abstention', 'contradiction_resolution', 'event_ordering', 'information_extraction', 'instruction_following',
             'knowledge_update', 'multi_session_reasoning', 'preference_following', 'summarization', 'temporal_reasoning']
EXPANSION = {7, 16, 21, 34}
# The four run parts that make up the 700 answers. Canary A uses R9's original answer run (two parts, same configuration).
PARTS = {
    'canary-a-part1': {'run': 'a6/canary-a-screen20-hive-r9', 'meta': 'a6/canary-a-screen20-hive-r9/hive', 'ledger': 'a6/canary-a-screen20-hive-r9/hive/ledger.jsonl'},
    'canary-a-part2': {'run': 'a6/canary-a-other80-hive-r9', 'meta': 'a6/canary-a-other80-hive-r9/hive', 'ledger': 'a6/canary-a-other80-hive-r9/hive/ledger.jsonl'},
    'canary-b': {'run': 'canary-b-r9-20261011/canary-b', 'meta': 'canary-b-r9-20261011', 'ledger': 'canary-b-r9-20261011/evidence/hive-ledger.jsonl'},
    'remaining-340': {'run': 'final-700-r9-20261012/remaining-340', 'meta': 'final-700-r9-20261012', 'ledger': 'final-700-r9-20261012/evidence/hive-ledger.jsonl'},
}
sha = lambda b: hashlib.sha256(b).hexdigest()
fsha = lambda p: sha(pathlib.Path(p).read_bytes())
cn = lambda q: q.replace('/', '__')
def wjson(p, v, gz=False):
    p = PKG / p; p.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(v, indent=1, ensure_ascii=False) + '\n').encode()
    if gz: p.write_bytes(gzip.compress(data, mtime=0))
    else: p.write_bytes(data)
def wjsonl(p, rows, gz=False):
    p = PKG / p; p.parent.mkdir(parents=True, exist_ok=True)
    data = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows).encode()
    p.write_bytes(gzip.compress(data, mtime=0) if gz else data)
def copy(src, dst):
    src, dst = pathlib.Path(src), PKG / dst
    if not src.exists(): return False
    dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst); return True
def gzcopy(src, dst):
    src, dst = pathlib.Path(src), PKG / dst
    if not src.exists(): return False
    dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(gzip.compress(src.read_bytes(), mtime=0)); return True
def partition_of(qid):
    n = int(qid.split('/')[1].split('-')[1])
    if n in {3, 8, 18, 25, 29}: return 'canary_a'
    if n in {1, 2, 9, 10, 12, 14, 17, 22, 24, 26, 27, 30, 35}: return 'canary_b'
    return 'expansion' if n in EXPANSION else 'fresh75'
PARTITION_INFO = {'canary_a': 'development set since the 1 Aug 2026 split (seen during development)',
                  'canary_b': 'sealed certification set since the 1 Aug 2026 split (never inspected before its run on 11 Oct)',
                  'fresh75': 'development histories: final-blind reserve in the 1 Aug plan, reallocated to development on 24 Sep 2026, when the '
                             'Fresh75 development set was drawn from them (seen during development)',
                  'expansion': 'sealed expansion block: precommitted on 1 Aug 2026 and kept sealed by the 24 Sep allocation (never inspected before '
                               'its run on 12 Oct)'}
# Every file that defined or changed the split, in date order. The 1 Aug files are the original plan; the 24 Sep allocation
# record supersedes the final-blind status of the 13 Fresh75 histories. holdout40 (8 Aug) lists 40 reserve questions that were
# never run; later experiments read it only as an exclusion list.
SPLIT_FILES = ['beam-1m-canary-design-v1.json', 'beam-1m-canary-a-development-v1.json', 'beam-1m-canary-b-certification-v1.json',
               'beam-1m-blind-reserve-v1.json', 'beam-1m-compression-holdout40-v1.json', 'beam-1m-jev-fresh75-development-v1.json',
               'beam-1m-holdout-allocation-20260924.json']
REPO_API = 'https://api.github.com/repos/arnavgupta00/memory/activity?per_page=100'
FREEZE_COMMIT = '595a2e28228c21cf842378fb9216cacb46478fd3'
git = lambda *a: subprocess.run(['git', *a], cwd=ROOT, capture_output=True, text=True)
frozen_hash = lambda files: sha(json.dumps(files, separators=(',', ':'), ensure_ascii=False).encode())   # as run.mjs: sha256(JSON.stringify(files))

# ---------- 1. questions, partitions, official source ----------
part_of_q, run_of_q = {}, {}
for part, cfg in PARTS.items():
    for l in open(RUNS / cfg['run'] / 'predictions.jsonl'):
        q = json.loads(l)['question_id']; assert q not in part_of_q, q; part_of_q[q] = part; run_of_q[q] = cfg['run']
all_ids = [f'beam-1m/chat-{n:02d}/{a}/{i}' for n in range(1, 36) for a in ABILITIES for i in (1, 2)]
assert sorted(part_of_q) == sorted(all_ids), 'the 700 answers must be exactly the BEAM-1M question set'
partition = {q: partition_of(q) for q in all_ids}
# GitHub's own server-side log of pushes to the public repository (not editable by the repository owner): it dates when each
# commit was first on GitHub, independently of the commit's self-reported date.
import urllib.request
activity = json.load(urllib.request.urlopen(REPO_API, timeout=60))
pushes = sorted(({'timestamp': e['timestamp'], 'activity_type': e['activity_type'], 'ref': e['ref'], 'before': e['before'], 'after': e['after']}
                 for e in activity), key=lambda e: e['timestamp'])
wjson('data/questions/github-push-log.json', {'source': REPO_API, 'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
      'note': "GitHub's server-side activity log for the public repository; anyone can fetch it again from the source URL.", 'events': pushes})
def on_github_by(commit):   # the first logged push whose new tip contains the commit
    for e in pushes:
        if git('merge-base', '--is-ancestor', commit, e['after']).returncode == 0: return {'utc': e['timestamp'], 'push': e}
    return None
split_files = {}
for f in SPLIT_FILES:
    first = git('log', '--diff-filter=A', '--format=%H %cI', '--', str(SLICES / f)).stdout.strip().splitlines()[-1].split()
    split_files[f] = {'sha256': fsha(SLICES / f), 'first_commit': first[0], 'first_commit_date_self_reported': first[1],
                      'on_github_by_utc': (on_github_by(first[0]) or {}).get('utc')}
    copy(SLICES / f, f'data/questions/partition-files/{f}')
wjson('data/questions/partition.json', {
    'benchmark': 'BEAM 1M tier: 35 conversations x 10 abilities x 2 questions = 700',
    'partitions': {k: {'meaning': PARTITION_INFO[k], 'conversations': sorted({int(q.split('/')[1][5:]) for q in all_ids if partition[q] == k}),
                       'questions': sum(1 for q in all_ids if partition[q] == k)} for k in PARTITION_INFO},
    'split_history': [
        {'date': '2026-08-01', 'event': 'Seeded split of the 35 histories on metadata only (no question text, answers or rubrics): Canary A '
                                        'development (5), Canary B sealed certification (13), blind reserve (17 = 13 final-blind + 4 precommitted '
                                        'expansion: 16, 21, then 7, 34).',
         'files': SPLIT_FILES[:4]},
        {'date': '2026-08-08', 'event': 'A 40-question compression holdout was listed from the reserve (10 of its questions are from expansion '
                                        'histories). It was never run; later experiments read it only as an exclusion list.', 'files': [SPLIT_FILES[4]]},
        {'date': '2026-09-24', 'event': 'Allocation approved: the 13 final-blind histories became development data (the Fresh75 development set was '
                                        'drawn from them). Canary B and the 4 expansion histories stayed sealed: 340 independent questions remain.',
         'files': SPLIT_FILES[5:]},
        {'date': '2026-10-11', 'event': 'Canary B (260) run once with the frozen R9 configuration.'},
        {'date': '2026-10-12', 'event': 'The remaining 340 (Fresh75 histories + expansion) run once with the same configuration.'}],
    'split_files': split_files,
    'question_ids': {q: {'partition': partition[q], 'run_part': part_of_q[q]} for q in all_ids},
})
records = {}
for f in ['beam-1m-canary-a-development-v1.json', 'beam-1m-canary-b-certification-v1.json', 'beam-1m-blind-reserve-v1.json']:
    for r in json.load(open(SLICES / f))['source_records']: records[int(r['conversation_id'])] = r
# BEAM's own content addresses: the git blob SHA-1 of every file in its tree at the pinned commit (same as GitHub's API "sha")
BEAM_COMMIT = '3e12035532eb85768f1a7cd779832b650c4b2ef9'
blob = lambda b: hashlib.sha1(b'blob %d\0' % len(b) + b).hexdigest()
tree = {}
for line in git('-C', str(RUNS / '.beam-official-source'), 'ls-tree', '-r', BEAM_COMMIT, '--', 'chats/1M').stdout.splitlines():
    meta, path = line.split('\t'); tree[path] = meta.split()[2]
source = {}
for q in all_ids:
    n = int(q.split('/')[1][5:])
    if n in source: continue
    base = RUNS / run_of_q[q] / 'source/chats/1M' / str(n)
    cb, pb = (base / 'chat.json').read_bytes(), (base / 'probing_questions/probing_questions.json').read_bytes()
    c, p = sha(cb), sha(pb)
    source[n] = {'chat_sha256': c, 'probing_questions_sha256': p, 'split_file_chat_sha256': records[n]['chat_sha256'],
                 'split_file_probing_questions_sha256': records[n]['probing_questions_sha256'],
                 'chat_git_blob_sha1': blob(cb), 'probing_questions_git_blob_sha1': blob(pb),
                 'beam_tree_chat_blob_sha1': tree[f'chats/1M/{n}/chat.json'], 'beam_tree_probing_questions_blob_sha1': tree[f'chats/1M/{n}/probing_questions/probing_questions.json'],
                 'match': c == records[n]['chat_sha256'] and p == records[n]['probing_questions_sha256']
                          and blob(cb) == tree[f'chats/1M/{n}/chat.json'] and blob(pb) == tree[f'chats/1M/{n}/probing_questions/probing_questions.json']}
assert all(v['match'] for v in source.values()), 'downloaded BEAM files must match BEAM\'s git tree and the split-file checksums'
wjson('data/questions/official-source-manifest.json', {'repository': 'https://github.com/mohammadtavakoli78/BEAM', 'commit': BEAM_COMMIT,
      'license': 'MIT', 'files': 'chats/1M/<n>/chat.json and chats/1M/<n>/probing_questions/probing_questions.json',
      'how_matched': 'Each file used by the runs has (a) the git blob SHA-1 recorded in BEAM\'s own tree at the pinned commit (check without cloning: '
                     'https://api.github.com/repos/mohammadtavakoli78/BEAM/contents/chats/1M/<n>?ref=<commit>, field "sha"), and (b) the sha256 '
                     'recorded in our split files when the split was made (1 Aug 2026).',
      'all_35_match': True, 'conversations': {str(k): v for k, v in sorted(source.items())}})

# ---------- 2. answers, plans, predictions as judged ----------
answers, plans = [], []
for q in all_ids:
    run = RUNS / run_of_q[q]
    a = json.load(open(run / 'answer/responses' / f'{cn(q)}.json')); p = json.load(open(run / 'plan/responses' / f'{cn(q)}.json'))
    text = a['output_text']
    answers.append({'question_id': q, 'partition': partition[q], 'run_part': part_of_q[q], 'answer': text, 'answer_sha256': sha(text.encode()),
                    'answer_usage': a.get('usage'), 'plan_usage': p.get('usage')})
    plans.append({'question_id': q, 'plan': p.get('parsed')})
for part, cfg in PARTS.items():   # the exact files the official judge read
    preds = [json.loads(l) for l in open(RUNS / cfg['run'] / 'predictions.jsonl')]
    by = {r['question_id']: r['hypothesis'] for r in preds}
    for r in answers:
        if r['run_part'] == part: assert by[r['question_id']] == r['answer'], f'answer mismatch {r["question_id"]}'
    copy(RUNS / cfg['run'] / 'predictions.jsonl', f'data/answers/predictions-as-judged/{part}.predictions.jsonl')
    copy(RUNS / cfg['run'] / 'cohort.json', f'data/answers/predictions-as-judged/{part}.cohort.json')
assert sum(1 for r in answers if not r['answer'].strip()) == 0
wjsonl('data/answers/answers.jsonl', answers)
wjsonl('data/plans/plans.jsonl.gz', plans, gz=True)

# ---------- 3. official judge outputs, per-question scores ----------
judge_rows = {}
for part, cfg in PARTS.items():
    J = json.load(open(RUNS / cfg['run'] / 'judge/judge.json')); copy(RUNS / cfg['run'] / 'judge/judge.json', f'data/judge/{part}.judge.json')
    assert J['status'] == 'completed'
    for r in J['rows']: judge_rows[r['question_id']] = r
assert sorted(judge_rows) == sorted(all_ids)
items = lambda r: [float(x['score']) for x in (r['official_result'].get('llm_judge_responses') or [])]
def official_pinned(r):   # exactly the pinned evaluator: event ordering = tau_norm; otherwise mean of int(item score)
    if r['ability'] == 'event_ordering': return r['official_result']['tau_norm']
    it = r['official_result'].get('llm_judge_responses') or []
    return sum(int(float(x['score'])) for x in it) / len(it)
def half_credit(r):
    return r['official_result']['tau_norm'] if r['ability'] == 'event_ordering' else st.mean(items(r))
def rubric_avg(r):
    return r['official_result']['llm_judge_score'] if r['ability'] == 'event_ordering' else st.mean(items(r))
for q, r in judge_rows.items():
    assert abs(official_pinned(r) - r['score']) < 1e-9, f'recomputed official score differs for {q}'
amb = {}
for f in ['score-gemini-3.5-flash-lite.json', 'score-gemini-3.5-flash-lite-remaining340.json']:
    for r in json.load(open(AMB / f))['rows']:
        if r['question_id'] in part_of_q and (f.endswith('remaining340.json') or r['set'] in ('canary-a', 'canary-b')): amb[r['question_id']] = r['score']
assert sorted(amb) == sorted(all_ids)
pf = {r['question_id']: r['correct'] for r in json.load(open(AMB / 'results.json'))['rows']}
scores = []
for q in all_ids:
    r = judge_rows[q]
    scores.append({'question_id': q, 'conversation': int(q.split('/')[1][5:]), 'ability': r['ability'], 'partition': partition[q], 'run_part': part_of_q[q],
                   'official_pinned': round(r['score'], 6), 'official_half_credit': round(half_credit(r), 6), 'rubric_average_beam_judge': round(rubric_avg(r), 6),
                   'vectorize_rubric_average': round(amb[q], 6), 'vectorize_pass_fail': ('' if q not in pf else int(pf[q]))})
(PKG / 'data/scores').mkdir(parents=True, exist_ok=True)
with open(PKG / 'data/scores/scores.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(scores[0])); w.writeheader(); w.writerows(scores)
mean = lambda xs: 100 * st.mean(xs)
groups = {'ALL 700': all_ids, 'Canary A (100, development)': [q for q in all_ids if partition[q] == 'canary_a'],
          'Canary B (260, sealed)': [q for q in all_ids if partition[q] == 'canary_b'], 'Fresh75 histories (260, development)': [q for q in all_ids if partition[q] == 'fresh75'],
          'Expansion (80, sealed)': [q for q in all_ids if partition[q] == 'expansion'], 'Unseen: Canary B + expansion (340)': [q for q in all_ids if partition[q] in ('canary_b', 'expansion')],
          'Remaining 340 run (Fresh75 + expansion)': [q for q in all_ids if part_of_q[q] == 'remaining-340']}
S = {s['question_id']: s for s in scores}
def agg(ids, key): return round(mean([S[q][key] for q in ids]), 2)
results = {g: {'questions': len(ids), 'official_pinned': agg(ids, 'official_pinned'), 'official_half_credit': agg(ids, 'official_half_credit'),
               'rubric_average_beam_judge': agg(ids, 'rubric_average_beam_judge'), 'vectorize_rubric_average': agg(ids, 'vectorize_rubric_average')} for g, ids in groups.items()}
by_ability = {a: {k: round(mean([S[q][k] for q in all_ids if S[q]['ability'] == a]), 1) for k in ['official_pinned', 'official_half_credit', 'rubric_average_beam_judge', 'vectorize_rubric_average']} for a in ABILITIES}
conv = collections.defaultdict(list)
for q in all_ids: conv[S[q]['conversation']].append(q)
conv_rows = [{'conversation': n, 'partition': partition[ids[0]], 'questions': len(ids), 'official_pinned': round(mean([S[q]['official_pinned'] for q in ids]), 2),
              'vectorize_rubric_average': round(mean([S[q]['vectorize_rubric_average'] for q in ids]), 2)} for n, ids in sorted(conv.items())]
with open(PKG / 'data/scores/conversations.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(conv_rows[0])); w.writeheader(); w.writerows(conv_rows)
cs = [c['official_pinned'] for c in conv_rows]
pf_ids = [q for q in all_ids if q in pf]

# ---------- 4. comparison data (ours + competitors' published numbers, with sources) ----------
wjsonl('data/comparison/vectorize-rubric-average-per-question.jsonl', [{'question_id': q, 'score': amb[q]} for q in all_ids])
wjsonl('data/comparison/vectorize-pass-fail-per-question.jsonl', [{'question_id': q, 'correct': pf[q]} for q in pf_ids])
copy(AMB / 'amb_score.py', 'data/comparison/scripts-as-run/amb_score.py'); copy(AMB / 'amb_judge.py', 'data/comparison/scripts-as-run/amb_judge.py')
copy(AMB / 'README.md', 'data/comparison/scripts-as-run/README-as-run.md')

# ---------- 5. run provenance ----------
def ledger_summary(path):
    ev = [json.loads(l) for l in open(path)]; resp = [e for e in ev if e.get('event') == 'hive_response']
    def stage(e):
        if str(e.get('requested_model', '')).startswith('gpt-5.4-nano'): return 'session_notes (reasoning none)'
        if e.get('effort_used') == 'low': return 'router_search_targeted (reasoning low)'
        if e.get('effort_used') == 'none': return 'packager_discarded_answer (reasoning none)'
        return 'planner_answerer (reasoning max)'
    by = collections.defaultdict(lambda: {'calls': 0, 'list_usd': 0.0, 'prompt_tokens': 0, 'completion_tokens': 0})
    for e in resp:
        b = by[stage(e)]; b['calls'] += 1; b['list_usd'] += e.get('cost_usd') or 0; b['prompt_tokens'] += e['usage'].get('prompt_tokens', 0); b['completion_tokens'] += e['usage'].get('completion_tokens', 0)
    return {'model': 'deepseek-ai/deepseek-v4.1-flash (Hive)', 'events': dict(collections.Counter(e.get('event') for e in ev)),
            'responses': len(resp), 'zero_output_responses': sum((e['usage'].get('completion_tokens') or 0) == 0 for e in resp),
            'discarded_answer_trims': sum(e.get('event') == 'discarded_answer_trimmed' for e in ev),
            'http_errors_retried': dict(collections.Counter(str(e.get('http_status')) for e in ev if e.get('event') == 'hive_error')),
            'list_usd_total': round(sum(e.get('cost_usd') or 0 for e in resp), 2), 'by_stage': {k: {**v, 'list_usd': round(v['list_usd'], 2)} for k, v in by.items()},
            'pricing_note': 'list price $0.30 / $1.20 per 1M tokens; Hive billed about 0.53x list in practice'}
def judge_log_summary(path):
    ev = [json.loads(l) for l in open(path)]
    return {'dispatch': sum(e['event'] == 'dispatch' for e in ev), 'response': sum(e['event'] == 'response' for e in ev), 'failure': sum(e['event'] == 'failure' for e in ev),
            'cost_usd': round(sum(e.get('cost_usd') or 0 for e in ev if e['event'] == 'response'), 2), 'model': 'gpt-4.1-mini, temperature 0'}
run_meta = {}
for part, cfg in PARTS.items():
    run, meta = RUNS / cfg['run'], RUNS / cfg['meta']
    for f in ['manifest.json', 'timing.json', 'cohort.json', 'score.json', 'SEEDED-FROM.json', 'v2/routes.json', 'jev/accounting.json', 'jev/forecast.json', 'judge.log']:
        copy(run / f, f'runs/{part}/pipeline-run/{f}')
    for f in ['README.md', 'run.log', 'pipeline.log', 'STATUS', 'FINAL-700.txt', 'score-official.txt', 'score-secondary.txt', 'score-remaining-340.txt', 'run.sh',
              'sha256.txt', 'frozen-verify.txt', 'git-head.txt', 'git-status.txt', 'proxy.log']:
        copy(meta / f, f'runs/{part}/{f}')
    for sub in ['scripts', 'evidence']:
        if (meta / sub).exists():
            for p in sorted((meta / sub).iterdir()):
                if p.is_file() and p.name != 'hive-ledger.jsonl': copy(p, f'runs/{part}/{sub}/{p.name}')
    if part.startswith('canary-a'):   # the question lists their run.sh names (sha256 recorded in runs/<part>/sha256.txt)
        qlist = {'canary-a-part1': 'haiku_screen20_canary_a.json', 'canary-a-part2': 'canary_a_other80.json'}[part]
        copy(RUNS / 'expert-review-20260927/analysis' / qlist, f'runs/{part}/scripts/{qlist}')
    wjson(f'runs/{part}/hive-ledger-summary.json', ledger_summary(RUNS / cfg['ledger']))
    ts = {}   # TypeSafe usage per stage, from the per-attempt records (input tokens at $0.042 per million; output is free)
    for stage, d in [('notebook (3)', 'v2/notebook/jev/attempts'), ('relevance filter (8)', 'jev/attempts'),
                     ('timeline (9)', 'v2/view/jev/attempts'), ('targeted checks (9)', 'v2/targeted/jev/attempts')]:
        n = tok = no_usage = 0
        for p in (run / d).glob('*.json'):
            a = json.load(open(p)); n += 1
            u = (json.loads(a.get('rawBody') or '{}') if a.get('status') == 200 else {}).get('usage') or {}
            t = u.get('input_tokens') or u.get('inputTokens') or u.get('prompt_tokens')
            if t is None: no_usage += 1
            else: tok += t
        ts[stage] = {'attempts': n, 'input_tokens': tok, 'attempts_without_usage': no_usage, 'list_usd': round(tok * 0.042 / 1e6, 4)}
    wjson(f'runs/{part}/typesafe-usage-summary.json', {'model': 'jev-1.13.0 (TypeSafe)', 'price': '$0.042 per 1M input tokens (docs.typesafe.ai/models)',
          'by_stage': ts, 'list_usd_total': round(sum(v['list_usd'] for v in ts.values()), 4)})
    wjson(f'runs/{part}/judge-call-log-summary.json', judge_log_summary(run / 'judge/judge-attempts.jsonl'))
    # bulk: full ledgers, judge call logs, stage logs, router/search outputs, memory packs
    gzcopy(RUNS / cfg['ledger'], f'bulk/{part}/hive-ledger.jsonl.gz')
    gzcopy(run / 'judge/judge-attempts.jsonl', f'bulk/{part}/judge-call-log.jsonl.gz')
    gzcopy(run / 'retrieval.json', f'bulk/{part}/search-retrieval.json.gz')
    if (run / 'logs').exists():
        for p in sorted((run / 'logs').glob('*.log')): gzcopy(p, f'bulk/{part}/stage-logs/{p.name}.gz')
    tpath = PKG / f'bulk/{part}/memory-packs.tar.gz'; tpath.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tpath, 'w:gz') as t:
        for p in sorted((run / 'context').glob('*.json')):
            info = t.gettarinfo(str(p), arcname=f'memory-packs/{p.name}'); info.mtime = 0; info.uid = info.gid = 0; info.uname = info.gname = ''
            with open(p, 'rb') as fh: t.addfile(info, fh)
    m = json.load(open(run / 'manifest.json'))
    run_meta[part] = {'run_folder': f'runs/{cfg["run"]}', 'started_utc': m.get('started'), 'git_commit_at_start': m.get('git_commit'),
                      'frozen_files_sha256_at_start': m.get('frozen_sha256'), 'resumes': len(m.get('resumes', [])), 'questions': len(m['questions'])}

# ---------- 6. code snapshot (final state) and amendments ----------
frozen = json.load(open(CUR / 'src/pipeline/a6/FROZEN.json'))
code_files = sorted(set(frozen['files']) | {'src/pipeline/a6/FROZEN.json', 'src/pipeline/a6/README.md', 'src/pipeline/a7/hive-proxy.mjs', 'src/pipeline/a7/hive-proxy.test.mjs'})
for f in code_files: copy(CUR / f, f'code/src/agents/current/{f}')
copy(ROOT / 'LICENSE', 'code/LICENSE')   # the repository's licence (Apache 2.0) travels with its code
mismatch = [f for f, h in frozen['files'].items() if fsha(CUR / f) != h]
assert not mismatch, f'frozen files drifted: {mismatch}'
r9 = CUR / 'freezes/R9-20261011/code'
patch = subprocess.run(['diff', '-ru', str(r9 / 'src'), str(CUR / 'src')], capture_output=True, text=True).stdout
keep, block = [], []
for line in patch.splitlines(keepends=True):   # keep only diffs of files that belong to the frozen pipeline or the translator
    if line.startswith('diff ') or line.startswith('Only in '):
        if block: keep.append(''.join(block)); block = []
    block.append(line)
if block: keep.append(''.join(block))
rel = lambda s: s.replace(str(r9) + '/', 'R9-freeze/').replace(str(CUR) + '/', 'final/')
wanted = [rel(b) for b in keep if b.startswith('diff ') and any(f'/{f} ' in b.split('\n')[0] + ' ' for f in code_files)]
(PKG / 'code/R9-freeze-to-final.patch').write_text(''.join(wanted))
changed = sorted({re.search(r'final/(\S+)', b.split('\n')[0]).group(1) for b in wanted})
# The same files as they are in the public freeze commit (tag r9-freeze-20261011), so the chain below can be checked offline.
for f in changed:
    old = subprocess.run(['git', 'show', f'{FREEZE_COMMIT}:src/agents/current/{f}'], cwd=ROOT, capture_output=True, check=True).stdout
    p = PKG / f'code/public-freeze/src/agents/current/{f}'; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(old)
fz0 = json.loads((PKG / 'code/public-freeze/src/agents/current/src/pipeline/a6/FROZEN.json').read_text())
files, chain = dict(fz0['files']), [{'state': 'public freeze (tag r9-freeze-20261011)', 'frozen_files_sha256': frozen_hash(fz0['files'])}]
for a in frozen['amendments']:   # each amendment replaces exactly one file hash; nothing else may differ
    assert files[a['file']] == a['old_sha256'], a['file']; files[a['file']] = a['new_sha256']
    chain.append({'state': f'after amendment ({a["date"]}): {a["file"]}', 'frozen_files_sha256': frozen_hash(files)})
assert files == frozen['files'], 'freeze + amendments must equal the final frozen file list'
seen = collections.defaultdict(list)   # where each chain state appears in the run manifests
for part, cfg in PARTS.items():
    m = json.load(open(RUNS / cfg['run'] / 'manifest.json'))
    seen[m['frozen_sha256']].append(f'{part} start {m["started"]}')
    for r in m.get('resumes', []): seen[r['frozen_sha256']].append(f'{part} resume {r["time"]}')
assert set(seen) <= {c['frozen_files_sha256'] for c in chain}, 'every run used a state on the chain'
for c in chain: c['used_by_runs'] = seen.get(c['frozen_files_sha256'], [])
freeze_push = on_github_by(FREEZE_COMMIT)
wjson('code/code-provenance.json', {
    'public_freeze': {'tag': 'r9-freeze-20261011', 'commit': FREEZE_COMMIT, 'committed_self_reported': '2026-10-11T15:36:19+05:30',
                      'on_github_by_utc': freeze_push['utc'], 'github_push': freeze_push['push'],
                      'repository': 'https://github.com/arnavgupta00/memory', 'snapshot_folder_in_repo': 'src/agents/current/freezes/R9-20261011',
                      'files_as_frozen_in_this_package': 'code/public-freeze/'},
    'files_changed_since_public_freeze': changed, 'amendments': frozen.get('amendments', []), 'frozen_hash_chain': chain,
    'translator': {'file': 'src/pipeline/a7/hive-proxy.mjs', 'sha256_public_freeze': fsha(PKG / 'code/public-freeze/src/agents/current/src/pipeline/a7/hive-proxy.mjs'),
                   'sha256_final': fsha(CUR / 'src/pipeline/a7/hive-proxy.mjs'),
                   'change': 'Canary B amendment 3 (11 Oct, 20:25 IST relaunch): a length-limit trim fallback for the packager\'s discarded answer only. '
                             'It never fired: 0 discarded_answer_trimmed events in any ledger.'},
    'frozen_file_hashes_verified_now': True})

# ---------- 7. claims.json and results tables ----------
claims = {'claim': 'BEAM-1M (all 700 questions), frozen R9 configuration, official BEAM evaluator (pinned commit 3e12035, gpt-4.1-mini, temperature 0)',
          'generated': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'results': results, 'by_ability_all_700': by_ability,
          'conversation_scores_official': {'n': len(cs), 'mean': round(st.mean(cs), 2), 'sd': round(st.stdev(cs), 2), 'min': min(cs), 'max': max(cs)},
          'vectorize_pass_fail': {'questions': len(pf_ids), 'correct': sum(pf[q] for q in pf_ids), 'accuracy': round(100 * sum(pf[q] for q in pf_ids) / len(pf_ids), 1),
                                  'note': 'Canary A + Canary B only; gemini-3.5-flash judge'},
          'runs': run_meta, 'source_files': {'scores': 'data/scores/scores.csv', 'official_judge_outputs': 'data/judge/*.judge.json', 'answers': 'data/answers/answers.jsonl'}}
wjson('claims.json', claims)

# ---------- 8. project documents (copies, unchanged) ----------
ER = CUR / 'architecture/expert-review-20260927'
for src_doc in [ER / 'RUN-LEDGER.md', ER / '23-LOSS-ATTRIBUTION.md', ER / '25-PIPELINE-MODEL-MAP.md', ER / '26-EVENT-ORDERING-TEMPORAL-DIAGNOSIS.md',
                ER / '27-CANARY-B-POSTMORTEM.md', CUR / 'architecture/BEAM-1M-CANARY-DESIGN.md', CUR / 'architecture/BEAM-JEV-FRESH75-SELECTION-V1.md',
                CUR / 'architecture/BEAM-JEV-FRESH75-SELECTION-V1-RESULTS.md', CUR / 'architecture/BEAM-REASSESSMENT-20260927.md',
                CUR / 'architecture/0008-FULL500-CERTIFICATION-2026-07-31.md', ROOT / 'PROJECT-EXPERIMENT-HISTORY-20260927.md']:
    assert copy(src_doc, f'project-docs/{src_doc.name}'), src_doc
print(json.dumps(results, indent=1)); print('changed since freeze:', changed)

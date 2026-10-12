#!/usr/bin/env python3
"""Verify the BEAM-1M proof package offline. Python 3 standard library only; no API keys; no network.

    python3 verify/verify.py                   # checks 1-14: integrity, provenance, every claimed number recomputed from the raw judge outputs
    python3 verify/verify.py --deep            # checks 1-19: also the bulk evidence (judge call logs, model-call ledgers)
    python3 verify/verify.py --deep --online   # check 20 as well: the third-party archive copies (Wayback Machine) match this package

It runs on both copies of the package: the full copy (for auditors), and the public copy, where the source code, prompts,
memory packs and answer plans are withheld and committed by sha256 instead. Every check prints PASS or FAIL. The script exits
0 only if every check passes. Only --online uses the network.
"""
import csv, gzip, hashlib, json, pathlib, statistics as st, sys, tarfile, datetime

PKG = pathlib.Path(__file__).resolve().parents[1]
DEEP = '--deep' in sys.argv
ONLINE = '--online' in sys.argv
PUBLIC = not (PKG / 'code/src/agents/current/src/pipeline/a6/run.mjs').exists()   # public copy: source withheld
ABILITIES = ['abstention', 'contradiction_resolution', 'event_ordering', 'information_extraction', 'instruction_following',
             'knowledge_update', 'multi_session_reasoning', 'preference_following', 'summarization', 'temporal_reasoning']
PARTS = ['canary-a-part1', 'canary-a-part2', 'canary-b', 'remaining-340']
BEAM_COMMIT = '3e12035532eb85768f1a7cd779832b650c4b2ef9'
FREEZE_COMMIT = '595a2e28228c21cf842378fb9216cacb46478fd3'
results = []
def check(name, ok, detail=''):
    results.append(bool(ok)); print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f'  [{detail}]' if detail else ''))
sha = lambda b: hashlib.sha256(b).hexdigest()
load = lambda p: json.loads((PKG / p).read_text())
utc = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
frozen_hash = lambda files: sha(json.dumps(files, separators=(',', ':'), ensure_ascii=False).encode())   # as run.mjs: sha256(JSON.stringify(files))
def jsonl(p):
    raw = (PKG / p).read_bytes(); raw = gzip.decompress(raw) if p.endswith('.gz') else raw
    return [json.loads(l) for l in raw.decode().splitlines() if l.strip()]

print(f'BEAM-1M proof package: {PKG.name}  ' + ('(public copy: source code, prompts, memory packs and plans withheld, committed by sha256)' if PUBLIC else '(full copy)') + '\n')
# 1. every file in the manifest is present and unchanged
man = [l.split('  ', 1) for l in (PKG / 'MANIFEST.sha256').read_text().splitlines() if l.strip()]
missing, bad, bulk_absent = [], [], 0
for h, rel in man:
    p = PKG / rel
    if not p.exists():
        if rel.startswith('bulk/'): bulk_absent += 1
        else: missing.append(rel)
        continue
    if sha(p.read_bytes()) != h: bad.append(rel)
check('1. MANIFEST.sha256: every file present and byte-identical', not missing and not bad,
      f'{len(man)} files; missing {len(missing)}; changed {len(bad)}' + (f'; bulk files not present: {bulk_absent}' if bulk_absent else ''))

# 2-3. the 700 answers are exactly BEAM-1M (35 conversations x 10 abilities x 2); the partition and its defining files
answers = jsonl('data/answers/answers.jsonl'); A = {r['question_id']: r for r in answers}
grid = {f'beam-1m/chat-{n:02d}/{a}/{i}' for n in range(1, 36) for a in ABILITIES for i in (1, 2)}
check('2. answers.jsonl holds exactly the 700 BEAM-1M questions, once each', len(answers) == 700 and set(A) == grid)
part = load('data/questions/partition.json'); parts = part['partitions']
files_ok = all(sha((PKG / 'data/questions/partition-files' / f).read_bytes()) == v['sha256'] for f, v in part['split_files'].items())
check('3. partitions: Canary A 100, Canary B 260, Fresh75 histories 260, expansion 80; split files match their recorded hashes',
      [parts[k]['questions'] for k in ('canary_a', 'canary_b', 'fresh75', 'expansion')] == [100, 260, 260, 80] and files_ok)

# 4-5. answers: hashes, non-empty, identical to the files the official judge read
ok_hash = all(sha(r['answer'].encode()) == r['answer_sha256'] for r in answers)
check('4. every answer matches its recorded sha256 and none is empty', ok_hash and all(r['answer'].strip() for r in answers))
same = True
for p in PARTS:
    for r in jsonl(f'data/answers/predictions-as-judged/{p}.predictions.jsonl'):
        same &= A[r['question_id']]['answer'] == r['hypothesis'] and A[r['question_id']]['run_part'] == p
check('5. answers are byte-identical to the prediction files submitted to the official judge', same)

# 6. official source: every file the runs used is BEAM's own (git blob hash in BEAM's tree at 3e12035; sha256 in the 1 Aug split files)
src = load('data/questions/official-source-manifest.json'); C = src['conversations'].values()
src_ok = src['commit'] == BEAM_COMMIT and len(C) == 35 and all(
    v['chat_git_blob_sha1'] == v['beam_tree_chat_blob_sha1'] and v['probing_questions_git_blob_sha1'] == v['beam_tree_probing_questions_blob_sha1']
    and v['chat_sha256'] == v['split_file_chat_sha256'] and v['probing_questions_sha256'] == v['split_file_probing_questions_sha256'] for v in C)
check("6. BEAM data: all 35 conversations' files match BEAM's own git tree at 3e12035 and the checksums in the 1 Aug split files", src_ok)

# 7-8. official judge outputs: pinned evaluator, one row per question, each score recomputed from the raw judge items
rows, judge_meta = {}, []
for p in PARTS:
    J = load(f'data/judge/{p}.judge.json')
    judge_meta.append((J['status'], J['official_source_commit'], json.dumps(J['official_source_hashes'], sort_keys=True), J['judge_model'], J['judge_temperature']))
    for r in J['rows']: rows[r['question_id']] = r
pinned_ok = all(m == ('completed', BEAM_COMMIT, judge_meta[0][2], 'gpt-4.1-mini', 0) for m in judge_meta)
def pinned(r):   # pinned evaluator 3e12035: event ordering = tau_norm; others = mean of int(item score) (half credit counts 0)
    if r['ability'] == 'event_ordering': return r['official_result']['tau_norm']
    it = r['official_result']['llm_judge_responses']; return sum(int(float(x['score'])) for x in it) / len(it)
def half(r):     # upstream fix b2da22e (int -> float) applied to the same judge outputs
    if r['ability'] == 'event_ordering': return r['official_result']['tau_norm']
    it = r['official_result']['llm_judge_responses']; return sum(float(x['score']) for x in it) / len(it)
def rubric(r):   # per-item rubric mean for every ability, event ordering by its rubric judge (Mem0/Vectorize convention)
    return r['official_result']['llm_judge_score'] if r['ability'] == 'event_ordering' else half(r)
check('7. official judge outputs: one completed row per question; all four runs used BEAM 3e12035 with identical evaluator files, gpt-4.1-mini, temperature 0',
      set(rows) == grid and all(rows[q]['ability'] == q.split('/')[2] for q in grid) and pinned_ok)
check('8. every stored official score equals the score recomputed from its raw judge items', all(abs(pinned(r) - r['score']) < 1e-9 for r in rows.values()))

# 9-11. recompute every claimed aggregate from the judge outputs and compare with claims.json
claims = load('claims.json'); P = {q: v['partition'] for q, v in part['question_ids'].items()}
vec = {r['question_id']: r['score'] for r in jsonl('data/comparison/vectorize-rubric-average-per-question.jsonl')}
groups = {'ALL 700': list(grid), 'Canary A (100, development)': [q for q in grid if P[q] == 'canary_a'], 'Canary B (260, sealed)': [q for q in grid if P[q] == 'canary_b'],
          'Fresh75 histories (260, development)': [q for q in grid if P[q] == 'fresh75'], 'Expansion (80, sealed)': [q for q in grid if P[q] == 'expansion'],
          'Unseen: Canary B + expansion (340)': [q for q in grid if P[q] in ('canary_b', 'expansion')],
          'Remaining 340 run (Fresh75 + expansion)': [q for q in grid if A[q]['run_part'] == 'remaining-340']}
m = lambda xs: round(100 * st.mean(xs), 2)
all_ok, lines = True, []
for g, ids in groups.items():
    got = {'official_pinned': m([pinned(rows[q]) for q in ids]), 'official_half_credit': m([half(rows[q]) for q in ids]),
           'rubric_average_beam_judge': m([rubric(rows[q]) for q in ids]), 'vectorize_rubric_average': m([vec[q] for q in ids])}
    want = {k: claims['results'][g][k] for k in got}
    all_ok &= got == want; lines.append(f'{g:42} official {got["official_pinned"]:6.2f}  half-credit {got["official_half_credit"]:6.2f}  rubric {got["rubric_average_beam_judge"]:6.2f}  vectorize {got["vectorize_rubric_average"]:6.2f}')
check('9. every claimed score recomputes exactly from the raw evidence', all_ok)
ab_ok = all(round(100 * st.mean(pinned(rows[q]) for q in grid if q.split('/')[2] == a), 1) == claims['by_ability_all_700'][a]['official_pinned'] for a in ABILITIES)
check('10. per-ability official scores recompute exactly', ab_ok)
with open(PKG / 'data/scores/scores.csv') as f: csv_rows = {r['question_id']: r for r in csv.DictReader(f)}
check('11. scores.csv agrees with the judge outputs', all(abs(float(csv_rows[q]['official_pinned']) - pinned(rows[q])) < 1e-6 for q in grid))
print('\n' + '\n'.join(lines) + '\n')

# 12. code snapshot = the frozen pipeline (every file hash listed in FROZEN.json)
fz = load('code/src/agents/current/src/pipeline/a6/FROZEN.json')
FULL = (PKG / 'withheld/FULL-PACKAGE-MANIFEST.sha256').read_text() if PUBLIC else ''
if not PUBLIC:
    code_ok = all((PKG / 'code/src/agents/current' / f).exists() and sha((PKG / 'code/src/agents/current' / f).read_bytes()) == h for f, h in fz['files'].items())
    check('12. code/ snapshot matches every hash in the frozen pipeline manifest (FROZEN.json)', code_ok, f'{len(fz["files"])} files; {len(fz.get("amendments", []))} recorded amendments')
else:   # the source is withheld: FROZEN.json and the full package's manifest commit to it, and must agree; the judge wrapper is published
    W = PKG / 'verify/judge-wrapper/src/agents/current'; pub = [f for f in fz['files'] if (W / f).exists()]
    code_ok = len(fz['files']) == 123 and len(pub) == 3 and all(sha((W / f).read_bytes()) == fz['files'][f] for f in pub)
    code_ok &= all(f'{h}  code/src/agents/current/{f}' in FULL for f, h in fz['files'].items())
    check('12. code: the 123 locked files are committed by sha256 (FROZEN.json agrees with the full-package manifest); the published judge wrapper matches',
          code_ok, f'{len(pub)} of {len(fz["files"])} files published; the rest withheld')

# 13. hash chain: public freeze -> one recorded amendment at a time -> final; every run start and resume used a state on it, in order
fz0 = load('code/public-freeze/src/agents/current/src/pipeline/a6/FROZEN.json')
files, chain, chain_ok = dict(fz0['files']), [frozen_hash(fz0['files'])], True
for a in fz['amendments']:
    old_file = PKG / 'code/public-freeze/src/agents/current' / a['file']; new_file = PKG / 'code/src/agents/current' / a['file']
    chain_ok &= files.get(a['file']) == a['old_sha256']
    if not PUBLIC: chain_ok &= a['old_sha256'] == sha(old_file.read_bytes()) and a['new_sha256'] == sha(new_file.read_bytes())
    else: chain_ok &= f"{a['old_sha256']}  code/public-freeze/src/agents/current/{a['file']}" in FULL and f"{a['new_sha256']}  code/src/agents/current/{a['file']}" in FULL
    files[a['file']] = a['new_sha256']; chain.append(frozen_hash(files))
chain_ok &= files == fz['files']
events = []
for p in PARTS:
    mf = load(f'runs/{p}/pipeline-run/manifest.json')
    events += [(utc(mf['started']), p, mf['frozen_sha256'])] + [(utc(r['time']), p, r['frozen_sha256']) for r in mf.get('resumes', [])]
events.sort(); idx = [chain.index(h) if h in chain else -1 for _, _, h in events]
starts = {p: load(f'runs/{p}/pipeline-run/manifest.json')['frozen_sha256'] for p in PARTS}
chain_ok &= -1 not in idx and idx == sorted(idx) and all(starts[p] == chain[0] for p in ('canary-a-part1', 'canary-a-part2', 'canary-b'))
check('13. code hash chain: public freeze -> each recorded amendment -> final code; every run start and resume used a state on the chain, in order',
      chain_ok, f'{len(events)} run starts/resumes; states used: ' + ' -> '.join(dict.fromkeys(chain[i][:8] for i in idx if i >= 0)))

# 14. timeline: GitHub's server-side push log dates the split files and the freeze before the sealed runs started
log = load('data/questions/github-push-log.json')['events']; pushed = {}
for e in log:   # first time each commit became a branch tip on GitHub
    if e['activity_type'] in ('push', 'branch_creation'): pushed[e['after']] = min(pushed.get(e['after'], utc(e['timestamp'])), utc(e['timestamp']))
prov = load('code/code-provenance.json')['public_freeze']
sealed_starts = [utc(load(f'runs/{p}/pipeline-run/manifest.json')['started']) for p in ('canary-b', 'remaining-340')]
t_freeze = pushed.get(FREEZE_COMMIT); t_split = [utc(v['on_github_by_utc']) for v in part['split_files'].values() if v['on_github_by_utc']]
split_in_log = all(utc(v['on_github_by_utc']) in pushed.values() for v in part['split_files'].values())
sealed_commit = all(load(f'runs/{p}/pipeline-run/manifest.json')['git_commit'] == FREEZE_COMMIT[:8] for p in ('canary-b', 'remaining-340'))
check('14. timeline (GitHub server log): split files and the frozen code were on GitHub before Canary B and the remaining 340 started',
      t_freeze is not None and utc(prov['on_github_by_utc']) == t_freeze and len(t_split) == len(part['split_files']) and split_in_log
      and max(t_split + [t_freeze]) < min(sealed_starts) and sealed_commit,
      f'freeze pushed {t_freeze:%Y-%m-%d %H:%M}Z; Canary B started {sealed_starts[0]:%Y-%m-%d %H:%M}Z' if t_freeze else 'freeze push not in log')

# 15-19. deep checks with bulk/ (judge call logs, model ledgers, memory packs)
if DEEP:
    if not (PKG / 'bulk').exists() or bulk_absent:
        check('15. --deep needs the bulk/ folder', False, 'bulk/ missing or incomplete')
    else:
        logs_ok, found, needed = True, 0, 0
        for p in PARTS:
            ev = jsonl(f'bulk/{p}/judge-call-log.jsonl.gz')
            d = sum(e['event'] == 'dispatch' for e in ev); rsp = sum(e['event'] == 'response' for e in ev); fail = sum(e['event'] == 'failure' for e in ev)
            logs_ok &= d == rsp and fail == 0
            prompts = '\n'.join(e['prompt'] if isinstance(e['prompt'], str) else json.dumps(e['prompt'], ensure_ascii=False) for e in ev if e['event'] == 'dispatch')
            for r in answers:
                if r['run_part'] != p or r['question_id'].split('/')[2] == 'event_ordering': continue
                needed += 1; found += r['answer'][:400] in prompts
        check('15. judge call logs: every call answered, no failed calls', logs_ok)
        check('16. the text the official judge evaluated is the published answer (non-ordering questions)', found == needed, f'{found}/{needed}')
        LEDGER = lambda p: f'bulk/{p}/hive-ledger.jsonl.gz' if (PKG / f'bulk/{p}/hive-ledger.jsonl.gz').exists() else f'bulk/{p}/hive-ledger.redacted.jsonl.gz'
        led_ok, n_resp, n_trim = True, 0, 0
        for p in PARTS:
            ev = jsonl(LEDGER(p)); resp = [e for e in ev if e.get('event') == 'hive_response']
            s = load(f'runs/{p}/hive-ledger-summary.json'); trims = sum(e.get('event') == 'discarded_answer_trimmed' for e in ev)
            led_ok &= len(resp) == s['responses'] and round(sum(e.get('cost_usd') or 0 for e in resp), 2) == s['list_usd_total']
            led_ok &= sum((e['usage'].get('completion_tokens') or 0) == 0 for e in resp) == s['zero_output_responses'] == 0 and trims == s['discarded_answer_trims'] == 0
            n_resp += len(resp); n_trim += trims
        # the published latency and token figures (data/performance/performance.json) recompute from the same ledgers
        perf_ok, stage_lat, stage_tok = True, {}, {}
        if (PKG / 'data/performance/performance.json').exists():
            for p in PARTS:
                for e in jsonl(LEDGER(p)):
                    if e.get('event') != 'hive_response': continue
                    s = ('session notes' if str(e.get('requested_model', '')).startswith('gpt-5.4-nano') else
                         ('planner' if e['structured'] else 'answerer') if e['effort_used'] == 'max' else
                         'router, search, targeted plans' if e['effort_used'] == 'low' else "packager's discarded answer")
                    stage_lat.setdefault(s, []).append(e['latency_ms'] / 1000)
                    t = stage_tok.setdefault(s, [0, 0, 0]); t[0] += e['usage'].get('prompt_tokens', 0); t[1] += e['usage'].get('completion_tokens', 0); t[2] += 1
            pf = load('data/performance/performance.json'); q = lambda xs, k: sorted(xs)[min(len(xs) - 1, int(round(k / 100 * (len(xs) - 1))))]
            perf_ok = all(round(q(v, 50), 1) == pf['model_call_latency_seconds'][s]['p50'] and round(q(v, 90), 1) == pf['model_call_latency_seconds'][s]['p90']
                          for s, v in stage_lat.items())
            perf_ok &= all(pf['tokens'][s] == {'prompt_tokens': v[0], 'completion_tokens': v[1], 'calls': v[2]} for s, v in stage_tok.items())
            rows = [r for r in csv.DictReader(open(PKG / 'data/performance/latency-per-question.csv')) if r['model_time_ms']]
            for col, key in (('retrieval_ms', 'query_retrieval_seconds'), ('answer_ms', 'query_answer_seconds'), ('model_time_ms', 'query_total_seconds')):
                xs = [float(r[col]) / 1000 for r in rows]
                perf_ok &= round(q(xs, 50), 1) == pf['latency_split'][key]['p50'] and round(q(xs, 90), 1) == pf['latency_split'][key]['p90']
        check('17. model-call ledgers match their summaries and the published latency and token figures; no empty replies; the trim fallback never fired',
              led_ok and perf_ok, f'{n_resp} model responses; {n_trim} trims')
        # one answer per question: the planner (structured) and the answerer (free text) are the only calls at max reasoning
        n_ans = n_plan = n_reask = 0
        for p in PARTS:
            for e in jsonl(LEDGER(p)):
                if e.get('event') != 'hive_response' or e.get('effort_used') != 'max': continue
                if not e['structured']: n_ans += 1
                elif e['ask'] == 1 and not e['corrective']: n_plan += 1
                else: n_reask += 1
        check('18. one answer per question: exactly 700 answer generations and 700 first plans; the only extra calls are schema re-asks of a plan',
              n_ans == 700 and n_plan == 700, f'{n_ans} answers, {n_plan} plans, {n_reask} plan re-asks')
        if not PUBLIC:
            packs = 0
            for p in PARTS:
                with tarfile.open(PKG / f'bulk/{p}/memory-packs.tar.gz') as t: packs += sum(1 for x in t.getmembers() if x.isfile())
            check('19. bulk/ holds a memory pack for every question', packs == 700, f'{packs} packs')
        else:   # packs and plans are withheld; each is committed by sha256 (an auditor with the full copy can check them)
            H = load('withheld/memory-pack-and-plan-hashes.json')['questions']
            ok = set(H) == grid and all(len(v['memory_pack_sha256']) == 64 and len(v['plan_sha256']) == 64 for v in H.values())
            check('19. a memory pack and an answer plan exist for every question (withheld; 700 + 700 sha256 commitments)', ok, f'{len(H)} questions')

# 20. --online: the third-party archive (Wayback Machine) copies of GitHub's records match this package
if ONLINE:
    import urllib.request, re as _re
    arch, arch_ok, seen = load('data/questions/independent-archives.json'), True, []
    for x in arch['archives']:
        try:
            for i in range(5):   # the archive can be briefly unavailable: retry before giving up
                try: b = urllib.request.urlopen(_re.sub(r'/web/(\d+)/', r'/web/\1id_/', x['snapshot']), timeout=120).read(); break
                except Exception:
                    if i == 4: raise
                    __import__('time').sleep(5 * (i + 1))
            b = gzip.decompress(b) if b[:2] == b'\x1f\x8b' else b
        except Exception as e:
            arch_ok = False; seen.append(f"{x['what']}: fetch failed"); continue
        ok = sha(b) == x['archived_content_sha256']
        if x['what'] == 'push log':
            ok &= any(e.get('after') == FREEZE_COMMIT and e.get('timestamp') == arch['freeze_pushed_utc'] for e in json.loads(b))
        if x['what'] == 'freeze tag': ok &= json.loads(b)['object']['sha'] == x['shows'].split()[-1]
        if x['what'] == 'freeze commit': ok &= json.loads(b)['sha'] == FREEZE_COMMIT
        if x.get('package_file'): ok &= sha(b) == sha((PKG / x['package_file']).read_bytes())
        arch_ok &= ok; seen.append(f"{x['what']}: {'ok' if ok else 'MISMATCH'}")
    check('20. independent archive: the Wayback Machine copies of the push log, the freeze manifest and the split files match this package',
          arch_ok, f"{sum(s.endswith('ok') for s in seen)}/{len(seen)} archived records match")

n_ok = sum(results); print(f'\n{n_ok}/{len(results)} checks passed.')
sys.exit(0 if all(results) else 1)

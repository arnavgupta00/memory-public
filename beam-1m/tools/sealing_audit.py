"""Sealing audit: before the sealed runs, did anything in the project use a Canary B or expansion history?

Two scans of the project's records (`runs/`, mostly git-ignored, 27 GB; plus `src/`), compressed files included:
  A. structured: every file that lists the questions or histories a run processed (predictions, cohorts, slices, manifests,
     datasets, judge outputs);
  B. full text: every file except third-party library code (site-packages, node_modules), for any reference to a sealed
     history (question IDs `beam-1m/chat-NN/...`, data paths `chats/1M/N/`, and `"conversation_id": N` fields). Uses ripgrep.
A file that mentions a sealed history and was last modified before that history's sealed run started, outside the sealed
run's own folder, must have a written explanation below; otherwise the audit fails.
The output is written to data/questions/sealing-audit.json.

Limitation: this shows the absence of such use in the project's records. It cannot prove that nobody ever opened the files
by hand. The split itself is dated by GitHub's server-side push log (see partition.json and github-push-log.json).
"""
import json, os, re, pathlib, datetime, collections, subprocess
ROOT = pathlib.Path('/Users/arnav/programming/projects/memory'); RUNS = ROOT / 'runs'
PKG = ROOT / 'proof/BEAM-1M-R9-final-20261012'
CANARY_B = {1, 2, 9, 10, 12, 14, 17, 22, 24, 26, 27, 30, 35}; EXPANSION = {7, 16, 21, 34}
SEALED = {'canary_b': CANARY_B, 'expansion': EXPANSION}
SEALED_RUN_START = {'canary_b': datetime.datetime(2026, 10, 11, 12, 21, 10, tzinfo=datetime.timezone.utc),
                    'expansion': datetime.datetime(2026, 10, 11, 19, 53, 38, tzinfo=datetime.timezone.utc)}
SEALED_RUN_FOLDERS = {'canary_b': 'runs/canary-b-r9-20261011/', 'expansion': 'runs/final-700-r9-20261012/'}
POST = ['canary-b-r9-20261011', 'final-700-r9-20261012', 'amb-judge-20261012', 'packager-answers-20261012']
EXPLAINED = {
    'src/agents/current/eval-slices/beam-1m/beam-1m-canary-b-certification-v1.json': 'the 1 Aug split file itself: question IDs and checksums only',
    'src/agents/current/eval-slices/beam-1m/beam-1m-blind-reserve-v1.json': 'the 1 Aug split file itself: question IDs and checksums only',
    'src/agents/current/eval-slices/beam-1m/beam-1m-compression-holdout40-v1.json': '8 Aug holdout list, question IDs only; never run, later read only as an exclusion list',
    'src/agents/current/tests/beamCompression.test.ts': 'unit-test fixture with an invented question ID and invented text; no BEAM data',
    'runs/final-all-deepseek-20261009/scripts/canary-b-questions.json': "R7's Canary B question list (IDs only), prepared on 9 Oct for a gated run that never happened: R7 failed its gate",
}

# A. structured scan (files that list what a run processed)
NAMES = {'predictions.jsonl', 'cohort.json', 'slice.json', 'manifest.json', 'dataset.json', 'judge.json'}
qid = re.compile(r'beam-1m/chat-(\d+)/')
hits, scanned = collections.defaultdict(list), 0
for dirpath, dirnames, filenames in os.walk(RUNS):
    dirnames[:] = [d for d in dirnames if d not in ('context', 'answer', 'plan', 'node_modules', '.git', 'semantic-index', 'annotations', 'traces')]
    for fn in filenames:
        if fn not in NAMES: continue
        p = pathlib.Path(dirpath) / fn; scanned += 1
        try: text = p.read_text(errors='ignore')
        except Exception: continue
        convs = {int(m) for m in qid.findall(text)}
        if fn == 'dataset.json' and not convs:
            try: convs = {int(c['conversation_id']) for c in json.loads(text).get('conversations', [])}
            except Exception: pass
        rel = str(p.relative_to(RUNS)); mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime, tz=datetime.timezone.utc)
        for label, sealed in SEALED.items():
            found = sorted(convs & sealed)
            if found:
                hits[label].append({'file': rel, 'conversations': found, 'modified_utc': mtime.isoformat(timespec='seconds'),
                                    'before_sealed_run': mtime < SEALED_RUN_START[label], 'post_run_or_sealed_run_folder': any(rel.startswith(x) for x in POST)})
structured = {}
for label in SEALED:
    h = hits[label]
    structured[label] = {'files_mentioning_these_histories': len(h),
                         'earlier_files_outside_the_sealed_run': [x for x in h if x['before_sealed_run'] and not x['post_run_or_sealed_run_folder']]}

# B. full-text scan of every file (ripgrep; ignore rules off, hidden files and compressed files included)
patterns = [r'beam-1m/chat-\d+/', r'chats/1M/\d+/', r'"conversation_id":\s*"?\d+"?']
EXCLUDE = ['!**/site-packages/**', '!**/node_modules/**']   # third-party library code, not project records
out = subprocess.run(['rg', '--no-ignore', '--hidden', '-z', '-o', '-N', '--null', '--no-messages', *sum((['-e', p] for p in patterns), []),
                      *sum((['-g', g] for g in EXCLUDE), []), 'runs', 'src'],
                     cwd=ROOT, capture_output=True, text=True).stdout
refs = collections.defaultdict(set)
for line in set(out.splitlines()):   # "path\0match" (--null: a match may itself contain ':')
    path, _, match = line.partition('\0')
    m = re.search(r'chat-(\d+)/', match) or re.search(r'1M/(\d+)/', match) or re.search(r'(\d+)"?$', match)
    if path and m: refs[path].add(int(m.group(1)))
full = {'files_with_any_history_reference': len(refs), 'patterns': patterns, 'excluded': EXCLUDE}
for label, sealed in SEALED.items():
    early, total = [], 0
    for path, convs in sorted(refs.items()):
        found = sorted(convs & sealed)
        if not found: continue
        total += 1
        mtime = datetime.datetime.fromtimestamp((ROOT / path).stat().st_mtime, tz=datetime.timezone.utc)
        if mtime >= SEALED_RUN_START[label]: continue
        own = path.startswith(SEALED_RUN_FOLDERS[label])
        early.append({'file': path, 'conversations': found, 'modified_utc': mtime.isoformat(timespec='seconds'),
                      'explanation': 'the sealed run\'s own question list, written just before the run started' if own else EXPLAINED.get(path)})
    # Date-independent test: a file outside the sealed-run and post-run folders that mentions a sealed history must be explained,
    # whatever its modification time (an early file touched again later would otherwise escape the date test).
    outside = [{'file': p, 'conversations': sorted(c & sealed), 'explanation': EXPLAINED.get(p)} for p, c in sorted(refs.items())
               if c & sealed and not any(p.startswith(f'runs/{x}/') for x in POST)]
    full[label] = {'sealed_run_started_utc': SEALED_RUN_START[label].isoformat(), 'files_mentioning_these_histories': total,
                   'modified_before_the_sealed_run': early, 'outside_sealed_run_and_post_run_folders': outside,
                   'unexplained': sorted({x['file'] for x in early + outside if not x['explanation']})}
ok = not any(full[l]['unexplained'] for l in SEALED) and not any(structured[l]['earlier_files_outside_the_sealed_run'] for l in SEALED)
result = {'verdict': 'PASS: no use of a sealed history before its sealed run' if ok else 'FAIL: unexplained earlier references (see lists)',
          'structured_scan': {'scanned_files': scanned, 'file_types': sorted(NAMES), **structured},
          'full_text_scan': full, 'all_structured_hits': hits,
          'limitation': 'Absence of earlier use in the project records; not a proof that no person opened the files.'}
(PKG / 'data/questions').mkdir(parents=True, exist_ok=True)
(PKG / 'data/questions/sealing-audit.json').write_text(json.dumps(result, indent=1) + '\n')
print(result['verdict'])
print('structured scan:', scanned, 'files;', {l: structured[l]['files_mentioning_these_histories'] for l in SEALED})
print('full-text scan:', full['files_with_any_history_reference'], 'files with history references')
for l in SEALED:
    print(f' {l}: {full[l]["files_mentioning_these_histories"]} files mention these histories; earlier than the sealed run:')
    for x in full[l]['modified_before_the_sealed_run']: print('   ', x['modified_utc'], x['file'], '->', x['explanation'])
    print(f'   outside the sealed-run and post-run folders (any date): {len(full[l]["outside_sealed_run_and_post_run_folders"])} files, '
          f'unexplained {len(full[l]["unexplained"])}')

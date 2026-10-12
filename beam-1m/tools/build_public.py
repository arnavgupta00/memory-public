"""Build the public view of the memory system's results: github.com/arnavgupta00/memory-public.

The development repository (github.com/arnavgupta00/memory) is private. This script turns its full proof package into the
public copy: everything a reviewer needs to check the result, without the system's source code, prompts, memory packs,
answer plans or internal research notes. Each withheld item is committed by sha256, so an auditor given the full copy can
check that nothing was changed.

What it does, in order:
1. copies an allow-list of files from the full package (answers, judge outputs, scores, split files, run records, ...);
2. writes the public documents: the full package's documents with their references to withheld files rewritten;
3. removes prompt text from the model-call ledgers (the `caller` and `problems` fields; counts, tokens and costs stay);
4. writes the commitments for what is withheld (the full package's manifest; per-question pack and plan hashes);
5. writes the repository front page, the website (docs/, for GitHub Pages) and the images;
6. refuses to finish if any code file, prompt text or API key value would be published, then runs the verifier.

Usage (private repository root): python3 proof/public/build_public.py [--out ../memory-public]
"""
import gzip, hashlib, json, pathlib, re, shutil, subprocess, sys, tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
SRC = ROOT / 'proof/BEAM-1M-R9-final-20261012'
OUT = pathlib.Path(sys.argv[sys.argv.index('--out') + 1]).resolve() if '--out' in sys.argv else ROOT.parent / 'memory-public'
PUB = OUT / 'beam-1m'
PARTS = ['canary-a-part1', 'canary-a-part2', 'canary-b', 'remaining-340']
sha = lambda b: hashlib.sha256(b).hexdigest()

def put(rel, data):
    p = PUB / rel; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())
def cp(rel, dst=None):
    src = SRC / rel; assert src.exists(), rel
    put(dst or rel, src.read_bytes())
def edit(text, pairs, name):
    for a, b in pairs:
        n = text.count(a)
        assert n >= 1, f'{name}: text to replace not found: {a[:80]!r}'
        text = text.replace(a, b)
    return text

# ---------- 0. start clean (generated folders only; the git history stays) ----------
OUT.mkdir(parents=True, exist_ok=True)
for d in ['beam-1m', 'assets', 'docs']: shutil.rmtree(OUT / d, ignore_errors=True)

# ---------- 1. allow-listed evidence ----------
for d in ['data/answers', 'data/judge', 'data/scores', 'data/comparison', 'data/questions', 'data/performance']:
    for p in sorted((SRC / d).rglob('*')):
        if p.is_file() and p.name != '.DS_Store': cp(str(p.relative_to(SRC)))
cp('claims.json'); cp('PROOF-PICTURE.svg')
RUN_DENY = re.compile(r'\.mjs$|\.patch$|/v2/routes\.json$|adjudicat|diagnos|stage-trace|\.DS_Store$')   # code, diffs, post-mortem analysis
for part in PARTS:
    for p in sorted((SRC / 'runs' / part).rglob('*')):
        rel = str(p.relative_to(SRC))
        if p.is_file() and not RUN_DENY.search(rel): cp(rel)
for f in ['code/code-provenance.json', 'code/src/agents/current/src/pipeline/a6/FROZEN.json',
          'code/public-freeze/src/agents/current/src/pipeline/a6/FROZEN.json']:
    cp(f)
for f in ['verify/verify.py', 'verify/compare_rejudge.py', 'verify/rescore_vectorize.py', 'verify/rejudge_official.sh']: cp(f)
for f in ['judgeExpertReview.py', 'judgeJevDownstream.py', 'runBeamEvidenceContractEvaluation.py']:   # the official-judge wrapper
    cp(f'code/src/agents/current/src/scripts/{f}', f'verify/judge-wrapper/src/agents/current/src/scripts/{f}')
cp('code/LICENSE', 'verify/LICENSE')
for f in ['tools/build_package.py', 'tools/sealing_audit.py', 'tools/make_manifest.py', 'tools/archive_anchors.py', 'tools/performance.py']: cp(f)
put('tools/build_public.py', pathlib.Path(__file__).read_bytes())

# ---------- 2. bulk: judge call logs as they are; model-call ledgers without prompt text ----------
for part in PARTS:
    cp(f'bulk/{part}/judge-call-log.jsonl.gz')
    rows = []
    for line in gzip.decompress((SRC / f'bulk/{part}/hive-ledger.jsonl.gz').read_bytes()).decode().splitlines():
        e = json.loads(line)
        for k in ('caller', 'problems'): e.pop(k, None)   # caller = the first words of the prompt; problems = schema field names
        rows.append(json.dumps(e, ensure_ascii=False))
    put(f'bulk/{part}/hive-ledger.redacted.jsonl.gz', gzip.compress(('\n'.join(rows) + '\n').encode(), mtime=0))

# ---------- 3. commitments for what is withheld ----------
put('withheld/FULL-PACKAGE-MANIFEST.sha256', (SRC / 'MANIFEST.sha256').read_bytes())
hashes = {}
for line in gzip.decompress((SRC / 'data/plans/plans.jsonl.gz').read_bytes()).decode().splitlines():
    if line.strip(): hashes.setdefault(json.loads(line)['question_id'], {})['plan_sha256'] = sha(line.encode())
for part in PARTS:
    with tarfile.open(SRC / f'bulk/{part}/memory-packs.tar.gz') as t:
        for m in t.getmembers():
            if m.isfile():
                q = m.name.split('/', 1)[1][:-5].replace('__', '/')
                hashes.setdefault(q, {})['memory_pack_sha256'] = sha(t.extractfile(m).read())
assert len(hashes) == 700 and all(len(v) == 2 for v in hashes.values())
put('withheld/memory-pack-and-plan-hashes.json', json.dumps({
    'note': 'sha256 of each withheld memory pack (the file memory-packs/<id>.json in bulk/<part>/memory-packs.tar.gz of the full copy) '
            'and of each answer plan (its UTF-8 line in data/plans/plans.jsonl.gz of the full copy).',
    'questions': dict(sorted(hashes.items()))}, indent=1) + '\n')
put('withheld/README.md', (HERE / 'templates/withheld-README.md').read_text())
put('code/README.md', (HERE / 'templates/code-README.md').read_text())

# ---------- 4. the split design note (protocol sections only) ----------
design = (SRC / 'project-docs/BEAM-1M-CANARY-DESIGN.md').read_text().split('## Canonical artifacts')[0].rstrip() + '\n'
design = edit(design, [
    ('see [the allocation record](BEAM-JEV-FRESH75-SELECTION-V1-RESULTS.md)\nand `eval-slices/beam-1m/beam-1m-holdout-allocation-20260924.json` for current status.',
     'see the allocation record\n`../data/questions/partition-files/beam-1m-holdout-allocation-20260924.json` for current status.'),
    ('**Measured checkpoint:** [BEAM-1M Canary A — 2026-08-01](BEAM-1M-CANARY-A-CHECKPOINT-2026-08-01.md)\n\n', ''),
], 'design note')
put('protocol/SPLIT-DESIGN.md', '> Excerpt of the internal design note for the BEAM-1M split, written 31 Jul–1 Aug 2026 (the allocation note at the top\n'
    '> was added on 24 Sep). The sections on implementation are omitted. The split files themselves are in\n'
    '> `../data/questions/partition-files/`.\n\n' + design)

# ---------- 5. documents: the full package's text, with references to withheld material rewritten ----------
INTERNAL = [('(doc 23)', '(internal loss analysis)'), ('(doc 26)', '(our offline replay of the official scorer)'),
            ('(`project-docs/27-CANARY-B-POSTMORTEM.md`)', '(internal)'), ('(doc 27)', '')]
DOCS = {
'README.md': [
    ('This package contains everything needed to check that claim, from the official dataset checksums to every answer, every\n'
     'judge decision and every model call. It also contains the code that produced them.',
     "This public copy contains everything needed to check that claim: the hashes that tie it to BEAM's data, every answer,\n"
     'every judge decision and every model call. The source code, prompts, memory packs and answer plans are withheld. Each\n'
     'is committed by sha256 and can be shown to an auditor ([withheld/](withheld/README.md)).'),
    ('python3 verify/verify.py --deep   # also checks the bulk evidence: judge call logs, model-call ledgers, memory packs\n',
     'python3 verify/verify.py --deep   # also checks the bulk evidence: judge call logs and model-call ledgers\n'
     "python3 verify/verify.py --deep --online   # also checks the Wayback Machine's copies of GitHub's records\n"),
    ('If you have the package as two zip files, unzip both into the same folder. The core zip alone (about 4 MB) is enough for\n'
     'the 14 offline checks; the bulk zip (about 110 MB) adds what `--deep` needs.\n',
     'Run them from this folder, after cloning the repository or unzipping the release download.\n'),
    ('Deeper checks, such as GitHub\'s server log, re-judging with the official evaluator\nyourself, or re-running the whole system, are in [VERIFY.md](VERIFY.md).',
     'Deeper checks, such as re-judging all 700 answers with the official evaluator\nyourself, are in [VERIFY.md](VERIFY.md).'),
    ('     **29 Aug**, six weeks before the sealed runs (check 14).',
     '     **29 Aug**, six weeks before the sealed runs (check 14). The Wayback Machine keeps a copy of that log (check 20).'),
    ('   - Every pipeline file is hash-locked, and every run start and resume records the code hash.',
     '   - The development repository is now private. The Wayback Machine\'s copies of the push log, the tag and the freeze-time\n'
     '     hash manifest keep the dates checkable by anyone (check 20).\n'
     '   - Every pipeline file is hash-locked, and every run start and resume records the code hash. The code is withheld here;\n'
     '     its hashes are published.'),
    ('| `data/plans/` | the 700 answer plans written by the planner |\n', ''),
    ('BEAM source hashes, GitHub\'s push log, sealing audit |', 'BEAM source hashes, GitHub\'s push log and its Wayback Machine copies, sealing audit |'),
    ('| `code/` | the exact code (123 frozen files + translator), the six changed files as they are in the public freeze, the patch between them, provenance and licence |',
     '| `code/` | the hash commitments for the code: `FROZEN.json` at the freeze and as run last, and the hash chain (`code-provenance.json`); the source is withheld |'),
    ('| `verify/` | `verify.py` (offline), plus the re-judge and Vectorize re-score helpers |',
     '| `verify/` | `verify.py`, the re-judge and Vectorize re-score helpers, and the official-judge wrapper used for the runs (its hashes match `FROZEN.json`) |'),
    ('| `project-docs/` | the run ledger, the split design and Fresh75 allocation, loss attribution, event-ordering diagnosis, Canary B post-mortem, and the full project history |',
     '| `protocol/` | the split design note (protocol sections) |\n| `withheld/` | what is withheld and why, with the sha256 that commits to each withheld file |'),
    ('| `bulk/` | large evidence: 700 memory packs, full judge call logs, full model-call ledgers, stage logs (109 MB) |',
     '| `bulk/` | the full judge call logs, and the model-call ledgers with the prompt text removed (9 MB) |'),
],
'VERIFY.md': [
    ('| **L2** | L1, plus the judge call logs, model-call ledgers and memory packs | Python 3, `bulk/` | < 1 min | free |',
     '| **L2** | L1, plus the judge call logs and the model-call ledgers | Python 3, `bulk/` | < 1 min | free |'),
    ("| **L2b** | Dates and code against public records: GitHub's server log, the frozen tag, BEAM's repository | git, network | 5 min | free |",
     "| **L2b** | Dates against third-party archives of GitHub's records; data against BEAM's repository | network | 5 min | free |"),
    ('| **L5** | Re-run the whole system on the 700 questions | 4 provider keys | about 7 hours | about $100 |',
     '| **L5** | Re-run the whole system (auditors only: the code is withheld) | the full copy, 4 provider keys | about 7 hours | about $100 |'),
    ('| 12 | The code snapshot matches all 123 hashes in `FROZEN.json` | The published code is not the code that ran |',
     '| 12 | The 123 locked files are committed by sha256: `FROZEN.json` agrees with the full package\'s manifest, and the published judge wrapper (3 files) matches its hashes | The commitment to the code is inconsistent |'),
    ('| 13 | **Hash chain.** The public freeze plus each recorded amendment, one file at a time, gives exactly the final code.',
     '| 13 | **Hash chain.** The freeze-time `FROZEN.json` plus each recorded amendment, one file at a time, gives exactly the final `FROZEN.json`.'),
    ('| 19 | `bulk/` holds a memory pack for every question | Missing evidence |',
     '| 19 | A memory pack and an answer plan exist for every question, each committed by sha256 (`withheld/`) | Missing evidence |'),
    ('6. Optionally, open the memory pack the answer was written from: `bulk/canary-b/memory-packs.tar.gz`, then\n'
     '   `memory-packs/beam-1m__chat-26__temporal_reasoning__1.json`.\n',
     '6. The memory pack the answer was written from is withheld; its sha256 is in\n   `withheld/memory-pack-and-plan-hashes.json`.\n'),
],
'CLAIMS.md': [
    ('(`code/.../runBeamEvidenceContractEvaluation.py`, `validate_official_repo`)',
     '(`verify/judge-wrapper/.../runBeamEvidenceContractEvaluation.py`, `validate_official_repo`)'),
    ('  - GitHub\'s server log records that commit\'s push at **2026-10-11 10:06:21 UTC**. Canary B started at **12:21:10 UTC**.',
     '  - GitHub\'s server log records that commit\'s push at **2026-10-11 10:06:21 UTC**. Canary B started at **12:21:10 UTC**.\n'
     '    The development repository is now private; the Wayback Machine keeps a copy of that log.'),
    ('  - `code/`: the final code.\n  - `code/public-freeze/`: the changed files as they are in the tag.\n  - `code/code-provenance.json`: the hash chain.\n',
     '  - `code/`: the hash commitments: `FROZEN.json` at the freeze and as run last, and the hash chain\n'
     '    (`code-provenance.json`). The source itself is withheld ([withheld/](withheld/README.md)).\n'
     '  - `data/questions/independent-archives.json`: the Wayback Machine\'s copies of the freeze records.\n'),
    ('  - 12: the code snapshot matches its hash manifest.',
     '  - 12: the 123 locked files are committed by sha256, and the published judge wrapper matches its hashes.'),
    ('- **Evidence.** The model-call ledgers in `bulk/*/hive-ledger.jsonl.gz`, and `runs/*/README.md`.',
     '- **Evidence.** The model-call ledgers in `bulk/*/hive-ledger.redacted.jsonl.gz`, and `runs/*/README.md`.'),
    ('  - A memory pack for each of the 700 questions.\n- **Evidence.** `bulk/` (109 MB) and the per-run summaries in `runs/*/`.',
     '  - A memory pack and an answer plan for each of the 700 questions (withheld; committed by sha256).\n'
     '- **Evidence.** `bulk/` (judge call logs, and model-call ledgers with the prompt text removed), the per-run summaries in\n'
     '  `runs/*/`, and `withheld/memory-pack-and-plan-hashes.json`.'),
],
'METHOD.md': [
    ('These guarantees are listed in `code/src/agents/current/src/pipeline/a6/README.md` and can be\nchecked in the code.',
     "These guarantees are listed in the pipeline's README, which is withheld with the code and can be\nchecked by an auditor."),
    ('(`code/.../src/pipeline/a7/hive-proxy.mjs`).', '(withheld with the code; sha256 `5be459b1…`).'),
    ('These ledgers are in `bulk/*/hive-ledger.jsonl.gz`.',
     'These ledgers are in `bulk/*/hive-ledger.redacted.jsonl.gz`, with the prompt text removed.'),
    ('through `code/.../src/scripts/judgeExpertReview.py`.',
     'through `verify/judge-wrapper/.../judgeExpertReview.py`, which is published and matches its hash in `FROZEN.json`.'),
],
'AMENDMENTS.md': [
    ('Check 13 recomputes it from\n`code/public-freeze/` and `code/`, and requires',
     'Check 13 recomputes it from the two\n`FROZEN.json` files in `code/`, and requires'),
    ('| remaining-340 resume 5 (and the final code in `code/`) |', '| remaining-340 resume 5 (and the final `FROZEN.json`) |'),
    ('- **Read the changes.** `code/R9-freeze-to-final.patch` holds the complete diff from the public freeze to the final code,\n'
     '  205 lines. Each change is a failure branch.\n'
     '- **Compare the files.** `code/public-freeze/` has the six changed files as they are in the tag; `code/src/...` has them as\n'
     '  they ran last. Check their sha256 against `code/code-provenance.json` → `amendments`, or against the tag on GitHub\n'
     '  ([VERIFY.md](VERIFY.md) L2b).\n'
     '- **Run the checks.** `python3 verify/verify.py` (checks 12, 13 and 14), then `--deep` (check 17).',
     '- **The code is withheld in this public copy.** The full copy for auditors holds the diff from the public freeze to the\n'
     '  final code (205 lines) and the six changed files, as frozen and as run last. Their sha256 are in\n'
     '  `code/code-provenance.json` → `amendments` and in `withheld/FULL-PACKAGE-MANIFEST.sha256`.\n'
     '- **The freeze side is archived.** The freeze-time `FROZEN.json` is in the Wayback Machine, and check 20 compares it\n'
     '  with this package.\n'
     '- **Run the checks.** `python3 verify/verify.py` (checks 12, 13 and 14), then `--deep` (check 17) and `--online`\n'
     '  (check 20).'),
],
'NOTICES.md': [
    ('- excerpts of BEAM conversations inside the memory packs (`bulk/*/memory-packs.tar.gz`);\n', ''),
    ('- **Origin.** `code/`, `verify/` and `tools/` come from https://github.com/arnavgupta00/memory.\n'
     '- **Licence.** They are licensed under the Apache License 2.0; see `code/LICENSE`.',
     '- **Origin.** `verify/` and `tools/` come from the development repository (github.com/arnavgupta00/memory, private\n'
     '  since 12 Oct 2026).\n'
     "- **Licence.** They are licensed under the Apache License 2.0; see `verify/LICENSE`. The system's source code is not\n"
     '  part of this public copy.'),
],
'JOURNEY.md': [
    ('This is how the result was reached, including the dead ends. The full record is in `project-docs/`:\n'
     '- `PROJECT-EXPERIMENT-HISTORY-20260927.md`, the whole project to 8 Oct;\n- `BEAM-REASSESSMENT-20260927.md`;\n'
     '- `RUN-LEDGER.md`, every scored run R1–R11;\n- docs 23, 25, 26 and 27.\n',
     'This is how the result was reached, including the dead ends. The detailed internal record (the experiment history, the\n'
     'run ledger and the analysis notes) stays private with the code.\n'),
    ('- **Loss attribution (doc 23).**', '- **Loss attribution.**'),
    ('- **The post-mortem (doc 27)** split', '- **The post-mortem** split'),
],
'LIMITATIONS.md': [],
'RESULTS.md': [], 'COMPARISON.md': [], 'COSTS.md': [],
}
for name, pairs in DOCS.items():
    text = edit((SRC / name).read_text(), pairs, name)
    for a, b in INTERNAL: text = text.replace(a, b)
    if name == 'LIMITATIONS.md':
        text = text.rstrip() + '\n\n' + (HERE / 'templates/limitations-public.md').read_text()
    if name == 'VERIFY.md':
        l2b = text[text.index('## L2b: public records (no keys)'):text.index('## L3: re-judge')]
        text = text.replace(l2b, (HERE / 'templates/verify-l2b-public.md').read_text() + '\n---\n\n')
        l5 = text[text.index('## L5: re-run the system'):text.index('## Spot-check one question')]
        text = text.replace(l5, (HERE / 'templates/verify-l5-public.md').read_text() + '\n---\n\n')
    assert 'project-docs' not in text and 'doc 2' not in text, f'{name}: reference to an internal document remains'
    put(name, text)

# ---------- 6. manifest of the public copy, then verify it ----------
subprocess.run([sys.executable, str(PUB / 'tools/make_manifest.py')], check=True)
r = subprocess.run([sys.executable, str(PUB / 'verify/verify.py'), '--deep'], capture_output=True, text=True)
out_lines = r.stdout.splitlines()
print(out_lines[0]); print('\n'.join(l for l in out_lines if l.startswith('FAIL'))); print(out_lines[-1])
assert r.returncode == 0, 'the public copy does not verify'

# ---------- 6b. the LongMemEval-S package (its own builder and verifier) ----------
subprocess.run([sys.executable, str(HERE / 'build_longmemeval.py'), '--out', str(OUT)], check=True)

# ---------- 7. front page, website and images ----------
TAG = 'beam-1m-r9-2026-10-12'; ZIP = f'memory-public-{TAG}.zip'
ZIP_URL = f'https://github.com/arnavgupta00/memory-public/releases/download/{TAG}/{ZIP}'
assets = OUT / 'assets'; assets.mkdir(parents=True, exist_ok=True)
for f in sorted((HERE / 'assets').iterdir()):
    if f.is_file(): shutil.copy2(f, assets / f.name)
(OUT / 'README.md').write_text((HERE / 'templates/README.md').read_text())
import html as _html
def term_line(l):
    e = _html.escape(l)
    if l.startswith('PASS'): return f'<span class="ok">PASS</span>{e[4:]}'
    if l.startswith('FAIL'): return f'<span class="bad">FAIL</span>{e[4:]}'
    return f'<span class="dim">{e}</span>' if l.strip() else ''
passes = [l for l in out_lines if l.startswith(('PASS', 'FAIL'))]
aggs = [l for l in out_lines if l.startswith('ALL 700')]   # the page shows the all-700 row; the script prints every run part
term = '\n'.join(['<span class="pr">$</span> python3 beam-1m/verify/verify.py --deep', ''] + [term_line(l) for l in passes[:11]] + [''] +
                 [term_line(l) for l in aggs] + [''] + [term_line(l) for l in passes[11:]] + ['', f'<span class="ok">{_html.escape(out_lines[-1])}</span>'])
site = OUT / 'docs'; site.mkdir(parents=True, exist_ok=True)
(site / '.nojekyll').write_text('')
page = (HERE / 'templates/site.html').read_text()
for k, v in {'__CHART__': (HERE / 'templates/site-chart.html').read_text(), '__TERM__': term, '__ZIP_URL__': ZIP_URL}.items():
    assert k in page, k; page = page.replace(k, v)
(site / 'index.html').write_text(page)
for f in ['beam-1m-by-ability.svg', 'social-card.png']: shutil.copy2(assets / f, site / f)

# ---------- 8. the release download: the public package as one zip (kept outside both repositories' history) ----------
dist = HERE / 'dist'; dist.mkdir(exist_ok=True); (dist / ZIP).unlink(missing_ok=True)
subprocess.run(['zip', '-q', '-r', '-X', str(dist / ZIP), 'beam-1m', '-x', '*.DS_Store'], cwd=OUT, check=True)
print('release zip:', dist / ZIP, f'{(dist / ZIP).stat().st_size / 1e6:.1f} MB', sha((dist / ZIP).read_bytes()))

# ---------- 9. refuse to publish code, prompts or keys ----------
banned_ext = {'.mjs', '.ts', '.tsx', '.yaml', '.yml', '.patch'}
bad = [str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and '.git' not in p.parts and p.suffix in banned_ext]
assert not bad, f'code files in the public copy: {bad}'
markers = [b'<role>', b'You prepare answers to questions', b'You write the final answer', b'You extract index terms for a BM25', b'"caller":']
keys = []
envf = ROOT / '.env'
if envf.exists():
    for line in envf.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            v = line.split('=', 1)[1].strip().strip('"').strip("'")
            if len(v) >= 12: keys.append(v.encode())
leaks = []
for p in list(OUT.rglob('*')) + [dist / ZIP]:
    if not p.is_file() or '.git' in p.parts: continue
    b = p.read_bytes(); b = gzip.decompress(b) if p.suffix == '.gz' else b
    if p.name != 'build_public.py': leaks += [f'{p.relative_to(OUT) if OUT in p.parents else p.name}: prompt text {m[:20]!r}' for m in markers if m in b]
    leaks += [f'{p.name}: an API key value' for k in keys if k in b]
assert not leaks, leaks
print(f'public copy written to {OUT}; no code files, prompt text or key values found')

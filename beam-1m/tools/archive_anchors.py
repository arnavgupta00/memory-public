"""Independent archive of the public records this result relies on (12 Oct 2026).

Before the development repository (github.com/arnavgupta00/memory) was made private, the GitHub records that date the
split and the freeze were saved to the Internet Archive's Wayback Machine (https://web.archive.org/save/<url>):
GitHub's server-side push log, the freeze tag, the freeze commit, the freeze-time hash manifest (FROZEN.json, file hashes
only, no code) and the five split files (question IDs and checksums only).

This script finds each URL's snapshot in the Wayback index, downloads the archived bytes, checks them against this package,
and writes data/questions/independent-archives.json. verify.py --online repeats the content checks.

Usage (package root): python3 tools/archive_anchors.py
"""
import gzip, hashlib, json, pathlib, re, urllib.parse, urllib.request

PKG = pathlib.Path(__file__).resolve().parents[1]
FREEZE = '595a2e28228c21cf842378fb9216cacb46478fd3'; SPLIT = '2e1719d385a28cb3728626e68230328ea4cb6a24'; ALLOC = 'f3961ce7bdf27c48691d630765678a7d5aefa3c8'
E = 'src/agents/current/eval-slices/beam-1m'; RAW = 'https://raw.githubusercontent.com/arnavgupta00/memory'
TARGETS = [
    ('push log', 'https://api.github.com/repos/arnavgupta00/memory/activity?per_page=100', None),
    ('freeze tag', 'https://api.github.com/repos/arnavgupta00/memory/git/refs/tags/r9-freeze-20261011', None),
    ('freeze commit', f'https://api.github.com/repos/arnavgupta00/memory/git/commits/{FREEZE}', None),
    ('freeze manifest (FROZEN.json)', f'{RAW}/{FREEZE}/src/agents/current/src/pipeline/a6/FROZEN.json', 'code/public-freeze/src/agents/current/src/pipeline/a6/FROZEN.json'),
] + [(f'split file {n}', f'{RAW}/{SPLIT}/{E}/{n}', f'data/questions/partition-files/{n}') for n in
     ['beam-1m-canary-design-v1.json', 'beam-1m-canary-a-development-v1.json', 'beam-1m-canary-b-certification-v1.json', 'beam-1m-blind-reserve-v1.json']] + [
    ('allocation record (24 Sep)', f'{RAW}/{ALLOC}/{E}/beam-1m-holdout-allocation-20260924.json', 'data/questions/partition-files/beam-1m-holdout-allocation-20260924.json')]
sha = lambda b: hashlib.sha256(b).hexdigest()

out = []
for what, url, pkg_file in TARGETS:
    q = 'https://web.archive.org/cdx/search/cdx?' + urllib.parse.urlencode({'url': url, 'output': 'json', 'filter': 'statuscode:200'})
    rows = json.load(urllib.request.urlopen(q, timeout=60))
    assert len(rows) > 1, f'no snapshot for {url}'
    ts = rows[1][1]   # the earliest snapshot
    snap = f'https://web.archive.org/web/{ts}/{url}'
    b = urllib.request.urlopen(f'https://web.archive.org/web/{ts}id_/{url}', timeout=120).read()
    b = gzip.decompress(b) if b[:2] == b'\x1f\x8b' else b
    rec = {'what': what, 'url': url, 'snapshot': snap, 'archived_utc': f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z',
           'archived_content_sha256': sha(b)}
    if pkg_file:
        rec['package_file'] = pkg_file
        assert sha(b) == sha((PKG / pkg_file).read_bytes()), f'{what}: archived copy differs from the package'
    if what == 'push log':
        hit = [e for e in json.loads(b) if e.get('after') == FREEZE]; assert hit, 'freeze push missing from the archived log'
        rec['shows'] = f"push of {FREEZE[:8]} to {hit[0]['ref']} at {hit[0]['timestamp']}"
        freeze_pushed = hit[0]['timestamp']
    if what == 'freeze tag': rec['shows'] = 'tag object ' + json.loads(b)['object']['sha']
    if what == 'freeze commit':
        d = json.loads(b); assert d['sha'] == FREEZE; rec['shows'] = f"commit {d['sha'][:8]}, committed {d['committer']['date']}"
    out.append(rec); print(f"{what:45} {rec['archived_utc']}  ok")

(PKG / 'data/questions/independent-archives.json').write_text(json.dumps({
    'note': "Third-party copies (Internet Archive, Wayback Machine) of the public GitHub records that date the split and the freeze, "
            "saved on 12 Oct 2026 while the development repository was still public. Each archived copy's content is checked against "
            "this package; verify.py --online repeats the check.",
    'freeze_commit': FREEZE, 'freeze_pushed_utc': freeze_pushed, 'archives': out}, indent=1) + '\n')
print('written data/questions/independent-archives.json')

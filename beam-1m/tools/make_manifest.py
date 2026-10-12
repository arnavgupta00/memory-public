"""Write MANIFEST.sha256: the sha256 of every file in the package (except the manifest itself), sorted by path."""
import hashlib, pathlib
PKG = pathlib.Path(__file__).resolve().parents[1]
lines = []
for p in sorted(PKG.rglob('*')):
    if p.is_file() and p.name not in ('MANIFEST.sha256', '.DS_Store'):
        lines.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(PKG).as_posix()}')
(PKG / 'MANIFEST.sha256').write_text('\n'.join(lines) + '\n')
print(len(lines), 'files hashed')

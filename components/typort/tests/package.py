from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
paths = [p for p in root.rglob('*') if p.is_file() and not any(part in ('artifacts', '__pycache__', '.git') for part in p.relative_to(root).parts)]
destination = root / 'artifacts' / 'mariotyport.zip'
with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
    for path in paths:
        archive.write(path, (Path('mariotyport') / path.relative_to(root)).as_posix())
print(f'{destination}: {len(paths)} files, {destination.stat().st_size} bytes')

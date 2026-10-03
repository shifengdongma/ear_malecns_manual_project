from __future__ import annotations

import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def manifest(files: list[Path], **metadata) -> dict:
    packages = {}
    for name in ['ear-malecns', 'numpy', 'pandas', 'brian2', 'neuprint-python', 'networkx', 'pyarrow']:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = 'not installed'
    return {'created_utc': datetime.now(timezone.utc).isoformat(),
            'packages': packages, 'files': {p.name: sha256(p) for p in files}, **metadata}


def verify_manifest(directory: Path) -> dict:
    meta = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in meta['files'].items():
        if Path(name).name != name:
            raise ValueError('Manifest file entries must be local filenames')
        path = directory / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f'Frozen data checksum mismatch: {name}')
    return meta

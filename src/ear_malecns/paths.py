"""One H-drive project root, independent of the caller's working directory."""
from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    default = Path(__file__).resolve().parents[2]
    root = Path(os.environ.get('EAR_MALECNS_PROJECT', default)).absolute()
    resolved = root.resolve()
    on_h = resolved.drive.lower() == 'h:' if os.name == 'nt' else resolved.is_relative_to('/mnt/h')
    if not on_h or not root.is_dir():
        raise RuntimeError('EAR_MALECNS_PROJECT must be an existing project directory on H: (WSL: /mnt/h).')
    if os.name != 'nt' and not Path('/mnt/h').is_mount():
        raise RuntimeError('H drive is not mounted at /mnt/h; refusing to write into the Linux system disk.')
    return root


def configure_storage() -> Path:
    root = project_root()
    directories = ['data/raw/malecns', 'data/raw/openear', 'data/raw/physiology',
                   'data/processed', 'fem/geometry', 'fem/mesh', 'fem/models',
                   'fem/results', 'fem/hdf5', 'skeletons/male-cns-v1.0',
                   'outputs/runs', 'outputs/parameter_sweeps', 'outputs/figures',
                   'build/brian2', 'downloads/pip-cache', 'downloads/tmp',
                   'downloads/matplotlib', 'downloads/cache']
    for directory in directories:
        (root / directory).mkdir(parents=True, exist_ok=True)
    for name, relative in {'PIP_CACHE_DIR': 'downloads/pip-cache',
                           'TMP': 'downloads/tmp', 'TEMP': 'downloads/tmp',
                           'TMPDIR': 'downloads/tmp', 'MPLCONFIGDIR': 'downloads/matplotlib',
                           'XDG_CACHE_HOME': 'downloads/cache'}.items():
        os.environ[name] = str(root / relative)
    os.environ['MPLBACKEND'] = 'Agg'
    import tempfile
    tempfile.tempdir = str(root / 'downloads/tmp')
    return root

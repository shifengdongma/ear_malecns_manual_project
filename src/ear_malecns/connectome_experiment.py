"""Brain-first workflow: frozen JON events -> real MaleCNS topology controls."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

import numpy as np
import pandas as pd

from .config import load_config
from .paths import configure_storage
from .pipeline import control_snapshot
from .provenance import verify_manifest, write_json, manifest, sha256
from .stage1 import fixed_events, run_stage1


def main(argv=None):
    root = configure_storage()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=root / 'configs/stage1_auditory_only.yaml')
    parser.add_argument('--input', type=Path, help='Frozen channel NPZ, including FEM-encoder output')
    parser.add_argument('--controls', action='store_true')
    parser.add_argument('--run-id', default=datetime.now(timezone.utc).strftime('connectome_%Y%m%dT%H%M%S_%fZ'))
    args = parser.parse_args(argv)
    if not re.fullmatch('[A-Za-z0-9_-]+', args.run_id):
        parser.error('Invalid run ID')
    snapshot = args.snapshot.resolve()
    if not snapshot.is_relative_to(root.resolve()):
        parser.error('Snapshot must reside in project')
    meta = verify_manifest(snapshot)
    if meta['source'] not in ['PUBLIC_MALECNS_V1_0', 'NEUPRINT_MALECNS']:
        parser.error('This brain experiment requires real MaleCNS structural data')
    cfg = load_config(args.config)
    ids = sorted(pd.read_csv(snapshot / 'auditory_input_cells.csv').bodyId.astype(int))
    if args.input:
        with np.load(args.input, allow_pickle=False) as data:
            if list(data['body_ids']) != ids:
                parser.error('Input body ID order differs from snapshot seed order')
            channels, times = data['channels'].copy(), data['times_s'].copy()
            if not np.issubdtype(channels.dtype, np.integer):
                parser.error('Input channel indices must be integers')
            for key, expected in [('dt_ms', cfg['snn']['dt_ms']), ('duration_ms', cfg['snn']['simulation_ms'])]:
                if key in data and not np.isclose(float(data[key]), expected):
                    parser.error(f'Input {key} differs from simulation')
        if channels.ndim != 1 or times.shape != channels.shape or not np.isfinite(times).all() or (times < 0).any() or (times >= cfg['snn']['simulation_ms'] / 1000).any() or (channels < 0).any() or (channels >= len(ids)).any():
            parser.error('Invalid frozen input events')
        bins = np.floor((times + 1e-13) / (cfg['snn']['dt_ms'] / 1000)).astype(np.int64)
        if len(set(zip(channels, bins))) != len(times):
            parser.error('Input has colliding channel/time bins; encode on simulation grid')
    else:
        channels, times = fixed_events(ids, cfg)
    parent = root / 'outputs/runs' / args.run_id
    parent.mkdir(parents=True, exist_ok=False)
    rows, runs, input_hashes = [], {}, []
    for kind in ['original', 'rewired', 'weight_shuffled'] if args.controls else ['original']:
        selected = snapshot
        if kind != 'original':
            selected = parent / (kind + '_snapshot')
            control_snapshot(snapshot, selected, kind, cfg['project']['seed'])
        out, metrics = run_stage1(root, cfg, selected, args.run_id + '_' + kind,
                                  input_events=(channels, times))
        input_hashes.append(sha256(out / 'fixed_input.npz'))
        neuron_metrics = pd.read_csv(out / 'neuron_metrics.csv')
        rows.append(dict(topology=kind, network_spikes=metrics['network_spikes'],
            software_checks_pass=metrics['software_checks_pass'], mean_stimulus_hz=metrics['mean_stimulus_hz'],
            downstream_active_fraction=float(neuron_metrics.loc[~neuron_metrics.is_seed, 'active'].mean())))
        runs[kind] = dict(path=str(out), manifest_sha256=sha256(out / 'manifest.json'))
    if len(set(input_hashes)) != 1:
        raise ValueError('Topology comparisons used different inputs')
    pd.DataFrame(rows).to_csv(parent / 'comparison.csv', index=False)
    write_json(parent / 'config.json', cfg)
    write_json(parent / 'manifest.json', manifest(list(parent.glob('*.csv')) + [parent / 'config.json'],
        source=meta['source'], dataset=meta['dataset'], runs=runs, identical_control_input=True,
        input_origin='external_frozen_input' if args.input else 'fixed_20_100_20_Hz_engineering_drive',
        external_input_sha256=sha256(args.input) if args.input else None,
        fixed_input_sha256=input_hashes[0], source_code_sha256={str(p.relative_to(root)): sha256(p) for p in sorted((root / 'src').rglob('*.py'))},
        limitations=['Real structural data; assumed LIF dynamics, not measured neural activity.',
                     'A 265-neuron auditory subgraph is not a whole-brain simulation.']))
    print(parent, flush=True)
    print(pd.DataFrame(rows).to_string(index=False), flush=True)
    return 0 if all(r['software_checks_pass'] for r in rows) else 2

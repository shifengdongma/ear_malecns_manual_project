"""Explicit FEM/encoder bridge and frozen-input topology comparisons."""
from pathlib import Path
import argparse
import copy
import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import networkx as nx

from .config import load_config
from .fem_io import read_fem_h5
from .experiment import make_selftest_fem
from .encoder import robust_envelope_feature, adaptive_rate_encoder
from .provenance import manifest, write_json, verify_manifest, sha256
from .stage1 import prepare_data, run_stage1
from .controls import degree_preserving_rewire
from .malecns import add_local_input_fraction, save_subgraph


def calibrate(paths, tau_ms):
    """Pool training log envelopes; never fit on each test signal separately."""
    from scipy.signal import hilbert
    from scipy.ndimage import gaussian_filter1d
    values = []
    for path in paths:
        data = read_fem_h5(path)
        env = gaussian_filter1d(np.abs(hilbert(data['stapes_velocity_m_s'])),
                               max(tau_ms * .001 * data['sample_rate_hz'], 1.0))
        values.append(np.log(env + 1e-15))
    if not values:
        raise ValueError('At least one calibration FEM file is required')
    low, high = np.quantile(np.concatenate(values), [.05, .95])
    if high <= low:
        raise ValueError('Calibration set has no envelope dynamic range')
    return dict(q_low=float(low), q_high=float(high), envelope_tau_ms=tau_ms,
                source_files={str(p): sha256(p) for p in paths})


def encode_events(data, cfg, calibration, count):
    e = cfg['encoder']
    if calibration['envelope_tau_ms'] != e['envelope_tau_ms']:
        raise ValueError('Calibration smoothing differs from encoder configuration')
    z, _ = robust_envelope_feature(data['stapes_velocity_m_s'], data['sample_rate_hz'],
                                  e['envelope_tau_ms'], calibration['q_low'], calibration['q_high'])
    rate = adaptive_rate_encoder(z, data['sample_rate_hz'], **{k: e[k] for k in
                    ['adaptation_tau_ms', 'r_base_hz', 'r_max_hz', 'threshold', 'gain']})
    dt = cfg['snn']['dt_ms'] / 1000
    duration = cfg['snn']['simulation_ms'] / 1000
    steps = round(duration / dt)
    if not np.isclose(steps * dt, duration) or not np.isclose(len(z) / data['sample_rate_hz'], duration):
        raise ValueError('FEM duration and simulation duration must agree on the simulation grid')
    # Integrate rate on the simulation grid instead of rounding sampled spikes,
    # which could put several spikes from a channel into one Brian2 time bin.
    cumulative = np.r_[0., np.cumsum(rate) / data['sample_rate_hz']]
    boundaries = np.arange(steps + 1) * dt
    mass = np.diff(np.interp(boundaries, np.arange(len(rate) + 1) / data['sample_rate_hz'], cumulative))
    probability = -np.expm1(-mass)
    rng = np.random.default_rng(cfg['project']['seed'])
    channels, bins = np.nonzero(rng.random((count, steps)) < probability)
    times = bins * dt
    order = np.lexsort((channels, times))
    return channels[order], times[order], z, rate


def control_snapshot(source, target, kind, seed):
    meta = verify_manifest(source)
    nodes = pd.read_parquet(source / 'nodes.parquet')
    edges = pd.read_parquet(source / 'edges.parquet')
    graph = nx.from_pandas_edgelist(edges, 'bodyId_pre', 'bodyId_post', edge_attr='weight', create_using=nx.DiGraph)
    graph.add_nodes_from(nodes.bodyId)
    stats = {}
    if kind == 'rewired':
        transformed = degree_preserving_rewire(graph, seed=seed)
        stats = transformed.graph
        edges = nx.to_pandas_edgelist(transformed).rename(columns={'source': 'bodyId_pre', 'target': 'bodyId_post'})
        if dict(graph.in_degree()) != dict(transformed.in_degree()) or dict(graph.out_degree()) != dict(transformed.out_degree()):
            raise ValueError('Rewiring changed node degree')
    else:
        edges['weight'] = np.random.default_rng(seed).permutation(edges.weight.to_numpy())
    target.mkdir(parents=True, exist_ok=False)
    save_subgraph(nodes, add_local_input_fraction(edges[['bodyId_pre', 'bodyId_post', 'weight']]), target)
    (target / 'auditory_input_cells.csv').write_bytes((source / 'auditory_input_cells.csv').read_bytes())
    write_json(target / 'manifest.json', manifest(list(target.iterdir()), source=meta['source'],
               dataset=meta.get('dataset'), topology_control=kind, control_seed=seed,
               parent_manifest_sha256=sha256(source / 'manifest.json'), rewire_statistics=stats,
               hop_labels='Original discovery hops retained for comparable groups'))


def main(argv=None):
    from .paths import configure_storage
    root = configure_storage()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, help='Frozen real-data snapshot; omitted uses synthetic fixture')
    parser.add_argument('--fem', type=Path, help='Validated FEM HDF5; omitted uses synthetic self-test')
    parser.add_argument('--calibration', type=Path, help='Previously frozen calibration JSON')
    parser.add_argument('--calibrate-fem', type=Path, nargs='+', help='Training FEM set to fit shared quantiles')
    parser.add_argument('--config', type=Path, default=root / 'configs/pipeline.yaml')
    parser.add_argument('--run-id', default=datetime.now(timezone.utc).strftime('pipeline_%Y%m%dT%H%M%S_%fZ'))
    parser.add_argument('--controls', action='store_true')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.run_id):
        parser.error('Invalid run ID')
    if args.calibration and args.calibrate_fem:
        parser.error('Choose existing calibration or training files')
    if args.fem and not (args.calibration or args.calibrate_fem):
        parser.error('External FEM requires explicit calibration or a training FEM set')
    cfg = load_config(args.config)
    out = root / 'outputs/runs' / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    snapshot = args.snapshot.resolve() if args.snapshot else prepare_data(root, cfg, 'offline', args.run_id)
    if not snapshot.is_relative_to(root.resolve()):
        raise ValueError('Snapshot must reside inside this project')
    verify_manifest(snapshot)
    fem = args.fem.resolve() if args.fem else make_selftest_fem(out / 'synthetic_selftest.h5', cfg)
    calibration = json.loads(args.calibration.read_text(encoding='utf-8')) if args.calibration else calibrate(
        args.calibrate_fem or [fem], cfg['encoder']['envelope_tau_ms'])
    write_json(out / 'calibration.json', calibration)
    data = read_fem_h5(fem)
    body_ids = sorted(pd.read_csv(snapshot / 'auditory_input_cells.csv').bodyId.astype(int))
    channels, times, feature, rate = encode_events(data, cfg, calibration, len(body_ids))
    np.savez_compressed(out / 'encoder.npz', body_ids=body_ids, channels=channels, times_s=times,
                        normalized_feature=feature, rate_hz=rate, sample_rate_hz=data['sample_rate_hz'])
    cfg = copy.deepcopy(cfg)
    cfg['fixed_input'] = {**cfg.get('fixed_input', {}), 'onset_s': cfg['stimulus']['onset_s'],
                          'offset_s': cfg['stimulus']['offset_s']}
    records, run_manifests, hashes = [], {}, []
    for kind in ['original', 'rewired', 'weight_shuffled'] if args.controls else ['original']:
        selected = snapshot
        if kind != 'original':
            selected = out / (kind + '_snapshot')
            control_snapshot(snapshot, selected, kind, cfg['project']['seed'])
        run, metrics = run_stage1(root, cfg, selected, args.run_id + '_' + kind, input_events=(channels, times))
        hashes.append(sha256(run / 'fixed_input.npz'))
        run_manifests[kind] = dict(path=str(run), sha256=sha256(run / 'manifest.json'))
        records.append(dict(topology=kind, network_spikes=metrics['network_spikes'],
                            mean_stimulus_hz=metrics['mean_stimulus_hz'],
                            software_checks_pass=metrics['software_checks_pass']))
    if len(set(hashes)) != 1:
        raise ValueError('Topology controls did not replay identical input')
    pd.DataFrame(records).to_csv(out / 'comparison.csv', index=False)
    write_json(out / 'config.json', cfg)
    write_json(out / 'manifest.json', manifest([p for p in out.iterdir() if p.is_file()],
               fem_version=data['fem_version'], fem_sha256=sha256(fem), graph_source=verify_manifest(snapshot)['source'],
               calibration_mode='external_shared' if args.calibration or args.calibrate_fem else 'SELFTEST_ONLY',
               identical_control_input=True, runs=run_manifests,
               source_code_sha256={str(p.relative_to(root)): sha256(p) for p in sorted((root / 'src').rglob('*.py'))},
               limitations=['Encoder is an assumed surrogate, not physiology-fitted.',
                            'Envelope-only M1 does not provide carrier frequency discrimination.',
                            'Synthetic fixture and transfer validate software only.']))
    print(json.dumps(dict(output=str(out), comparison=records), indent=2))
    return 0 if all(r['software_checks_pass'] for r in records) else 2

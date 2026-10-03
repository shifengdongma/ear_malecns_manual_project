"""Stage 1: fixed sensory events -> small connectome-constrained LIF network.

The offline fixture proves software behavior only and is never MaleCNS data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

import numpy as np
import pandas as pd

from .config import load_config
from .malecns import (make_client, discover_auditory_jons, fetch_downstream_hops,
                      add_local_input_fraction, save_subgraph, seed_annotation_audit)
from .provenance import manifest, sha256, verify_manifest, write_json


def synthetic_fixture():
    """Negative IDs and explicit names prevent confusion with real body IDs."""
    ids = np.arange(-120, 0, dtype=np.int64)
    nodes = pd.DataFrame({'bodyId': ids, 'type': ['SYNTHETIC_INPUT'] * 30 + ['SYNTHETIC_HOP1'] * 45 + ['SYNTHETIC_HOP2'] * 45,
                          'hop': [0] * 30 + [1] * 45 + [2] * 45,
                          'is_seed': [True] * 30 + [False] * 90, 'consensusNt': 'ACh'})
    edges = pd.DataFrame([(int(a), int(b), 10) for source, target in [(ids[:30], ids[30:75]), (ids[30:75], ids[75:])]
                         for a in source for b in target], columns=['bodyId_pre', 'bodyId_post', 'weight'])
    return nodes, edges, nodes[nodes.is_seed].copy()


def fixed_events(body_ids, cfg: dict):
    s, drive = cfg['snn'], cfg['fixed_input']
    dt = float(s['dt_ms']) / 1000
    duration = float(s['simulation_ms']) / 1000
    if not np.isfinite([dt, duration]).all() or dt <= 0 or duration <= 0:
        raise ValueError('Duration and dt must be finite and positive')
    onset, offset = float(drive['onset_s']), float(drive['offset_s'])
    baseline, stimulated = float(drive['baseline_hz']), float(drive['stimulus_hz'])
    if not np.isfinite([onset, offset, baseline, stimulated]).all() or not 0 < onset < offset < duration or min(baseline, stimulated) < 0 or max(baseline, stimulated) * dt > 1:
        raise ValueError('Invalid fixed-input rates, windows, or dt')
    steps = duration / dt
    if dt <= 0 or abs(steps - round(steps)) > 1e-8:
        raise ValueError('Duration must be an integer multiple of positive dt')
    times = np.arange(round(steps)) * dt
    rates = np.where((times >= onset) & (times < offset), stimulated, baseline)
    rng = np.random.default_rng(int(cfg['project']['seed']))
    # Independent channel draws, frozen once, replayed for every scenario.
    all_channels, all_times = [], []
    for channel in range(len(body_ids)):
        sampled = times[rng.random(len(times)) < rates * dt]
        all_channels.extend([channel] * len(sampled))
        all_times.extend(sampled)
    order = np.lexsort((all_channels, all_times))
    return np.asarray(all_channels, dtype=np.int64)[order], np.asarray(all_times)[order]


def prepare_data(root: Path, cfg: dict, mode: str, snapshot_id: str) -> Path:
    if mode == 'offline':
        directory = root / 'data/processed/offline_fixture' / snapshot_id
        nodes, edges, seeds = synthetic_fixture()
        source = 'SYNTHETIC_SOFTWARE_TEST_NOT_MALECNS'
        extra = {}
    elif mode == 'public':
        from .bulk import public_subgraph
        nodes, edges, seeds, extra = public_subgraph(root, cfg['malecns'])
        directory = root / 'data/processed/malecns_snapshots' / snapshot_id
        source = 'PUBLIC_MALECNS_V1_0'
    else:
        m = cfg['malecns']
        client = make_client(m['server'], m['dataset'])
        from neuprint import fetch_meta
        server_meta = fetch_meta(client=client)  # a real dataset request, not merely Client creation
        if server_meta.get('dataset') != m['dataset']:
            raise ValueError('Server returned a different dataset')
        seeds = discover_auditory_jons(client, m['jon_type_regex'], m['auditory_type_regex'])
        audit = seed_annotation_audit(seeds, m.get('seed_subclass'))
        if m.get('seed_subclass'):
            seeds = seeds[seeds['subclass'] == m['seed_subclass']].copy()
        nodes, edges = fetch_downstream_hops(seeds.bodyId.astype(int).tolist(), client,
                     hops=int(m['hops']), min_weight=int(m['min_weight']),
                     max_new_nodes_per_hop=int(m['max_new_nodes_per_hop']), max_nodes=int(m['max_nodes']),
                     status_filter=m.get('status_filter'))
        directory = root / 'data/processed/malecns_snapshots' / snapshot_id
        source = 'NEUPRINT_MALECNS'
        extra = {'server': m['server'], 'dataset': m['dataset'],
                 'dataset_metadata': {k: server_meta.get(k) for k in ['dataset', 'uuid', 'lastDatabaseEdit', 'latestMutationId']},
                 'query_config': m, 'seed_annotation_audit': audit, 'annotation_review': 'PENDING_HUMAN_REVIEW'}
    directory.mkdir(parents=True, exist_ok=False)
    edges = add_local_input_fraction(edges)
    save_subgraph(nodes, edges, directory)
    seeds.to_csv(directory / 'auditory_input_cells.csv', index=False)
    files = [directory / name for name in ['nodes.parquet', 'edges.parquet', 'auditory_subgraph.graphml', 'auditory_input_cells.csv']]
    if 'seed_annotation_audit' in extra:
        pd.DataFrame(extra['seed_annotation_audit']).to_csv(directory / 'seed_annotation_audit.csv', index=False)
        files.append(directory / 'seed_annotation_audit.csv')
    write_json(directory / 'manifest.json', manifest(files, source=source, node_count=len(nodes), edge_count=len(edges), **extra))
    return directory


def run_simulation(nodes, edges, body_ids, channels, times, cfg, *, silence=False):
    from brian2 import Network, defaultclock, ms, prefs, seed, start_scope
    from .snn import build_lif_network, attach_event_input
    from .analysis import spike_table
    start_scope()
    prefs.codegen.target = 'numpy'  # stage-1 CPU, no compiler cache on the system disk
    defaultclock.dt = float(cfg['snn']['dt_ms']) * ms
    seed(int(cfg['project']['seed']))
    keys = ['tau_m_ms', 'e_l_mv', 'v_th_mv', 'v_reset_mv', 'refractory_ms', 'delay_ms', 'w0_mv', 'uncertain_sign']
    params = {key: float(cfg['snn'][key]) for key in keys}
    nt_col = next((x for x in ['consensusNt', 'predictedNt'] if x in nodes), None)
    nt_map = {} if nt_col is None else nodes.set_index('bodyId')[nt_col].dropna().astype(str).to_dict()
    group, syn, spikes, voltage, to_idx, to_body = build_lif_network(nodes, edges, nt_map=nt_map, **params)
    network = Network(group, syn, spikes, voltage)
    source, drive = attach_event_input(group, to_idx, body_ids,
                    channels[:0] if silence else channels, times[:0] if silence else times,
                    float(cfg['snn']['input_weight_mv']))
    network.add(source, drive)
    network.run(float(cfg['snn']['simulation_ms']) * ms)
    table = spike_table(spikes, to_body)
    return table


def summarize(nodes, spikes, cfg):
    onset = 1000 * float(cfg['fixed_input']['onset_s'])
    offset = 1000 * float(cfg['fixed_input']['offset_s'])
    end = float(cfg['snn']['simulation_ms'])
    result = nodes[['bodyId', 'type', 'hop', 'is_seed']].copy()
    for name, lo, hi in [('baseline', 0, onset), ('stimulus', onset, offset), ('recovery', offset, end)]:
        counts = spikes[(spikes.time_ms >= lo) & (spikes.time_ms < hi)].groupby('bodyId').size()
        result[name + '_spikes'] = result.bodyId.map(counts).fillna(0).astype(int)
        result[name + '_rate_hz'] = result[name + '_spikes'] * 1000 / (hi - lo) if hi > lo else 0.0
    result['active'] = result.stimulus_spikes > 0
    hops = result.groupby('hop', as_index=False).agg(neurons=('bodyId', 'size'), active_neurons=('active', 'sum'),
                                                 stimulus_rate_hz=('stimulus_rate_hz', 'mean'))
    hops['activation_fraction'] = hops.active_neurons / hops.neurons
    return result, hops


def save_graph_figure(nodes, edges, path, source):
    import matplotlib.pyplot as plt
    import networkx as nx
    graph = nx.from_pandas_edgelist(edges, 'bodyId_pre', 'bodyId_post', create_using=nx.DiGraph)
    graph.add_nodes_from(nodes.bodyId.tolist())
    positions = {}
    for hop, group in nodes.groupby('hop'):
        for i, body in enumerate(sorted(group.bodyId)):
            positions[body] = (int(hop), (i + .5) / len(group))
    fig, ax = plt.subplots(figsize=(10, 7))
    nx.draw_networkx_edges(graph, positions, ax=ax, alpha=.025, arrows=False, width=.5)
    colors = nodes.set_index('bodyId').hop.to_dict()
    nx.draw_networkx_nodes(graph, positions, ax=ax, node_size=22,
                          node_color=[colors[x] for x in graph], cmap='viridis')
    ax.set_title(f'{source}\nGraph structure; no anatomical coordinates')
    ax.set_xlabel('Discovery hop'); ax.set_ylabel('Within-hop display order')
    ax.tick_params(left=False, labelleft=False, bottom=True, labelbottom=True)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def run_stage1(root, cfg, data_dir, run_id, *, input_events=None):
    from .analysis import first_spike_latency, save_raster
    meta = verify_manifest(data_dir)
    required = {'nodes.parquet', 'edges.parquet', 'auditory_input_cells.csv', 'auditory_subgraph.graphml'}
    if not required.issubset(meta['files']):
        raise ValueError('Snapshot manifest must cover nodes, edges, seeds and graph')
    if meta['source'] in ['NEUPRINT_MALECNS', 'PUBLIC_MALECNS_V1_0'] and meta.get('dataset') != cfg['malecns']['dataset']:
        raise ValueError('Snapshot dataset differs from configured dataset')
    if meta['source'] not in ['NEUPRINT_MALECNS', 'PUBLIC_MALECNS_V1_0', 'SYNTHETIC_SOFTWARE_TEST_NOT_MALECNS']:
        raise ValueError('Unknown snapshot source')
    nodes = pd.read_parquet(data_dir / 'nodes.parquet')
    edges = pd.read_parquet(data_dir / 'edges.parquet')
    seeds = pd.read_csv(data_dir / 'auditory_input_cells.csv')
    if not {'hop', 'is_seed', 'type'}.issubset(nodes):
        raise ValueError('Use a stage-1 snapshot with hop, is_seed, type metadata')
    if len(nodes) > int(cfg['malecns']['max_nodes']):
        raise ValueError('Snapshot exceeds configured max_nodes')
    body_ids = sorted(seeds.bodyId.astype(int).tolist())
    if set(body_ids) != set(nodes.loc[nodes.is_seed, 'bodyId']):
        raise ValueError('Snapshot seed CSV and node seed flags differ')
    out = root / 'outputs/runs' / run_id
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'config.json', cfg)
    # Freeze the exact structural snapshot next to the experiment.
    shutil.copytree(data_dir, out / 'graph_snapshot')
    channels, times = fixed_events(body_ids, cfg) if input_events is None else input_events
    np.savez_compressed(out / 'fixed_input.npz', body_ids=body_ids, channels=channels, times_s=times,
                        dt_ms=cfg['snn']['dt_ms'], duration_ms=cfg['snn']['simulation_ms'])
    spikes = run_simulation(nodes, edges, body_ids, channels, times, cfg)
    silent = run_simulation(nodes, edges, body_ids, channels, times, cfg, silence=True)
    spikes.to_parquet(out / 'spikes.parquet', index=False)
    onset = float(cfg['fixed_input']['onset_s']) * 1000
    offset = float(cfg['fixed_input']['offset_s']) * 1000
    latency = first_spike_latency(spikes, onset, nodes.bodyId, offset)
    latency.to_csv(out / 'latency.csv', index=False)
    per_neuron, hops = summarize(nodes, spikes, cfg)
    per_neuron.to_csv(out / 'neuron_metrics.csv', index=False)
    hops.to_csv(out / 'hop_metrics.csv', index=False)
    per_neuron.groupby('type', as_index=False)[['baseline_rate_hz', 'stimulus_rate_hz', 'recovery_rate_hz']].mean().to_csv(out / 'cell_type_rates.csv', index=False)
    title = f'{meta["source"]} / {meta.get("topology_control", "original")}: simulation-derived LIF activity'
    save_raster(spikes, out / 'raster.png', title)
    save_graph_figure(nodes, edges, out / 'graph.png', meta['source'])
    checks = {'size_100_to_300': 100 <= len(nodes) <= 300,
              'zero_input_no_spikes': len(silent) == 0,
              'sensory_response': bool(per_neuron.loc[per_neuron.is_seed, 'active'].any()),
              'downstream_response': bool(per_neuron.loc[~per_neuron.is_seed, 'active'].any()),
              'no_immediate_whole_network_burst': int(spikes[(spikes.time_ms >= onset) & (spikes.time_ms < onset + 2)].bodyId.nunique()) < .95 * len(nodes),
              'no_neuron_near_refractory_ceiling': bool((per_neuron.stimulus_rate_hz < .8 * 1000 / cfg['snn']['refractory_ms']).all()),
              'recovery_below_stimulus': bool(per_neuron.recovery_rate_hz.mean() < per_neuron.stimulus_rate_hz.mean())}
    metrics = {'checks': checks, 'software_checks_pass': all(checks.values()),
               'source': meta['source'], 'nodes': len(nodes), 'edges': len(edges),
               'network_spikes': len(spikes), 'fixed_input_events': len(times),
               'zero_input_spikes': len(silent),
               'mean_stimulus_hz': float(per_neuron.stimulus_rate_hz.mean()),
               'mean_recovery_hz': float(per_neuron.recovery_rate_hz.mean()),
               'real_malecns_acceptance': False,
               'limitations': ['LIF and synaptic gains are assumed; no physiological calibration.',
                              'Post-onset first spike is descriptive, not a causal response-latency estimate.',
                              'Recovery uses a 20 Hz baseline, not removal of all external input.',
                              'Real-data acceptance additionally needs annotation review, morphology and parameter sensitivity.']}
    write_json(out / 'metrics.json', metrics)
    files = [p for p in out.iterdir() if p.is_file()]
    write_json(out / 'manifest.json', manifest(files, source=meta['source'],
               graph_manifest_sha256=sha256(data_dir / 'manifest.json'),
               source_code_sha256={str(p.relative_to(root)): sha256(p) for p in sorted((root / 'src').rglob('*.py'))},
               status='PASS_SOFTWARE_CHECKS' if all(checks.values()) else 'REVIEW_REQUIRED'))
    return out, metrics


def main(argv=None):
    from .paths import configure_storage
    root = configure_storage()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['offline', 'live', 'public', 'cached'], default='offline')
    parser.add_argument('--config', type=Path, default=root / 'configs/stage1.yaml')
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--run-id', default=datetime.now(timezone.utc).strftime('stage1_%Y%m%dT%H%M%S_%fZ'))
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.run_id):
        parser.error('run-id must contain only letters, digits, underscore or hyphen')
    cfg = load_config(args.config)
    if args.mode == 'cached':
        if args.snapshot is None:
            parser.error('--snapshot is required for cached mode')
        data_dir = args.snapshot.resolve()
        if not data_dir.is_relative_to(root.resolve()):
            parser.error('snapshot must be stored inside the H-drive project')
    else:
        data_dir = prepare_data(root, cfg, args.mode, args.run_id)
    out, metrics = run_stage1(root, cfg, data_dir, args.run_id)
    print(json.dumps({'output': str(out), **metrics}, ensure_ascii=False, indent=2))
    return 0 if metrics['software_checks_pass'] else 2

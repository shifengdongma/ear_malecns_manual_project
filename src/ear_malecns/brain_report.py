"""Self-contained visual report from verified MaleCNS runs; no remote JS."""
import argparse
from pathlib import Path
import json
import html
import shutil

import numpy as np
import pandas as pd

from .paths import configure_storage
from .provenance import verify_manifest, sha256, write_json, manifest

COLORS = ['#38bdf8', '#fb923c', '#a78bfa']


def segments_from_swc(path, cap=1600):
    data = np.loadtxt(path, comments='#', ndmin=2)
    xyz = data[:, 2:5] * .008  # official 8 nm coordinate units -> micrometres
    lookup = {int(row[0]): i for i, row in enumerate(data)}
    segments = np.asarray([[xyz[i], xyz[lookup[int(row[6])]]] for i, row in enumerate(data)
                           if int(row[6]) in lookup])
    step = max(1, int(np.ceil(len(segments) / cap)))
    return np.round(segments[::step], 3), len(segments)


def load_runs(parent):
    meta = verify_manifest(parent)
    result = {}
    for kind, info in meta['runs'].items():
        path = Path(info['path'])
        expected = info.get('manifest_sha256', info.get('sha256'))
        if sha256(path / 'manifest.json') != expected:
            raise ValueError('Run manifest differs from parent record')
        verify_manifest(path)
        verify_manifest(path / 'graph_snapshot')
        result[kind] = path
    return meta, result


def data_bundle(root, parent, sweep, skeleton_dir):
    meta, paths = load_runs(parent)
    original = paths['original']
    nodes = pd.read_parquet(original / 'graph_snapshot/nodes.parquet').sort_values(['hop', 'bodyId'])
    cfg = json.loads((original / 'config.json').read_text(encoding='utf-8'))
    index = {int(body): i for i, body in enumerate(nodes.bodyId)}
    edges = pd.read_parquet(original / 'graph_snapshot/edges.parquet')
    ordered = edges.sort_values(['weight', 'bodyId_pre', 'bodyId_post'], ascending=[False, True, True])
    positions = {}
    for hop, group in nodes.groupby('hop'):
        for j, body in enumerate(group.bodyId):
            positions[int(body)] = [.13 + .37 * int(hop), .05 + .9 * (j + .5) / len(group)]
    indegree = edges.groupby('bodyId_post').size()
    outdegree = edges.groupby('bodyId_pre').size()
    rows = []
    for row in nodes.to_dict('records'):
        body = int(row['bodyId'])
        nt = row.get('consensusNt', row.get('predictedNt', 'unknown'))
        rows.append(dict(id=str(body), type=str(row.get('type', 'untyped')), hop=int(row['hop']),
                         nt='unknown' if pd.isna(nt) else str(nt),
                         pos=positions[body], indegree=int(indegree.get(body, 0)), outdegree=int(outdegree.get(body, 0))))
    runs = {}
    for kind, path in paths.items():
        current = pd.read_parquet(path / 'graph_snapshot/edges.parquet')
        stats = json.loads((path / 'metrics.json').read_text(encoding='utf-8'))
        spikes = pd.read_parquet(path / 'spikes.parquet').sort_values('time_ms')
        neurons = pd.read_csv(path / 'neuron_metrics.csv').set_index('bodyId')
        latency = pd.read_csv(path / 'latency.csv')
        latency_field = next((c for c in latency if c != 'bodyId' and 'latency' in c), None)
        latency_map = {} if latency_field is None else latency.set_index('bodyId')[latency_field].to_dict()
        trains = [[] for _ in rows]
        for body, time in spikes[['bodyId', 'time_ms']].itertuples(index=False, name=None):
            trains[index[int(body)]].append(round(float(time), 2))
        selected = current.sort_values(['weight', 'bodyId_pre', 'bodyId_post'], ascending=[False, True, True]).head(900)
        graph_meta = verify_manifest(path / 'graph_snapshot')
        runs[kind] = dict(spikes=trains, metrics=stats,
            hops=pd.read_csv(path / 'hop_metrics.csv').to_dict('records'),
            rates=[round(float(neurons.loc[int(n['id']), 'stimulus_rate_hz']), 3) for n in rows],
            latency=[None if pd.isna(latency_map.get(int(n['id']), np.nan)) else round(float(latency_map[int(n['id'])]), 2) for n in rows],
            edges=[[index[int(r.bodyId_pre)], index[int(r.bodyId_post)], int(r.weight)] for r in selected.itertuples()],
            rewire_statistics=graph_meta.get('rewire_statistics', {}))
    with np.load(original / 'fixed_input.npz') as archive:
        times = archive['times_s'] * 1000
        bins = np.arange(0, cfg['snn']['simulation_ms'] + 20, 20)
        rates = np.histogram(times, bins)[0] / .02 / len(archive['body_ids'])
        input_trace = [[float(t), round(float(r), 2)] for t, r in zip(bins[:-1], rates)]
        input_count = len(times)
    morphology = []
    if skeleton_dir:
        skel_meta = verify_manifest(skeleton_dir)
        for filename in skel_meta['files']:
            if not filename.endswith('.swc') or int(Path(filename).stem) not in index:
                continue
            segments, full_count = segments_from_swc(skeleton_dir / filename)
            morphology.append(dict(node=index[int(Path(filename).stem)], segments=segments.tolist(),
                                   original_segments=full_count, displayed_segments=len(segments)))
    annotations = pd.read_feather(root / 'data/raw/malecns/body-annotations-male-cns-v1.0-minconf-0.5.feather')
    traced = annotations[annotations.status == 'Traced']
    norm = traced.type.fillna('').str.match(cfg['malecns']['auditory_type_regex'])
    candidate_counts = traced.loc[norm, 'subclass'].fillna('missing').value_counts().to_dict()
    audit = dict(annotated_rows=len(annotations), traced_rows=len(traced),
                 jo_name_candidate_counts={str(k): int(v) for k, v in candidate_counts.items()})
    sensitivity = []
    if sweep:
        verify_manifest(sweep)
        sensitivity = pd.read_csv(sweep / 'summary.csv').to_dict('records')
    return dict(nodes=rows, runs=runs, skeletons=morphology, input_trace=input_trace,
                config=cfg, input_count=input_count, duration=cfg['snn']['simulation_ms'],
                edge_count=len(edges), seed_count=int(nodes.is_seed.sum()),
                source=meta['source'], dataset=meta['dataset'], audit=audit,
                sensitivity=sensitivity, run_id=parent.name,
                identical_control_input=meta['identical_control_input'])


def static_figures(data, paths, output):
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    fig = plt.figure(figsize=(16, 13), layout='constrained')
    grid = fig.add_gridspec(4, 3, height_ratios=[.6, 1, 2.5, 2.5])
    title = fig.add_subplot(grid[0, :]); title.axis('off')
    title.text(0, .8, 'MaleCNS v1.0 | Real structure, explicit neural simulation', fontsize=21, weight='bold')
    title.text(0, .17, 'Official files  >  audited JO-A/B seeds  >  1-2 hop graph  >  frozen input  >  LIF  >  activity / controls', fontsize=13)
    input_ax = fig.add_subplot(grid[1, :2])
    trace = np.asarray(data['input_trace'])
    input_ax.step(trace[:, 0], trace[:, 1], where='post', color=COLORS[0])
    input_ax.axvspan(200, 800, color='#e6f1f7', zorder=0)
    input_ax.set(xlim=(0, data['duration']), ylabel='Hz / channel', title=f'Frozen JON engineering input | {data["seed_count"]} channels, {data["input_count"]:,} events')
    note = fig.add_subplot(grid[1, 2]); note.axis('off')
    note.text(0, .95, f'{len(data["nodes"])} real neurons\n{data["edge_count"]:,} directed edges\n{len(data["skeletons"])} real SWC morphologies\nIdentical input for all controls', va='top', linespacing=1.7, fontsize=12)
    raster = fig.add_subplot(grid[2, :2])
    original = data['runs']['original']
    for hop in range(3):
        tx, ny = [], []
        for i, node in enumerate(data['nodes']):
            if node['hop'] == hop:
                tx.extend(original['spikes'][i]); ny.extend([i] * len(original['spikes'][i]))
        raster.scatter(tx, ny, s=6, color=COLORS[hop], label=f'Hop {hop}')
    raster.axvspan(200, 800, color='#e6f1f7', zorder=0)
    raster.set(xlim=(0, data['duration']), ylim=(-3, len(data['nodes']) + 3), xlabel='Time (ms)', ylabel='Neuron ordered by original hop', title='Simulation-derived activity over the real auditory subgraph')
    raster.legend(loc='upper right')
    graph = fig.add_subplot(grid[2, 2])
    xy = np.asarray([n['pos'] for n in data['nodes']])
    graph.add_collection(LineCollection([[xy[a], xy[b]] for a, b, _ in original['edges']], colors='#475569', alpha=.06, linewidths=.45))
    graph.scatter(xy[:, 0], xy[:, 1], s=18, c=[COLORS[n['hop']] for n in data['nodes']])
    graph.set(xlim=(0, 1), ylim=(0, 1), xticks=[.13, .5, .87], xticklabels=['Input', 'Hop 1', 'Hop 2'], yticks=[], title='Topology | 900 strongest edges displayed')
    anatomy = fig.add_subplot(grid[3, 0], projection='3d')
    all_points = []
    for skel in data['skeletons']:
        seg = np.asarray(skel['segments'])
        anatomy.add_collection3d(Line3DCollection(seg, linewidths=.45, colors=COLORS[data['nodes'][skel['node']]['hop']], alpha=.65))
        all_points.extend(seg.reshape(-1, 3))
    if all_points:
        points = np.asarray(all_points)
        anatomy.auto_scale_xyz(points[:, 0], points[:, 1], points[:, 2])
        anatomy.set_box_aspect(np.maximum(np.ptp(points, axis=0), 1))
    anatomy.set(xlabel='X (um)', ylabel='Y (um)', zlabel='Z (um)', title='Official SWC | structure colored by hop')
    bars = fig.add_subplot(grid[3, 1])
    kinds = list(data['runs'])
    for hop in range(3):
        values = [100 * next(h['activation_fraction'] for h in data['runs'][k]['hops'] if h['hop'] == hop) for k in kinds]
        bars.bar(np.arange(len(kinds)) + (hop - 1) * .23, values, .23, label=f'Hop {hop}', color=COLORS[hop])
    bars.set(xticks=np.arange(len(kinds)), xticklabels=['Original', 'Rewired', 'Weights\nshuffled'], ylim=(0, 115), ylabel='Active neurons (%)', title='Topology controls | same frozen input')
    bars.legend(fontsize=9)
    sweep_ax = fig.add_subplot(grid[3, 2])
    sweep = pd.DataFrame(data['sensitivity'])
    if not sweep.empty:
        table = sweep.pivot(index='w0_mv', columns='input_weight_mv', values='downstream_active_fraction')
        im = sweep_ax.imshow(100 * table.to_numpy(), origin='lower', aspect='auto', cmap='YlOrRd', vmin=0, vmax=100)
        sweep_ax.set(xticks=range(len(table.columns)), xticklabels=table.columns, yticks=range(len(table.index)), yticklabels=table.index,
                     xlabel='Input gain (mV)', ylabel='Recurrent w0 (mV)', title='Sensitivity | downstream active (%)')
        for y in range(len(table.index)):
            for x in range(len(table.columns)):
                sweep_ax.text(x, y, f'{100 * table.iloc[y, x]:.0f}', ha='center', va='center', fontsize=10)
        fig.colorbar(im, ax=sweep_ax, shrink=.7)
    else:
        sweep_ax.axis('off')
    fig.suptitle('Auditory subgraph demonstration; not whole CNS, not measured electrical activity', fontsize=11, color='#475569')
    fig.savefig(output / 'brain_overview.png', dpi=150)
    fig.savefig(output / 'brain_overview.pdf')
    plt.close(fig)
    for kind, path in paths.items():
        shutil.copy2(path / 'raster.png', output / f'{kind}_raster.png')


def activity_gif(data, output):
    from PIL import Image, ImageDraw, ImageFont
    width, height = 1040, 620
    xy = np.array([n['pos'] for n in data['nodes']]) * [850, 430] + [85, 120]
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    frames = []
    run = data['runs']['original']
    for time in range(0, int(data['duration']) + 1, 20):
        frame = Image.new('RGB', (width, height), '#0b1425')
        draw = ImageDraw.Draw(frame)
        draw.text((30, 22), 'MaleCNS v1.0 | real auditory topology + simulated LIF activity', fill='#e2e8f0', font=font)
        draw.text((30, 53), '265 neurons; all simulated. 900 strongest edges displayed. No anatomical coordinates.', fill='#94a3b8', font=small)
        for a, b, _ in run['edges']:
            draw.line([tuple(xy[a]), tuple(xy[b])], fill='#152638', width=1)
        active = [0, 0, 0]
        for i, node in enumerate(data['nodes']):
            age = np.asarray(run['spikes'][i])
            age = time - age[(age <= time) & (age > time - 100)]
            intensity = min(1., float(np.exp(-age / 20).sum()))
            if intensity > .1:
                active[node['hop']] += 1
            color = tuple(int(c) for c in (np.array([255, 222, 122]) * intensity + np.array([40, 73, 95]) * (1 - intensity)))
            x, y = xy[i]; r = 2.5 + 3 * intensity
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
        for hop, x in enumerate([195, 510, 825]):
            draw.text((x - 45, 92), ['JO input', 'Hop 1', 'Hop 2'][hop], fill=COLORS[hop], font=font)
        draw.text((30, 567), f't = {time:04d} ms | brightness: spike decay (tau=20 ms) | activity counts: {active}', fill='#e2e8f0', font=font)
        draw.rectangle((30, 603, 1010, 607), fill='#25344d')
        draw.rectangle((30, 603, 30 + 980 * time / data['duration'], 607), fill='#38bdf8')
        frames.append(frame)
    frames[0].save(output / 'brain_activity.gif', save_all=True, append_images=frames[1:], duration=100, loop=0)


def main(argv=None):
    root = configure_storage()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--sweep', type=Path)
    parser.add_argument('--skeleton-dir', type=Path)
    parser.add_argument('--report-id', help='Optional unique output directory name')
    parser.add_argument('--refresh', action='store_true', help='Regenerate a verified existing report for this same run')
    args = parser.parse_args(argv)
    parent = args.run.resolve()
    if not parent.is_relative_to(root.resolve()):
        parser.error('Run must reside in project')
    if args.report_id and (Path(args.report_id).name != args.report_id or args.report_id in ['.', '..']):
        parser.error('report-id must be a simple directory name')
    output = root / 'outputs/visualizations' / (args.report_id or parent.name)
    if args.refresh and output.exists():
        prior = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        # A previous refresh from early versions could include its own manifest
        # hash. Core inputs are verified above; refresh repairs derived outputs.
        if prior['source'] != 'VERIFIED_MALECNS_SIMULATION_REPORT' or prior['input_run_manifest_sha256'] != sha256(parent / 'manifest.json'):
            raise ValueError('Refresh requires a verified report from the same input run')
    output.mkdir(parents=True, exist_ok=args.refresh)
    meta, paths = load_runs(parent)
    data = data_bundle(root, parent, args.sweep, args.skeleton_dir)
    write_json(output / 'report_data.json', data)
    static_figures(data, paths, output)
    activity_gif(data, output)
    template = (Path(__file__).parent / 'brain_report_template.html').read_text(encoding='utf-8')
    embedded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    (output / 'index.html').write_text(template.replace('__BRAIN_DATA__', embedded), encoding='utf-8')
    report_files = [output / name for name in ['index.html', 'report_data.json', 'brain_overview.png',
        'brain_overview.pdf', 'brain_activity.gif'] + [f'{kind}_raster.png' for kind in paths]]
    write_json(output / 'manifest.json', manifest(report_files,
        source='VERIFIED_MALECNS_SIMULATION_REPORT', input_run_manifest_sha256=sha256(parent / 'manifest.json'),
        dataset=meta['dataset'], skeleton_display='Max 1600 segments per SWC; original SWCs retained',
        template_sha256=sha256(Path(__file__).parent / 'brain_report_template.html'),
        topology_display='900 strongest edges; all edges used in simulation',
        source_code_sha256={str(p.relative_to(root)): sha256(p) for p in sorted((root / 'src').rglob('*.py'))}))
    print(output / 'index.html', flush=True)


if __name__ == '__main__':
    main()

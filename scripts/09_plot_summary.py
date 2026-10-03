"""Make a compact, explicitly simulation-derived figure from a verified run."""
from _bootstrap import ROOT
import argparse
from pathlib import Path
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ear_malecns.provenance import verify_manifest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', type=Path, required=True)
args = parser.parse_args()
run = args.run.resolve()
if not run.is_relative_to(ROOT.resolve()):
    parser.error('Run must be in the H-drive project')
meta = verify_manifest(run)
nodes = pd.read_parquet(run / 'graph_snapshot/nodes.parquet').sort_values(['hop', 'bodyId'])
spikes = pd.read_parquet(run / 'spikes.parquet')
hops = pd.read_csv(run / 'hop_metrics.csv')
cfg = json.loads((run / 'config.json').read_text(encoding='utf-8'))
onset, offset = [1000 * cfg['fixed_input'][key] for key in ['onset_s', 'offset_s']]
end = cfg['snn']['simulation_ms']
with np.load(run / 'fixed_input.npz') as events:
    bins = np.arange(0, end + 20, 20)
    counts = np.histogram(events['times_s'] * 1000, bins=bins)[0]
    rate = counts / .02 / len(events['body_ids'])
index = dict(zip(nodes.bodyId, range(len(nodes))))
colors = ['#207a9e', '#dd7733', '#665191']
fig = plt.figure(figsize=(13, 8), layout='constrained')
grid = fig.add_gridspec(2, 2, width_ratios=[2.3, 1], height_ratios=[1, 3])
ax_input = fig.add_subplot(grid[0, 0])
ax_input.step(bins[:-1], rate, where='post', color=colors[0], linewidth=1.5)
ax_input.axvspan(onset, offset, color='#eff3f6')
ax_input.set(xlim=(0, end), ylabel='Input spikes / s / channel', title='Frozen independent sensory input (20 ms bins)')
ax_raster = fig.add_subplot(grid[1, 0])
for hop, group in nodes.groupby('hop'):
    selected = spikes[spikes.bodyId.isin(group.bodyId)]
    ax_raster.scatter(selected.time_ms, selected.bodyId.map(index), s=4, color=colors[int(hop)], label=f'Hop {hop}: {len(group)} cells')
ax_raster.axvspan(onset, offset, color='#eff3f6', zorder=0)
ax_raster.set(xlim=(0, end), ylim=(-3, len(nodes) + 3), xlabel='Time (ms)', ylabel='Neuron ordered by hop', title='Simulation-derived LIF spikes')
ax_raster.legend(loc='upper right', fontsize=9)
ax_bar = fig.add_subplot(grid[0, 1])
ax_bar.bar(hops.hop, 100 * hops.activation_fraction, color=colors)
ax_bar.set(ylim=(0, 125), xticks=hops.hop, ylabel='Active (%)', title='Stimulus-window activation')
for row in hops.itertuples():
    ax_bar.text(row.hop, 100 * row.activation_fraction + 4, f'{row.active_neurons}/{row.neurons}', ha='center', fontsize=9)
ax_note = fig.add_subplot(grid[1, 1]); ax_note.axis('off')
summary = json.loads((run / 'metrics.json').read_text(encoding='utf-8'))
ax_note.text(0, .96, 'Engineering validation', fontsize=14, weight='bold', va='top')
ax_note.text(0, .85, f'{len(nodes)} neurons / {summary["edges"]:,} edges\n'
             f'{summary["network_spikes"]:,} network spikes\n'
             f'No-input control: {summary["zero_input_spikes"]} spikes\n\n'
             'Real MaleCNS structural data\nAssumed LIF dynamics and gains\n\n'
             'JO candidate annotations need review.\nNo physiological calibration.\nNo human-ear FEM in this stage.\n\n'
             'Zero hop-2 response is retained\nas a result, not hidden.',
             fontsize=11, va='top', linespacing=1.6)
fig.suptitle('MaleCNS v1.0 | Stage 1 fixed-input experiment\nStructural data + assumed dynamics; not measured neural activity', fontsize=15)
out = ROOT / 'outputs/figures' / f'{run.name}_summary.png'
fig.savefig(out, dpi=160); plt.close(fig)
print(out)

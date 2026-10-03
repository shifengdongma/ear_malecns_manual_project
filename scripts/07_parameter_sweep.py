"""Replay an existing run's frozen input; vary only declared neural gains."""
from _bootstrap import ROOT
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd
from ear_malecns.provenance import manifest, sha256, verify_manifest, write_json
from ear_malecns.stage1 import run_simulation, summarize

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', type=Path, required=True)
parser.add_argument('--nt-sign-only', action='store_true', help='Two unknown-NT sign priors with unchanged gains')
args = parser.parse_args()
run_dir = args.run.resolve()
if not run_dir.is_relative_to(ROOT.resolve()):
    parser.error('Run must be stored in the H-drive project')
meta = verify_manifest(run_dir)
verify_manifest(run_dir / 'graph_snapshot')
cfg = json.loads((run_dir / 'config.json').read_text(encoding='utf-8'))
nodes = pd.read_parquet(run_dir / 'graph_snapshot/nodes.parquet')
edges = pd.read_parquet(run_dir / 'graph_snapshot/edges.parquet')
with np.load(run_dir / 'fixed_input.npz', allow_pickle=False) as archive:
    events = {key: archive[key] for key in ['body_ids', 'channels', 'times_s']}
out = ROOT / 'outputs/parameter_sweeps' / datetime.now(timezone.utc).strftime('gains_%Y%m%dT%H%M%S_%fZ')
out.mkdir(parents=True, exist_ok=False)
rows = []
for recurrent_scale in ([1.] if args.nt_sign_only else [.25, .5, 1., 2., 4.]):
    for input_scale, unknown_sign in ([(1., -1.), (1., 1.)] if args.nt_sign_only else [(x, cfg['snn']['uncertain_sign']) for x in [.5, 1., 2.]]):
        current = deepcopy(cfg)
        current['snn']['w0_mv'] *= recurrent_scale
        current['snn']['input_weight_mv'] *= input_scale
        current['snn']['uncertain_sign'] = unknown_sign
        spikes = run_simulation(nodes, edges, events['body_ids'], events['channels'], events['times_s'], current)
        neurons, hops = summarize(nodes, spikes, current)
        name = f'w{recurrent_scale:g}_input{input_scale:g}_nt{unknown_sign:g}'
        spikes.to_parquet(out / f'{name}.parquet', index=False)
        rows.append({'scenario': name, 'w0_mv': current['snn']['w0_mv'],
                     'uncertain_sign': unknown_sign,
                     'input_weight_mv': current['snn']['input_weight_mv'],
                     'network_spikes': len(spikes), 'downstream_active_fraction': float(neurons.loc[~neurons.is_seed, 'active'].mean()),
                     'mean_stimulus_hz': float(neurons.stimulus_rate_hz.mean()),
                     'mean_recovery_hz': float(neurons.recovery_rate_hz.mean()),
                     'max_neuron_stimulus_hz': float(neurons.stimulus_rate_hz.max())})
pd.DataFrame(rows).to_csv(out / 'summary.csv', index=False)
write_json(out / 'manifest.json', manifest(list(out.glob('*.parquet')) + [out / 'summary.csv'],
           source=meta['source'], base_run=str(run_dir), fixed_input_sha256=sha256(run_dir / 'fixed_input.npz'),
           base_config=cfg, statement='Engineering sensitivity only; does not establish a biological effect.'))
print(f'Saved {len(rows)} fixed-input scenarios:', out)

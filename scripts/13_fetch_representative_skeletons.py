from _bootstrap import ROOT
import argparse
from pathlib import Path
import pandas as pd
from ear_malecns.provenance import verify_manifest, write_json, manifest
from ear_malecns.visualize import fetch_public_skeletons, save_skeleton_figure

parser = argparse.ArgumentParser()
parser.add_argument('--snapshot', required=True, type=Path)
parser.add_argument('--run', type=Path, help='Prioritize responding cells for activity display')
args = parser.parse_args()
meta = verify_manifest(args.snapshot)
if meta['source'] != 'PUBLIC_MALECNS_V1_0':
    parser.error('Requires official public MaleCNS snapshot')
nodes = pd.read_parquet(args.snapshot / 'nodes.parquet')
if args.run:
    verify_manifest(args.run)
    responses = pd.read_csv(args.run / 'neuron_metrics.csv')[['bodyId', 'stimulus_rate_hz']]
    nodes = nodes.merge(responses, on='bodyId', validate='one_to_one')
    nodes = nodes.sort_values(['stimulus_rate_hz', 'bodyId'], ascending=[False, True])
else:
    nodes = nodes.sort_values('bodyId')
selected = nodes.groupby('hop', group_keys=False).head(8)
out = ROOT / 'skeletons/male-cns-v1.0' / ('activity_representative' if args.run else 'representative')
paths = fetch_public_skeletons(selected.bodyId.tolist(), out)
write_json(out / 'manifest.json', manifest(paths, dataset='male-cns:v1.0',
    source='PUBLIC_MALECNS_V1_0', selection='Eight per discovery hop; response-ranked if a run is given',
    response_run=str(args.run) if args.run else None,
    snapshot_manifest_sha256=__import__('ear_malecns.provenance', fromlist=['sha256']).sha256(args.snapshot / 'manifest.json')))
save_skeleton_figure(paths, ROOT / 'outputs/figures/representative_skeletons.png')
print(f'Verified {len(paths)} representative SWCs', flush=True)

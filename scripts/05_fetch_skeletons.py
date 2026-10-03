from _bootstrap import ROOT
import argparse
from pathlib import Path
import pandas as pd
from ear_malecns.config import load_config
from ear_malecns.malecns import make_client
from ear_malecns.provenance import verify_manifest, manifest, write_json
from ear_malecns.visualize import fetch_and_save_skeletons, fetch_public_skeletons, save_skeleton_figure

parser = argparse.ArgumentParser()
parser.add_argument('--snapshot', type=Path, default=ROOT / 'data/processed/auditory_subgraph_v1')
parser.add_argument('--limit', type=int, default=20)
args = parser.parse_args()
if not 1 <= args.limit <= 50:
    parser.error('For stage 1 use 1-50 skeletons')
meta = verify_manifest(args.snapshot)
if meta['source'] not in ['NEUPRINT_MALECNS', 'PUBLIC_MALECNS_V1_0']:
    parser.error('Skeleton downloads require a real MaleCNS snapshot')
m = load_config(ROOT / 'configs/stage1.yaml')['malecns']
if meta.get('dataset') != m['dataset']:
    parser.error('Snapshot dataset mismatch')
nodes = pd.read_parquet(args.snapshot / 'nodes.parquet').sort_values(['hop', 'bodyId'])
out = ROOT / 'skeletons/male-cns-v1.0'
if meta['source'] == 'PUBLIC_MALECNS_V1_0':
    paths = fetch_public_skeletons(nodes.bodyId.head(args.limit).tolist(), out / 'public')
    save_skeleton_figure(paths, ROOT / 'outputs/figures/stage1_public_skeletons.png')
else:
    client = make_client(m['server'], m['dataset'])
    paths = fetch_and_save_skeletons(client, nodes.bodyId.head(args.limit).tolist(), out / 'neuprint')
write_json(paths[0].parent / 'manifest.json', manifest(paths, source=meta['source'], dataset=m['dataset'], server=m['server']))
print(f'Saved {len(paths)} SWC skeletons')

from _bootstrap import ROOT
import json
import shutil
import pandas as pd
from ear_malecns.config import load_config
from ear_malecns.malecns import make_client, fetch_downstream_hops, add_local_input_fraction, save_subgraph
from ear_malecns.provenance import manifest, sha256, write_json

m = load_config(ROOT / 'configs/stage1.yaml')['malecns']
seed_file = ROOT / 'data/processed/auditory_input_cells.csv'
seed_meta = json.loads(seed_file.with_suffix('.manifest.json').read_text(encoding='utf-8'))
if seed_meta['files'][seed_file.name] != sha256(seed_file) or seed_meta['dataset'] != m['dataset']:
    raise RuntimeError('Seed snapshot checksum or dataset mismatch')
out = ROOT / 'data/processed/auditory_subgraph_v1'
if out.exists():
    raise SystemExit('Subgraph already exists; use 06_stage1.py --mode live for a new snapshot.')
seeds = pd.read_csv(seed_file)
client = make_client(m['server'], m['dataset'])
nodes, edges = fetch_downstream_hops(seeds.bodyId.tolist(), client, hops=m['hops'], min_weight=m['min_weight'],
               max_new_nodes_per_hop=m['max_new_nodes_per_hop'], max_nodes=m['max_nodes'], status_filter=m.get('status_filter'))
save_subgraph(nodes, add_local_input_fraction(edges), out)
shutil.copy2(seed_file, out / seed_file.name)
write_json(out / 'manifest.json', manifest([out / n for n in ['nodes.parquet', 'edges.parquet',
           'auditory_subgraph.graphml', seed_file.name]], source='NEUPRINT_MALECNS', dataset=m['dataset'],
           server=m['server'], query_config=m, seed_manifest=seed_meta, annotation_review='PENDING_HUMAN_REVIEW'))
print(f'Saved {len(nodes)} nodes / {len(edges)} edges:', out)

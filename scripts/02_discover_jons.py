from _bootstrap import ROOT
from ear_malecns.config import load_config
from ear_malecns.malecns import make_client, discover_auditory_jons
from ear_malecns.provenance import manifest, write_json

m = load_config(ROOT / 'configs/stage1.yaml')['malecns']
out = ROOT / 'data/processed/auditory_input_cells.csv'
if out.exists():
    raise SystemExit('Seed CSV already exists; use 06_stage1.py --mode live for a new snapshot.')
client = make_client(m['server'], m['dataset'])
seeds = discover_auditory_jons(client, m['jon_type_regex'], m['auditory_type_regex'])
seeds.to_csv(out, index=False)
write_json(out.with_suffix('.manifest.json'), manifest([out], source='NEUPRINT_MALECNS',
           dataset=m['dataset'], server=m['server'], auditory_type_regex=m['auditory_type_regex'],
           annotation_review='PENDING_HUMAN_REVIEW'))
print(seeds[['bodyId', 'type']].to_string(index=False))
print('Saved candidate seeds; annotation review remains necessary:', out)

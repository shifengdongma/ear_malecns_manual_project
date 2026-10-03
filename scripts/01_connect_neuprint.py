from _bootstrap import ROOT
from ear_malecns.config import load_config
from ear_malecns.malecns import make_client
from neuprint import fetch_meta

m = load_config(ROOT / 'configs/stage1.yaml')['malecns']
client = make_client(m['server'], m['dataset'])
meta = fetch_meta(client=client)
if meta.get('dataset') != m['dataset']:
    raise RuntimeError('Returned dataset differs from configured MaleCNS version')
print('PASS: dataset metadata fetched:', m['dataset'])

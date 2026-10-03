from _bootstrap import ROOT
from concurrent.futures import ThreadPoolExecutor
import shutil
import pandas as pd
from ear_malecns.visualize import fetch_public_skeletons
from ear_malecns.provenance import manifest, write_json, verify_manifest, sha256

snapshot = ROOT / 'data/processed/malecns_snapshots/real_public_fixed_20261003'
verify_manifest(snapshot)
nodes = pd.read_parquet(snapshot/'nodes.parquet')
out = ROOT/'skeletons/male-cns-v1.0/all_auditory'
out.mkdir(parents=True, exist_ok=True)
def fetch(body):
    target = out/f'{body}.swc'
    if not target.exists():
        for source in (ROOT/'skeletons/male-cns-v1.0').glob(f'*/{body}.swc'):
            if source.parent == out:
                continue
            if source.with_suffix('.swc.json').exists():
                shutil.copy2(source,target)
                shutil.copy2(source.with_suffix('.swc.json'),target.with_suffix('.swc.json'))
                break
    path = fetch_public_skeletons([body],out)[0]
    print(f'Verified SWC {body}', flush=True)
    return path
with ThreadPoolExecutor(max_workers=6) as pool:
    paths=list(pool.map(fetch,sorted(nodes.bodyId.astype(int))))
write_json(out/'manifest.json', manifest(paths, source='PUBLIC_MALECNS_V1_0',dataset='male-cns:v1.0',
    snapshot_manifest_sha256=sha256(snapshot/'manifest.json'), selection='Every neuron of the frozen auditory subgraph'))
print(f'Complete: {len(paths)} real SWCs',flush=True)

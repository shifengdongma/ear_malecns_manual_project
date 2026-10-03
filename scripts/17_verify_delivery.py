"""Audit real inputs, frozen comparisons and the rendered report before delivery."""
from _bootstrap import ROOT
import json
from pathlib import Path
import hashlib
import base64
import numpy as np
import pandas as pd
from ear_malecns.bulk import FILES
from ear_malecns.provenance import verify_manifest, sha256, write_json
from ear_malecns.brain_report import load_runs

parent = ROOT / 'outputs/runs/malecns_brain_focus_20261003'
report = ROOT / 'outputs/visualizations/malecns_brain_explorer'
checks, raw = {}, []
for name in FILES:
    path = ROOT / 'data/raw/malecns' / name
    record = json.loads(path.with_suffix(path.suffix + '.json').read_text(encoding='utf-8'))
    with path.open('rb') as stream:
        md5 = base64.b64encode(hashlib.file_digest(stream, 'md5').digest()).decode()
    checks[name] = sha256(path) == record['sha256'] and md5 == record['provider_md5_base64'] and path.stat().st_size == record['bytes']
    raw.append(dict(file=name, bytes=path.stat().st_size, sha256=record['sha256'], provider_md5=md5))
meta, paths = load_runs(parent)
hashes = [sha256(p / 'fixed_input.npz') for p in paths.values()]
checks['identical_fixed_inputs'] = len(set(hashes)) == 1
nodes = pd.read_parquet(paths['original'] / 'graph_snapshot/nodes.parquet')
baseline = pd.read_parquet(paths['original'] / 'graph_snapshot/edges.parquet')
rewired = pd.read_parquet(paths['rewired'] / 'graph_snapshot/edges.parquet')
shuffled = pd.read_parquet(paths['weight_shuffled'] / 'graph_snapshot/edges.parquet')
degree = lambda edges, field: edges.groupby(field).size().reindex(nodes.bodyId, fill_value=0).to_numpy()
checks['directed_degree_preserved'] = all(np.array_equal(degree(baseline,k),degree(rewired,k)) for k in ['bodyId_pre','bodyId_post'])
checks['rewired_weight_multiset_preserved'] = np.array_equal(np.sort(baseline.weight), np.sort(rewired.weight))
checks['shuffled_topology_preserved'] = set(zip(baseline.bodyId_pre,baseline.bodyId_post)) == set(zip(shuffled.bodyId_pre,shuffled.bodyId_post))
checks['shuffled_weight_multiset_preserved'] = np.array_equal(np.sort(baseline.weight),np.sort(shuffled.weight))
report_meta = verify_manifest(report)
checks['report_verified'] = report_meta['input_run_manifest_sha256'] == sha256(parent / 'manifest.json')
checks['browser_9_interactions_pass'] = 'data-selftest="PASS"' in (ROOT/'downloads/browser-selftest-result.txt').read_text(encoding='utf-8-sig')
skels = verify_manifest(ROOT / 'skeletons/male-cns-v1.0/activity_representative')
checks['24_real_morphologies'] = len(skels['files']) == 24
ear = json.loads((ROOT/'fem/geometry/openear_zeta/manifest.json').read_text(encoding='utf-8'))
checks['openear_geometry_sha256'] = all(sha256(ROOT/'fem/geometry/openear_zeta'/r['local_file']) == r['sha256'] for r in ear['files'])
delivery = dict(checks=checks, all_artifact_checks_pass=all(checks.values()),
    raw_files=raw, total_raw_malecns_bytes=sum(r['bytes'] for r in raw),
    input_sha256=hashes[0], run_source=meta['source'], dataset=meta['dataset'],
    report=str(report/'index.html'), openear_geometry_files=len(ear['files']),
    openear_geometry_bytes=sum(r['bytes'] for r in ear['files']),
    modeling_boundary='Artifact integrity and software checks do not constitute biological validation',
    expected_negative_control='Rewired downstream_response=false is retained as an experimental outcome')
write_json(ROOT/'outputs/delivery_verification.json', delivery)
print(json.dumps(delivery, ensure_ascii=False, indent=2))
if not all(checks.values()):
    raise SystemExit(2)

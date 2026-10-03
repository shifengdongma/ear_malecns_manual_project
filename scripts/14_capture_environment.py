from _bootstrap import ROOT
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import argparse
from ear_malecns.provenance import write_json

parser = argparse.ArgumentParser()
parser.add_argument('--wsl-summary', default='Initial sandbox probe returned E_ACCESSDENIED; Windows native runtime used')
args = parser.parse_args()

write_json(ROOT / 'outputs/environment_actual.json', {
    'platform': platform.platform(), 'python': sys.version, 'executable': sys.executable,
    'project': str(ROOT), 'cpu_count': os.cpu_count(),
    'H_disk': dict(zip(['total', 'used', 'free'], shutil.disk_usage(ROOT))),
    'packages': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
    'storage': {k: os.environ.get(k) for k in ['PIP_CACHE_DIR','TMP','TEMP','MPLCONFIGDIR','XDG_CACHE_HOME']},
    'neuprint_token_present': bool(os.environ.get('NEUPRINT_APPLICATION_CREDENTIALS')),
    'wsl_probe': args.wsl_summary,
    'solver_status': 'No validated human-ear FE model or solved response provided',
})
print(ROOT / 'outputs/environment_actual.json')

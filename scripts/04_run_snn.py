from _bootstrap import ROOT
import sys
from ear_malecns.stage1 import main

if __name__ == '__main__':
    raise SystemExit(main(['--mode', 'cached', '--snapshot',
                          str(ROOT / 'data/processed/auditory_subgraph_v1'), *sys.argv[1:]]))

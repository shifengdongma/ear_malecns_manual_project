from _bootstrap import ROOT
import numpy as np


from ear_malecns.config import load_config
from ear_malecns.experiment import make_selftest_fem, encode_fem_file

cfg = load_config(ROOT / "configs/default.yaml")
fem = make_selftest_fem(ROOT / "data/processed/selftest_fem.h5", cfg)
spikes = encode_fem_file(fem, ROOT / "data/processed/selftest_encoder.npz", cfg)
d = np.load(spikes)
print("Self-test FEM:", fem)
print("Encoder spikes:", len(d["spike_times_s"]))
print("PASS: stimulus -> synthetic transfer -> encoder")

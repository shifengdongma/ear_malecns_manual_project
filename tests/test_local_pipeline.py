from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ear_malecns.stimulus import gated_tone, pulse_song_like
from ear_malecns.fem_io import synthetic_transfer_response
from ear_malecns.encoder import robust_envelope_feature, adaptive_rate_encoder, poisson_spike_times


def test_local_signal_pipeline():
    fs = 10000
    t, x = gated_tone(250, fs, 1.0, onset_s=0.2, offset_s=0.8)
    tm, v = synthetic_transfer_response(x, fs)
    z, _ = robust_envelope_feature(v, fs)
    r = adaptive_rate_encoder(z, fs)
    spikes = poisson_spike_times(r, fs, seed=1)
    assert len(t) == len(x) == len(v) == len(z) == len(r)
    assert np.all((z >= 0) & (z <= 1))
    assert np.all(r >= 0)
    assert spikes.ndim == 1


def test_pulse_generator():
    t, x = pulse_song_like(275, 36, 10000, 1.0)
    assert t.shape == x.shape
    assert np.any(np.abs(x) > 0)

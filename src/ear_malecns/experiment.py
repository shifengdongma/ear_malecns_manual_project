from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd

from .stimulus import gated_tone
from .fem_io import synthetic_transfer_response, write_fem_h5, read_fem_h5
from .encoder import robust_envelope_feature, adaptive_rate_encoder, poisson_spike_times


def make_selftest_fem(out_path: str | Path, cfg: dict) -> Path:
    s = cfg["stimulus"]
    t, pressure = gated_tone(
        frequency_hz=float(s["frequency_hz"]),
        fs_hz=float(s["fs_hz"]),
        duration_s=float(s["duration_s"]),
        amplitude=float(s["pressure_pa"]),
        onset_s=float(s["onset_s"]),
        offset_s=float(s["offset_s"]),
    )
    tm, stapes_v = synthetic_transfer_response(pressure, float(s["fs_hz"]))
    write_fem_h5(out_path, t, pressure, tm, stapes_v, float(s["fs_hz"]), "SYNTHETIC_SELFTEST_NOT_FEM")
    return Path(out_path)


def encode_fem_file(fem_path: str | Path, out_npz: str | Path, cfg: dict, *, calibration: dict | None = None) -> Path:
    d = read_fem_h5(fem_path)
    e = cfg["encoder"]
    z, norm_meta = robust_envelope_feature(
        np.asarray(d["stapes_velocity_m_s"]),
        fs_hz=float(d["sample_rate_hz"]),
        envelope_tau_ms=float(e["envelope_tau_ms"]),
        q_low=None if calibration is None else float(calibration['q_low']),
        q_high=None if calibration is None else float(calibration['q_high']),
    )
    rate = adaptive_rate_encoder(
        z,
        fs_hz=float(d["sample_rate_hz"]),
        adaptation_tau_ms=float(e["adaptation_tau_ms"]),
        r_base_hz=float(e["r_base_hz"]),
        r_max_hz=float(e["r_max_hz"]),
        threshold=float(e["threshold"]),
        gain=float(e["gain"]),
    )
    spikes = poisson_spike_times(rate, float(d["sample_rate_hz"]), seed=int(cfg["project"]["seed"]))
    out_npz = Path(out_npz)
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_npz, rate_hz=rate, spike_times_s=spikes, normalized_feature=z)
    norm_meta['normalization_mode'] = 'per_signal_selftest_only' if calibration is None else 'shared_calibration'
    norm_meta['fem_version'] = d['fem_version']
    out_npz.with_suffix(".json").write_text(json.dumps(norm_meta, indent=2), encoding="utf-8")
    return out_npz

from __future__ import annotations

import numpy as np
from scipy.signal import hilbert
from scipy.ndimage import gaussian_filter1d


def robust_envelope_feature(
    signal: np.ndarray,
    fs_hz: float,
    envelope_tau_ms: float = 5.0,
    q_low: float | None = None,
    q_high: float | None = None,
) -> tuple[np.ndarray, dict[str, float]]:
    """Extract log-envelope and robust-normalize to [0, 1].

    For publication-grade comparisons, q_low/q_high should be learned once from
    the complete training stimulus set and then reused for every test stimulus.
    """
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1 or len(signal) < 2 or not np.isfinite(signal).all() or not np.isfinite(fs_hz) or fs_hz <= 0 or envelope_tau_ms <= 0:
        raise ValueError('Invalid envelope signal, sample rate or smoothing time')
    if (q_low is None) != (q_high is None):
        raise ValueError('Both calibration quantiles are required together')
    envelope = np.abs(hilbert(signal))
    sigma_samples = max(envelope_tau_ms * 1e-3 * fs_hz, 1.0)
    envelope = gaussian_filter1d(envelope, sigma=sigma_samples)
    log_env = np.log(envelope + 1e-15)
    if q_low is None:
        q_low = float(np.quantile(log_env, 0.05))
    if q_high is None:
        q_high = float(np.quantile(log_env, 0.95))
    denom = q_high - q_low
    if not np.isfinite([q_low, q_high]).all() or denom < 0:
        raise ValueError('Invalid calibration quantiles')
    if denom <= 1e-15:
        z = np.zeros_like(log_env)
    else:
        z = np.clip((log_env - q_low) / denom, 0.0, 1.0)
    return z, {"q_low": q_low, "q_high": q_high}


def adaptive_rate_encoder(
    z: np.ndarray,
    fs_hz: float,
    adaptation_tau_ms: float = 10.0,
    r_base_hz: float = 5.0,
    r_max_hz: float = 150.0,
    threshold: float = 0.30,
    gain: float = 1.0,
) -> np.ndarray:
    """Transparent physiology-informed surrogate.

    It captures fast adaptation qualitatively but is NOT claimed to be a fitted
    JON electrophysiological model until parameters are calibrated to data.
    """
    z = np.asarray(z, dtype=float)
    if z.ndim != 1 or not np.isfinite(z).all() or ((z < 0) | (z > 1)).any():
        raise ValueError('Encoder feature must be a finite 1-D vector in [0, 1]')
    if not np.isfinite([fs_hz, adaptation_tau_ms, r_base_hz, r_max_hz, threshold, gain]).all() or fs_hz <= 0 or adaptation_tau_ms <= 0 or r_base_hz < 0 or r_max_hz < r_base_hz or gain < 0 or not 0 <= threshold <= 1:
        raise ValueError('Invalid encoder parameters')
    dt = 1.0 / fs_hz
    tau = adaptation_tau_ms * 1e-3
    alpha = min(dt / max(tau, dt), 1.0)
    a = np.zeros_like(z)
    for i in range(1, len(z)):
        a[i] = a[i - 1] + alpha * (z[i] - a[i - 1])
    drive = np.maximum(0.0, z - threshold) / (0.05 + a)
    drive = 1.0 - np.exp(-gain * drive)
    return r_base_hz + (r_max_hz - r_base_hz) * drive


def poisson_spike_times(rate_hz: np.ndarray, fs_hz: float, seed: int = 0) -> np.ndarray:
    rate_hz = np.asarray(rate_hz, dtype=float)
    rng = np.random.default_rng(seed)
    dt = 1.0 / fs_hz
    if not np.isfinite(fs_hz) or fs_hz <= 0 or rate_hz.ndim != 1 or not np.isfinite(rate_hz).all() or (rate_hz < 0).any() or (rate_hz * dt > 1).any():
        raise ValueError('Invalid rate or Bernoulli probability; use a finer time step')
    p = rate_hz * dt
    mask = rng.random(rate_hz.size) < p
    return np.flatnonzero(mask) * dt


def equivalent_particle_velocity_mm_s(
    z: np.ndarray,
    v_min_mm_s: float = 0.1,
    v_max_mm_s: float = 1.0,
) -> np.ndarray:
    """Artificial cross-species mapping used only as an explicit bridge variable."""
    z = np.asarray(z, dtype=float)
    return v_min_mm_s * (v_max_mm_s / v_min_mm_s) ** z

from __future__ import annotations

import numpy as np


def gated_tone(
    frequency_hz: float,
    fs_hz: float,
    duration_s: float,
    amplitude: float = 1.0,
    onset_s: float = 0.2,
    offset_s: float = 0.8,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a gated sine tone. Amplitude may represent Pa for a calibrated input."""
    t = np.arange(int(round(duration_s * fs_hz))) / fs_hz
    gate = ((t >= onset_s) & (t < offset_s)).astype(float)
    x = amplitude * np.sin(2 * np.pi * frequency_hz * t) * gate
    return t, x


def pulse_song_like(
    carrier_hz: float,
    ipi_ms: float,
    fs_hz: float,
    duration_s: float,
    pulse_ms: float = 8.0,
    amplitude: float = 1.0,
    start_s: float = 0.15,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a simple pulse-train stimulus for controlled temporal-pattern tests."""
    t = np.arange(int(round(duration_s * fs_hz))) / fs_hz
    x = np.zeros_like(t)
    ipi_s = ipi_ms * 1e-3
    pulse_s = pulse_ms * 1e-3
    center = start_s
    while center < duration_s:
        mask = (t >= center) & (t < center + pulse_s)
        local_t = t[mask] - center
        # Smooth pulse envelope avoids hard discontinuities.
        env = np.sin(np.pi * np.clip(local_t / max(pulse_s, 1e-12), 0, 1)) ** 2
        x[mask] += amplitude * env * np.sin(2 * np.pi * carrier_hz * local_t)
        center += ipi_s
    return t, x

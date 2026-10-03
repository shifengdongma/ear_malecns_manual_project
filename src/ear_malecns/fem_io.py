from __future__ import annotations

from pathlib import Path
import h5py
import numpy as np


def validate_fem_data(data):
    fs = float(data['sample_rate_hz'])
    arrays = [np.asarray(data[k], dtype=float) for k in
              ['time_s', 'pressure_pa', 'tm_displacement_m', 'stapes_velocity_m_s']]
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError('Sample rate must be finite and positive')
    if any(a.ndim != 1 or len(a) < 2 or not np.isfinite(a).all() for a in arrays):
        raise ValueError('FEM arrays must be finite 1-D vectors with at least two samples')
    if len({len(a) for a in arrays}) != 1:
        raise ValueError('FEM arrays must have matching lengths')
    if not np.isclose(arrays[0][0], 0, atol=1e-12) or not np.allclose(np.diff(arrays[0]), 1 / fs, rtol=1e-6, atol=1e-12):
        raise ValueError('FEM time must start at zero and be uniformly sampled at sample_rate_hz')
    if not str(data['fem_version']).strip():
        raise ValueError('fem_version is required')


def write_fem_h5(
    path: str | Path,
    time_s: np.ndarray,
    pressure_pa: np.ndarray,
    tm_displacement_m: np.ndarray,
    stapes_velocity_m_s: np.ndarray,
    sample_rate_hz: float,
    fem_version: str,
) -> None:
    validate_fem_data(dict(time_s=time_s, pressure_pa=pressure_pa, tm_displacement_m=tm_displacement_m,
                           stapes_velocity_m_s=stapes_velocity_m_s, sample_rate_hz=sample_rate_hz, fem_version=fem_version))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as f:
        f.create_dataset("stimulus/time_s", data=time_s)
        f.create_dataset("stimulus/pressure_Pa", data=pressure_pa)
        f.create_dataset("fem/tm_displacement_m", data=tm_displacement_m)
        f.create_dataset("fem/stapes_velocity_m_s", data=stapes_velocity_m_s)
        meta = f.require_group("metadata")
        meta.attrs["fem_version"] = fem_version
        meta.attrs["sample_rate_hz"] = float(sample_rate_hz)


def read_fem_h5(path: str | Path) -> dict[str, np.ndarray | float | str]:
    with h5py.File(path, "r") as f:
        out = {
            "time_s": f["stimulus/time_s"][:],
            "pressure_pa": f["stimulus/pressure_Pa"][:],
            "tm_displacement_m": f["fem/tm_displacement_m"][:],
            "stapes_velocity_m_s": f["fem/stapes_velocity_m_s"][:],
            "sample_rate_hz": float(f["metadata"].attrs["sample_rate_hz"]),
            "fem_version": str(f["metadata"].attrs["fem_version"]),
        }
    validate_fem_data(out)
    return out


def synthetic_transfer_response(
    pressure_pa: np.ndarray,
    fs_hz: float,
    resonance_hz: float = 900.0,
    damping_ratio: float = 0.35,
) -> tuple[np.ndarray, np.ndarray]:
    """Pipeline self-test only; NOT a validated human-ear FEM.

    Uses a damped second-order transfer function as a stand-in so the full
    data/encoder/SNN pipeline can be exercised before a real FE solver exists.
    """
    from scipy.signal import bilinear, lfilter

    w0 = 2 * np.pi * resonance_hz
    # H(s) = w0^2 / (s^2 + 2*zeta*w0*s + w0^2)
    b_a = [w0**2]
    a_a = [1.0, 2.0 * damping_ratio * w0, w0**2]
    b_d, a_d = bilinear(b_a, a_a, fs=fs_hz)
    displacement_like = lfilter(b_d, a_d, pressure_pa) * 1e-8
    velocity_like = np.gradient(displacement_like, 1.0 / fs_hz)
    return displacement_like, velocity_like

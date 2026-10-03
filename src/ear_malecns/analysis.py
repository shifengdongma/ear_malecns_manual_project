from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def spike_table(spike_monitor, idx_to_body: dict[int, int]) -> pd.DataFrame:
    from brian2 import ms
    idx = np.asarray(spike_monitor.i, dtype=int)
    times_ms = np.asarray(spike_monitor.t / ms, dtype=float)
    return pd.DataFrame({
        "time_ms": times_ms,
        "neuron_index": idx,
        "bodyId": [idx_to_body[int(i)] for i in idx],
    })


def save_raster(spikes: pd.DataFrame, path: str | Path, title: str = "MaleCNS auditory subnetwork raster"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(12, 6))
    if not spikes.empty:
        plt.scatter(spikes["time_ms"], spikes["neuron_index"], s=3)
    plt.xlabel("Time (ms)")
    plt.ylabel("Neuron index")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def first_spike_latency(spikes: pd.DataFrame, stimulus_onset_ms: float,
                        body_ids=None, stimulus_offset_ms: float | None = None) -> pd.DataFrame:
    selected = spikes[spikes.time_ms >= stimulus_onset_ms]
    if stimulus_offset_ms is not None:
        selected = selected[selected.time_ms < stimulus_offset_ms]
    first = selected.groupby("bodyId", as_index=False)["time_ms"].min()
    first = first.rename(columns={"time_ms": "first_spike_ms"})
    first["latency_ms"] = first["first_spike_ms"] - float(stimulus_onset_ms)
    if body_ids is not None:
        first = pd.DataFrame({'bodyId': list(body_ids)}).merge(first, on='bodyId', how='left')
    return first

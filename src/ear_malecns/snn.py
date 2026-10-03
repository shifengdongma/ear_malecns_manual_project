from __future__ import annotations

import numpy as np
import pandas as pd


def nt_sign(nt: str | None, uncertain_sign: float = 1.0) -> float:
    """Engineering prior only; receptor context can reverse/modify effects."""
    if nt is None or (isinstance(nt, float) and np.isnan(nt)):
        return uncertain_sign
    s = str(nt).lower()
    if "gaba" in s:
        return -1.0
    if "acetylcholine" in s or s.strip() == "ach" or "cholin" in s:
        return 1.0
    return uncertain_sign


def build_lif_network(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    nt_map: dict[int, str] | None = None,
    tau_m_ms: float = 20.0,
    e_l_mv: float = -60.0,
    v_th_mv: float = -50.0,
    v_reset_mv: float = -60.0,
    refractory_ms: float = 2.0,
    delay_ms: float = 1.5,
    w0_mv: float = 0.5,
    uncertain_sign: float = 1.0,
):
    from brian2 import NeuronGroup, Synapses, SpikeMonitor, StateMonitor, mV, ms

    nt_map = nt_map or {}
    body_ids = sorted(set(nodes["bodyId"].astype(int)))
    if not body_ids or len(body_ids) != len(nodes):
        raise ValueError('Network needs nonempty unique body IDs')
    from .malecns import validate_edges
    validate_edges(edges)
    if not set(edges.bodyId_pre).union(edges.bodyId_post).issubset(body_ids):
        raise ValueError('Edge endpoint missing from nodes')
    if tau_m_ms <= 0 or refractory_ms <= 0 or delay_ms < 0 or w0_mv < 0:
        raise ValueError('Invalid LIF time or gain parameter')
    if not (e_l_mv < v_th_mv and v_reset_mv < v_th_mv):
        raise ValueError('Rest and reset must lie below threshold')
    body_to_idx = {body_id: i for i, body_id in enumerate(body_ids)}
    idx_to_body = {i: body_id for body_id, i in body_to_idx.items()}

    eqs = "dv/dt = (E_L - v) / tau_m : volt (unless refractory)"
    neurons = NeuronGroup(
        len(body_ids),
        model=eqs,
        threshold="v >= V_th",
        reset="v = V_reset",
        refractory=refractory_ms * ms,
        method="exact",
        namespace={
            "E_L": e_l_mv * mV,
            "V_th": v_th_mv * mV,
            "V_reset": v_reset_mv * mV,
            "tau_m": tau_m_ms * ms,
        },
    )
    neurons.v = e_l_mv * mV

    edge_df = edges[
        edges["bodyId_pre"].astype(int).isin(body_to_idx)
        & edges["bodyId_post"].astype(int).isin(body_to_idx)
    ].copy()
    log_w = np.log1p(edge_df["weight"].to_numpy(dtype=float))
    scale = float(np.median(log_w)) if len(log_w) else 1.0
    if scale <= 0:
        scale = 1.0
    signs = np.array([
        nt_sign(nt_map.get(int(pre)), uncertain_sign=uncertain_sign)
        for pre in edge_df["bodyId_pre"]
    ])
    weights_mv = signs * w0_mv * log_w / scale

    synapses = Synapses(neurons, neurons, model="w : volt", on_pre="v_post += w")
    if len(edge_df):
        pre_idx = np.array([body_to_idx[int(x)] for x in edge_df["bodyId_pre"]], dtype=int)
        post_idx = np.array([body_to_idx[int(x)] for x in edge_df["bodyId_post"]], dtype=int)
        synapses.connect(i=pre_idx, j=post_idx)
        synapses.w = weights_mv * mV
        synapses.delay = delay_ms * ms
    else:
        synapses.active = False

    spike_monitor = SpikeMonitor(neurons)
    record_idx = np.arange(min(len(body_ids), 50), dtype=int)
    voltage_monitor = StateMonitor(neurons, "v", record=record_idx)
    return neurons, synapses, spike_monitor, voltage_monitor, body_to_idx, idx_to_body


def attach_fixed_spike_input(
    neurons,
    body_to_idx: dict[int, int],
    target_body_ids: list[int],
    spike_times_s: np.ndarray,
    input_weight_mv: float = 2.0,
):
    """Replay exactly the same sensory spike train into each selected JON target."""
    from brian2 import SpikeGeneratorGroup, Synapses, second, mV

    targets = [int(x) for x in target_body_ids if int(x) in body_to_idx]
    if not targets:
        raise ValueError("No target JON body IDs are present in the extracted network")
    # Replicate one fixed spike train for each input channel.
    indices = []
    times = []
    for channel in range(len(targets)):
        indices.extend([channel] * len(spike_times_s))
        times.extend(spike_times_s.tolist())
    input_group = SpikeGeneratorGroup(
        len(targets),
        np.asarray(indices, dtype=int),
        np.asarray(times, dtype=float) * second,
    )
    input_syn = Synapses(input_group, neurons, model="w_in : volt", on_pre="v_post += w_in")
    input_syn.connect(i=np.arange(len(targets), dtype=int), j=np.array([body_to_idx[x] for x in targets]))
    input_syn.w_in = input_weight_mv * mV
    return input_group, input_syn


def attach_event_input(neurons, body_to_idx, target_body_ids, channels, times_s, input_weight_mv):
    """Replay channel-resolved frozen events; reject missing targets or bin collisions."""
    from brian2 import SpikeGeneratorGroup, Synapses, defaultclock, second, mV
    targets = list(map(int, target_body_ids))
    channels = np.asarray(channels, dtype=int)
    times_s = np.asarray(times_s, dtype=float)
    if not targets or len(set(targets)) != len(targets) or not set(targets).issubset(body_to_idx):
        raise ValueError('Input target IDs must be unique and present in the network')
    if channels.shape != times_s.shape or channels.ndim != 1:
        raise ValueError('Input events require aligned 1-D channels and times')
    if not np.isfinite(times_s).all() or (times_s < 0).any() or (channels < 0).any() or (channels >= len(targets)).any():
        raise ValueError('Invalid input event')
    bins = np.floor((times_s + 1e-9 * float(defaultclock.dt / second)) / float(defaultclock.dt / second)).astype('int64')
    if len(set(zip(channels, bins))) != len(channels):
        raise ValueError('Multiple spikes in the same channel and simulation time bin')
    order = np.lexsort((channels, times_s))
    source = SpikeGeneratorGroup(len(targets), channels[order], times_s[order] * second)
    syn = Synapses(source, neurons, model='w_in : volt', on_pre='v_post += w_in')
    syn.connect(i=np.arange(len(targets)), j=[body_to_idx[x] for x in targets])
    syn.w_in = input_weight_mv * mV
    return source, syn

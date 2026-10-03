import numpy as np
import pytest
import networkx as nx

from ear_malecns.encoder import robust_envelope_feature, adaptive_rate_encoder
from ear_malecns.fem_io import write_fem_h5, read_fem_h5
from ear_malecns.pipeline import calibrate, encode_events
from ear_malecns.config import load_config
from ear_malecns.controls import degree_preserving_rewire
from pathlib import Path


def test_shared_calibration_preserves_relative_amplitude(tmp_path):
    t = np.arange(10000) / 10000
    wave = np.sin(2 * np.pi * 250 * t)
    paths = []
    for i, amplitude in enumerate([.1, 1.]):
        path = tmp_path / f'{i}.h5'
        write_fem_h5(path, t, wave, wave, wave * amplitude, 10000, 'TEST')
        paths.append(path)
    norm = calibrate(paths, 5)
    low, _ = robust_envelope_feature(.1 * wave, 10000, 5, norm['q_low'], norm['q_high'])
    high, _ = robust_envelope_feature(wave, 10000, 5, norm['q_low'], norm['q_high'])
    assert high.mean() > low.mean() + .5
    cfg = load_config(Path(__file__).resolve().parents[1] / 'configs/pipeline.yaml')
    a = encode_events(read_fem_h5(paths[1]), cfg, norm, 4)
    b = encode_events(read_fem_h5(paths[1]), cfg, norm, 4)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
    bins = np.rint(a[1] / .0001).astype(int)
    assert len(set(zip(a[0], bins))) == len(bins)


def test_silence_encoder_is_baseline():
    assert np.allclose(adaptive_rate_encoder(np.zeros(1000), 10000), 5)


def test_fem_rejects_inconsistent_time(tmp_path):
    with pytest.raises(ValueError, match='uniformly'):
        write_fem_h5(tmp_path / 'bad.h5', np.arange(10), np.ones(10), np.ones(10), np.ones(10), 10000, 'TEST')


def test_rewire_preserves_directed_degrees_and_small_graph():
    graph = nx.gnp_random_graph(20, .15, seed=1, directed=True)
    nx.set_edge_attributes(graph, 10, 'weight')
    control = degree_preserving_rewire(graph)
    assert dict(control.in_degree()) == dict(graph.in_degree())
    assert dict(control.out_degree()) == dict(graph.out_degree())
    assert control.graph['successful_swaps'] > 0
    assert not list(nx.selfloop_edges(control))
    assert len(degree_preserving_rewire(nx.DiGraph([(1, 2)])).edges) == 1

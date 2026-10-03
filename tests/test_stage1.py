from copy import deepcopy
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from ear_malecns.analysis import first_spike_latency
from ear_malecns.config import load_config
from ear_malecns.malecns import fetch_downstream_hops, discover_auditory_jons, save_subgraph, validate_edges
from ear_malecns.provenance import manifest, verify_manifest, write_json
from ear_malecns.stage1 import fixed_events, run_simulation


@pytest.fixture
def cfg():
    return load_config(Path(__file__).resolve().parents[1] / 'configs/stage1.yaml')


def test_latency_excludes_baseline_and_keeps_silent_cells():
    spikes = pd.DataFrame({'bodyId': [1, 1, 2, 3], 'time_ms': [100., 210., 900., 205.]})
    got = first_spike_latency(spikes, 200, [1, 2, 3, 4], 800).set_index('bodyId')
    assert got.loc[1, 'latency_ms'] == 10
    assert got.loc[3, 'latency_ms'] == 5
    assert got.loc[[2, 4], 'latency_ms'].isna().all()


def test_empty_latency():
    got = first_spike_latency(pd.DataFrame(columns=['bodyId', 'time_ms']), 200, [1, 2], 800)
    assert len(got) == 2 and got.latency_ms.isna().all()


def test_fixed_input_is_repeatable_independent_and_binned(cfg):
    channels, times = fixed_events([1, 2, 3], cfg)
    c2, t2 = fixed_events([1, 2, 3], cfg)
    np.testing.assert_array_equal(channels, c2)
    np.testing.assert_array_equal(times, t2)
    assert not np.array_equal(times[channels == 0], times[channels == 1])
    assert times.min() >= 0 and times.max() < 1
    assert len(set(zip(channels, np.rint(times / .0001).astype(int)))) == len(times)
    stimulus_rate = ((times >= .2) & (times < .8)).sum() / .6 / 3
    baseline_rate = ((times < .2) | (times >= .8)).sum() / .4 / 3
    assert stimulus_rate > 3 * baseline_rate


@pytest.mark.parametrize('section,key,value', [('snn', 'dt_ms', 0), ('snn', 'dt_ms', -1),
    ('fixed_input', 'onset_s', 0), ('fixed_input', 'offset_s', 2), ('fixed_input', 'stimulus_hz', float('nan'))])
def test_invalid_input_configuration(cfg, section, key, value):
    cfg[section][key] = value
    with pytest.raises(ValueError):
        fixed_events([1], cfg)


def test_induced_graph_retains_return_edges_and_limits_new_nodes(monkeypatch):
    import neuprint
    table = pd.DataFrame([(1, 2, 20), (1, 3, 15), (1, 4, 15), (2, 1, 100),
                          (2, 5, 8), (3, 6, 10), (6, 2, 9)],
                         columns=['bodyId_pre', 'bodyId_post', 'weight'])
    calls = []
    def adjacency(sources, targets, **kwargs):
        calls.append((sources, targets))
        filtered = table[table.bodyId_pre.isin(sources)]
        if targets is not None:
            filtered = filtered[filtered.bodyId_post.isin(targets)]
        return pd.DataFrame({'bodyId': []}), filtered.copy()
    monkeypatch.setattr(neuprint, 'fetch_adjacencies', adjacency)
    monkeypatch.setattr(neuprint, 'NeuronCriteria', lambda **kw: kw)
    monkeypatch.setattr(neuprint, 'fetch_neurons', lambda criteria, **kw: pd.DataFrame({'bodyId': criteria['bodyId']}))
    nodes, edges = fetch_downstream_hops([1], object(), max_new_nodes_per_hop=2, max_nodes=4)
    assert nodes.bodyId.tolist() == [1, 2, 3, 6]  # ties by ID; revisits do not consume quota
    assert len(nodes) <= 4
    assert (6, 2) in set(zip(edges.bodyId_pre, edges.bodyId_post))
    assert (2, 1) in set(zip(edges.bodyId_pre, edges.bodyId_post))
    assert nodes.set_index('bodyId').loc[6, 'hop'] == 2
    assert calls[-1][0] == calls[-1][1] == [1, 2, 3, 6]


def test_empty_discovery_fails(monkeypatch):
    import neuprint
    monkeypatch.setattr(neuprint, 'NeuronCriteria', lambda **kw: kw)
    monkeypatch.setattr(neuprint, 'fetch_neurons', lambda *a, **k: pd.DataFrame({'bodyId': [1], 'type': ['JO-C1']}))
    with pytest.raises(ValueError, match='No auditory'):
        discover_auditory_jons(object(), '^JO-.*', '^JO-[AB].*')


def test_reject_roi_duplicate_and_invalid_weights():
    df = pd.DataFrame({'bodyId_pre': [1, 1], 'bodyId_post': [2, 2], 'weight': [3, 5]})
    with pytest.raises(ValueError, match='unique'):
        validate_edges(df)
    with pytest.raises(ValueError):
        validate_edges(df.iloc[:1].assign(weight=float('nan')))


def test_graphml_preserves_isolates_and_nested_metadata(tmp_path):
    nodes = pd.DataFrame({'bodyId': [1, 2, 3], 'type': ['A', 'B', None],
                          'location': [[1, 2, 3], None, [4, 5, 6]]})
    edges = pd.DataFrame({'bodyId_pre': [1], 'bodyId_post': [2], 'weight': [5]})
    save_subgraph(nodes, edges, tmp_path)
    graph = nx.read_graphml(tmp_path / 'auditory_subgraph.graphml')
    assert set(graph) == {'1', '2', '3'} and graph.degree('3') == 0


def test_manifest_detects_changed_data(tmp_path):
    path = tmp_path / 'seeds.csv'
    path.write_text('bodyId\n1\n')
    write_json(tmp_path / 'manifest.json', manifest([path], source='TEST'))
    assert verify_manifest(tmp_path)['source'] == 'TEST'
    path.write_text('bodyId\n2\n')
    with pytest.raises(ValueError, match='checksum'):
        verify_manifest(tmp_path)


def tiny_network():
    nodes = pd.DataFrame({'bodyId': [1, 2], 'consensusNt': ['ACh', 'ACh']})
    edges = pd.DataFrame({'bodyId_pre': [1], 'bodyId_post': [2], 'weight': [10]})
    return nodes, edges


def test_known_spike_propagates_with_delay_and_replays_exactly(cfg):
    nodes, edges = tiny_network()
    cfg['snn'].update(simulation_ms=30, input_weight_mv=11, w0_mv=11)
    args = (nodes, edges, [1], np.array([0]), np.array([.01]), cfg)
    spikes = run_simulation(*args)
    pd.testing.assert_frame_equal(spikes, run_simulation(*args))
    first = spikes.groupby('bodyId').time_ms.min()
    assert set(first.index) == {1, 2}
    assert cfg['snn']['delay_ms'] <= first[2] - first[1] <= cfg['snn']['delay_ms'] + .2
    assert run_simulation(*args, silence=True).empty


def test_inhibitory_source_prevents_downstream_spike(cfg):
    nodes, edges = tiny_network()
    nodes.loc[0, 'consensusNt'] = 'GABA'
    cfg['snn'].update(simulation_ms=30, input_weight_mv=11, w0_mv=11)
    spikes = run_simulation(nodes, edges, [1], [0], [.01], cfg)
    assert set(spikes.bodyId) == {1}


def test_no_edges_is_valid_and_unknown_endpoints_fail(cfg):
    nodes, edges = tiny_network()
    cfg['snn'].update(simulation_ms=30, input_weight_mv=11)
    spikes = run_simulation(nodes, edges.iloc[:0], [1], [0], [.01], cfg)
    assert set(spikes.bodyId) == {1}
    with pytest.raises(ValueError, match='endpoint'):
        run_simulation(nodes, edges.assign(bodyId_post=3), [1], [0], [.01], cfg)


def test_duplicate_time_bins_fail(cfg):
    nodes, edges = tiny_network()
    with pytest.raises(ValueError, match='same channel'):
        run_simulation(nodes, edges, [1], [0, 0], [.01, .010001], cfg)


def test_public_arrow_backend_excludes_untraced_segments(tmp_path, cfg):
    from ear_malecns.bulk import FILES, public_subgraph
    from ear_malecns.provenance import sha256
    raw = tmp_path / 'data/raw/malecns'
    raw.mkdir(parents=True)
    pd.DataFrame({'bodyId': [1, 2, 3, 4], 'type': ['JO-A1', 'relay', 'output', 'orphan'],
                  'status': ['Traced', 'Traced', 'Traced', 'Orphan']}).to_feather(raw / FILES[0])
    pd.DataFrame({'body': [1, 2, 3, 4], 'predicted_nt': ['acetylcholine'] * 4,
                  'consensus_nt': ['acetylcholine', 'gaba', 'glutamate', 'gaba']}).to_feather(raw / FILES[1])
    pd.DataFrame({'body_pre': [1, 1, 2, 3], 'body_post': [2, 4, 3, 2],
                  'weight': [6, 1000, 7, 8]}).to_feather(raw / FILES[2])
    for name in FILES:
        write_json((raw / name).with_suffix('.feather.json'), {'sha256': sha256(raw / name)})
    nodes, edges, seeds, info = public_subgraph(tmp_path, cfg['malecns'])
    assert seeds.bodyId.tolist() == [1]
    assert nodes.bodyId.tolist() == [1, 2, 3]
    assert (3, 2) in set(zip(edges.bodyId_pre, edges.bodyId_post))
    assert nodes.set_index('bodyId').loc[2, 'consensusNt'] == 'gaba'
    assert len(info['batch_scans']) == 3


def test_missing_token_fails_before_api_call(monkeypatch):
    from ear_malecns.malecns import make_client
    monkeypatch.delenv('NEUPRINT_APPLICATION_CREDENTIALS', raising=False)
    with pytest.raises(RuntimeError, match='Missing NEUPRINT'):
        make_client('https://neuprint.janelia.org', 'male-cns:v1.0')


def test_seed_audit_does_not_equate_type_name_with_auditory_function():
    from ear_malecns.malecns import seed_annotation_audit
    table = pd.DataFrame({'bodyId': [1, 2, 3], 'type': ['JO-A1', 'JO-B1_a', 'JO-B2'],
                          'subclass': ['auditory', 'wind_gravity', None]})
    rows = seed_annotation_audit(table, 'auditory')
    assert [r['selected'] for r in rows] == [True, False, False]
    assert rows[2]['subclass'] is None

from __future__ import annotations

import os
import json
from pathlib import Path
import numpy as np
import pandas as pd


def make_client(server: str, dataset: str):
    from neuprint import Client

    token = os.getenv("NEUPRINT_APPLICATION_CREDENTIALS")
    if not token:
        raise RuntimeError(
            "Missing NEUPRINT_APPLICATION_CREDENTIALS. "
            "Create a neuPrint token and export it as an environment variable."
        )
    return Client(server, dataset=dataset, token=token)


def _neuron_table(fetch_result):
    # fetch_neurons normally returns (neurons, roi_counts); keep this adapter
    # defensive against future API wrapper changes.
    if isinstance(fetch_result, tuple):
        for item in fetch_result:
            if isinstance(item, pd.DataFrame) and "bodyId" in item.columns:
                return item
    if isinstance(fetch_result, pd.DataFrame):
        return fetch_result
    raise TypeError("Could not identify neuron DataFrame from neuPrint result")


def _edge_table(fetch_result):
    # fetch_adjacencies examples across docs/wrappers may name/order outputs
    # differently. Detect the table by its actual columns instead of assuming.
    candidates = fetch_result if isinstance(fetch_result, tuple) else (fetch_result,)
    for item in candidates:
        if isinstance(item, pd.DataFrame):
            cols = set(item.columns)
            if {"bodyId_pre", "bodyId_post"}.issubset(cols):
                return item
    raise TypeError("Could not identify adjacency DataFrame from neuPrint result")


def discover_auditory_jons(client, jon_regex: str, auditory_regex: str) -> pd.DataFrame:
    from neuprint import NeuronCriteria as NC, fetch_neurons

    criteria = NC(type=jon_regex, regex=True)
    result = fetch_neurons(criteria, omit_rois=True, client=client)
    jons = _neuron_table(result).copy()
    if "type" not in jons.columns:
        raise KeyError("neuPrint result has no 'type' column")
    mask = jons["type"].fillna("").str.match(auditory_regex)
    auditory = jons.loc[mask].copy()
    auditory = auditory[~auditory["type"].fillna("").str.contains("unclear", case=False)]
    if auditory.empty:
        raise ValueError('No auditory JO-A/JO-B candidates matched; inspect current annotations before continuing.')
    if auditory['bodyId'].duplicated().any():
        raise ValueError('Duplicate auditory body IDs in neuPrint response')
    return auditory.sort_values(["type", "bodyId"], na_position="last")


def seed_annotation_audit(candidates: pd.DataFrame, subclass: str | None = None) -> list[dict]:
    records = []
    for row in candidates.to_dict(orient='records'):
        label = row.get('subclass')
        label = None if label is None or pd.isna(label) else str(label)
        records.append({'bodyId': int(row['bodyId']), 'type': str(row['type']),
                        'subclass': label, 'selected': subclass is None or label == subclass,
                        'annotation_supports_auditory': label == 'auditory'})
    return records


def fetch_downstream_hops(
    seed_ids: list[int],
    client,
    hops: int = 2,
    min_weight: int = 5,
    max_new_nodes_per_hop: int | None = 150,
    max_nodes: int = 300,
    status_filter: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from neuprint import NeuronCriteria as NC, fetch_adjacencies, fetch_neurons

    def connections(sources, targets):
        if targets is None and status_filter:
            targets = NC(status=status_filter)
        return _edge_table(fetch_adjacencies(sources=sources, targets=targets,
                           min_total_weight=min_weight, omit_rois=True, client=client))

    def metadata(ids):
        return _neuron_table(fetch_neurons(NC(bodyId=ids), omit_rois=True, client=client))

    return extract_downstream_hops(seed_ids, connections, metadata, hops, min_weight,
                                   max_new_nodes_per_hop, max_nodes)


def extract_downstream_hops(seed_ids, connection_fetcher, neuron_fetcher,
                            hops=2, min_weight=5, max_new_nodes_per_hop=150, max_nodes=300):
    """Shared deterministic node selection for live neuPrint and public flat files."""
    visited = set(map(int, seed_ids))
    if len(visited) != len(seed_ids):
        raise ValueError('Seed IDs must be unique')
    if not visited or len(visited) > max_nodes:
        raise ValueError('Seeds must be nonempty and fit max_nodes; explicitly select a documented seed subset if needed.')
    if hops not in (1, 2) or min_weight < 1 or (max_new_nodes_per_hop is not None and max_new_nodes_per_hop < 1):
        raise ValueError('Stage 1 requires 1-2 hops, positive weight threshold and node limits')
    frontier = set(visited)
    node_hops = {x: 0 for x in visited}

    for hop in range(1, hops + 1):
        if not frontier:
            break
        edges = validate_edges(connection_fetcher(sorted(frontier), None))
        if edges.empty:
            break
        candidates = edges[(edges['weight'] >= min_weight) & ~edges['bodyId_post'].isin(visited)]
        strength = candidates.groupby('bodyId_post', as_index=False)['weight'].sum()
        strength = strength.sort_values(['weight', 'bodyId_post'], ascending=[False, True])
        limit = max_nodes - len(visited)
        if max_new_nodes_per_hop is not None:
            limit = min(limit, max_new_nodes_per_hop)
        frontier = set(strength.head(limit)['bodyId_post'].astype(int))
        node_hops.update({x: hop for x in frontier})
        visited |= frontier

    # Fetch the INDUCED graph, including final-hop outputs and recurrent edges.
    edge_df = validate_edges(connection_fetcher(sorted(visited), sorted(visited)))
    edge_df = edge_df[(edge_df['weight'] >= min_weight)
                      & edge_df.bodyId_pre.isin(visited) & edge_df.bodyId_post.isin(visited)].copy()
    edge_df['hop'] = edge_df.bodyId_pre.map(node_hops) + 1
    neurons = neuron_fetcher(sorted(visited)).copy()
    if set(neurons.bodyId.astype(int)) != visited or neurons.bodyId.duplicated().any():
        raise ValueError('Node metadata does not match the selected body IDs')
    neurons['hop'] = neurons.bodyId.map(node_hops)
    neurons['is_seed'] = neurons.bodyId.isin(seed_ids)
    neurons = neurons.sort_values('bodyId').reset_index(drop=True)
    return neurons, edge_df


def validate_edges(edges: pd.DataFrame) -> pd.DataFrame:
    """Require pair totals; never silently take max over per-ROI rows."""
    columns = ['bodyId_pre', 'bodyId_post', 'weight']
    if not set(columns).issubset(edges.columns):
        raise ValueError('Connections require bodyId_pre, bodyId_post, weight')
    if 'roi' in edges.columns or edges.duplicated(columns[:2]).any():
        raise ValueError('Expected unique neuron-pair totals (omit_rois=True), not ROI rows or duplicate pairs')
    out = edges[columns].copy()
    for column in columns:
        values = pd.to_numeric(out[column], errors='raise')
        if not np.isfinite(values).all() or (values % 1 != 0).any():
            raise ValueError(f'{column} must contain finite integers')
        out[column] = values.astype('int64')
    if (out.weight <= 0).any():
        raise ValueError('Connection weights must be positive')
    return out.sort_values(columns[:2]).reset_index(drop=True)


def add_local_input_fraction(edges: pd.DataFrame) -> pd.DataFrame:
    """Exploratory-only normalization within the extracted subgraph.

    Paper-grade input fractions should use each postsynaptic neuron's global
    total input, not merely the truncated subgraph denominator.
    """
    out = edges.copy()
    total = out.groupby("bodyId_post")["weight"].transform("sum")
    out["local_input_fraction"] = out["weight"] / total.clip(lower=1)
    return out


def save_subgraph(nodes: pd.DataFrame, edges: pd.DataFrame, out_dir: str | Path) -> None:
    import networkx as nx

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stored_nodes = nodes.copy()
    for column in stored_nodes:
        if stored_nodes[column].dtype == object:
            stored_nodes[column] = stored_nodes[column].map(
                lambda v: json.dumps(v.tolist() if isinstance(v, np.ndarray) else v, default=str)
                if isinstance(v, (dict, list, tuple, np.ndarray)) else v)
    stored_nodes.to_parquet(out_dir / "nodes.parquet", index=False)
    edges.to_parquet(out_dir / "edges.parquet", index=False)

    g = nx.from_pandas_edgelist(
        edges,
        source="bodyId_pre",
        target="bodyId_post",
        edge_attr=[c for c in ["weight", "hop", "local_input_fraction"] if c in edges.columns],
        create_using=nx.DiGraph,
    )
    for row in nodes.to_dict(orient='records'):
        body_id = int(row.pop('bodyId'))
        safe = {}
        for key, value in row.items():
            if isinstance(value, (list, dict, tuple, np.ndarray)):
                value = json.dumps(value.tolist() if isinstance(value, np.ndarray) else value, default=str)
            elif value is None or pd.isna(value):
                value = ''
            elif isinstance(value, np.generic):
                value = value.item()
            elif not isinstance(value, (str, int, float, bool)):
                value = str(value)
            safe[key] = value
        g.add_node(body_id, **safe)  # preserve isolated nodes too
    nx.write_graphml(g, out_dir / "auditory_subgraph.graphml")

"""Authenticated API alternative: pinned public MaleCNS v1.0 flat files."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import time
import json

import requests

from .provenance import sha256, write_json

BASE = 'https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/'
FILES = ['body-annotations-male-cns-v1.0-minconf-0.5.feather',
         'body-neurotransmitters-male-cns-v1.0.feather',
         'connectome-weights-male-cns-v1.0-minconf-0.5.feather']


def download_large_verified(url: str, path: Path) -> dict:
    """Bounded range requests avoid stalled giant responses; reassemble and MD5-check."""
    from concurrent.futures import ThreadPoolExecutor
    path.parent.mkdir(parents=True, exist_ok=True)
    head = requests.head(url, timeout=30)
    head.raise_for_status()
    size = int(head.headers['Content-Length'])
    etag = head.headers['ETag']
    expected = next(part.strip()[4:] for part in head.headers['x-goog-hash'].split(',') if part.strip().startswith('md5='))
    if path.exists():
        with path.open('rb') as stream:
            md5 = base64.b64encode(hashlib.file_digest(stream, 'md5').digest()).decode()
        if md5 != expected:
            raise ValueError('Existing bulk file checksum mismatch')
    else:
        chunks = path.parent / (path.name + '.chunks')
        chunks.mkdir(exist_ok=True)
        chunk_size = 8 * 1024 * 1024
        ranges = [(i, start, min(size - 1, start + chunk_size - 1)) for i, start in enumerate(range(0, size, chunk_size))]
        def fetch(part):
            i, start, end = part
            target = chunks / f'{i:05d}.part'
            for attempt in range(3):
                try:
                    response = requests.get(url, headers={'Range': f'bytes={start}-{end}', 'If-Match': etag}, timeout=(15, 60))
                    response.raise_for_status()
                    if response.status_code != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{size}' or len(response.content) != end - start + 1:
                        raise ValueError('Invalid HTTP range response')
                    target.write_bytes(response.content)
                    return target
                except requests.RequestException:
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
        with ThreadPoolExecutor(max_workers=4) as pool:
            parts = list(pool.map(fetch, ranges))
        partial = path.with_suffix(path.suffix + '.part')
        digest = hashlib.md5()
        with partial.open('wb') as output:
            for part in parts:
                block = part.read_bytes(); digest.update(block); output.write(block)
        if base64.b64encode(digest.digest()).decode() != expected:
            raise ValueError('Bulk file checksum mismatch')
        partial.replace(path)
        for part in parts:
            part.unlink()  # only exact chunk files created by this download
        chunks.rmdir()
    record = {'url': url, 'bytes': size, 'sha256': sha256(path), 'provider_md5_base64': expected,
              'etag': etag, 'dataset': 'male-cns:v1.0', 'license': 'CC-BY',
              'source_page': 'https://male-cns.janelia.org/download/'}
    write_json(path.with_suffix(path.suffix + '.json'), record)
    return record


def download_verified(url: str, path: Path) -> dict:
    """Stream to H drive; verify provider MD5 before publishing a complete file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with requests.get(url, stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                expected = next((part.strip()[4:] for part in response.headers.get('x-goog-hash', '').split(',')
                                 if part.strip().startswith('md5=')), None)
                expected_length = int(response.headers.get('Content-Length', 0))
                if path.exists():
                    with path.open('rb') as existing:
                        md5 = hashlib.file_digest(existing, 'md5').digest()
                    if not expected or base64.b64encode(md5).decode() != expected:
                        raise ValueError(f'Existing file differs from provider checksum: {path.name}')
                else:
                    md5_hash = hashlib.md5()
                    partial = path.with_suffix(path.suffix + '.part')
                    with partial.open('wb') as stream:
                        for block in response.iter_content(1024 * 1024):
                            if block:
                                stream.write(block); md5_hash.update(block)
                    if expected_length and partial.stat().st_size != expected_length:
                        raise ValueError('Incomplete download')
                    if not expected or base64.b64encode(md5_hash.digest()).decode() != expected:
                        raise ValueError('Provider checksum mismatch or missing MD5')
                    partial.replace(path)
                record = {'url': url, 'bytes': path.stat().st_size, 'sha256': sha256(path),
                          'provider_md5_base64': expected, 'etag': response.headers.get('ETag'),
                          'dataset': 'male-cns:v1.0', 'license': 'CC-BY',
                          'source_page': 'https://male-cns.janelia.org/download/'}
                write_json(path.with_suffix(path.suffix + '.json'), record)
                return record
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError('Download failed')


def public_subgraph(root: Path, config: dict):
    """Scan Arrow record batches; never materialize the full segment graph."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.compute as pc
    from .malecns import extract_downstream_hops, seed_annotation_audit
    directory = root / 'data/raw/malecns'
    records = {}
    for name in FILES:
        path = directory / name
        info = json.loads(path.with_suffix(path.suffix + '.json').read_text(encoding='utf-8'))
        if sha256(path) != info['sha256']:
            raise ValueError(f'Raw public file checksum mismatch: {name}')
        records[name] = info
    annotations = pd.read_feather(directory / FILES[0])
    status = config.get('status_filter', 'Traced')
    annotations = annotations[annotations.status == status].copy()
    auditory = annotations[annotations.type.fillna('').str.match(config['auditory_type_regex'])].copy()
    if auditory.empty or auditory.bodyId.duplicated().any():
        raise ValueError('No unique JO-A/JO-B seeds found in public annotations')
    auditory = auditory.sort_values(['type', 'bodyId'])
    audit = seed_annotation_audit(auditory, config.get('seed_subclass'))
    if config.get('seed_subclass'):
        auditory = auditory[auditory['subclass'] == config['seed_subclass']].copy()
    if auditory.empty:
        raise ValueError('Seed subclass filter selected no neurons')
    nt = pd.read_feather(directory / FILES[1], columns=['body', 'predicted_nt', 'consensus_nt'])
    nt = nt.rename(columns={'body': 'bodyId', 'predicted_nt': 'predictedNt', 'consensus_nt': 'consensusNt'})
    annotations = annotations.merge(nt, on='bodyId', how='left', validate='one_to_one')
    valid_ids = set(annotations.bodyId.astype(int))
    scans = []
    def connections(sources, targets):
        selected = []
        with pa.memory_map(str(directory / FILES[2]), 'r') as stream:
            reader = pa.ipc.open_file(stream)
            source_set = pa.array(sources, type=pa.int64())
            target_set = None if targets is None else pa.array(targets, type=pa.int64())
            rows = 0
            for i in range(reader.num_record_batches):
                batch = reader.get_batch(i)
                rows += batch.num_rows
                mask = pc.and_(pc.is_in(batch.column('body_pre'), value_set=source_set),
                               pc.greater_equal(batch.column('weight'), config['min_weight']))
                if target_set is not None:
                    mask = pc.and_(mask, pc.is_in(batch.column('body_post'), value_set=target_set))
                reduced = batch.filter(mask)
                if reduced.num_rows:
                    selected.append(reduced.to_pandas())
        scans.append({'source_count': len(sources), 'target_count': None if targets is None else len(targets), 'scanned_segment_edges': rows})
        out = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame(columns=['body_pre', 'body_post', 'weight'])
        out = out[out.body_post.isin(valid_ids)]
        return out.rename(columns={'body_pre': 'bodyId_pre', 'body_post': 'bodyId_post'})
    def metadata(ids):
        return annotations[annotations.bodyId.isin(ids)].copy()
    nodes, edges = extract_downstream_hops(auditory.bodyId.astype(int).tolist(), connections, metadata,
                    hops=config['hops'], min_weight=config['min_weight'],
                    max_new_nodes_per_hop=config['max_new_nodes_per_hop'], max_nodes=config['max_nodes'])
    return nodes, edges, auditory, {'raw_files': records, 'batch_scans': scans, 'status_filter': status,
                                  'seed_annotation_audit': audit,
                                  'annotation_review': 'PENDING_HUMAN_REVIEW',
                                  'dataset': 'male-cns:v1.0', 'source_page': 'https://male-cns.janelia.org/download/',
                                  'query_config': config, 'license': 'CC-BY'}

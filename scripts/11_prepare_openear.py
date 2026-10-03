"""Fetch official OpenEar metadata and only geometry members of ZETA.zip.

Raw image stacks are not needed to inspect existing geometry. HTTP ranges avoid
downloading the entire 3.9 GB archive; ZipFile verifies each selected member CRC.
"""
from _bootstrap import ROOT
import argparse
import io
import json
import zipfile
from pathlib import Path
import requests
from ear_malecns.provenance import write_json, sha256


class HTTPZip(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0
        self.session = requests.Session()
        self.downloaded = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if self.position < 0:
            raise ValueError('Negative offset')
        return self.position

    def read(self, n=-1):
        n = self.size - self.position if n < 0 else min(n, self.size - self.position)
        if n <= 0:
            return b''
        start, end = self.position, self.position + n - 1
        # Per-range query avoids a proxy reusing a response for a different range.
        response = self.session.get(self.url, params={'range_start': start, 'range_end': end},
                    headers={'Range': f'bytes={start}-{end}'}, timeout=(30, 120))
        response.raise_for_status()
        if response.status_code != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{self.size}':
            raise RuntimeError('OpenEar server did not honor byte range; refusing a full archive response')
        if len(response.content) != n:
            raise RuntimeError('Truncated range')
        self.position += n
        self.downloaded += n
        return response.content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    directory = ROOT / 'data/raw/openear'
    directory.mkdir(parents=True, exist_ok=True)
    response = requests.get('https://zenodo.org/api/records/1473724', timeout=60)
    response.raise_for_status()
    metadata = response.json()
    write_json(directory / 'zenodo_record_1473724.json', metadata)
    archive = next(f for f in metadata['files'] if f['key'] == 'ZETA.zip')
    url = archive['links']['self']
    stream = HTTPZip(url, archive['size'])
    with zipfile.ZipFile(stream) as z:
        entries = [i for i in z.infolist() if i.filename.lower().endswith(('.stl', '.obj', '.ply'))]
        write_json(directory / 'geometry_inventory.json', {'archive': archive,
            'members': [dict(name=i.filename, bytes=i.file_size, compressed_bytes=i.compress_size,
                             crc32=f'{i.CRC:08x}') for i in entries]})
        print(json.dumps({'geometry_members': len(entries), 'total_geometry_bytes': sum(i.file_size for i in entries)}, indent=2), flush=True)
        if args.download:
            target = ROOT / 'fem/geometry/openear_zeta'
            target.mkdir(parents=True, exist_ok=True)
            records = []
            for i in entries:
                # Flatten to safe local filenames; never trust archive paths.
                name = Path(i.filename.replace('\\', '/')).name
                path = target / name
                if any(r['local_file'] == name for r in records):
                    raise ValueError('Duplicate flattened geometry filename')
                payload = z.read(i)  # CRC-verified by zipfile
                path.write_bytes(payload)
                records.append(dict(archive_member=i.filename, local_file=name, bytes=len(payload),
                                    sha256=sha256(path), crc32=f'{i.CRC:08x}'))
                print(f'Geometry verified: {name} ({len(payload)} bytes)', flush=True)
            write_json(target / 'manifest.json', {'source': 'OpenEar ZETA anatomical geometry',
                'source_page': 'https://zenodo.org/records/1473724', 'archive': archive,
                'files': records, 'network_bytes': stream.downloaded,
                'verification': 'ZIP member CRC32 plus local SHA256; entire archive MD5 not checked',
                'limitations': 'Anatomical surface geometry, not a mechanical FEM or validated response'})


if __name__ == '__main__':
    main()

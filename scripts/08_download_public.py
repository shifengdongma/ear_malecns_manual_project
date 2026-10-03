from _bootstrap import ROOT
from concurrent.futures import ThreadPoolExecutor
from ear_malecns.bulk import BASE, FILES, download_verified, download_large_verified

def download(name):
    downloader = download_large_verified if name.startswith('connectome-weights') else download_verified
    record = downloader(BASE + name, ROOT / 'data/raw/malecns' / name)
    print(f'Verified {name}: {record["bytes"]} bytes', flush=True)

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download, FILES))

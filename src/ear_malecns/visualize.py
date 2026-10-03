from __future__ import annotations

from pathlib import Path
import numpy as np


def fetch_and_save_skeletons(client, body_ids: list[int], out_dir: str | Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for body_id in body_ids:
        path = out_dir / f"{int(body_id)}.swc"
        if not path.exists():
            swc = client.fetch_skeleton(int(body_id), heal=False, format='swc')
            path.write_text(swc, encoding='utf-8')
        paths.append(path)
    return paths


def fetch_public_skeletons(body_ids: list[int], out_dir: str | Path) -> list[Path]:
    from .bulk import download_verified
    base = 'https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/'
    paths = []
    for body_id in body_ids:
        if int(body_id) <= 0:
            raise ValueError('Public skeleton IDs must be positive real body IDs')
        path = Path(out_dir) / f'{int(body_id)}.swc'
        download_verified(base + path.name, path)
        paths.append(path)
    return paths


def save_skeleton_figure(paths: list[Path], output: Path) -> None:
    """Public SWC coordinates are 8-nm voxels; display micrometres."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    points = []
    for i, path in enumerate(paths):
        data = np.loadtxt(path, comments='#', ndmin=2)
        coordinates = data[:, 2:5] * .008
        index = {int(row[0]): j for j, row in enumerate(data)}
        segments = [[coordinates[j], coordinates[index[int(row[6])]]]
                    for j, row in enumerate(data) if int(row[6]) in index]
        ax.add_collection3d(Line3DCollection(segments, linewidths=.4, colors=[plt.get_cmap('tab20')(i % 20)]))
        points.extend(coordinates)
    if points:
        xyz = np.asarray(points)
        ax.auto_scale_xyz(xyz[:, 0], xyz[:, 1], xyz[:, 2])
        ax.set_box_aspect(np.maximum(np.ptp(xyz, axis=0), 1))
    ax.set(xlabel='X (um)', ylabel='Y (um)', zlabel='Z (um)',
           title=f'MaleCNS v1.0: {len(paths)} public SWC skeletons\nMorphology only; not measured or simulated electrical activity')
    fig.tight_layout(); fig.savefig(output, dpi=150); plt.close(fig)


def skeleton_to_polydata(swc):
    import pyvista as pv

    row_lookup = {int(row.rowId): row for _, row in swc.iterrows()}
    points: list[list[float]] = []
    lines: list[int] = []
    for _, row in swc.iterrows():
        parent_id = int(row.link)
        if parent_id < 0:
            continue
        parent = row_lookup.get(parent_id)
        if parent is None:
            continue
        i0 = len(points)
        points.append([float(row.x), float(row.y), float(row.z)])
        i1 = len(points)
        points.append([float(parent.x), float(parent.y), float(parent.z)])
        lines.extend([2, i0, i1])
    mesh = pv.PolyData(np.asarray(points, dtype=float))
    if lines:
        mesh.lines = np.asarray(lines, dtype=np.int64)
    return mesh

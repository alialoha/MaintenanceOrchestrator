"""Download Kaggle datasets used by the maintenance orchestrator demo.

Supports two backends:
1) kagglehub (Python package)
2) kaggle CLI

Usage (from repo root):
  python scripts/download_kaggle_seed.py

Options:
  --method auto|kagglehub|kaggle
  --dataset all|logistics_and_supply_chain|vehicle_maintenance_history
  --dest data/raw/kaggle
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

DATASETS = {
    "logistics_and_supply_chain": "datasetengineer/logistics-and-supply-chain-dataset",
    "vehicle_maintenance_history": "datasetengineer/logistics-vehicle-maintenance-history-dataset",
}

DEFAULT_DEST = Path("data/raw/kaggle")
MANIFEST = Path("data/sources.kaggle.json")


def _copy_tree(src: Path, dst: Path) -> list[str]:
    dst.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        copied.append(str(out.as_posix()))
    return copied


def _download_with_kagglehub(dataset_ref: str, out_dir: Path) -> list[str]:
    try:
        import kagglehub  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local env
        raise RuntimeError(
            "kagglehub is not installed. Install with: pip install kagglehub"
        ) from exc
    download_path = Path(kagglehub.dataset_download(dataset_ref))
    return _copy_tree(download_path, out_dir)


def _download_with_kaggle_cli(dataset_ref: str, out_dir: Path) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="kaggle-dl-") as td:
        temp_dir = Path(td)
        cmd = [
            "kaggle",
            "datasets",
            "download",
            "-d",
            dataset_ref,
            "-p",
            str(temp_dir),
            "--unzip",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                "kaggle CLI download failed.\n"
                f"Command: {' '.join(cmd)}\n"
                f"stderr: {proc.stderr.strip()}\n"
                "Ensure Kaggle API credentials are configured "
                "(~/.kaggle/kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY)."
            )
        return _copy_tree(temp_dir, out_dir)


def _try_methods(method: str, dataset_ref: str, out_dir: Path) -> tuple[str, list[str]]:
    if method == "kagglehub":
        return "kagglehub", _download_with_kagglehub(dataset_ref, out_dir)
    if method == "kaggle":
        return "kaggle", _download_with_kaggle_cli(dataset_ref, out_dir)

    errors: list[str] = []
    for m, fn in (
        ("kagglehub", _download_with_kagglehub),
        ("kaggle", _download_with_kaggle_cli),
    ):
        try:
            return m, fn(dataset_ref, out_dir)
        except Exception as exc:  # pragma: no cover - depends on local env
            errors.append(f"{m}: {exc}")
    raise RuntimeError("All download methods failed:\n- " + "\n- ".join(errors))


def _selected_datasets(name: str) -> Iterable[tuple[str, str]]:
    if name == "all":
        return DATASETS.items()
    return [(name, DATASETS[name])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--method",
        default="auto",
        choices=("auto", "kagglehub", "kaggle"),
        help="Downloader backend.",
    )
    parser.add_argument(
        "--dataset",
        default="all",
        choices=("all", *DATASETS.keys()),
        help="Which dataset to download.",
    )
    parser.add_argument(
        "--dest",
        default=str(DEFAULT_DEST),
        help="Destination directory for downloaded files.",
    )
    args = parser.parse_args()

    dest_root = Path(args.dest)
    dest_root.mkdir(parents=True, exist_ok=True)
    run_manifest: dict[str, object] = {
        "method_requested": args.method,
        "dest": str(dest_root.as_posix()),
        "datasets": [],
    }

    for alias, dataset_ref in _selected_datasets(args.dataset):
        print(f"Downloading {alias} ({dataset_ref}) ...", flush=True)
        alias_out = dest_root / alias
        method_used, files = _try_methods(args.method, dataset_ref, alias_out)
        print(f"  OK via {method_used}: {len(files)} files", flush=True)
        run_manifest["datasets"].append(
            {
                "alias": alias,
                "dataset_ref": dataset_ref,
                "method_used": method_used,
                "output_dir": str(alias_out.as_posix()),
                "files": files,
            }
        )

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest: {MANIFEST.as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

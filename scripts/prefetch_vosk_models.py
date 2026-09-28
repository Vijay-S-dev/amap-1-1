#!/usr/bin/env python3
"""Provision the Vosk speech-recognition models for AMAP (deterministic).

AMAP has exactly ONE speech-recognition engine: Vosk. This script installs
the two required offline models into AMAP_VOSK_MODELS_DIR (default:
backend/.vosk_cache). Runtime never touches the network: the backend loads
models only from that directory.

Models (both Apache-2.0, from Alpha Cephei):

  English  vosk-model-small-en-us-0.15   41,205,931 bytes (zip)
           sha256 30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498
           unpacks to ~68 MB on disk
  Hindi    vosk-model-small-hi-0.22      44,458,845 bytes (zip)
           sha256 7c50a10866889f0ac21d912c20537a055a597ed09fc1d3e5bcd798f9f0017e48
           unpacks to ~79 MB on disk

Download sources, in order:
  1. Official: https://alphacephei.com/vosk/models/<model>.zip
  2. GitHub mirror fallback (for restricted networks where alphacephei.com is
     unreachable — same artifacts, verified against the pinned checksums):
       - en: github.com/kercre123/vosk-models (zip blob, sha256 == official)
       - hi: github.com/rajkishorbgp/JARVIS-AI-Assistant (unpacked model tree;
         verified against a pinned per-file SHA-256 manifest because the
         official zip is not mirrored as a single blob anywhere reachable)

Verification: every byte is checksum-verified before installation; a mismatch
aborts with a non-zero exit code. Installation is idempotent — already-present,
verified models are left untouched.

Startup behavior: backend/app/main.py preloads both models once per process in
a background thread at startup; /voice/stt-health reports
READY/ERROR/NOT_INITIALIZED. A missing model disables /voice/stream with a
clear error (close code 4503) — it never crashes the backend and never falls
back to any other engine.

Usage:  python scripts/prefetch_vosk_models.py [--dir <models_dir>]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "backend" / ".vosk_cache"

EN_ZIP_SHA256 = "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"
HI_ZIP_SHA256 = "7c50a10866889f0ac21d912c20537a055a597ed09fc1d3e5bcd798f9f0017e48"

MODELS = {
    "en": {
        "name": "vosk-model-small-en-us-0.15",
        "zip_url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        "zip_sha256": EN_ZIP_SHA256,
        "mirror_repo": "https://github.com/kercre123/vosk-models.git",
        "mirror_path": "vosk-model-small-en-us-0.15.zip",  # zip blob in repo root
    },
    "hi": {
        "name": "vosk-model-small-hi-0.22",
        "zip_url": "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip",
        "zip_sha256": HI_ZIP_SHA256,
        # Unpacked tree inside a GitHub repo (sparse checkout).
        "mirror_repo": "https://github.com/rajkishorbgp/JARVIS-AI-Assistant.git",
        "mirror_path": "vosk/vosk-model-small-hi-0.22",
        # Per-file manifest of the unpacked tree (sha256), pinned for the
        # mirror fallback so installation stays deterministic even without the
        # official zip. Cross-checked against the working model validated in
        # the AMAP feasibility investigation (4/4 Hindi command clips).
        "manifest": {
            "README": "9ffae7d857a7671a0a53b9f6f432e7c312459fde02ca1f139d808fffc3d2644a",
            "am/final.mdl": "c5d7ea51a074bc64430137a74fc8a0a06097df485a3d356cf37d2d78ef6bd712",
            "conf/mfcc.conf": "31dab8bb1dea9b33e039988ac079dfe5d50ebaa4a94826b9f9adc8fe84b147c6",
            "conf/model.conf": "d8d91d310a9659fed2d89f8ea4996af6163a43c3ab008cd278e4264120551712",
            "graph/Gr.fst": "9b219e22fc7d3033ba1b175757a700d8f02139d75d7f57cc12bc318d53038ccf",
            "graph/HCLr.fst": "4f36aad2566853473603abc66fac3985eff0860229c465540b348c22fcbbb4f5",
            "graph/disambig_tid.int": "3f87fd5a92742b3827d2da31dae0874c4077e9f0011e507423b6f876d743e37b",
            "graph/phones/word_boundary.int": "b8f981d84d8765fb15003ac54ec0f9599efa65a00d6d4d60086e5969ad45ff01",
            "ivector/final.dubm": "e495541a7e99e78a42cd098adfd94a72b6118a8c0d3c5ea8fe17436b578c55d4",
            "ivector/final.ie": "89d91ca6e99e7e4f067b3ef8ac1faa9ba73276c225d927aaa296492a03a639b7",
            "ivector/final.mat": "3009aea21b59ad36f86c89d68dd152264aa3a784260dbdace823d991f3ff71b4",
            "ivector/global_cmvn.stats": "a056b7592116d4a5e5fc6f872f8398190878bb6690bf486827fa79dabaf33f97",
            "ivector/online_cmvn.conf": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "ivector/splice.conf": "9f0c5f7c82d18eaf25d8bce470efa9f7741f88411fe428774bc0a9bb69a24756",
        },
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, dest: Path) -> bool:
    try:
        print(f"+ downloading {url}")
        with urllib.request.urlopen(url, timeout=300) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  download failed: {exc}")
        return False


def git_sparse_clone(repo: str, path: str, dest: Path) -> bool:
    """Sparse-clone exactly one path (file or tree) from a GitHub repo."""
    try:
        print(f"+ git sparse clone {repo} :: {path}")
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--filter=blob:none",
             "--no-checkout", repo, str(dest)],
            check=True,
        )
        subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone",
                        f"/{path}"], check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "--quiet"], check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  git clone failed: {exc}")
        return False


def already_installed(out_dir: Path, name: str, manifest: dict | None) -> bool:
    model_dir = out_dir / name
    if not model_dir.is_dir():
        return False
    if manifest is None:
        # zip-installed model: verify the two required structure dirs exist
        return (model_dir / "am").is_dir() and (model_dir / "conf").is_dir()
    # manifest-installed model: verify every pinned file
    for rel, expected in manifest.items():
        file_path = model_dir / rel
        if not file_path.is_file() or sha256_file(file_path) != expected:
            return False
    return True


def install_from_zip(zip_path: Path, out_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(out_dir)


def provision(language: str, spec: dict, out_dir: Path) -> None:
    name = spec["name"]
    if already_installed(out_dir, name, spec.get("manifest")):
        print(f"{language}: model already present and verified: {out_dir / name}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    # Path 1: official zip (normal networks).
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / f"{name}.zip"
        if download(spec["zip_url"], zip_path):
            digest = sha256_file(zip_path)
            if digest != spec["zip_sha256"]:
                print(f"  checksum mismatch for official zip ({digest}); aborting")
                sys.exit(1)
            install_from_zip(zip_path, out_dir)
            print(f"{language}: installed {name} from official zip (sha256 verified)")
            return
        # Path 2a: GitHub mirror zip blob (English).
        if "mirror_path" in spec and spec["mirror_path"].endswith(".zip"):
            repo_dir = tmp_path / "mirror"
            if git_sparse_clone(spec["mirror_repo"], spec["mirror_path"], repo_dir):
                mirror_zip = repo_dir / spec["mirror_path"]
                digest = sha256_file(mirror_zip)
                if digest != spec["zip_sha256"]:
                    print(f"  mirror zip checksum mismatch ({digest}); aborting")
                    sys.exit(1)
                install_from_zip(mirror_zip, out_dir)
                print(f"{language}: installed {name} from GitHub mirror zip (sha256 verified)")
                return
        # Path 2b: GitHub mirror unpacked tree with pinned manifest (Hindi).
        manifest = spec.get("manifest")
        if manifest:
            repo_dir = tmp_path / "mirror"
            if git_sparse_clone(spec["mirror_repo"], spec["mirror_path"], repo_dir):
                tree = repo_dir / spec["mirror_path"]
                ok = all(
                    (tree / rel).is_file() and sha256_file(tree / rel) == expected
                    for rel, expected in manifest.items()
                )
                found = sorted(str(p.relative_to(tree)) for p in tree.rglob("*") if p.is_file())
                ok = ok and found == sorted(manifest.keys())
                if not ok:
                    print("  mirror tree does not match the pinned manifest; aborting")
                    sys.exit(1)
                shutil.copytree(tree, out_dir / name)
                print(f"{language}: installed {name} from GitHub mirror tree (manifest verified)")
                return

    print(
        f"{language}: could not provision {name}. Install manually from "
        f"{spec['zip_url']} (sha256 {spec['zip_sha256']}) into {out_dir}."
    )
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=str(DEFAULT_OUT), help="models directory")
    args = parser.parse_args()
    out_dir = Path(args.dir)
    print(f"AMAP Vosk model provisioning -> {out_dir}")
    for language, spec in MODELS.items():
        provision(language, spec, out_dir)
    print("OK: all Vosk models ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

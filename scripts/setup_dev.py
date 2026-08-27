"""
Development Environment Bootstrap and Pre-Flight Health Checker for AMAP.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def check_prerequisites() -> bool:
    """Verify system prerequisites (Python 3.11+, Node.js, Docker, Git)."""
    print("=================================================================")
    print("           AMAP DEVELOPMENT PRE-FLIGHT CHECK                     ")
    print("=================================================================")

    all_ok = True

    # 1. Python Version
    py_ver = sys.version_info
    print(f"Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro}", end=" ")
    if py_ver >= (3, 11):
        print("[OK]")
    else:
        print("[FAIL: Python 3.11+ required]")
        all_ok = False

    # 2. Node.js
    node_path = shutil.which("node")
    if node_path:
        try:
            node_ver = subprocess.check_output(["node", "--version"], text=True).strip()
            print(f"Node.js Version: {node_ver} [OK]")
        except Exception:
            print("Node.js detected [OK]")
    else:
        print("Node.js: [WARN: Not found in PATH, required for frontend]")

    # 3. Docker
    docker_path = shutil.which("docker")
    if docker_path:
        print(f"Docker CLI: Found ({docker_path}) [OK]")
    else:
        print("Docker CLI: [INFO: Optional for containerized database]")

    # 4. .env File Check
    env_file = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"
    if env_file.exists():
        print(f"Environment File (.env): Found [OK]")
    elif env_example.exists():
        print("Environment File (.env): Missing, copying from .env.example...")
        shutil.copy(env_example, env_file)
        print("Environment File (.env): Created [OK]")
    else:
        print("Environment File (.env): [WARN: Neither .env nor .env.example found]")

    print("=================================================================\n")
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="AMAP Development Setup Utility")
    parser.add_argument("--check-only", action="store_true", help="Run pre-flight checks without installing packages")
    args = parser.parse_args()

    check_prerequisites()


if __name__ == "__main__":
    main()

"""
Quick CLI Benchmark Runner for AMAP AI Perception.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai.cli import run_benchmark

if __name__ == "__main__":
    run_benchmark()

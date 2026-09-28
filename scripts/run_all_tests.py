"""
Unified Automated Test Suite Runner for the Entire AMAP Platform.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_VENV_PYTEST = ROOT_DIR / "backend" / ".venv" / "Scripts" / "pytest.exe"
if not BACKEND_VENV_PYTEST.exists():
    BACKEND_VENV_PYTEST = ROOT_DIR / "backend" / ".venv" / "bin" / "pytest"
if not BACKEND_VENV_PYTEST.exists():
    BACKEND_VENV_PYTEST = "pytest"


def run_test_suite(suite_path: str, description: str) -> bool:
    """Run a specific pytest suite and return success status."""
    print(f"\n=================================================================")
    print(f"  RUNNING: {description}")
    print(f"=================================================================")

    cmd = [str(BACKEND_VENV_PYTEST), "-v", suite_path]
    t0 = time.perf_counter()
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    elapsed = time.perf_counter() - t0

    if res.returncode == 0:
        print(f"--> [PASS] {description} ({elapsed:.2f}s)")
        return True
    else:
        print(f"--> [FAIL] {description} ({elapsed:.2f}s)")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="AMAP Unified Test Runner")
    parser.add_argument("--fast", action="store_true", help="Skip heavy performance/stress tests")
    args = parser.parse_args()

    suites = [
        ("backend/tests/test_realtime_interaction_engine.py", "Real-Time Worker Interaction Engine (gestures/voice/fusion/sessions/supervisor)"),
        ("backend/tests/test_ai_subsystem.py", "AI Multimodal Perception & Personalization"),
        ("backend/tests/test_readiness_and_lifecycle.py", "Worker Readiness & Fresher vs. Existing Employee Lifecycle"),
        ("backend/tests/test_custom_gestures.py", "Worker Custom Gesture Pipeline & Isolation (§ 24-27)"),
        ("backend/tests/test_supervisor_module.py", "Supervisor & Operations Management Module (§ 30)"),
        ("backend/tests/test_organization_management.py", "Enterprise Organization Management & Tenant Governance (§ 1-38)"),
        ("tests/e2e/test_full_platform_e2e.py", "End-to-End Workflow & Governance Lifecycle"),
        ("tests/integration/test_multimodal_api_integration.py", "Cross-Modal API & Multi-Tenant Integration"),
        ("tests/security/test_security_governance.py", "Security, Cryptography & Safety Interlocks"),
    ]

    if not args.fast:
        suites.append(("tests/performance/test_platform_benchmarks.py", "Performance & Throughput Benchmarks"))

    total = len(suites) + 2  # + frontend engine tests + E2E worker journey
    passed = 0

    print("=================================================================")
    print(f"      AMAP PLATFORM TEST SUITE RUNNER ({total} SUITES)           ")
    print("=================================================================")

    for suite_path, desc in suites:
        if run_test_suite(suite_path, desc):
            passed += 1

    # Non-pytest suites: frontend gesture engine unit tests + E2E journey.
    print("\n=================================================================")
    print("  RUNNING: Frontend Gesture Engine Unit Tests (node)")
    print("=================================================================")
    t0 = time.perf_counter()
    res = subprocess.run(["node", "scripts/run-engine-tests.mjs"], cwd=str(ROOT_DIR / "frontend"))
    elapsed = time.perf_counter() - t0
    if res.returncode == 0:
        print(f"--> [PASS] Frontend Gesture Engine Unit Tests ({elapsed:.2f}s)")
        passed += 1
    else:
        print(f"--> [FAIL] Frontend Gesture Engine Unit Tests ({elapsed:.2f}s)")

    print("\n=================================================================")
    print("  RUNNING: E2E Worker Journey (real PostgreSQL, API-level)")
    print("=================================================================")
    t0 = time.perf_counter()
    res = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "e2e_worker_journey.py")],
        cwd=str(ROOT_DIR / "backend"),
    )
    elapsed = time.perf_counter() - t0
    if res.returncode == 0:
        print(f"--> [PASS] E2E Worker Journey ({elapsed:.2f}s)")
        passed += 1
    else:
        print(f"--> [FAIL] E2E Worker Journey ({elapsed:.2f}s)")

    print("\n=================================================================")
    if passed == total:
        print(f"      FINAL TEST SUMMARY: {passed}/{total} SUITES PASSED         ")
    else:
        print(f"      FINAL TEST SUMMARY: {passed}/{total} PASSED ({total - passed} FAILED)")
    print("=================================================================\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()

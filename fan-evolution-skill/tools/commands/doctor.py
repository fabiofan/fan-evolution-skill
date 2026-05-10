"""
doctor — Validate companion configuration and file integrity.

Checks:
- Config file exists and is valid JSON
- All required files exist
- Config fields are present and reasonable
- Automation directory structure is sound
- Python modules compile
"""

import os
import json
import subprocess

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, get_llm_client


REQUIRED_FILES = [
    "companion_config.json",
    "SOUL.md",
    "PRESENCE.md",
    "MEMORY.md",
    "WATCHLIST.md",
    "ACTIVE_PROJECTS.md",
]

REQUIRED_DIRS = [
    "AUTOMATION",
    "AUTOMATION/archive-packages",
]

REQUIRED_CONFIG_FIELDS = [
    "companion_name",
    "authorized_dirs",
    "protected_patterns",
    "reminder_policy",
]


def cmd_doctor(args, root):
    """Execute the doctor command."""
    print(f"[doctor] Checking companion workspace: {root}")
    print()

    issues = []
    warnings = []
    ok_count = 0

    # Check config
    config_path = os.path.join(root, "companion_config.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            ok_count += 1
            print(f"  ✓ companion_config.json — valid JSON")

            # Check required fields
            for field in REQUIRED_CONFIG_FIELDS:
                if field in config:
                    ok_count += 1
                else:
                    issues.append(f"Config missing field: {field}")

        except json.JSONDecodeError as e:
            issues.append(f"companion_config.json is invalid JSON: {e}")
    else:
        issues.append(f"companion_config.json not found at {config_path}")

    # Check required files
    for fname in REQUIRED_FILES:
        fpath = os.path.join(root, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            if size == 0:
                warnings.append(f"{fname} exists but is empty")
            else:
                ok_count += 1
                print(f"  ✓ {fname} ({size}B)")
        else:
            issues.append(f"Missing file: {fname}")

    # Check required directories
    for dname in REQUIRED_DIRS:
        dpath = os.path.join(root, dname)
        if os.path.isdir(dpath):
            ok_count += 1
            print(f"  ✓ {dname}/")
        else:
            issues.append(f"Missing directory: {dname}")

    # Check Python compilation
    tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    companion_py = os.path.join(tools_dir, "companion.py")
    if os.path.isfile(companion_py):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", companion_py],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok_count += 1
            print(f"  ✓ tools/companion.py compiles")
        else:
            issues.append(f"companion.py compilation error: {result.stderr}")
    else:
        warnings.append("tools/companion.py not found at expected location")

    # Check reminders.json validity
    reminders_path = os.path.join(root, "AUTOMATION", "reminders.json")
    if os.path.isfile(reminders_path):
        try:
            with open(reminders_path, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                ok_count += 1
                print(f"  ✓ AUTOMATION/reminders.json ({len(data)} entries)")
            else:
                warnings.append("reminders.json should be a JSON array")
        except json.JSONDecodeError:
            issues.append("AUTOMATION/reminders.json is invalid JSON")
    else:
        warnings.append("AUTOMATION/reminders.json not found (will be created on first use)")

    # LLM health check
    llm_client = get_llm_client(root)
    if llm_client:
        if llm_client.is_available():
            ok_count += 1
            print(f"  ✓ LLM configured ({llm_client.model})")
            # Optionally test connection (skip in doctor to avoid network dependency)
            api_key_env = llm_client.api_key_env
            if os.environ.get(api_key_env, ""):
                ok_count += 1
                print(f"  ✓ API key found in ${api_key_env}")
            else:
                warnings.append(f"LLM enabled but ${api_key_env} not set in environment")
        else:
            warnings.append("LLM enabled in config but not available (missing API key)")
    else:
        # LLM not configured — just informational
        print(f"  ℹ LLM not configured (optional)")

    # Summary
    print()
    print(f"{'─' * 40}")
    print(f"  Results: {ok_count} OK, {len(warnings)} warnings, {len(issues)} issues")
    print(f"{'─' * 40}")

    if warnings:
        print("\n  Warnings:")
        for w in warnings:
            print(f"    ⚠️  {w}")

    if issues:
        print("\n  Issues (need fixing):")
        for i in issues:
            print(f"    ❌ {i}")
        print()
        print("  Run `companion init` to fix missing files.")
        return 1

    print("\n  🎉 Companion workspace is healthy!")
    return 0

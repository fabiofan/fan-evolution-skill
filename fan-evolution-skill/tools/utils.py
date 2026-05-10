"""
Shared utilities for the companion engine.
"""

VERSION = "3.0.0"

import json
import os
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


def load_config(root):
    """Load companion_config.json from the root directory."""
    config_path = os.path.join(root, "companion_config.json")
    if not os.path.isfile(config_path):
        raise FileNotFoundError(
            f"Config not found: {config_path}\n"
            f"Run 'companion init' to create a workspace."
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(root, config):
    """Write companion_config.json to the root directory."""
    config_path = os.path.join(root, "companion_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def now_iso():
    """Return current time as ISO string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_local():
    """Return current local time as readable string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_id(prefix="mem"):
    """Generate a short unique ID based on timestamp + hash."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    h = hashlib.sha256(ts.encode()).hexdigest()[:6]
    return f"{prefix}-{ts}-{h}"


def is_protected(filepath, protected_patterns):
    """
    Check if a filepath matches any protected pattern.
    Protected patterns are glob-like strings checked against the path.
    """
    for pattern in protected_patterns:
        # Simple pattern matching: support * as wildcard
        regex = pattern.replace(".", r"\.").replace("*", ".*")
        if re.search(regex, filepath, re.IGNORECASE):
            return True
    return False


def read_markdown(filepath):
    """Read a markdown file, return content or empty string if missing."""
    if os.path.isfile(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def write_markdown(filepath, content):
    """Write content to a markdown file, creating dirs if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def append_markdown(filepath, content):
    """Append content to a markdown file, creating if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(content)


def load_json(filepath, default=None):
    """Load a JSON file, return default if missing."""
    if os.path.isfile(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(filepath, data):
    """Save data to a JSON file, creating dirs if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def hours_ago(hours):
    """Return a datetime object N hours in the past."""
    from datetime import timedelta
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def file_mtime_recent(filepath, since_dt):
    """Check if a file's mtime is more recent than since_dt."""
    mtime = os.path.getmtime(filepath)
    file_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return file_dt > since_dt


def truncate_lines(text, limit):
    """Truncate text to a max number of lines."""
    lines = text.split("\n")
    if len(lines) > limit:
        return "\n".join(lines[:limit]) + f"\n... ({len(lines) - limit} more lines)"
    return text


def ensure_dir(path):
    """Ensure a directory exists."""
    os.makedirs(path, exist_ok=True)
    return path


def get_llm_client(root):
    """Factory: create an LLMClient from companion config, or None if unavailable."""
    from llm import LLMClient
    try:
        config = load_config(root)
    except FileNotFoundError:
        return None
    llm_config = config.get("llm", {})
    if not llm_config.get("enabled", False):
        return None
    return LLMClient(config)

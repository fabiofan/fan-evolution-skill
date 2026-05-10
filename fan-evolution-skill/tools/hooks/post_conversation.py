#!/usr/bin/env python3
"""
post_conversation hook — Auto-trigger ingest after a Codex conversation ends.

Design:
  - Reads the most recent conversation file from the configured conversation_source
  - Calls ingest on that file
  - Intended to be called by Codex (or similar) at the end of each session

Usage:
  python3 tools/hooks/post_conversation.py --root <companion_root>
  python3 tools/hooks/post_conversation.py --root <root> --source <conversations_dir>

Configuration (companion_config.json):
  "hooks": {
    "post_conversation": true,
    "conversation_source": "~/.codex/conversations/"
  }
"""

import argparse
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, ensure_dir, now_iso
from commands.ingest import cmd_ingest


class MockArgs:
    """Minimal args for passing to ingest."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def find_latest_conversation(source_dir):
    """Find the most recent file in the conversation source directory."""
    if not os.path.isdir(source_dir):
        return None

    # Look for common conversation file patterns
    patterns = ["*.md", "*.txt", "*.json", "*.log"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(source_dir, pattern)))
        files.extend(glob.glob(os.path.join(source_dir, "**", pattern), recursive=True))

    if not files:
        return None

    # Sort by modification time, most recent first
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return files[0]


def run_hook(root, source_dir=None):
    """Execute the post-conversation hook."""
    config = load_config(root)

    # Determine source directory
    if source_dir is None:
        hooks_config = config.get("hooks", {})
        if not hooks_config.get("post_conversation", False):
            print("[hook] post_conversation hook is disabled in config.")
            return False
        source_dir = hooks_config.get("conversation_source", "~/.codex/conversations/")

    # Expand user path
    source_dir = os.path.expanduser(source_dir)

    if not os.path.isdir(source_dir):
        print(f"[hook] Conversation source not found: {source_dir}")
        return False

    # Find latest conversation
    latest = find_latest_conversation(source_dir)
    if not latest:
        print(f"[hook] No conversation files found in: {source_dir}")
        return False

    print(f"[hook] Found latest conversation: {latest}")

    # Call ingest
    ingest_args = MockArgs(text=None, file=latest)
    try:
        cmd_ingest(ingest_args, root)
        print(f"[hook] Successfully ingested: {os.path.basename(latest)}")
        return True
    except Exception as e:
        print(f"[hook] Ingest failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Post-conversation hook — auto-ingest latest Codex conversation"
    )
    parser.add_argument(
        "--root", "-r", required=True,
        help="Companion root directory"
    )
    parser.add_argument(
        "--source", "-s", default=None,
        help="Override conversation source directory"
    )
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    success = run_hook(root, source_dir=args.source)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

"""
ingest — Ingest conversation content into the companion system.

Accepts dialogue text via --text, --file, or stdin.
Stores conversations as timestamped markdown files in
AUTOMATION/conversations/ for later processing by digest.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import ensure_dir, write_markdown, now_iso, now_local


def format_conversation(text):
    """
    Format raw conversation text into structured markdown.
    Attempts to detect role markers (user:/companion:/assistant:/human:).
    If none found, stores as-is with a generic marker.
    """
    lines = text.strip().split("\n")
    formatted = []
    role_pattern_found = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted.append("")
            continue
        # Detect common role prefixes
        lower = stripped.lower()
        if lower.startswith(("user:", "human:", "我:", "用户:")):
            formatted.append(f"**user**: {stripped.split(':', 1)[1].strip()}")
            role_pattern_found = True
        elif lower.startswith(("companion:", "assistant:", "ai:", "kitty:")):
            formatted.append(f"**companion**: {stripped.split(':', 1)[1].strip()}")
            role_pattern_found = True
        else:
            formatted.append(stripped)

    if not role_pattern_found:
        # Wrap entire content as user input
        return f"**user**: {text.strip()}"

    return "\n".join(formatted)


def cmd_ingest(args, root):
    """Execute the ingest command."""
    # Determine input source
    text = None

    if args.text:
        text = args.text
    elif args.file:
        if not os.path.isfile(args.file):
            print(f"[ingest] Error: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("[ingest] Error: provide input via --text, --file, or stdin", file=sys.stderr)
        sys.exit(1)

    if not text or not text.strip():
        print("[ingest] Error: empty input", file=sys.stderr)
        sys.exit(1)

    # Create conversations directory
    conversations_dir = os.path.join(root, "AUTOMATION", "conversations")
    ensure_dir(conversations_dir)

    # Generate filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp}.md"
    filepath = os.path.join(conversations_dir, filename)

    # Format content
    formatted = format_conversation(text)

    # Build document
    content = f"""# Conversation — {now_local()}

Ingested: {now_iso()}

---

{formatted}

---
*Ingested by companion at {now_iso()}*
"""

    write_markdown(filepath, content)

    print(f"[ingest] Stored conversation: {filepath}")
    print(f"[ingest] Size: {len(text)} chars, {len(text.splitlines())} lines")
    print(f"[ingest] Will be processed by next `companion digest` run.")

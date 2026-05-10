"""
memory-rollback — Remove a memory block by ID from MEMORY.md.

Finds the block delimited by MEMORY_BLOCK comments with the given ID,
removes it, and logs the rollback.
"""

import os
import re

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, write_markdown, append_markdown,
    now_iso, now_local
)


def cmd_memory_rollback(args, root):
    """Execute the memory-rollback command."""
    config = load_config(root)
    target_id = args.id

    memory_path = os.path.join(root, "MEMORY.md")
    log_path = os.path.join(root, "AUTOMATION", "MEMORY_WRITEBACK_LOG.md")

    content = read_markdown(memory_path)
    if not content:
        print("[memory-rollback] MEMORY.md is empty or missing.")
        return

    # Find and remove the block
    # Pattern: <!-- MEMORY_BLOCK id=TARGET ... --> ... <!-- /MEMORY_BLOCK -->
    pattern = (
        r"\n*<!-- MEMORY_BLOCK id=" + re.escape(target_id) + r"[^>]*-->\n"
        r".*?"
        r"<!-- /MEMORY_BLOCK -->\n?"
    )

    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print(f"[memory-rollback] Block '{target_id}' not found in MEMORY.md")
        print("[memory-rollback] Available blocks:")
        # List available block IDs
        blocks = re.findall(r"<!-- MEMORY_BLOCK id=(\S+)", content)
        for b in blocks:
            print(f"  - {b}")
        return

    removed_text = match.group(0)
    new_content = content[:match.start()] + content[match.end():]
    write_markdown(memory_path, new_content)

    # Log the rollback
    log_entry = (
        f"\n## Rollback at {now_local()}\n\n"
        f"- Removed block: {target_id}\n"
        f"- Content was:\n```\n{removed_text.strip()}\n```\n\n"
    )
    append_markdown(log_path, log_entry)

    print(f"[memory-rollback] Removed block '{target_id}' from MEMORY.md")
    print(f"[memory-rollback] Rollback logged to: {log_path}")

"""
memory-recall — Recall blocks from cold storage back to MEMORY.md.

Usage:
  companion memory-recall --id <block_id>          Recall a specific block by ID
  companion memory-recall --search "keyword"       Search cold storage and recall matches

Recalled blocks are restored to MEMORY.md with tier=active and
reference_count reset to 0.
"""

import os
import re

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, write_markdown, append_markdown,
    now_iso, now_local
)
from commands.memory_decay import parse_memory_blocks, rebuild_full_block


def cmd_memory_recall(args, root):
    """Execute the memory-recall command."""
    config = load_config(root)

    archive_path = os.path.join(root, "AUTOMATION", "MEMORY_ARCHIVE.md")
    memory_path = os.path.join(root, "MEMORY.md")

    archive_content = read_markdown(archive_path)
    if not archive_content.strip():
        print("[memory-recall] Cold storage (MEMORY_ARCHIVE.md) is empty.")
        return

    blocks = parse_memory_blocks(archive_content)
    if not blocks:
        print("[memory-recall] No memory blocks found in cold storage.")
        return

    target_id = getattr(args, 'id', None)
    search_term = getattr(args, 'search', None)

    if not target_id and not search_term:
        # List available blocks in cold storage
        print(f"[memory-recall] Cold storage contains {len(blocks)} blocks:")
        print()
        for block in blocks:
            print(f"  {block['id']}: {block['content'][:70]}")
        print()
        print("[memory-recall] Use --id <id> or --search \"keyword\" to recall.")
        return

    # Find matching blocks
    matches = []
    if target_id:
        matches = [b for b in blocks if b["id"] == target_id]
        if not matches:
            print(f"[memory-recall] Block '{target_id}' not found in cold storage.")
            print(f"[memory-recall] Available: {', '.join(b['id'] for b in blocks[:5])}")
            return
    elif search_term:
        term_lower = search_term.lower()
        matches = [b for b in blocks if term_lower in b["content"].lower()]
        if not matches:
            print(f"[memory-recall] No blocks matching '{search_term}' in cold storage.")
            return
        print(f"[memory-recall] Found {len(matches)} matching block(s):")
        print()

    # Recall matched blocks
    recalled_blocks = []
    for block in matches:
        # Reset to active tier
        block["tier"] = "active"
        block["reference_count"] = 0
        block["last_referenced"] = now_iso().split("T")[0]
        recalled_text = rebuild_full_block(block)
        recalled_blocks.append((block, recalled_text))
        print(f"  ← recalled: {block['id']}: {block['content'][:60]}")

    # Append to MEMORY.md
    for block, text in recalled_blocks:
        append_markdown(memory_path, f"\n\n{text}\n")

    # Remove from archive
    updated_archive = archive_content
    for block, _ in recalled_blocks:
        updated_archive = updated_archive.replace(block["full_match"], "")

    # Clean up multiple blank lines
    updated_archive = re.sub(r"\n{4,}", "\n\n\n", updated_archive)
    write_markdown(archive_path, updated_archive)

    print(f"\n[memory-recall] Recalled {len(recalled_blocks)} block(s) to MEMORY.md")
    print(f"[memory-recall] Blocks restored with tier=active")

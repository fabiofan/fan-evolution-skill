"""
memory-apply — Apply confirmed memory proposals to MEMORY.md.

Reads MEMORY_WRITEBACK_PROPOSAL.md, applies pending proposals
as structured blocks in MEMORY.md. Each block has:
- ID, date, source, category, content
- Rollback marker for future removal

Supports --dry-run to preview without writing.
"""

import os
import re

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, write_markdown, append_markdown,
    now_iso, now_local, generate_id, load_json, save_json
)
from commands.memory_decay import determine_initial_tier

# Note: auto-confirm threshold (default 7) guarantees that auto-confirmed
# blocks always have score >= 7. Since fading requires score < 4, there is
# no scenario where an auto-confirmed block gets assigned fading tier.
# This invariant holds as long as auto_confirm_threshold >= 4.


def parse_proposals(content):
    """Parse pending proposals from MEMORY_WRITEBACK_PROPOSAL.md."""
    proposals = []
    current = None

    for line in content.split("\n"):
        line_stripped = line.strip()

        # Detect proposal header
        header_match = re.match(r"^###\s+Proposal\s+\d+:\s+(prop-\S+)", line_stripped)
        if header_match:
            if current:
                proposals.append(current)
            current = {"id": header_match.group(1), "category": "", "content": "", "score": 0, "status": ""}
            continue

        if current:
            cat_match = re.match(r"^-\s+\*\*Category\*\*:\s+(.+)$", line_stripped)
            if cat_match:
                current["category"] = cat_match.group(1)
                continue

            score_match = re.match(r"^-\s+\*\*Score\*\*:\s+(\d+)", line_stripped)
            if score_match:
                current["score"] = int(score_match.group(1))
                continue

            content_match = re.match(r"^-\s+\*\*Content\*\*:\s+(.+)$", line_stripped)
            if content_match:
                current["content"] = content_match.group(1)
                continue

            status_match = re.match(r"^-\s+\*\*Status\*\*:\s+(.+)$", line_stripped)
            if status_match:
                current["status"] = status_match.group(1)
                continue

    if current:
        proposals.append(current)

    return proposals


def cmd_memory_apply(args, root):
    """Execute the memory-apply command."""
    config = load_config(root)
    dry_run = args.dry_run
    target_id = getattr(args, 'id', None)
    auto_mode = getattr(args, 'auto', False)

    proposal_path = os.path.join(root, "AUTOMATION", "MEMORY_WRITEBACK_PROPOSAL.md")
    memory_path = os.path.join(root, "MEMORY.md")
    log_path = os.path.join(root, "AUTOMATION", "MEMORY_WRITEBACK_LOG.md")

    content = read_markdown(proposal_path)
    if not content.strip():
        print("[memory-apply] No proposal found. Run `companion curate` first.")
        return

    proposals = parse_proposals(content)
    pending = [p for p in proposals if p.get("status") == "pending"]

    if target_id:
        pending = [p for p in pending if p["id"] == target_id]

    # Auto-confirm mode: only apply proposals with score >= threshold
    if auto_mode:
        mem_gov = config.get("memory_governance", {})
        threshold = mem_gov.get("auto_confirm_threshold", 7)
        pending = [p for p in pending if p.get("score", 0) >= threshold]
        if not pending:
            print(f"[memory-apply] No proposals meet auto-confirm threshold ({threshold}).")
            return
        print(f"[memory-apply] Auto-confirm mode: threshold={threshold}, qualifying={len(pending)}")

    if not pending:
        print("[memory-apply] No pending proposals to apply.")
        return

    print(f"[memory-apply] {'DRY RUN \u2014 ' if dry_run else ''}Applying {len(pending)} proposals...")
    print()

    applied_blocks = []
    for p in pending:
        block_id = generate_id("mem")
        score = p.get("score", 0)
        category = p.get("category", "other")
        tier = determine_initial_tier(category, score)
        today = now_iso().split("T")[0]
        block = (
            f"\n\n<!-- MEMORY_BLOCK id={block_id} date={now_iso()} source={p['id']}"
            f" tier={tier} reference_count=0 last_referenced={today} score={score} -->\n"
            f"### [{p['category']}] {now_local()}\n\n"
            f"{p['content']}\n\n"
            f"<!-- /MEMORY_BLOCK -->\n"
        )
        applied_blocks.append({"id": block_id, "proposal_id": p["id"], "block": block, "auto": auto_mode, "tier": tier})
        print(f"  \u2713 {block_id} [{tier}] <- {p['id']}: {p['content'][:60]}")

    if dry_run:
        print(f"\n[memory-apply] DRY RUN complete. {len(applied_blocks)} blocks would be written.")
        print("[memory-apply] Remove --dry-run to apply.")
        return

    # Write to MEMORY.md
    for item in applied_blocks:
        append_markdown(memory_path, item["block"])

    # Log the writeback
    log_entry = f"\n## Writeback at {now_local()}\n\n"
    for item in applied_blocks:
        marker = " [auto-confirmed]" if item.get("auto") else ""
        log_entry += f"- Applied {item['id']} from proposal {item['proposal_id']}{marker}\n"
    log_entry += "\n"
    append_markdown(log_path, log_entry)

    # Update proposal status
    updated_content = content
    for p in pending:
        updated_content = updated_content.replace(
            f"- **Status**: pending",
            f"- **Status**: applied",
            1  # Replace one at a time
        )
    write_markdown(proposal_path, updated_content)

    print(f"\n[memory-apply] Applied {len(applied_blocks)} blocks to MEMORY.md")
    print(f"[memory-apply] Log updated: {log_path}")

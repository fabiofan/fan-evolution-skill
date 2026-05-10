"""
export — Export/backup all companion data.

Usage:
  companion export --format json       Export as single JSON file
  companion export --format markdown   Export as structured markdown
  companion export --restore <file>    Restore from exported file

Output: AUTOMATION/exports/export-YYYYMMDD.{json|md}
"""

import os
import re
import json
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, write_markdown,
    load_json, save_json, ensure_dir, now_local
)


def gather_export_data(root):
    """Gather all companion data into a structured dict."""
    config = load_config(root)

    data = {
        "export_date": now_local(),
        "config": config,
        "memory_blocks": [],
        "reminders": [],
        "timeline": "",
        "archives": [],
        "presence_rules": [],
        "soul": "",
        "watchlist": "",
        "active_projects": "",
    }

    # MEMORY.md blocks
    memory_content = read_markdown(os.path.join(root, "MEMORY.md"))
    data["memory_raw"] = memory_content

    # Parse memory blocks
    from commands.memory_decay import parse_memory_blocks
    blocks = parse_memory_blocks(memory_content)
    data["memory_blocks"] = [
        {
            "id": b["id"],
            "date": b["date"],
            "tier": b.get("tier", "active"),
            "reference_count": b.get("reference_count", 0),
            "last_referenced": b.get("last_referenced"),
            "score": b.get("score", 0),
            "category": b.get("category", "other"),
            "content": b["content"],
        }
        for b in blocks
    ]

    # Reminders
    reminders_path = os.path.join(root, "AUTOMATION", "reminders.json")
    data["reminders"] = load_json(reminders_path, default=[])

    # Timeline
    timeline_path = os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md")
    data["timeline"] = read_markdown(timeline_path)

    # Archives list
    archive_dir = os.path.join(root, "AUTOMATION", "archive-packages")
    if os.path.isdir(archive_dir):
        data["archives"] = sorted(os.listdir(archive_dir))

    # Presence rules
    rules_path = os.path.join(root, "AUTOMATION", "presence_rules.json")
    data["presence_rules"] = load_json(rules_path, default=[])

    # SOUL.md
    data["soul"] = read_markdown(os.path.join(root, "SOUL.md"))

    # WATCHLIST.md
    data["watchlist"] = read_markdown(os.path.join(root, "WATCHLIST.md"))

    # ACTIVE_PROJECTS.md
    data["active_projects"] = read_markdown(os.path.join(root, "ACTIVE_PROJECTS.md"))

    # Cold storage
    archive_memory = read_markdown(os.path.join(root, "AUTOMATION", "MEMORY_ARCHIVE.md"))
    data["cold_storage"] = archive_memory

    return data


def export_json(root, data):
    """Export data as JSON file."""
    export_dir = os.path.join(root, "AUTOMATION", "exports")
    ensure_dir(export_dir)
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = os.path.join(export_dir, f"export-{date_str}.json")
    save_json(filepath, data)
    return filepath


def export_markdown(root, data):
    """Export data as structured markdown file."""
    export_dir = os.path.join(root, "AUTOMATION", "exports")
    ensure_dir(export_dir)
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = os.path.join(export_dir, f"export-{date_str}.md")

    lines = [
        f"# Companion Export — {data['export_date']}",
        "",
        "---",
        "",
        "## Configuration",
        "",
        "```json",
        json.dumps(data["config"], indent=2, ensure_ascii=False),
        "```",
        "",
        "---",
        "",
        "## Memory Blocks",
        "",
        f"Total: {len(data['memory_blocks'])} blocks",
        "",
    ]

    for block in data["memory_blocks"]:
        lines.append(f"### {block['id']} [{block['tier']}] ({block['category']})")
        lines.append(f"- Date: {block['date']}")
        lines.append(f"- Score: {block['score']}, References: {block['reference_count']}")
        lines.append(f"- Content: {block['content'][:200]}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Reminders",
        "",
        f"Total: {len(data['reminders'])}",
        "",
    ])
    for r in data["reminders"]:
        if isinstance(r, dict):
            lines.append(f"- {r.get('text', r.get('content', str(r)))}")
        else:
            lines.append(f"- {r}")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## Timeline",
        "",
        data["timeline"][:2000] if data["timeline"] else "(empty)",
        "",
        "---",
        "",
        "## Archives",
        "",
        f"Total: {len(data['archives'])} files",
        "",
    ])
    for a in data["archives"][:20]:
        lines.append(f"- {a}")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## Presence Rules",
        "",
    ])
    for rule in data["presence_rules"]:
        if isinstance(rule, dict):
            lines.append(f"- [P{rule.get('priority', 3)}] {rule.get('text', '')}")
        else:
            lines.append(f"- {rule}")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## Soul",
        "",
        data["soul"][:1000] if data["soul"] else "(empty)",
        "",
        "---",
        "",
        "## Cold Storage",
        "",
        data["cold_storage"][:2000] if data["cold_storage"] else "(empty)",
        "",
    ])

    write_markdown(filepath, "\n".join(lines))
    return filepath


def restore_from_file(root, filepath):
    """Restore companion data from an exported JSON file.

    Supports both full exports and incremental exports.
    Incremental exports are identified by data["incremental"] == True.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Restore file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle incremental format: restore conversations with content
    if data.get("incremental") and data.get("conversations"):
        conversations_dir = os.path.join(root, "AUTOMATION", "conversations")
        ensure_dir(conversations_dir)
        for conv in data["conversations"]:
            if isinstance(conv, dict) and conv.get("filename") and conv.get("content"):
                conv_path = os.path.join(conversations_dir, conv["filename"])
                write_markdown(conv_path, conv["content"])

    # Restore MEMORY.md
    if data.get("memory_raw"):
        write_markdown(os.path.join(root, "MEMORY.md"), data["memory_raw"])

    # Restore reminders
    if data.get("reminders"):
        reminders_path = os.path.join(root, "AUTOMATION", "reminders.json")
        ensure_dir(os.path.dirname(reminders_path))
        save_json(reminders_path, data["reminders"])

    # Restore timeline
    if data.get("timeline"):
        timeline_path = os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md")
        write_markdown(timeline_path, data["timeline"])

    # Restore presence rules
    if data.get("presence_rules"):
        rules_path = os.path.join(root, "AUTOMATION", "presence_rules.json")
        ensure_dir(os.path.dirname(rules_path))
        save_json(rules_path, data["presence_rules"])

    # Restore SOUL.md
    if data.get("soul"):
        write_markdown(os.path.join(root, "SOUL.md"), data["soul"])

    # Restore WATCHLIST.md
    if data.get("watchlist"):
        write_markdown(os.path.join(root, "WATCHLIST.md"), data["watchlist"])

    # Restore ACTIVE_PROJECTS.md
    if data.get("active_projects"):
        write_markdown(os.path.join(root, "ACTIVE_PROJECTS.md"), data["active_projects"])

    # Restore cold storage
    if data.get("cold_storage"):
        archive_path = os.path.join(root, "AUTOMATION", "MEMORY_ARCHIVE.md")
        write_markdown(archive_path, data["cold_storage"])

    # Restore config
    if data.get("config"):
        config_path = os.path.join(root, "companion_config.json")
        save_json(config_path, data["config"])

    return data


def gather_incremental_data(root, last_export_dt):
    """Gather only data modified after last_export_dt."""
    config = load_config(root)

    data = {
        "export_date": now_local(),
        "incremental": True,
        "since": last_export_dt.isoformat(),
        "config": config,
        "memory_blocks": [],
        "reminders": [],
        "timeline": "",
        "archives": [],
        "conversations": [],
    }

    # Memory blocks: only those with date > last_export
    memory_content = read_markdown(os.path.join(root, "MEMORY.md"))
    from commands.memory_decay import parse_memory_blocks
    blocks = parse_memory_blocks(memory_content)
    for b in blocks:
        block_date_str = b.get("date", "")
        try:
            block_dt = datetime.strptime(block_date_str[:19], "%Y-%m-%dT%H:%M:%S")
            if block_dt > last_export_dt:
                data["memory_blocks"].append({
                    "id": b["id"],
                    "date": b["date"],
                    "tier": b.get("tier", "active"),
                    "reference_count": b.get("reference_count", 0),
                    "last_referenced": b.get("last_referenced"),
                    "score": b.get("score", 0),
                    "category": b.get("category", "other"),
                    "content": b["content"],
                })
        except (ValueError, TypeError):
            continue

    # Archives: only files with mtime > last_export
    archive_dir = os.path.join(root, "AUTOMATION", "archive-packages")
    if os.path.isdir(archive_dir):
        for fname in sorted(os.listdir(archive_dir)):
            fpath = os.path.join(archive_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime > last_export_dt:
                    data["archives"].append(fname)
            except OSError:
                continue

    # Conversations: only files with mtime > last_export (include content for restore)
    conversations_dir = os.path.join(root, "AUTOMATION", "conversations")
    if os.path.isdir(conversations_dir):
        for fname in sorted(os.listdir(conversations_dir)):
            fpath = os.path.join(conversations_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime > last_export_dt:
                    data["conversations"].append({
                        "filename": fname,
                        "content": read_markdown(fpath),
                    })
            except OSError:
                continue

    # Timeline: always full (append-only single file)
    timeline_path = os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md")
    data["timeline"] = read_markdown(timeline_path)

    # Reminders: full (small file)
    reminders_path = os.path.join(root, "AUTOMATION", "reminders.json")
    data["reminders"] = load_json(reminders_path, default=[])

    return data


def export_incremental(root, data):
    """Export incremental data as JSON."""
    export_dir = os.path.join(root, "AUTOMATION", "exports")
    ensure_dir(export_dir)
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = os.path.join(export_dir, f"export-{date_str}-incremental.json")
    save_json(filepath, data)
    return filepath


def read_last_export(root):
    """Read last export timestamp from .last_export file."""
    last_export_path = os.path.join(root, "AUTOMATION", "exports", ".last_export")
    if os.path.isfile(last_export_path):
        with open(last_export_path, "r", encoding="utf-8") as f:
            ts = f.read().strip()
        if ts:
            try:
                return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass
    return None


def write_last_export(root):
    """Write current timestamp to .last_export file."""
    export_dir = os.path.join(root, "AUTOMATION", "exports")
    ensure_dir(export_dir)
    last_export_path = os.path.join(export_dir, ".last_export")
    with open(last_export_path, "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))


def cmd_export(args, root):
    """Execute the export command."""
    restore_file = getattr(args, 'restore', None)
    incremental = getattr(args, 'incremental', False)

    if restore_file:
        # Restore mode
        print(f"[export] Restoring from: {restore_file}")
        data = restore_from_file(root, restore_file)
        print(f"[export] Restored companion data from {data.get('export_date', 'unknown')}")
        print(f"[export] Memory blocks: {len(data.get('memory_blocks', []))}")
        print(f"[export] Reminders: {len(data.get('reminders', []))}")
        print(f"[export] Root: {root}")
        return

    if incremental:
        # Incremental export mode
        last_export_dt = read_last_export(root)
        if last_export_dt is None:
            print("[export] No previous export found. Running full export instead.")
            incremental = False
        else:
            print(f"[export] Incremental export since: {last_export_dt.isoformat()}")
            data = gather_incremental_data(root, last_export_dt)
            filepath = export_incremental(root, data)
            write_last_export(root)
            print(f"[export] Memory blocks (new): {len(data['memory_blocks'])}")
            print(f"[export] Archives (new): {len(data['archives'])}")
            print(f"[export] Conversations (new): {len(data['conversations'])}")
            print(f"[export] Written to: {filepath}")
            return

    # Full export mode
    fmt = getattr(args, 'format', 'json') or 'json'
    print(f"[export] Gathering companion data...")
    data = gather_export_data(root)

    if fmt == "json":
        filepath = export_json(root, data)
    elif fmt == "markdown":
        filepath = export_markdown(root, data)
    else:
        print(f"[export] Unknown format: {fmt}. Use 'json' or 'markdown'.")
        return

    # Update last export timestamp
    write_last_export(root)

    print(f"[export] Format: {fmt}")
    print(f"[export] Memory blocks: {len(data['memory_blocks'])}")
    print(f"[export] Reminders: {len(data['reminders'])}")
    print(f"[export] Archives: {len(data['archives'])}")
    print(f"[export] Presence rules: {len(data['presence_rules'])}")
    print(f"[export] Written to: {filepath}")

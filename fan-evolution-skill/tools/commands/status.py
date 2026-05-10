"""
status — Output companion current state summary.

Quick overview: name, last activity, reminder counts, memory size,
archive count, and loop health.
"""

import os
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, load_json, read_markdown, now_local, VERSION, get_llm_client


def get_file_age(filepath):
    """Get human-readable age of a file."""
    if not os.path.isfile(filepath):
        return "never"
    mtime = os.path.getmtime(filepath)
    delta = datetime.now().timestamp() - mtime
    if delta < 60:
        return f"{int(delta)}s ago"
    elif delta < 3600:
        return f"{int(delta/60)}m ago"
    elif delta < 86400:
        return f"{int(delta/3600)}h ago"
    else:
        return f"{int(delta/86400)}d ago"


def get_soul_summary(root):
    """Get the first paragraph of SOUL.md as personality summary."""
    soul = read_markdown(os.path.join(root, "SOUL.md"))
    if not soul.strip():
        return None
    # Extract first non-header, non-empty paragraph
    lines = soul.split("\n")
    paragraph = []
    started = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("---"):
            if started:
                break
            continue
        if stripped:
            started = True
            paragraph.append(stripped)
        elif started:
            break
    return " ".join(paragraph) if paragraph else None


def cmd_status(args, root):
    """Execute the status command."""
    config = load_config(root)
    companion_name = config.get("companion_name", "companion")

    # Gather metrics
    reminders = load_json(os.path.join(root, "AUTOMATION", "reminders.json"), default=[])
    memory = read_markdown(os.path.join(root, "MEMORY.md"))
    watchlist = read_markdown(os.path.join(root, "WATCHLIST.md"))

    # Count archives
    archive_dir = os.path.join(root, "AUTOMATION", "archive-packages")
    archive_count = 0
    if os.path.isdir(archive_dir):
        archive_count = len([f for f in os.listdir(archive_dir) if f.endswith(".md")])

    # Reminder stats
    waiting = len([r for r in reminders if r.get("status") == "waiting"])
    done = len([r for r in reminders if r.get("status") == "done"])

    # Memory block count
    memory_blocks = memory.count("<!-- MEMORY_BLOCK")

    # Watchlist items
    watchlist_items = watchlist.count("- [")

    # Last activity timestamps
    snapshot_age = get_file_age(os.path.join(root, "AUTOMATION", "ENVIRONMENT_SNAPSHOT.md"))
    draft_age = get_file_age(os.path.join(root, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md"))
    feedback_age = get_file_age(os.path.join(root, "AUTOMATION", "ACTION_FEEDBACK.md"))

    # Get soul summary
    soul_summary = get_soul_summary(root)

    # Output
    print(f"┌{'─' * 50}┐")
    print(f"│  {companion_name} — Status Report (v{VERSION})")
    print(f"│  {now_local()}")
    print(f"├{'─' * 50}┤")
    if soul_summary:
        # Truncate soul summary to fit display
        summary_display = soul_summary[:70] + ("..." if len(soul_summary) > 70 else "")
        print(f"│")
        print(f"│  🎭 Personality: {summary_display}")
    print(f"│")
    print(f"│  📋 Reminders:  {len(reminders)} total ({waiting} waiting, {done} done)")
    print(f"│  🧠 Memory:     {memory_blocks} blocks")
    print(f"│  📦 Archives:   {archive_count} packages")
    print(f"│  👁  Watchlist:  {watchlist_items} items")
    print(f"│")
    print(f"│  Last Sense:     {snapshot_age}")
    print(f"│  Last Reflect:   {draft_age}")
    print(f"│  Last Feedback:  {feedback_age}")
    print(f"│")
    print(f"│  Authorized dirs: {len(config.get('authorized_dirs', []))}")
    print(f"│  Protected patterns: {len(config.get('protected_patterns', []))}")
    print(f"│")
    # LLM status
    llm_client = get_llm_client(root)
    if llm_client:
        print(f"│  🤖 {llm_client.status_summary()}")
    else:
        print(f"│  🤖 LLM: disabled")
    print(f"│")
    print(f"└{'─' * 50}┘")

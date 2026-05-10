"""
watchlist — Read WATCHLIST.md, sync due items to reminders.

The watchlist contains future concerns with optional due dates.
When --sync-reminders is used, items with dates that are now due
get promoted to the reminders system.
"""

import os
import re
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, read_markdown, load_json, save_json, now_local


def parse_watchlist(content):
    """
    Parse WATCHLIST.md entries.
    Expected format:
      - [ ] Item description [due: YYYY-MM-DD] [priority: must|gentle|inbox]
      - [x] Completed item
    """
    items = []
    for line in content.split("\n"):
        line = line.strip()
        # Match checkbox items
        m = re.match(r"^-\s*\[([ x])\]\s*(.+)$", line)
        if not m:
            continue
        done = m.group(1) == "x"
        text = m.group(2)

        # Extract due date
        due_match = re.search(r"\[due:\s*(\d{4}-\d{2}-\d{2})\]", text)
        due = due_match.group(1) if due_match else None

        # Extract priority
        pri_match = re.search(r"\[priority:\s*(must|gentle|inbox)\]", text)
        priority = pri_match.group(1) if pri_match else "inbox"

        # Clean text
        clean_text = re.sub(r"\[due:\s*\d{4}-\d{2}-\d{2}\]", "", text)
        clean_text = re.sub(r"\[priority:\s*(?:must|gentle|inbox)\]", "", clean_text).strip()

        items.append({
            "text": clean_text,
            "done": done,
            "due": due,
            "priority": priority,
            "raw": line,
        })
    return items


def cmd_watchlist(args, root):
    """Execute the watchlist command."""
    config = load_config(root)
    watchlist_path = os.path.join(root, "WATCHLIST.md")
    content = read_markdown(watchlist_path)

    if not content.strip():
        print("[watchlist] WATCHLIST.md is empty or missing.")
        print(f"[watchlist] Expected at: {watchlist_path}")
        return

    items = parse_watchlist(content)
    today = datetime.now().strftime("%Y-%m-%d")

    pending = [i for i in items if not i["done"]]
    due_now = [i for i in pending if i["due"] and i["due"] <= today]
    future = [i for i in pending if not i["due"] or i["due"] > today]

    print(f"[watchlist] Total items: {len(items)}")
    print(f"[watchlist] Pending: {len(pending)}, Due now: {len(due_now)}, Future: {len(future)}")
    print()

    if due_now:
        print("## Due Now")
        for item in due_now:
            print(f"  [{item['priority']}] {item['text']} (due: {item['due']})")
        print()

    if future:
        print("## Upcoming")
        for item in future[:10]:
            due_str = f" (due: {item['due']})" if item['due'] else ""
            print(f"  [{item['priority']}] {item['text']}{due_str}")

    # Sync to reminders if requested
    if args.sync_reminders and due_now:
        reminders_path = os.path.join(root, "AUTOMATION", "reminders.json")
        reminders = load_json(reminders_path, default=[])

        existing_texts = {r.get("text", "") for r in reminders}
        added = 0

        for item in due_now:
            if item["text"] not in existing_texts:
                reminders.append({
                    "text": item["text"],
                    "priority": item["priority"],
                    "due": item["due"],
                    "status": "waiting",
                    "source": "watchlist",
                    "synced_at": now_local(),
                })
                added += 1

        save_json(reminders_path, reminders)
        print(f"\n[watchlist] Synced {added} items to reminders.json")

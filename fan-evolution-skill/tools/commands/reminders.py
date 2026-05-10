"""
reminders — Manage the reminder list (must/gentle/inbox tiers).

Reads AUTOMATION/reminders.json, filters by status and priority,
outputs currently actionable items.
"""

import os
import json
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, load_json, save_json, now_local, generate_id


def cmd_reminders(args, root):
    """Execute the reminders command."""
    config = load_config(root)
    reminders_path = os.path.join(root, "AUTOMATION", "reminders.json")
    reminders = load_json(reminders_path, default=[])

    # Add a new reminder if --add is provided
    if args.add:
        try:
            new_item = json.loads(args.add)
        except json.JSONDecodeError:
            # Treat as plain text
            new_item = {"text": args.add}

        reminder = {
            "id": generate_id("rem"),
            "text": new_item.get("text", args.add),
            "priority": new_item.get("priority", "inbox"),
            "due": new_item.get("due", None),
            "status": "waiting",
            "created_at": now_local(),
            "source": "manual",
        }
        reminders.append(reminder)
        save_json(reminders_path, reminders)
        print(f"[reminders] Added: {reminder['text']} [{reminder['priority']}]")
        return

    # Display current reminders
    today = datetime.now().strftime("%Y-%m-%d")
    waiting = [r for r in reminders if r.get("status") == "waiting"]
    due_now = [r for r in waiting if not r.get("due") or r["due"] <= today]

    # Group by priority
    must = [r for r in due_now if r.get("priority") == "must"]
    gentle = [r for r in due_now if r.get("priority") == "gentle"]
    inbox = [r for r in due_now if r.get("priority") == "inbox"]

    print(f"[reminders] Total: {len(reminders)}, Waiting: {len(waiting)}, Due now: {len(due_now)}")
    print()

    if args.notify:
        # Output only actionable items for notification
        if must:
            print("🔴 MUST (interrupt-worthy):")
            for r in must:
                print(f"  • {r['text']}")
            print()
        if gentle:
            print("🟡 GENTLE (next natural pause):")
            for r in gentle:
                print(f"  • {r['text']}")
            print()
        if inbox:
            print("📥 INBOX (when convenient):")
            for r in inbox:
                print(f"  • {r['text']}")
        if not (must or gentle or inbox):
            print("  (No reminders due right now)")
    else:
        # Full listing
        print("## All Reminders")
        for r in reminders:
            status_icon = {
                "waiting": "⏳",
                "done": "✅",
                "snoozed": "😴",
                "blocked": "🚫",
                "ignored": "⚪",
            }.get(r.get("status", "waiting"), "?")
            due_str = f" due:{r['due']}" if r.get("due") else ""
            print(f"  {status_icon} [{r.get('priority', '?')}] {r.get('text', '?')}{due_str} — {r.get('status', '?')}")

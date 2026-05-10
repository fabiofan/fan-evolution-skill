"""
feedback — Check reminder execution status.

Reads reminders.json and action_feedback.json, reports on:
- waiting: not yet acted on
- done: completed
- snoozed: postponed
- blocked: cannot proceed
- ignored: no action taken after due date

Produces ACTION_FEEDBACK.md summary.
"""

import os
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, load_json, save_json, write_markdown,
    now_local, now_iso
)


def cmd_feedback(args, root):
    """Execute the feedback command."""
    config = load_config(root)
    reminders_path = os.path.join(root, "AUTOMATION", "reminders.json")
    feedback_path = os.path.join(root, "AUTOMATION", "ACTION_FEEDBACK.md")

    reminders = load_json(reminders_path, default=[])
    today = datetime.now().strftime("%Y-%m-%d")

    # Classify reminders by status
    status_groups = {
        "waiting": [],
        "done": [],
        "snoozed": [],
        "blocked": [],
        "ignored": [],
    }

    for r in reminders:
        status = r.get("status", "waiting")
        if status in status_groups:
            status_groups[status].append(r)
        else:
            status_groups["waiting"].append(r)

    # Check for overdue waiting items (due date passed, still waiting)
    overdue = []
    for r in status_groups["waiting"]:
        if r.get("due") and r["due"] < today:
            overdue.append(r)

    # Build feedback report
    lines = [
        "# Action Feedback Report",
        "",
        f"Generated: {now_local()}",
        f"Total reminders: {len(reminders)}",
        "",
        "---",
        "",
        f"## Status Summary",
        "",
        f"| Status | Count |",
        f"|--------|-------|",
    ]

    for status, items in status_groups.items():
        icon = {"waiting": "⏳", "done": "✅", "snoozed": "😴",
                "blocked": "🚫", "ignored": "⚪"}.get(status, "?")
        lines.append(f"| {icon} {status} | {len(items)} |")

    lines.extend(["", ""])

    if overdue:
        lines.extend([
            f"## ⚠️ Overdue ({len(overdue)} items)",
            "",
        ])
        for r in overdue:
            lines.append(f"- [{r.get('priority', '?')}] {r.get('text', '?')} (due: {r.get('due', '?')})")
        lines.append("")

    if status_groups["done"]:
        lines.extend([
            f"## ✅ Completed ({len(status_groups['done'])} items)",
            "",
        ])
        for r in status_groups["done"][-5:]:  # Last 5
            lines.append(f"- {r.get('text', '?')}")
        lines.append("")

    if status_groups["blocked"]:
        lines.extend([
            f"## 🚫 Blocked ({len(status_groups['blocked'])} items)",
            "",
        ])
        for r in status_groups["blocked"]:
            lines.append(f"- {r.get('text', '?')}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Feedback report by companion at {now_iso()}*")

    report = "\n".join(lines)
    write_markdown(feedback_path, report)

    # Console output
    print(f"[feedback] Reminders: {len(reminders)} total")
    print(f"  ⏳ waiting: {len(status_groups['waiting'])}")
    print(f"  ✅ done: {len(status_groups['done'])}")
    print(f"  😴 snoozed: {len(status_groups['snoozed'])}")
    print(f"  🚫 blocked: {len(status_groups['blocked'])}")
    print(f"  ⚪ ignored: {len(status_groups['ignored'])}")
    if overdue:
        print(f"  ⚠️  OVERDUE: {len(overdue)}")
    print(f"[feedback] Report written to: {feedback_path}")

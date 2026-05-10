"""
timeline — Generate relationship timeline entries.

Scans recent archives, memory writebacks, and feedback for
relationship-significant events. Appends to RELATIONSHIP_TIMELINE.md.

Timeline entries capture how the companion and user changed together:
trust moments, shared accomplishments, emotional exchanges, growth.
"""

import os
import re
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, append_markdown, write_markdown,
    now_iso, now_local
)


# Signals that indicate relationship-significant content
RELATIONSHIP_SIGNALS = [
    (r"(?i)(thank|grateful|appreciate)", "gratitude"),
    (r"(谢谢|感谢|感恩|辛苦了)", "gratitude"),
    (r"(?i)(trust|rely|depend|count on)", "trust"),
    (r"(信任|靠你|依赖|放心)", "trust"),
    (r"(?i)(together|we did|our|helped me)", "collaboration"),
    (r"(一起|我们|帮我|配合)", "collaboration"),
    (r"(?i)(first time|milestone|achievement)", "milestone"),
    (r"(第一次|突破|做到了)", "milestone"),
    (r"(?i)(sorry|apolog|my bad|mistake)", "repair"),
    (r"(对不起|抱歉|我错了)", "repair"),
    (r"(?i)(miss|wish|hope|look forward)", "anticipation"),
    (r"(期待|想念|下次|以后)", "anticipation"),
    (r"(?i)(remember when|last time|before)", "continuity"),
    (r"(上次|之前|还记得)", "continuity"),
]


def extract_timeline_events(content, source_name):
    """Extract relationship-relevant events from content."""
    events = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        if len(line) < 15:
            continue

        for pattern, event_type in RELATIONSHIP_SIGNALS:
            if re.search(pattern, line):
                events.append({
                    "text": line[:200],
                    "type": event_type,
                    "source": source_name,
                })
                break

    return events


def cmd_timeline(args, root):
    """Execute the timeline command."""
    config = load_config(root)
    hours = args.hours
    limit = args.limit
    companion_name = config.get("companion_name", "companion")

    timeline_path = os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md")
    archive_dir = os.path.join(root, "AUTOMATION", "archive-packages")

    cutoff = datetime.now() - timedelta(hours=hours)
    all_events = []

    # Scan recent archives
    if os.path.isdir(archive_dir):
        for fname in sorted(os.listdir(archive_dir), reverse=True):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(archive_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    continue
            except OSError:
                continue
            content = read_markdown(fpath)
            events = extract_timeline_events(content, fname)
            all_events.extend(events)

    # Scan recent memory
    memory = read_markdown(os.path.join(root, "MEMORY.md"))
    if memory:
        mem_events = extract_timeline_events(memory, "MEMORY")
        all_events.extend(mem_events)

    # Deduplicate
    seen = set()
    unique_events = []
    for e in all_events:
        key = e["text"][:40].lower()
        if key not in seen:
            seen.add(key)
            unique_events.append(e)

    unique_events = unique_events[:limit]

    if not unique_events:
        print(f"[timeline] No relationship events found in last {hours}h.")
        return

    # Build timeline entry
    entry_lines = [
        f"\n## {now_local()} — Daily Timeline Entry",
        f"",
        f"Events detected: {len(unique_events)}",
        f"",
    ]

    type_counts = {}
    for e in unique_events:
        t = e["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
        entry_lines.append(f"- **{t}**: {e['text'][:100]}")

    entry_lines.extend([
        "",
        f"Summary: " + ", ".join(f"{k}({v})" for k, v in sorted(type_counts.items())),
        "",
        "---",
        "",
    ])

    entry_content = "\n".join(entry_lines)

    # Ensure file exists with header
    if not os.path.isfile(timeline_path):
        write_markdown(timeline_path,
            f"# Relationship Timeline — {companion_name}\n\n"
            f"Daily record of how we grow together.\n\n---\n"
        )

    append_markdown(timeline_path, entry_content)

    print(f"[timeline] Found {len(unique_events)} relationship events")
    for t, c in sorted(type_counts.items()):
        print(f"  {t}: {c}")
    print(f"[timeline] Appended to: {timeline_path}")

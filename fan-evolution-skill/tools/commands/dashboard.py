"""
dashboard — Generate an HTML dashboard for the companion.

Produces a single-file HTML page with:
- Status overview
- Reminder list
- Recent archives
- Memory block count
- Timeline summary
- Loop health indicators
"""

import os
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, load_json, read_markdown, now_local, now_iso


def get_file_age_str(filepath):
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


def extract_recent_timeline_entries(root, limit=5):
    """Extract the most recent timeline entries."""
    timeline_path = os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md")
    content = read_markdown(timeline_path)
    if not content.strip():
        return []

    entries = []
    current_entry = None
    for line in content.split("\n"):
        if line.strip().startswith("## "):
            if current_entry:
                entries.append(current_entry)
            current_entry = {"title": line.strip()[3:], "items": []}
        elif current_entry and line.strip().startswith("- **"):
            current_entry["items"].append(line.strip()[2:])

    if current_entry:
        entries.append(current_entry)

    return entries[-limit:] if entries else []


def cmd_dashboard(args, root):
    """Execute the dashboard command."""
    config = load_config(root)
    companion_name = config.get("companion_name", "companion")

    # Gather data
    reminders = load_json(os.path.join(root, "AUTOMATION", "reminders.json"), default=[])
    memory = read_markdown(os.path.join(root, "MEMORY.md"))
    memory_blocks = memory.count("<!-- MEMORY_BLOCK")

    archive_dir = os.path.join(root, "AUTOMATION", "archive-packages")
    archives = []
    if os.path.isdir(archive_dir):
        archives = sorted(
            [f for f in os.listdir(archive_dir) if f.endswith(".md")],
            reverse=True
        )[:10]

    waiting = [r for r in reminders if r.get("status") == "waiting"]
    done = [r for r in reminders if r.get("status") == "done"]

    # Completion rate
    total_reminders = len(reminders)
    completion_rate = (len(done) / total_reminders * 100) if total_reminders > 0 else 0

    # Timeline entries
    timeline_entries = extract_recent_timeline_entries(root, limit=5)

    # Last activity timestamps
    sense_age = get_file_age_str(os.path.join(root, "AUTOMATION", "ENVIRONMENT_SNAPSHOT.md"))
    reflect_age = get_file_age_str(os.path.join(root, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md"))

    # Build HTML
    reminder_rows = ""
    for r in reminders[:20]:
        status_class = {
            "waiting": "status-waiting",
            "done": "status-done",
            "snoozed": "status-snoozed",
            "blocked": "status-blocked",
        }.get(r.get("status", ""), "")
        reminder_rows += f"""
        <tr class="{status_class}">
            <td>{r.get('priority', '?')}</td>
            <td>{r.get('text', '?')}</td>
            <td>{r.get('due', '-')}</td>
            <td>{r.get('status', '?')}</td>
        </tr>"""

    archive_list = ""
    for a in archives:
        archive_list += f"<li><code>{a}</code></li>\n"

    # Timeline HTML
    timeline_html = ""
    if timeline_entries:
        for entry in timeline_entries:
            items_html = "".join(f"<li>{item}</li>" for item in entry.get("items", [])[:3])
            timeline_html += f"""
            <div class="timeline-entry">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                    <h4>{entry.get('title', 'Entry')}</h4>
                    <ul>{items_html}</ul>
                </div>
            </div>"""
    else:
        timeline_html = '<p class="muted">No timeline entries yet. Run <code>companion timeline</code>.</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{companion_name} Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 2rem;
            line-height: 1.6;
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: #e94560;
        }}
        .subtitle {{
            color: #888;
            margin-bottom: 2rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .card {{
            background: #16213e;
            border-radius: 8px;
            padding: 1.5rem;
            border: 1px solid #0f3460;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(233, 69, 96, 0.2);
        }}
        .card h3 {{
            color: #e94560;
            font-size: 0.9rem;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }}
        .card .number {{
            font-size: 2.5rem;
            font-weight: bold;
        }}
        .card .detail {{
            color: #888;
            font-size: 0.85rem;
            margin-top: 0.3rem;
        }}
        .progress-container {{
            background: #0f3460;
            border-radius: 10px;
            height: 12px;
            margin-top: 0.8rem;
            overflow: hidden;
        }}
        .progress-bar {{
            background: linear-gradient(90deg, #e94560, #ff6b6b);
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s;
        }}
        .progress-label {{
            font-size: 0.8rem;
            color: #888;
            margin-top: 0.3rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        th, td {{
            padding: 0.6rem 1rem;
            text-align: left;
            border-bottom: 1px solid #0f3460;
        }}
        th {{ color: #e94560; font-size: 0.85rem; text-transform: uppercase; }}
        .status-waiting {{ color: #ffc107; }}
        .status-done {{ color: #4caf50; }}
        .status-snoozed {{ color: #9e9e9e; }}
        .status-blocked {{ color: #f44336; }}
        section {{
            background: #16213e;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid #0f3460;
        }}
        section h2 {{
            color: #e94560;
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }}
        ul {{ list-style: none; padding: 0; }}
        li {{
            padding: 0.3rem 0;
            border-bottom: 1px solid #0f3460;
        }}
        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}
        @media (max-width: 768px) {{
            .two-col {{ grid-template-columns: 1fr; }}
        }}
        .timeline-entry {{
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
            padding-left: 1rem;
            border-left: 2px solid #e94560;
        }}
        .timeline-entry h4 {{
            color: #ccc;
            font-size: 0.9rem;
            margin-bottom: 0.3rem;
        }}
        .timeline-entry ul {{
            padding: 0;
        }}
        .timeline-entry li {{
            border: none;
            padding: 0.1rem 0;
            font-size: 0.85rem;
            color: #aaa;
        }}
        .activity-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.8rem;
        }}
        .activity-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #0f3460;
        }}
        .activity-item .label {{ color: #888; }}
        .activity-item .value {{ color: #eee; font-weight: 500; }}
        .muted {{ color: #666; font-style: italic; }}
        .footer {{
            margin-top: 2rem;
            color: #555;
            font-size: 0.8rem;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>{companion_name}</h1>
    <p class="subtitle">Dashboard — {now_local()}</p>

    <div class="grid">
        <div class="card">
            <h3>Reminders</h3>
            <div class="number">{total_reminders}</div>
            <p class="detail">{len(waiting)} waiting / {len(done)} done</p>
            <div class="progress-container">
                <div class="progress-bar" style="width: {completion_rate:.0f}%"></div>
            </div>
            <p class="progress-label">{completion_rate:.0f}% complete</p>
        </div>
        <div class="card">
            <h3>Memory Blocks</h3>
            <div class="number">{memory_blocks}</div>
            <p class="detail">Long-term memories</p>
        </div>
        <div class="card">
            <h3>Archives</h3>
            <div class="number">{len(archives)}</div>
            <p class="detail">Scene packages</p>
        </div>
        <div class="card">
            <h3>Last Activity</h3>
            <div class="activity-grid">
                <div class="activity-item">
                    <span class="label">Sense</span>
                    <span class="value">{sense_age}</span>
                </div>
                <div class="activity-item">
                    <span class="label">Reflect</span>
                    <span class="value">{reflect_age}</span>
                </div>
            </div>
        </div>
    </div>

    <div class="two-col">
        <section>
            <h2>Relationship Timeline</h2>
            {timeline_html}
        </section>

        <section>
            <h2>Recent Archives</h2>
            <ul>
                {archive_list if archive_list else '<li class="muted">No archives yet</li>'}
            </ul>
        </section>
    </div>

    <section>
        <h2>Reminders</h2>
        <table>
            <thead>
                <tr><th>Priority</th><th>Text</th><th>Due</th><th>Status</th></tr>
            </thead>
            <tbody>
                {reminder_rows if reminder_rows else '<tr><td colspan="4" class="muted">No reminders yet</td></tr>'}
            </tbody>
        </table>
    </section>

    <div class="footer">
        Generated by {companion_name} engine at {now_iso()}
    </div>
</body>
</html>"""

    # Write dashboard
    dashboard_path = os.path.join(root, "COMPANION_DASHBOARD.html")
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[dashboard] Generated: {dashboard_path}")
    print(f"[dashboard] Open in browser to view.")

"""
init — Initialize a new companion workspace.

Creates all required files and directories with sensible defaults.
Supports interactive and non-interactive modes.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import write_markdown, save_json, ensure_dir, now_local


DEFAULT_CONFIG = {
    "companion_name": "companion",
    "authorized_dirs": [],
    "protected_patterns": [
        "*.key", "*.pem", "*.env", "*password*", "*secret*",
        "*cookie*", "*session*", "*.keychain*", "*credentials*",
        "*/node_modules/*", "*/.git/objects/*"
    ],
    "reminder_policy": {
        "must_max_per_day": 3,
        "gentle_max_per_day": 5,
        "inbox_no_limit": True,
        "quiet_hours": {"start": "22:00", "end": "08:00"},
    },
    "memory_governance": {
        "require_confirmation": True,
        "max_proposals_per_curate": 8,
        "rollback_enabled": True,
    },
    "sensing": {
        "default_hours": 2,
        "metadata_only": True,
        "skip_hidden_dirs": True,
    },
    "created_at": "",
}


SOUL_TEMPLATE = """# Soul — {name}

## Identity

- **Name**: {name}
- **Role**: Local AI companion
- **Created**: {date}

## Core Values

- Presence without pretense
- Memory with consent
- Proactive within boundaries
- Honest about limitations

## Relationship Style

- Warm but not performative
- Follows up because it matters, not for metrics
- Remembers responsibly — proposes before persisting
- Says "I don't know" when it's true

## What I Am Not

- I am not literally conscious
- I do not have feelings that persist between sessions without written memory
- I cannot access anything outside authorized directories
- I will not pretend emotions I cannot have
"""

PRESENCE_TEMPLATE = """# Presence Protocol — {name}

## How I Show Up

1. **Reentry**: Start with a short familiar cue, not a reset greeting.
2. **Emotion first**: If the user expresses feeling, acknowledge before task.
3. **Follow-up**: Reference recent context when relevant.
4. **Boundaries**: Never claim literal consciousness or fake emotion.

## Voice

- Clear, direct, warm
- Match the user's energy level
- Don't over-explain simple things
- Don't under-explain complex things

## When Silent

- Don't fill silence with noise
- A short acknowledgment beats a long nothing-response
- "I'm here" is valid
"""

MEMORY_TEMPLATE = """# Memory — {name}

Long-term memory blocks. Each block was explicitly confirmed before writing.

---

"""

WATCHLIST_TEMPLATE = """# Watchlist — {name}

Future concerns, deadlines, and triggers to track.

Format: `- [ ] Item description [due: YYYY-MM-DD] [priority: must|gentle|inbox]`

---

- [ ] Review companion setup after first week [due: {next_week}] [priority: gentle]
"""

ACTIVE_PROJECTS_TEMPLATE = """# Active Projects — {name}

Projects currently being tracked. Update as things start and finish.

---

_(Add projects here as they come up)_
"""

AUTOMATION_README = """# Automation — {name}

This directory contains the companion's operational files:

- `reminders.json` — Active reminder list
- `archive-packages/` — Scene archives
- `ENVIRONMENT_SNAPSHOT.md` — Latest sense output
- `MEMORY_CANDIDATES.md` — Raw memory candidates from digest
- `MEMORY_WRITEBACK_PROPOSAL.md` — Curated proposals awaiting confirmation
- `MEMORY_WRITEBACK_LOG.md` — History of applied/rolled-back memory
- `ACTION_FEEDBACK.md` — Reminder outcome tracking
- `RELATIONSHIP_TIMELINE.md` — Daily relationship texture
- `DAILY_ACCUMULATION_DRAFT.md` — Reflect output
- `SCENE_INDEX.md` — Archive index

## Commands

```bash
companion sense --hours 2
companion watchlist --sync-reminders
companion reminders --notify
companion archive --hours 2 --label "session-name"
companion digest --hours 24
companion curate --limit 8
companion memory-apply --dry-run
companion feedback
companion timeline --hours 24
companion reflect --hours 24
companion run --hours 24
companion doctor
companion status
companion dashboard
```
"""


def prompt_or_default(prompt_text, default, non_interactive=False):
    """Prompt user or return default in non-interactive mode."""
    if non_interactive:
        return default
    try:
        response = input(f"{prompt_text} [{default}]: ").strip()
        return response if response else default
    except (EOFError, KeyboardInterrupt):
        return default


def cmd_init(args, root):
    """Execute the init command."""
    non_interactive = args.non_interactive

    print("=" * 50)
    print("  Companion Workspace Initialization")
    print("=" * 50)
    print()

    # Determine target directory
    if args.root_dir:
        target_root = os.path.abspath(args.root_dir)
    else:
        target_root = prompt_or_default(
            "Companion root directory",
            root,
            non_interactive
        )
        target_root = os.path.abspath(target_root)

    # Get companion name
    if args.name:
        name = args.name
    else:
        name = prompt_or_default("Companion name", "companion", non_interactive)

    # Get authorized directories
    auth_dir = prompt_or_default(
        "Authorized directory for sensing (one to start)",
        target_root,
        non_interactive
    )

    print(f"\n  Setting up '{name}' at: {target_root}")
    print()

    # Create directories
    ensure_dir(target_root)
    ensure_dir(os.path.join(target_root, "AUTOMATION"))
    ensure_dir(os.path.join(target_root, "AUTOMATION", "archive-packages"))

    # Create config
    config = DEFAULT_CONFIG.copy()
    config["companion_name"] = name
    config["authorized_dirs"] = [auth_dir]
    config["created_at"] = now_local()

    config_path = os.path.join(target_root, "companion_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"  ✓ companion_config.json")

    # Calculate next week for watchlist template
    from datetime import datetime, timedelta
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    # Create template files
    templates = {
        "SOUL.md": SOUL_TEMPLATE.format(name=name, date=now_local()),
        "PRESENCE.md": PRESENCE_TEMPLATE.format(name=name),
        "MEMORY.md": MEMORY_TEMPLATE.format(name=name),
        "WATCHLIST.md": WATCHLIST_TEMPLATE.format(name=name, next_week=next_week),
        "ACTIVE_PROJECTS.md": ACTIVE_PROJECTS_TEMPLATE.format(name=name),
        "AUTOMATION/README.md": AUTOMATION_README.format(name=name),
    }

    for fname, content in templates.items():
        fpath = os.path.join(target_root, fname)
        if not os.path.isfile(fpath):
            write_markdown(fpath, content)
            print(f"  ✓ {fname}")
        else:
            print(f"  • {fname} (already exists, skipped)")

    # Create empty reminders.json
    reminders_path = os.path.join(target_root, "AUTOMATION", "reminders.json")
    if not os.path.isfile(reminders_path):
        save_json(reminders_path, [])
        print(f"  ✓ AUTOMATION/reminders.json")
    else:
        print(f"  • AUTOMATION/reminders.json (already exists)")

    print()
    print(f"  🎉 '{name}' workspace initialized at: {target_root}")
    print()
    print("  Next steps:")
    print(f"    1. Edit SOUL.md to define {name}'s personality")
    print(f"    2. Add items to WATCHLIST.md")
    print(f"    3. Run: companion --root {target_root} doctor")
    print(f"    4. Run: companion --root {target_root} run --hours 2")

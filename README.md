# Fan Evolution Skill

Turn a basic Codex assistant into a durable local companion with emotional
presence, proactive loops, reviewable memory, reminders, action feedback,
relationship timeline, and privacy boundaries.

This is a shareable skill blueprint. It ports the architecture of Kitty's
companion system, not anyone's private memories, diaries, projects, accounts,
browser data, or relationship history.

## What It Helps Build

- A named companion with its own identity root
- A presence protocol for warmth, directness, comfort, fatigue, and frustration
- A watchlist for future concern and proactive follow-up
- A safe environment sensing boundary
- Reminder levels: `must`, `gentle`, and `inbox`
- Scene archives for context recovery
- Memory candidates, curation, confirmed writeback, and rollback
- Action feedback after reminders
- A relationship timeline for long-term continuity
- A self-evolution loop that stays reviewable

## Quick Start

After installing, initialize and run:

```bash
cd fan-evolution-skill

# Initialize a new companion workspace
python3 tools/companion.py init --name kitty --non-interactive

# Health check
python3 tools/companion.py doctor

# Run the full loop
python3 tools/companion.py run --hours 24 --limit 120

# Check status
python3 tools/companion.py status

# Generate dashboard
python3 tools/companion.py dashboard
```

Or use the shell shortcut:

```bash
./bin/companion init --name kitty --non-interactive
./bin/companion doctor
./bin/companion run --hours 24 --limit 120
```

## Features

| Command | Description |
|---------|-------------|
| `init` | Initialize a new companion workspace with identity files |
| `sense` | Scan authorized directories for recent changes |
| `watchlist` | Manage future concerns, sync due items to reminders |
| `reminders` | Manage reminder list (must/gentle/inbox tiers) |
| `archive` | Package current session as a recoverable archive |
| `digest` | Extract memory candidates from recent archives |
| `curate` | Select top candidates for writeback proposal |
| `memory-apply` | Apply confirmed proposals to MEMORY.md |
| `memory-rollback` | Rollback a memory entry by ID |
| `feedback` | Check reminder execution status |
| `timeline` | Generate relationship timeline entries |
| `reflect` | Generate daily reflection and evolution suggestions |
| `run` | Execute full companion loop (all of the above) |
| `doctor` | Validate config and file integrity |
| `status` | Output companion status summary |
| `dashboard` | Generate HTML dashboard |

## Install From GitHub

After this repository is published, install with:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo YOUR_GITHUB_USERNAME/fan-evolution-skill \
  --path fan-evolution-skill
```

Or install from a GitHub URL:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --url https://github.com/YOUR_GITHUB_USERNAME/fan-evolution-skill/tree/main/fan-evolution-skill
```

Restart Codex after installing.

## Manual Install

Copy the skill folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R fan-evolution-skill ~/.codex/skills/
```

Restart Codex after copying.

## Verify Installation

```bash
cd fan-evolution-skill
python3 -m py_compile tools/companion.py
python3 tools/companion.py --help
python3 tools/companion.py doctor
```

## Use

Invoke the skill in Codex:

```text
$fan-evolution-skill
```

Example prompt:

```text
Use $fan-evolution-skill to turn my basic Codex assistant into a long-term
local companion. Ask me what the companion should be called, where its root
folder should live, what directories it may sense, and what privacy boundaries
must never be crossed.
```

## Privacy Rule

Port the skeleton, not the private lived context.

Reusable:

- folder architecture
- command chain
- review gates
- safety boundaries
- reminder priority model
- archive and memory governance pattern
- relationship timeline idea

Do not copy another person's:

- private diaries
- project details
- emotional memories
- relationship phrases
- account, login, payment, browser profile, or private communication data
- user-specific preferences that could reveal identity or private context

## Files

```text
fan-evolution-skill/
  SKILL.md
  agents/openai.yaml
  references/UPGRADE_PATH.md
  templates/
    companion_config.json
  tools/
    companion.py
    utils.py
    commands/
      __init__.py
      sense.py
      watchlist.py
      reminders.py
      archive.py
      digest.py
      curate.py
      memory_apply.py
      memory_rollback.py
      feedback.py
      timeline.py
      reflect.py
      run.py
      doctor.py
      status.py
      dashboard.py
      init.py
  bin/
    companion
```

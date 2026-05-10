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

## Install From GitHub

Install with:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo fabiofan/fan-evolution-skill \
  --path fan-evolution-skill
```

Or install from a GitHub URL:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --url https://github.com/fabiofan/fan-evolution-skill/tree/main/fan-evolution-skill
```

If Python reports a local SSL certificate error, use git mode:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo fabiofan/fan-evolution-skill \
  --path fan-evolution-skill \
  --method git
```

Restart Codex after installing.

## Manual Install

Copy the skill folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R fan-evolution-skill ~/.codex/skills/
```

Restart Codex after copying.

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
```

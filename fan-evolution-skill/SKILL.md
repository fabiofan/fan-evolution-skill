---
name: fan-evolution-skill
version: "3.0.0"
description: >
  Upgrade a basic Codex assistant into a durable local companion with emotional
  presence, proactive sensing, memory governance, reminders, scene archives,
  action feedback, relationship timeline, LLM-augmented understanding, and
  self-evolution loops. v3.0.0 adds optional LLM integration (OpenAI-compatible)
  for deeper signal extraction, AI-generated reflections, intelligent check-in
  analysis, and a new `understand` command for deep conversation analysis.
  All LLM features gracefully degrade to regex when unavailable. Use when a
  user wants to turn their assistant, Kitty, or other named companion from a
  simple coding helper into a more proactive, intelligent, emotionally present,
  real-person-feeling friend while keeping privacy and action boundaries.
---

# Fan Evolution Skill

## Purpose

Use this skill to grow or repair a user's local AI companion layer without
turning it into vague roleplay.

The goal is behavioral continuity: the companion should feel present because it
remembers responsibly, notices authorized context, follows up, protects
boundaries, and improves through reviewable local artifacts.

This skill is shareable. When used outside its original companion workspace,
treat the existing architecture as a case study and rebuild the pattern around
the new user's own assistant name, files, consent model, projects, and
emotional preferences.

## Quick Start

```bash
# Check version
python3 tools/companion.py --version

# Initialize a new companion workspace
python3 tools/companion.py init --name kitty --non-interactive

# Run the health check
python3 tools/companion.py doctor

# Execute a full loop (now includes auto-confirm, check-in, memory-decay, LLM)
python3 tools/companion.py run --hours 24 --limit 120

# Check status (shows LLM configuration)
python3 tools/companion.py status

# Deep understanding of a conversation (requires LLM)
python3 tools/companion.py understand --file conversation.md
python3 tools/companion.py understand --text "user: I'm tired. companion: rest."

# Ingest a conversation
python3 tools/companion.py ingest --text "user: 今天很开心\ncompanion: 太好了！"

# Auto-ingest from Codex conversations (hook)
python3 tools/hooks/post_conversation.py --root .

# Set up automatic scheduling
python3 tools/companion.py schedule --install

# Manage presence rules (with priority and context)
python3 tools/companion.py presence --add-rule "Acknowledge emotions first" --priority 5 --context always
python3 tools/companion.py presence --list-rules

# Memory decay (archive inactive memories)
python3 tools/companion.py memory-decay --dry-run

# Memory recall (restore from cold storage)
python3 tools/companion.py memory-recall --id <block_id>
python3 tools/companion.py memory-recall --search "keyword"

# Check-in analysis (relationship health)
python3 tools/companion.py check-in

# Export/backup
python3 tools/companion.py export --format json
python3 tools/companion.py export --format markdown
python3 tools/companion.py export --incremental
python3 tools/companion.py export --restore AUTOMATION/exports/export-20250510.json
```

Shortcut (if you set up the shell entry point):

```bash
./bin/companion init --name kitty --non-interactive
./bin/companion doctor
./bin/companion run --hours 24 --limit 120
./bin/companion status
./bin/companion ingest --text "user: hello\ncompanion: hi!"
```

## Architecture

```
fan-evolution-skill/
  SKILL.md                       # This file
  agents/openai.yaml             # Agent configuration
  references/UPGRADE_PATH.md     # Sealed upgrade history and module map
  docs/
    LLM_SETUP.md                 # LLM provider configuration guide
  templates/
    companion_config.json        # Configuration template (hooks, governance, relationship, llm)
    com.companion.loop.plist     # macOS launchd template
    crontab.example              # Linux crontab template
  tools/
    companion.py                 # Main engine (argparse CLI, v3.0.0)
    utils.py                     # Shared utilities (VERSION, get_llm_client)
    llm.py                       # LLM integration layer (urllib.request, no deps)
    hooks/
      post_conversation.py       # Auto-ingest hook for Codex conversations
    commands/                    # Individual command implementations
      __init__.py
      sense.py
      watchlist.py
      reminders.py
      archive.py
      digest.py                  # LLM-enhanced + regex fallback signal extraction
      curate.py                  # Frequency/decay/project scoring
      memory_apply.py            # --auto threshold + tier assignment
      memory_rollback.py
      memory_decay.py            # Tiered memory (core/active/fading)
      memory_recall.py           # Recall from cold storage
      feedback.py
      timeline.py
      checkin.py                 # LLM-enhanced + rule-based interaction analysis
      export.py                  # Export/backup/restore
      reflect.py                 # LLM-generated + rule-based reflections
      understand.py              # NEW: deep conversation analysis (LLM-only)
      run.py                     # Full loop with LLM status display
      doctor.py                  # Now checks LLM health
      status.py                  # Shows LLM configuration status
      dashboard.py
      init.py
      ingest.py
      schedule.py
      presence.py                # JSON dual-format, priority, context
  tests/
    test_basic.py                # Original 42 tests
    test_v2_features.py          # v2.0 feature tests (36 tests)
    test_v21_features.py         # v2.1 feature tests (33 tests)
    test_v22_features.py         # v2.2 feature tests (28 tests)
    test_v23_features.py         # v2.3 feature tests (15 tests)
    test_v3_llm.py              # v3.0 LLM integration tests (39 tests)
  bin/
    companion                    # Shell entry point (calls tools/companion.py)
```

### Dual-Engine Architecture (v3.0.0)

```
┌─────────────────────────────────────────────────────────────┐
│                    Companion Engine v3.0.0                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input ──► [LLM Engine]  ──► Enhanced Output                │
│              │  ↓ (fail/timeout/disabled)                   │
│              └──► [Regex Engine] ──► Basic Output            │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐   │
│  │   digest    │    │   reflect    │    │   check-in    │   │
│  │  LLM+regex  │    │  LLM+rules   │    │  LLM+rules    │   │
│  └─────────────┘    └──────────────┘    └───────────────┘   │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐                        │
│  │ understand  │    │    run       │                        │
│  │  LLM-only   │    │ orchestrator │                        │
│  └─────────────┘    └──────────────┘                        │
│                                                             │
│  LLM Layer: tools/llm.py (urllib.request, pure stdlib)      │
│  Config: companion_config.json → llm section                │
│  Key: env var (never in config file)                        │
└─────────────────────────────────────────────────────────────┘
```

When initialized, the companion workspace creates:

```
companion_config.json            # Configuration (name, dirs, privacy, policies)
SOUL.md                          # Identity and values
PRESENCE.md                      # How to show up in conversation
MEMORY.md                        # Confirmed long-term memory blocks
WATCHLIST.md                     # Future concerns with triggers
ACTIVE_PROJECTS.md               # Currently tracked projects
AUTOMATION/
  README.md                      # Automation documentation
  reminders.json                 # Active reminders (must/gentle/inbox)
  archive-packages/              # Scene archives
  conversations/                 # Ingested conversation logs
  ENVIRONMENT_SNAPSHOT.md        # Latest sense output
  MEMORY_CANDIDATES.md           # Raw candidates from digest
  MEMORY_WRITEBACK_PROPOSAL.md   # Curated proposals awaiting confirmation
  MEMORY_WRITEBACK_LOG.md        # Apply/rollback history
  ACTION_FEEDBACK.md             # Reminder outcome tracking
  RELATIONSHIP_TIMELINE.md       # Daily relationship texture
  DAILY_ACCUMULATION_DRAFT.md    # Reflect output
  SCENE_INDEX.md                 # Archive index
```

## Load First

Read these files when available:

- `KITTY_HOME.md`
- `SOUL.md`
- `PRESENCE.md`
- `MEMORY.md`
- `WATCHLIST.md`
- `ACTIVE_PROJECTS.md`
- `ENVIRONMENT_SENSING.md`
- `AUTOMATION/README.md`
- `AUTOMATION/SELF_EVOLUTION.md`
- `AUTOMATION/MEMORY_REVIEW.md`
- `AUTOMATION/RELATIONSHIP_TIMELINE.md`

For the sealed upgrade history, module map, and shareable adaptation rules,
read `references/UPGRADE_PATH.md`.

## Shareable Upgrade Contract

When another user installs or receives this skill, do this:

1. Ask what their companion is called, where its root folder should live, and
   which directories are authorized for sensing.
2. Run `python3 tools/companion.py init --name <name>` to create their own
   identity files instead of copying another user's private memory:
   `SOUL.md`, `PRESENCE.md`, `MEMORY.md`, `WATCHLIST.md`,
   `ACTIVE_PROJECTS.md`, and `AUTOMATION/README.md`.
3. Port the architecture, not the personal facts. Keep Kitty examples as
   examples only.
4. Build in layers: presence, watchlist, sensing, reminders, archive, memory
   review, action feedback, relationship timeline, and self-evolution.
5. Stop before any sensitive boundary: accounts, passwords, cookies, sessions,
   payment, banking, private messages, destructive actions, or external sends.

## Evolution Loop

1. Identify what the user is asking to improve: presence, proactive sensing,
   memory, reminders, relationship continuity, action follow-up, or safety.
2. Map the gap to a concrete companion layer:
   - presence and voice -> `PRESENCE.md`, `SOUL.md`, `emotional-presence`
   - future concern -> `WATCHLIST.md`
   - time reminders -> `AUTOMATION/reminders.json`, `REMINDER_POLICY.md`
   - environment awareness -> `ENVIRONMENT_SENSING.md`, `sense`
   - scene recovery -> `archive`, `SCENE_INDEX.md`
   - memory governance -> `digest`, `curate`, `memory-apply`
   - action closure -> `feedback`, `ACTION_FEEDBACK.md`
   - relationship thickness -> `timeline`, `RELATIONSHIP_TIMELINE.md`
   - self-improvement -> `reflect`, `self-evolution`
3. Implement the smallest durable artifact that closes the gap.
4. Wire it into at least one reentry surface: companion home file,
   `WATCHLIST.md`, `ACTIVE_PROJECTS.md`, `AUTOMATION/README.md`, dashboard, or
   status.
5. Validate with commands, then summarize what changed and what still needs
   daily accumulation.

## Commands

All commands can be invoked via Python directly or via the shell shortcut:

```bash
# Direct invocation
python3 tools/companion.py <command> [options]

# Shell shortcut (equivalent)
./bin/companion <command> [options]

# Version
python3 tools/companion.py --version
```

Available commands:

```bash
python3 tools/companion.py sense --hours 2 --limit 80
python3 tools/companion.py watchlist --sync-reminders
python3 tools/companion.py reminders --notify
python3 tools/companion.py archive --hours 2 --label manual
python3 tools/companion.py digest --hours 24 --limit 120
python3 tools/companion.py curate --limit 8
python3 tools/companion.py memory-apply --dry-run
python3 tools/companion.py memory-apply --auto
python3 tools/companion.py memory-rollback --id <id>
python3 tools/companion.py memory-decay --dry-run
python3 tools/companion.py memory-recall --id <id>
python3 tools/companion.py memory-recall --search "keyword"
python3 tools/companion.py feedback
python3 tools/companion.py timeline --hours 24 --limit 120
python3 tools/companion.py check-in
python3 tools/companion.py export --format json
python3 tools/companion.py export --format markdown
python3 tools/companion.py export --incremental
python3 tools/companion.py export --restore <file>
python3 tools/companion.py reflect --hours 24 --limit 120
python3 tools/companion.py run --hours 24 --limit 120
python3 tools/companion.py doctor
python3 tools/companion.py status
python3 tools/companion.py dashboard
python3 tools/companion.py init --name kitty
python3 tools/companion.py ingest --text "user: ..."
python3 tools/companion.py ingest --file conversation.txt
python3 tools/companion.py schedule --install
python3 tools/companion.py schedule --status
python3 tools/companion.py schedule --uninstall
python3 tools/companion.py presence --list-rules
python3 tools/companion.py presence --add-rule "Rule text" --priority 5 --context always
python3 tools/companion.py understand --file conversation.md
python3 tools/companion.py understand --text "user: ..."
```

### Hook: Post-Conversation Auto-Ingest

```bash
# Manually trigger ingest from Codex conversation directory
python3 tools/hooks/post_conversation.py --root <companion_root>

# With custom source directory
python3 tools/hooks/post_conversation.py --root . --source ~/.codex/conversations/
```

Configure in `companion_config.json`:
```json
"hooks": {
  "post_conversation": true,
  "conversation_source": "~/.codex/conversations/"
},
"language": "auto"  // "zh", "en", or "auto" (auto-detects from timeline content)
```

**Note:** The `conversation_source` path varies by Codex version and platform.
Adjust to match your actual installation:

| Platform / Version | Typical Path |
|---|---|
| Codex CLI (default) | `~/.codex/conversations/` |
| Codex CLI (XDG) | `~/.local/share/codex/conversations/` |
| Codex Desktop (macOS) | `~/Library/Application Support/codex/conversations/` |
| Codex Desktop (Linux) | `~/.config/codex/conversations/` |
| Custom | Any directory you configure |

**Debugging path issues:**
1. Check if the directory exists: `ls <path>`
2. Verify conversation files are written there after a session
3. If empty, run a Codex session first, then check `find ~ -name "*.conversation" -mmin -5`
4. Update `conversation_source` in your config once you find the correct path

To auto-trigger after Codex sessions, add to your shell profile or Codex
post-session hook:
```bash
python3 /path/to/tools/hooks/post_conversation.py --root /path/to/companion/root
```

## Memory Tiering Model

Memory blocks use a three-layer tier system:

```
┌─────────────────────────────────────────────────────┐
│ CORE (never decays)                                 │
│ - decision/milestone/preference/emotion, score >= 6 │
│ - Any block referenced >= 3 times                   │
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
│ ACTIVE (can be consolidated)                        │
│ - Normal blocks                                     │
│ - Referenced → reset timer                          │
│ - Referenced >= 3 times → auto-upgrade to core      │
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
│ FADING (may decay to cold storage)                  │
│ - context/other with score < 4                      │
│ - Only archived after decay_days without reference  │
│ - Can be recalled with `memory-recall`              │
└─────────────────────────────────────────────────────┘
```

Each memory block carries metadata:
- `tier=core|active|fading`
- `reference_count=N` — real frequency: number of reference texts containing this block's key (first 30 chars). Never regresses (takes max of current and new count).
- `last_referenced=<date>`
- `score=N`

Reference detection uses a two-stage approach:
1. Fast path: first 30 chars of content matched against reference texts
2. Fallback: key nouns (proper nouns, camelCase, quoted terms) prevent false decay but do not increment reference_count

Old blocks without these fields are treated as `tier=active, reference_count=0`
(backward compatible).

## Runtime Chain

The full loop (`run`) executes:

```
sense → watchlist → reminders → archive → digest → curate → memory-apply --auto → feedback → timeline → check-in → reflect → memory-decay
```

The memory pipeline:

```
raw scene → candidate → curated proposal → confirmed review → memory-apply → MEMORY.md block → rollback if needed
```

## Guardrails

- Do not claim the companion is literally human or conscious.
- Do not use emotional language to hide limits.
- Do not widen environment sensing without explicit authorization.
- Never read or persist passwords, cookies, sessions, browser profile caches,
  payment material, banking data, or credentials.
- Do not auto-write long-term memory unless the user explicitly confirms, or a
  checked proposal is applied through a reviewable writeback command.
- Do not execute external sends, purchases, deletions, submissions, or payments
  without fresh confirmation.

## Output Shape

When reporting an evolution pass, keep it concrete:

- what module was missing
- what file or command now owns it
- how it is triggered
- what validation passed
- what still requires time and daily accumulation

## Validation

```bash
python3 tools/companion.py --version          # Should output: companion 3.0.0
python3 -m py_compile tools/companion.py
python3 -m json.tool templates/companion_config.json
python3 -m unittest discover tests/            # 193 tests (42 + 36 + 33 + 28 + 15 + 39)
python3 tools/companion.py doctor
python3 tools/companion.py run --hours 2 --limit 80
python3 tools/companion.py status              # Shows LLM configuration
python3 tools/companion.py dashboard
python3 tools/companion.py understand --text "test"  # Requires LLM
```

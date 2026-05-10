# Fan Evolution Skill

> v3.0.0 — LLM Dual-Engine Architecture

Turn a basic Codex assistant into a durable local companion with persistent memory, emotional presence, proactive relationship loops, LLM-enhanced understanding, and privacy boundaries.

**Zero external dependencies.** Pure Python 3 standard library. 193 unit tests. 25 CLI commands.

---

## What It Does

| Capability | Description |
|-----------|-------------|
| 🧠 **Persistent Memory** | Three-layer tiering (core / active / fading). Important things never decay. |
| 🤖 **LLM-Enhanced Understanding** | Optional AI-powered signal extraction, reflection, and relationship analysis. Falls back to regex when offline. |
| 💬 **Deep Conversation Analysis** | `understand` command reads a conversation and outputs emotional trajectory, implicit needs, and relationship dynamics. |
| ⏰ **Proactive Loops** | Auto-scheduled (macOS launchd / Linux cron). Companion runs in the background every 2 hours. |
| 🔒 **Privacy First** | 11 protected patterns. All data stays on your local disk. Fully auditable, rollback-able. |
| 📊 **Relationship Timeline** | Tracks trust signals, milestones, gratitude, and repair moments across conversations. |
| 📦 **Export & Migrate** | Full + incremental backup. Your memory is portable — switch LLM providers without losing anything. |

---

## Demo

### `companion doctor` — Health Check
```
[doctor] Checking companion workspace...

  ✓ companion_config.json — valid JSON
  ✓ SOUL.md (662B)
  ✓ PRESENCE.md (589B)
  ✓ MEMORY.md (103B)
  ✓ WATCHLIST.md (245B)
  ✓ AUTOMATION/
  ✓ tools/companion.py compiles
  ✓ AUTOMATION/reminders.json (0 entries)
  ℹ LLM not configured (optional)

────────────────────────────────────────
  Results: 15 OK, 0 warnings, 0 issues
────────────────────────────────────────
  🎉 Companion workspace is healthy!
```

### `companion status` — At a Glance
```
┌──────────────────────────────────────────────────┐
│  Kitty — Status Report (v3.0.0)
│  2026-05-10 14:42:45
├──────────────────────────────────────────────────┤
│
│  📋 Reminders:  3 total (1 waiting, 2 done)
│  🧠 Memory:     12 blocks (4 core, 6 active, 2 fading)
│  📦 Archives:   7 packages
│  👁  Watchlist:  2 items
│
│  Last Sense:     2 hours ago
│  Last Reflect:   2 hours ago
│  Last Feedback:  2 hours ago
│
│  🤖 LLM: enabled (gpt-4o-mini via api.openai.com)
│
└──────────────────────────────────────────────────┘
```

### `companion run` — Full Loop
```
============================================================
  COMPANION LOOP — 24h window, limit 120
  LLM: enabled (gpt-4o-mini)
============================================================

  ✓ sense         — 12 modified files, 3 git commits
  ✓ watchlist     — 1 due now → synced to reminders
  ✓ archive       — arc-20260510-a23ed5
  ✓ digest        — 4 candidates extracted [LLM-powered]
  ✓ curate        — top 2 scored for writeback
  ✓ memory-apply  — 2 blocks auto-confirmed (score ≥ 7)
  ✓ feedback      — 1 reminder done, 1 waiting
  ✓ timeline      — 2 relationship events detected
  ✓ check-in      — interaction healthy, no action needed
  ✓ reflect       — daily reflection generated [AI-generated]
  ✓ memory-decay  — 1 block fading → cold storage

============================================================
  LOOP COMPLETE — 12 steps, 0 errors
============================================================
```

---

## Quick Start

```bash
git clone https://github.com/fabiofan/fan-evolution-skill.git
cd fan-evolution-skill/fan-evolution-skill

python3 tools/companion.py init          # Interactive setup
python3 tools/companion.py doctor        # Health check
python3 tools/companion.py run           # Full daily loop
python3 tools/companion.py status        # See what's happening
```

### Enable LLM (optional but recommended)

```bash
export OPENAI_API_KEY=sk-...
```

Supports any OpenAI-compatible API: GPT-4o, Claude (via proxy), DeepSeek, Groq, Ollama (local). See [docs/LLM_SETUP.md](fan-evolution-skill/docs/LLM_SETUP.md) for all providers.

Without an API key, everything still works — just uses regex-based analysis instead of AI.

---

## Install as Codex Skill

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo fabiofan/fan-evolution-skill \
  --path fan-evolution-skill
```

Or from URL:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --url https://github.com/fabiofan/fan-evolution-skill/tree/main/fan-evolution-skill
```

Restart Codex after installing. Then invoke with `$fan-evolution-skill`.

---

## All Commands (25)

| Command | Description |
|---------|-------------|
| `init` | Initialize companion workspace with identity files |
| `sense` | Scan authorized directories for recent changes |
| `watchlist` | Manage future concerns, sync due items to reminders |
| `reminders` | Manage reminder list (must/gentle/inbox tiers) |
| `archive` | Package current session as a recoverable archive |
| `digest` | Extract memory candidates (LLM + regex dual engine) |
| `curate` | Score and rank candidates for writeback |
| `memory-apply` | Write confirmed proposals to MEMORY.md |
| `memory-rollback` | Rollback a memory entry by ID |
| `memory-decay` | Run tier promotion/demotion cycle |
| `memory-recall` | Retrieve from cold storage by ID or keyword |
| `feedback` | Check reminder execution status |
| `timeline` | Generate relationship timeline entries |
| `check-in` | Analyze relationship health, suggest actions (LLM-powered) |
| `reflect` | Generate daily reflection (LLM-powered) |
| `understand` | Deep conversation analysis: emotions, needs, dynamics |
| `ingest` | Import conversation text for processing |
| `schedule` | Install/manage auto-scheduling (launchd/cron) |
| `presence` | Manage behavioral rules in PRESENCE.md |
| `export` | Full or incremental backup (JSON) |
| `run` | Execute full companion loop |
| `doctor` | Validate config, files, and LLM connectivity |
| `status` | Output companion status summary |
| `dashboard` | Generate HTML dashboard with progress visualization |
| `init` | Interactive workspace initialization |

---

## Memory Architecture

```
┌─────────────────────────────────────────────────┐
│                Memory Tiering                     │
├─────────────────────────────────────────────────┤
│  CORE     — Never decays. Decisions, milestones, │
│             strong emotions, referenced ≥3 times │
│                                                  │
│  ACTIVE   — Default tier. Referenced = reset     │
│             timer. ≥3 references → promote core  │
│                                                  │
│  FADING   — Low-score context. After decay_days  │
│             without reference → cold storage     │
│             (still recallable, never deleted)     │
└─────────────────────────────────────────────────┘
```

---

## Privacy Rule

This skill ports the **architecture**, not private data.

✅ Reusable: folder structure, command chain, review gates, safety boundaries, memory governance patterns

❌ Never copy: private diaries, project details, emotional memories, relationship phrases, account/login/payment data, user-specific preferences

---

## File Structure

```
fan-evolution-skill/
├── SKILL.md
├── agents/openai.yaml
├── bin/companion
├── docs/LLM_SETUP.md
├── references/UPGRADE_PATH.md
├── templates/companion_config.json
├── tests/                          (193 tests)
│   ├── test_basic.py
│   ├── test_v2_features.py
│   ├── test_v21_features.py
│   ├── test_v22_features.py
│   ├── test_v23_features.py
│   └── test_v3_llm.py
└── tools/
    ├── companion.py                (main CLI entry point)
    ├── llm.py                      (LLM integration layer)
    ├── utils.py                    (shared utilities)
    ├── commands/                   (25 command modules)
    └── hooks/post_conversation.py
```

---

## License

MIT

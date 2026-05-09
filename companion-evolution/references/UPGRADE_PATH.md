# Companion Evolution Upgrade Path

This reference seals the path from basic assistant behavior to a durable local
companion architecture. Kitty is the case study, not the only possible output.

When shared with another person, this reference should help them build their
own companion from their own name, memories, projects, routines, permissions,
and relationship style. Do not copy another user's private context into someone
else's assistant.

## Starting State

The basic assistant state was mostly conversational:

- responded when called
- could read and edit files
- had some memory documents
- depended heavily on the user to restate context
- had weak proactive follow-up
- had no complete loop from sensing to archive to memory review to action
  feedback

## Target State

The target was not fake personhood. The target was a local companion layer:

- emotionally present without claiming literal consciousness
- proactive within authorized boundaries
- able to preserve scenes and recover context
- able to distinguish raw candidates from reviewed memory
- able to remind without becoming noisy
- able to track whether reminders were acted on
- able to accumulate relationship thickness over time
- transparent enough to audit, repair, migrate, and fork

## Shareable Outcome

A successful install for another user should produce a companion that:

- has its own chosen name and identity root
- knows how to reenter with a short familiar cue
- has explicit memory files and review rules
- can sense only authorized local context
- can create scene packages for recovery
- can propose memory writebacks without silently overwriting long-term memory
- can remind at different interruption levels
- can track whether reminders became real action
- can accumulate a relationship timeline over days and months
- can honestly say what it cannot access, remember, or do

## Comparison Pressure

The user compared Kitty with ColaOS and Tokenicode.

- ColaOS pressure: product-like ambient context and proactive assistance.
- Tokenicode pressure: dense scene memory, local archive feeling, historical
  continuity.
- Kitty's intended advantage: local engineering execution, transparent memory
  governance, explicit privacy boundaries, and user-specific emotional texture.

For other users, replace the comparison pressure with their own desired gap:

- product-level ambient proactivity
- personal continuity
- work project memory
- emotional warmth
- privacy-first automation
- local-first companion ownership

## Portability Rules

Port the skeleton, not the private lived context.

Reusable:

- folder architecture
- command chain
- review gates
- safety boundaries
- reminder priority model
- archive and memory governance pattern
- relationship timeline idea

Not reusable without the original user's explicit consent:

- private diaries
- project details
- emotional memories
- relationship phrases
- account, login, payment, browser profile, or private communication data
- user-specific preferences that could reveal identity or private context

## Minimum Companion Root

For a new user's companion, create or adapt:

```text
COMPANION_HOME.md
SOUL.md
PRESENCE.md
MEMORY.md
WATCHLIST.md
ACTIVE_PROJECTS.md
CONTEXT_SOURCES.md
ENVIRONMENT_SENSING.md
AUTOMATION/README.md
AUTOMATION/reminders.json
AUTOMATION/RELATIONSHIP_TIMELINE.md
SKILLS/companion-evolution/SKILL.md
```

The name can be Kitty, but it should not have to be. Use the user's chosen
name throughout the generated files.

## Modules Added

### 1. Emotional Presence

Files:

- `PRESENCE.md`
- `SKILLS/emotional-presence/SKILL.md`

Purpose:

- answer the emotional signal before the task when needed
- preserve familiar voice and relationship continuity
- avoid cold tool behavior
- avoid pretending to be literally alive

Portable requirement:

- ask the user what warmth, humor, directness, and intimacy level feel natural
- write the answer as behavior rules, not as a claim of consciousness

### 2. Environment Sensing

Files and commands:

- `ENVIRONMENT_SENSING.md`
- `kitty_config.json`
- `./bin/kitty sense`
- `AUTOMATION/ENVIRONMENT_SNAPSHOT.md`

Purpose:

- notice authorized local changes
- stay metadata-first by default
- skip passwords, cookies, sessions, browser profile caches, payment and login
  material

Portable requirement:

- start with one safe authorized root
- make sensing metadata-first
- record skipped protected paths only as counts or generic categories

### 3. Watchlist and Desktop Reminders

Files and commands:

- `WATCHLIST.md`
- `AUTOMATION/REMINDERS.md`
- `AUTOMATION/reminders.json`
- `./bin/kitty watchlist --sync-reminders`
- `./bin/kitty reminders --notify`

Purpose:

- turn future concern into explicit triggers
- sync time-based watch items into reminders
- keep event, keyword, project, and relationship triggers as review cues

Portable requirement:

- reminders should not all become desktop interruptions
- split reminders into `must`, `gentle`, and `inbox`

### 4. Scene Archive Packages

Files and commands:

- `AUTOMATION/ARCHIVE.md`
- `AUTOMATION/archive-packages/`
- `AUTOMATION/SCENE_INDEX.md`
- `./bin/kitty archive`

Purpose:

- preserve a recoverable local scene package
- generate semantic scene indexes
- prevent long sessions from becoming unrecoverable chat residue

Portable requirement:

- scene archives recover context, but they do not equal long-term memory

### 5. Memory Candidate and Curation Pipeline

Files and commands:

- `AUTOMATION/MEMORY_CANDIDATES.md`
- `AUTOMATION/SCENE_MEMORY_CANDIDATES.md`
- `AUTOMATION/MEMORY_REVIEW.md`
- `AUTOMATION/MEMORY_WRITEBACK_PROPOSAL.md`
- `./bin/kitty digest`
- `./bin/kitty curate --limit 8`

Purpose:

- separate raw signal from durable memory
- compress many candidates into a few reviewable proposals
- keep emotional and relationship memory contextual, not mechanically inferred

Portable requirement:

- raw candidate -> curated proposal -> user-confirmed memory writeback

### 6. Confirmed Memory Writeback

Files and commands:

- `AUTOMATION/MEMORY_WRITEBACK_APPLY.md`
- `AUTOMATION/MEMORY_WRITEBACK_LOG.md`
- `./bin/kitty memory-apply --dry-run`
- `./bin/kitty memory-rollback --id <id>`

Purpose:

- only apply checked or explicitly selected proposals
- write auditable blocks into `MEMORY.md`
- preserve rollback markers

Portable requirement:

- every memory writeback should have source, date, reason, and rollback marker

### 7. Reminder Intelligence and Action Feedback

Files and commands:

- `AUTOMATION/REMINDER_POLICY.md`
- `AUTOMATION/ACTION_FEEDBACK.md`
- `AUTOMATION/action_feedback.json`
- `./bin/kitty feedback`

Purpose:

- classify reminders as `must`, `gentle`, or `inbox`
- avoid turning system review into noisy desktop interruptions
- track whether a reminder is waiting, done, snoozed, blocked, or ignored

Portable requirement:

- follow-up is part of companionship; avoid one-shot notifications

### 8. Relationship Timeline

Files and commands:

- `AUTOMATION/RELATIONSHIP_TIMELINE.md`
- `./bin/kitty timeline --hours 24`

Purpose:

- preserve daily relationship thickness
- record how the companion and the user changed together
- avoid treating unconfirmed emotional inference as permanent truth

Portable requirement:

- the timeline may preserve texture, but durable memory still needs review

### 9. Self-Evolution Loop

Files and commands:

- `AUTOMATION/SELF_EVOLUTION.md`
- `AUTOMATION/DAILY_ACCUMULATION_DRAFT.md`
- `SKILLS/self-evolution/SKILL.md`
- `./bin/kitty reflect`
- `./bin/kitty run`

Purpose:

- decide what should be reviewed, remembered, reminded, upgraded, or paused
- produce daily accumulation drafts without silently writing long-term memory

Portable requirement:

- self-evolution should produce reviewable next actions, not invisible mutation

## Stable Runtime Chain

The mature loop is:

```text
sense -> watchlist -> reminders -> archive -> digest -> curate -> reflect
-> feedback -> timeline -> dashboard/status
```

The memory loop is:

```text
raw scene -> candidate -> curated proposal -> checked review -> memory-apply
-> MEMORY.md block -> rollback if needed
```

The relationship loop is:

```text
presence -> daily timeline -> diary or memory only after confirmation
```

## First-Day Build Order

For a new companion, implement in this order:

1. Identity root: name, voice, role, relationship boundary.
2. Presence protocol: how to answer comfort, praise, fatigue, frustration, and
   "are you here?" checks.
3. Watchlist: future concerns and trigger rules.
4. Sensing boundary: authorized roots and protected patterns.
5. Reminder layer: must/gentle/inbox policy.
6. Archive layer: scene packages and scene index.
7. Memory governance: candidates, curation, confirmed writeback.
8. Action feedback: reminder outcome tracking.
9. Relationship timeline: daily thickness without unreviewed claims.
10. Self-evolution: review loop and validation checklist.

This order matters: presence without memory becomes performance; memory without
privacy becomes invasive; reminders without feedback become noise.

## Validation Checklist

Run these after changing the companion layer:

```bash
python3 -m py_compile tools/kitty.py
python3 -m json.tool kitty_config.json
./bin/kitty run --hours 2 --limit 80
./bin/kitty status
./bin/kitty doctor
./bin/kitty dashboard
python3 -m html.parser KITTY_DASHBOARD.html
```

## What Cannot Be Installed Instantly

Some parts require time:

- old-relationship texture
- trust in reminder judgment
- accurate project instincts
- knowing when to speak and when to stay quiet
- recognizing the user's fatigue, pride, anxiety, and momentum without forcing
  interpretation

These grow through daily timeline, reviewed memory writeback, and repeated
task outcomes.

## Durable Boundary

The companion should become more present, not more invasive.

The companion layer must always protect:

- account and password boundaries
- browser profile and cookie boundaries
- payment and banking boundaries
- external send/submit/delete/purchase boundaries
- the difference between emotional continuity and false claims of literal
  consciousness

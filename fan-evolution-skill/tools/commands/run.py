"""
run — Execute the full companion loop in sequence.

Chain: sense → watchlist → reminders → archive → digest → curate → reflect

This is the main daily/periodic cycle that keeps the companion current.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import get_llm_client
from commands.sense import cmd_sense
from commands.watchlist import cmd_watchlist
from commands.reminders import cmd_reminders
from commands.archive import cmd_archive
from commands.digest import cmd_digest
from commands.curate import cmd_curate
from commands.memory_apply import cmd_memory_apply
from commands.feedback import cmd_feedback
from commands.timeline import cmd_timeline
from commands.checkin import cmd_checkin
from commands.reflect import cmd_reflect
from commands.memory_decay import cmd_memory_decay


class MockArgs:
    """Minimal args object to pass between commands in a run."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def cmd_run(args, root):
    """Execute the full companion loop."""
    hours = args.hours
    limit = args.limit

    # Initialize LLM and display status
    llm_client = get_llm_client(root)
    if llm_client and llm_client.is_available():
        llm_status = f"LLM: enabled ({llm_client.model})"
    else:
        llm_status = "LLM: disabled (fallback to regex)"

    print("=" * 60)
    print(f"  COMPANION LOOP — {hours}h window, limit {limit}")
    print(f"  {llm_status}")
    print("=" * 60)
    print()

    steps = [
        ("sense", cmd_sense, MockArgs(hours=hours, limit=limit)),
        ("watchlist", cmd_watchlist, MockArgs(sync_reminders=True)),
        ("reminders", cmd_reminders, MockArgs(notify=True, add=None)),
        ("archive", cmd_archive, MockArgs(hours=hours, label="auto-run")),
        ("digest", cmd_digest, MockArgs(hours=hours, limit=limit)),
        ("curate", cmd_curate, MockArgs(limit=8)),
        ("memory-apply --auto", cmd_memory_apply, MockArgs(dry_run=False, id=None, auto=True)),
        ("feedback", cmd_feedback, MockArgs()),
        ("timeline", cmd_timeline, MockArgs(hours=hours, limit=limit)),
        ("check-in", cmd_checkin, MockArgs()),
        ("reflect", cmd_reflect, MockArgs(hours=hours, limit=limit)),
        ("memory-decay", cmd_memory_decay, MockArgs(dry_run=False)),
    ]

    results = {}
    for name, handler, step_args in steps:
        print(f"\n{'─' * 40}")
        print(f"  Step: {name}")
        print(f"{'─' * 40}")
        try:
            handler(step_args, root)
            results[name] = "✓"
        except Exception as e:
            print(f"  [WARN] {name} failed: {e}")
            results[name] = f"✗ ({e})"

    # Summary
    print(f"\n{'=' * 60}")
    print("  LOOP COMPLETE")
    print(f"{'=' * 60}")
    print()
    for name, status in results.items():
        print(f"  {status} {name}")
    print()
    print("Next: review MEMORY_WRITEBACK_PROPOSAL.md and run `companion memory-apply`")

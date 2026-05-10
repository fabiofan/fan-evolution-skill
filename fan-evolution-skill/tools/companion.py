#!/usr/bin/env python3
"""
Companion Evolution Engine
===========================
Main dispatch engine for a local AI companion's operational loop.

Commands:
  sense, watchlist, reminders, archive, digest, curate,
  memory-apply, memory-rollback, feedback, timeline, reflect,
  run, doctor, status, dashboard, init, ingest, schedule, presence

All operations are local-filesystem based, no external dependencies.
"""

import argparse
import sys
import os

# Ensure tools/ subdirectories are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from commands.sense import cmd_sense
from commands.watchlist import cmd_watchlist
from commands.reminders import cmd_reminders
from commands.archive import cmd_archive
from commands.digest import cmd_digest
from commands.curate import cmd_curate
from commands.memory_apply import cmd_memory_apply
from commands.memory_rollback import cmd_memory_rollback
from commands.feedback import cmd_feedback
from commands.timeline import cmd_timeline
from commands.reflect import cmd_reflect
from commands.run import cmd_run
from commands.doctor import cmd_doctor
from commands.status import cmd_status
from commands.dashboard import cmd_dashboard
from commands.init import cmd_init
from commands.ingest import cmd_ingest
from commands.schedule import cmd_schedule
from commands.presence import cmd_presence
from commands.memory_decay import cmd_memory_decay
from commands.checkin import cmd_checkin
from commands.memory_recall import cmd_memory_recall
from commands.export import cmd_export
from commands.understand import cmd_understand
from utils import VERSION


def build_parser():
    """Build the top-level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="companion",
        description="Companion Evolution Engine — grow your local AI companion.",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {VERSION}"
    )
    parser.add_argument(
        "--config", "-c",
        default="companion_config.json",
        help="Path to config file (default: companion_config.json in companion root)"
    )
    parser.add_argument(
        "--root", "-r",
        default=None,
        help="Companion root directory (default: auto-detect from config location)"
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- sense ---
    p = sub.add_parser("sense", help="Scan authorized directories for recent changes")
    p.add_argument("--hours", type=int, default=2, help="Look back N hours (default: 2)")
    p.add_argument("--limit", type=int, default=80, help="Max entries to report (default: 80)")

    # --- watchlist ---
    p = sub.add_parser("watchlist", help="Manage and sync the watchlist")
    p.add_argument("--sync-reminders", action="store_true", help="Sync due items to reminders")

    # --- reminders ---
    p = sub.add_parser("reminders", help="Manage reminder list")
    p.add_argument("--notify", action="store_true", help="Output currently due reminders")
    p.add_argument("--add", type=str, default=None, help="Add a reminder (JSON string)")

    # --- archive ---
    p = sub.add_parser("archive", help="Archive current session/scene")
    p.add_argument("--hours", type=int, default=2, help="Look back N hours for scene content")
    p.add_argument("--label", type=str, default="auto", help="Archive label (default: auto)")

    # --- digest ---
    p = sub.add_parser("digest", help="Extract memory candidates from recent archives")
    p.add_argument("--hours", type=int, default=24, help="Look back N hours (default: 24)")
    p.add_argument("--limit", type=int, default=120, help="Max candidates (default: 120)")

    # --- curate ---
    p = sub.add_parser("curate", help="Select top memory candidates for writeback proposal")
    p.add_argument("--limit", type=int, default=8, help="Max proposals (default: 8)")

    # --- memory-apply ---
    p = sub.add_parser("memory-apply", help="Apply confirmed memory proposals to MEMORY.md")
    p.add_argument("--dry-run", action="store_true", help="Show what would be written without writing")
    p.add_argument("--id", type=str, default=None, help="Apply only a specific proposal ID")
    p.add_argument("--auto", action="store_true", help="Auto-confirm proposals above score threshold")

    # --- memory-rollback ---
    p = sub.add_parser("memory-rollback", help="Rollback a memory entry by ID")
    p.add_argument("--id", type=str, required=True, help="Memory block ID to rollback")

    # --- feedback ---
    p = sub.add_parser("feedback", help="Check reminder execution status")

    # --- timeline ---
    p = sub.add_parser("timeline", help="Generate relationship timeline entries")
    p.add_argument("--hours", type=int, default=24, help="Look back N hours (default: 24)")
    p.add_argument("--limit", type=int, default=120, help="Max entries (default: 120)")

    # --- reflect ---
    p = sub.add_parser("reflect", help="Generate daily reflection and evolution suggestions")
    p.add_argument("--hours", type=int, default=24, help="Look back N hours (default: 24)")
    p.add_argument("--limit", type=int, default=120, help="Max inputs (default: 120)")

    # --- run ---
    p = sub.add_parser("run", help="Execute full companion loop")
    p.add_argument("--hours", type=int, default=24, help="Look back N hours (default: 24)")
    p.add_argument("--limit", type=int, default=120, help="Max entries per step (default: 120)")

    # --- doctor ---
    p = sub.add_parser("doctor", help="Validate config and file integrity")

    # --- status ---
    p = sub.add_parser("status", help="Output companion status summary")

    # --- dashboard ---
    p = sub.add_parser("dashboard", help="Generate HTML dashboard")

    # --- init ---
    p = sub.add_parser("init", help="Initialize a new companion workspace")
    p.add_argument("--name", type=str, default=None, help="Companion name")
    p.add_argument("--root-dir", type=str, default=None, help="Root directory for companion files")
    p.add_argument("--non-interactive", action="store_true", help="Use defaults without prompting")

    # --- ingest ---
    p = sub.add_parser("ingest", help="Ingest conversation content")
    p.add_argument("--text", type=str, default=None, help="Conversation text to ingest")
    p.add_argument("--file", type=str, default=None, help="File containing conversation to ingest")

    # --- schedule ---
    p = sub.add_parser("schedule", help="Manage automatic scheduling")
    p.add_argument("--install", action="store_true", help="Install launchd/cron schedule")
    p.add_argument("--uninstall", action="store_true", help="Remove schedule")
    p.add_argument("--status", action="store_true", help="Check schedule status")

    # --- presence ---
    p = sub.add_parser("presence", help="Manage PRESENCE.md behavioral rules")
    p.add_argument("--list-rules", action="store_true", help="List current rules")
    p.add_argument("--add-rule", type=str, default=None, help="Add a new behavioral rule")
    p.add_argument("--priority", type=int, default=3, help="Rule priority 1-5 (default: 3)")
    p.add_argument("--context", type=str, default="always", help="Rule context: always, when_tired, when_happy, etc.")

    # --- memory-decay ---
    p = sub.add_parser("memory-decay", help="Archive inactive memory blocks (cold storage)")
    p.add_argument("--dry-run", action="store_true", help="Show what would be archived without writing")

    # --- check-in ---
    p = sub.add_parser("check-in", help="Analyze interaction patterns and suggest proactive outreach")

    # --- memory-recall ---
    p = sub.add_parser("memory-recall", help="Recall blocks from cold storage back to MEMORY.md")
    p.add_argument("--id", type=str, default=None, help="Block ID to recall")
    p.add_argument("--search", type=str, default=None, help="Search keyword in cold storage")

    # --- export ---
    p = sub.add_parser("export", help="Export/backup all companion data")
    p.add_argument("--format", type=str, default="json", choices=["json", "markdown"], help="Export format (default: json)")
    p.add_argument("--restore", type=str, default=None, help="Restore from exported file")
    p.add_argument("--incremental", action="store_true", help="Only export changes since last export")

    # --- understand ---
    p = sub.add_parser("understand", help="Deep analysis of a conversation or text (requires LLM)")
    p.add_argument("--file", type=str, default=None, help="File containing conversation to analyze")
    p.add_argument("--text", type=str, default=None, help="Text to analyze")

    return parser


def resolve_root(args):
    """Determine the companion root directory."""
    if args.root:
        return os.path.abspath(args.root)
    # Try to find config relative to cwd
    if os.path.isfile(args.config):
        return os.path.dirname(os.path.abspath(args.config)) or os.getcwd()
    # Default to cwd
    return os.getcwd()


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Resolve companion root
    root = resolve_root(args)

    # Dispatch
    commands = {
        "sense": cmd_sense,
        "watchlist": cmd_watchlist,
        "reminders": cmd_reminders,
        "archive": cmd_archive,
        "digest": cmd_digest,
        "curate": cmd_curate,
        "memory-apply": cmd_memory_apply,
        "memory-rollback": cmd_memory_rollback,
        "feedback": cmd_feedback,
        "timeline": cmd_timeline,
        "reflect": cmd_reflect,
        "run": cmd_run,
        "doctor": cmd_doctor,
        "status": cmd_status,
        "dashboard": cmd_dashboard,
        "init": cmd_init,
        "ingest": cmd_ingest,
        "schedule": cmd_schedule,
        "presence": cmd_presence,
        "memory-decay": cmd_memory_decay,
        "check-in": cmd_checkin,
        "memory-recall": cmd_memory_recall,
        "export": cmd_export,
        "understand": cmd_understand,
    }

    handler = commands.get(args.command)
    if handler:
        try:
            handler(args, root)
        except Exception as e:
            print(f"[ERROR] {args.command}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
schedule — Manage automatic scheduling for the companion loop.

Generates and installs macOS launchd plist or Linux crontab entries
to run the companion loop periodically.

Usage:
  companion schedule --install    Install the schedule (launchd or cron)
  companion schedule --uninstall  Remove the schedule
  companion schedule --status     Check if schedule is active
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, ensure_dir


PLIST_LABEL = "com.companion.loop"


def get_companion_script_path(root):
    """Get the absolute path to the companion.py script."""
    return os.path.join(root, "tools", "companion.py")


def generate_plist(root, interval_seconds=7200):
    """Generate launchd plist content."""
    script_path = get_companion_script_path(root)
    python_path = sys.executable

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
        <string>run</string>
        <string>--hours</string>
        <string>2</string>
        <string>--root</string>
        <string>{root}</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>WorkingDirectory</key>
    <string>{root}</string>
    <key>StandardOutPath</key>
    <string>{os.path.join(root, 'AUTOMATION', 'companion_loop.log')}</string>
    <key>StandardErrorPath</key>
    <string>{os.path.join(root, 'AUTOMATION', 'companion_loop_error.log')}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def generate_crontab_entry(root, interval_hours=2):
    """Generate crontab entry string."""
    script_path = get_companion_script_path(root)
    python_path = sys.executable
    # Run every N hours at minute 0
    if interval_hours == 1:
        schedule = "0 * * * *"
    elif interval_hours == 2:
        schedule = "0 */2 * * *"
    elif interval_hours == 4:
        schedule = "0 */4 * * *"
    else:
        schedule = f"0 */{interval_hours} * * *"

    return f"{schedule} cd {root} && {python_path} {script_path} run --hours {interval_hours} --root {root} >> {os.path.join(root, 'AUTOMATION', 'companion_loop.log')} 2>&1"


def get_plist_path():
    """Get the user LaunchAgents plist path."""
    return os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")


def install_launchd(root):
    """Install launchd plist on macOS."""
    plist_content = generate_plist(root)
    plist_path = get_plist_path()

    # Ensure LaunchAgents directory exists
    os.makedirs(os.path.dirname(plist_path), exist_ok=True)

    # Write plist
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(plist_content)

    # Load the agent
    try:
        subprocess.run(["launchctl", "unload", plist_path],
                       capture_output=True, timeout=10)
    except Exception:
        pass

    result = subprocess.run(["launchctl", "load", plist_path],
                            capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print(f"[schedule] Installed launchd agent: {plist_path}")
        print(f"[schedule] Companion loop will run every 2 hours.")
    else:
        print(f"[schedule] Error loading agent: {result.stderr}", file=sys.stderr)
        sys.exit(1)


def uninstall_launchd():
    """Uninstall launchd plist on macOS."""
    plist_path = get_plist_path()
    if not os.path.isfile(plist_path):
        print("[schedule] No launchd agent installed.")
        return

    try:
        subprocess.run(["launchctl", "unload", plist_path],
                       capture_output=True, timeout=10)
    except Exception:
        pass

    os.remove(plist_path)
    print(f"[schedule] Removed launchd agent: {plist_path}")


def status_launchd():
    """Check launchd status."""
    plist_path = get_plist_path()
    if not os.path.isfile(plist_path):
        print("[schedule] Status: NOT INSTALLED")
        print(f"[schedule] Expected at: {plist_path}")
        return

    result = subprocess.run(["launchctl", "list", PLIST_LABEL],
                            capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print("[schedule] Status: ACTIVE")
        print(f"[schedule] Plist: {plist_path}")
        # Parse output for last run info
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}")
    else:
        print("[schedule] Status: INSTALLED but NOT LOADED")
        print(f"[schedule] Plist exists at: {plist_path}")
        print(f"[schedule] Run `companion schedule --install` to reload.")


def save_templates(root):
    """Save plist and crontab templates to templates/ directory."""
    templates_dir = os.path.join(root, "templates")
    ensure_dir(templates_dir)

    # Save plist template
    plist_content = generate_plist(root)
    plist_template_path = os.path.join(templates_dir, "com.companion.loop.plist")
    with open(plist_template_path, "w", encoding="utf-8") as f:
        f.write(plist_content)

    # Save crontab template
    cron_entry = generate_crontab_entry(root)
    crontab_template_path = os.path.join(templates_dir, "crontab.example")
    crontab_content = f"""# Companion Loop — automatic scheduling
# Add this line to your crontab (crontab -e):
#
# Run every 2 hours:
{cron_entry}
#
# Run every 4 hours instead:
# {generate_crontab_entry(root, 4)}
#
# Run once daily at 9am:
# 0 9 * * * cd {root} && {sys.executable} {get_companion_script_path(root)} run --hours 24 --root {root}
"""
    with open(crontab_template_path, "w", encoding="utf-8") as f:
        f.write(crontab_content)

    print(f"[schedule] Templates saved:")
    print(f"  - {plist_template_path}")
    print(f"  - {crontab_template_path}")


def cmd_schedule(args, root):
    """Execute the schedule command."""
    is_macos = platform.system() == "Darwin"

    # Always save templates
    save_templates(root)

    if args.status:
        if is_macos:
            status_launchd()
        else:
            print("[schedule] On Linux, check crontab with: crontab -l")
            print(f"[schedule] See templates/crontab.example for the entry.")
    elif args.install:
        if is_macos:
            install_launchd(root)
        else:
            cron_entry = generate_crontab_entry(root)
            print("[schedule] On Linux, add this to your crontab (crontab -e):")
            print(f"  {cron_entry}")
            print()
            print("[schedule] Or use: (crontab -l; echo '{cron_entry}') | crontab -")
    elif args.uninstall:
        if is_macos:
            uninstall_launchd()
        else:
            print("[schedule] On Linux, edit crontab manually: crontab -e")
            print(f"[schedule] Remove the companion loop line.")
    else:
        print("[schedule] Use --install, --uninstall, or --status")
        if is_macos:
            status_launchd()
        else:
            print("[schedule] Platform: Linux — use crontab")

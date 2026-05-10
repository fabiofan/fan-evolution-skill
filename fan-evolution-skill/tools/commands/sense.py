"""
sense — Scan authorized directories for recent changes.

Produces an environment snapshot in markdown format showing:
- Recently modified files (by mtime)
- Recent git commits (if in a git repo)
- Summary of activity areas

Respects privacy boundaries: skips protected patterns.
"""

import os
import subprocess
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, is_protected, write_markdown, now_iso, now_local, ensure_dir


def scan_filesystem(authorized_dirs, protected_patterns, since_dt, limit):
    """Walk authorized directories, find recently modified files."""
    results = []
    skipped_count = 0

    for dir_path in authorized_dirs:
        dir_path = os.path.expanduser(dir_path)
        if not os.path.isdir(dir_path):
            continue
        for dirpath, dirnames, filenames in os.walk(dir_path):
            # Skip hidden directories
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in filenames:
                if fname.startswith("."):
                    continue
                fpath = os.path.join(dirpath, fname)
                # Check protected
                if is_protected(fpath, protected_patterns):
                    skipped_count += 1
                    continue
                try:
                    mtime = os.path.getmtime(fpath)
                    file_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                    if file_dt > since_dt:
                        results.append({
                            "path": fpath,
                            "mtime": file_dt.isoformat(),
                            "size": os.path.getsize(fpath),
                        })
                except (OSError, PermissionError):
                    skipped_count += 1
                    continue

    # Sort by mtime descending
    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results[:limit], skipped_count


def scan_git_log(authorized_dirs, hours, limit):
    """Get recent git commits from authorized directories."""
    commits = []
    since_str = f"{hours} hours ago"

    for dir_path in authorized_dirs:
        dir_path = os.path.expanduser(dir_path)
        if not os.path.isdir(os.path.join(dir_path, ".git")):
            # Check if it's inside a git repo
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    cwd=dir_path, capture_output=True, text=True, timeout=5
                )
                if result.returncode != 0:
                    continue
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        try:
            result = subprocess.run(
                ["git", "log", f"--since={since_str}", "--oneline", f"-{limit}"],
                cwd=dir_path, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    commits.append({"repo": dir_path, "log": line.strip()})
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return commits[:limit]


def cmd_sense(args, root):
    """Execute the sense command."""
    config = load_config(root)
    authorized_dirs = config.get("authorized_dirs", [root])
    protected_patterns = config.get("protected_patterns", [])
    hours = args.hours
    limit = args.limit

    since_dt = datetime.now(timezone.utc) - timedelta(hours=hours)

    print(f"[sense] Scanning last {hours}h, limit {limit} entries...")
    print(f"[sense] Authorized dirs: {authorized_dirs}")

    # Filesystem scan
    files, skipped = scan_filesystem(authorized_dirs, protected_patterns, since_dt, limit)
    # Git scan
    commits = scan_git_log(authorized_dirs, hours, limit // 2)

    # Build snapshot markdown
    lines = [
        f"# Environment Snapshot",
        f"",
        f"Generated: {now_local()}",
        f"Window: last {hours} hours",
        f"Protected paths skipped: {skipped}",
        f"",
        f"## Recently Modified Files ({len(files)} found)",
        f"",
    ]

    for f in files[:limit]:
        rel = os.path.relpath(f["path"], root) if f["path"].startswith(root) else f["path"]
        lines.append(f"- `{rel}` — {f['size']}B — {f['mtime']}")

    lines.append("")
    lines.append(f"## Recent Git Activity ({len(commits)} commits)")
    lines.append("")

    for c in commits:
        lines.append(f"- [{os.path.basename(c['repo'])}] {c['log']}")

    lines.append("")
    lines.append("---")
    lines.append(f"*Snapshot by companion sense at {now_iso()}*")

    snapshot_content = "\n".join(lines)

    # Write snapshot
    automation_dir = ensure_dir(os.path.join(root, "AUTOMATION"))
    snapshot_path = os.path.join(automation_dir, "ENVIRONMENT_SNAPSHOT.md")
    write_markdown(snapshot_path, snapshot_content)

    print(f"[sense] Found {len(files)} modified files, {len(commits)} git commits")
    print(f"[sense] Snapshot written to: {snapshot_path}")
    print(snapshot_content)

"""
curate — Select top memory candidates for writeback proposal.

Reads MEMORY_CANDIDATES.md, ranks by importance heuristics,
outputs a writeback proposal (MEMORY_WRITEBACK_PROPOSAL.md)
that must be confirmed before applying.
"""

import os
import re
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, write_markdown,
    now_iso, now_local, generate_id
)


# Stop words to filter when computing project relevance
STOP_WORDS_EN = {
    "the", "and", "or", "is", "are", "was", "were", "has", "have", "had",
    "this", "that", "with", "for", "from", "into", "not", "but", "its",
    "all", "can", "will", "just", "been", "than", "them", "then",
    "some", "other", "what", "which", "when", "who", "how",
}
STOP_WORDS_ZH = {
    "的", "了", "是", "在", "和", "也", "就", "都", "而", "及",
    "与", "不", "来",
}
STOP_WORDS = STOP_WORDS_EN | STOP_WORDS_ZH

# Category importance weights
CATEGORY_WEIGHTS = {
    "decision": 5,
    "milestone": 4,
    "insight": 4,
    "preference": 3,
    "challenge": 2,
    "emotion": 2,
    "other": 1,
}


def parse_candidates(content):
    """Parse MEMORY_CANDIDATES.md back into structured candidates."""
    candidates = []
    current_category = "other"
    last_source = None

    for line in content.split("\n"):
        line = line.strip()
        # Detect category headers
        cat_match = re.match(r"^##\s+(\w+)", line)
        if cat_match:
            current_category = cat_match.group(1).lower()
            continue

        # Detect candidate lines (starts with -)
        if line.startswith("- ") and not line.startswith("- _source"):
            text = line[2:].strip()
            candidates.append({
                "text": text,
                "category": current_category,
                "weight": CATEGORY_WEIGHTS.get(current_category, 1),
                "source": last_source,
            })
        elif line.startswith("_source:") or line.startswith("  _source:"):
            # Extract source for the previous candidate
            source_match = re.match(r"_?\s*_source:\s*(.+?)_?$", line.strip(" _"))
            if source_match and candidates:
                candidates[-1]["source"] = source_match.group(1).strip()
                last_source = candidates[-1]["source"]

    return candidates


def extract_date_from_source(source_name):
    """Extract date from source filename (e.g. '2025-05-08_143022.md')."""
    if not source_name:
        return None
    match = re.search(r"(\d{4}-\d{2}-\d{2})", source_name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def compute_frequency_bonus(candidate, all_candidates):
    """Frequency weight: if similar content (first 30 chars) appears multiple times, bonus."""
    key = candidate["text"][:30].lower()
    count = sum(1 for c in all_candidates if c["text"][:30].lower() == key)
    # Each additional occurrence beyond the first adds +2
    return (count - 1) * 2


def compute_time_decay(candidate):
    """Time decay: older candidates get score reduction."""
    source_date = extract_date_from_source(candidate.get("source"))
    if source_date is None:
        return 0
    age = datetime.now() - source_date
    if age > timedelta(days=7):
        return -2
    elif age > timedelta(days=2):
        return -1
    return 0


def compute_project_relevance(candidate, root):
    """Project relevance: bonus if candidate text mentions active project keywords."""
    projects_path = os.path.join(root, "ACTIVE_PROJECTS.md")
    if not os.path.isfile(projects_path):
        return 0
    projects_content = read_markdown(projects_path)
    if not projects_content.strip():
        return 0

    # Extract keywords from ACTIVE_PROJECTS.md (words from non-header lines)
    keywords = set()
    for line in projects_content.split("\n"):
        line = line.strip()
        if line.startswith("#") or line.startswith("---") or not line:
            continue
        # Extract meaningful words (3+ chars)
        words = re.findall(r"[a-zA-Z\u4e00-\u9fff]{3,}", line)
        keywords.update(w.lower() for w in words)

    # Filter out stop words
    keywords = keywords - STOP_WORDS

    if not keywords:
        return 0

    text_lower = candidate["text"].lower()
    for kw in keywords:
        if kw in text_lower:
            return 2
    return 0


def score_candidate(candidate, all_candidates=None, root=None):
    """Score a candidate by weight, text quality, frequency, decay, and project relevance."""
    score = candidate["weight"]
    text = candidate["text"]

    # Bonus for longer, more specific entries
    # (skipped for context category — length is incidental for context)
    if candidate.get("category") != "context":
        if len(text) > 50:
            score += 1
        if len(text) > 100:
            score += 1

    # Bonus for containing dates or specifics
    if re.search(r"\d{4}-\d{2}-\d{2}", text):
        score += 1
    if re.search(r"(?:project|file|repo|api|feature)", text, re.I):
        score += 1

    # Frequency bonus
    if all_candidates:
        score += compute_frequency_bonus(candidate, all_candidates)

    # Time decay
    score += compute_time_decay(candidate)

    # Project relevance
    if root:
        score += compute_project_relevance(candidate, root)

    return score


def cmd_curate(args, root):
    """Execute the curate command."""
    config = load_config(root)
    limit = args.limit

    candidates_path = os.path.join(root, "AUTOMATION", "MEMORY_CANDIDATES.md")
    content = read_markdown(candidates_path)

    if not content.strip():
        print("[curate] No candidates found. Run `companion digest` first.")
        return

    candidates = parse_candidates(content)
    if not candidates:
        print("[curate] No parseable candidates in MEMORY_CANDIDATES.md")
        return

    # Score and sort (with frequency, decay, and project relevance)
    for c in candidates:
        c["score"] = score_candidate(c, all_candidates=candidates, root=root)
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Take top N
    selected = candidates[:limit]

    # Build proposal
    lines = [
        "# Memory Writeback Proposal",
        "",
        f"Generated: {now_local()}",
        f"Selected: {len(selected)} from {len(candidates)} candidates",
        "",
        "**Review these before applying with `companion memory-apply`.**",
        "",
        "---",
        "",
    ]

    for i, item in enumerate(selected, 1):
        proposal_id = generate_id("prop")
        lines.extend([
            f"### Proposal {i}: {proposal_id}",
            f"",
            f"- **Category**: {item['category']}",
            f"- **Score**: {item['score']}",
            f"- **Content**: {item['text']}",
            f"- **Status**: pending",
            f"",
        ])

    lines.append("---")
    lines.append(f"*Curated by companion at {now_iso()}*")

    proposal_content = "\n".join(lines)

    # Write proposal
    proposal_path = os.path.join(root, "AUTOMATION", "MEMORY_WRITEBACK_PROPOSAL.md")
    write_markdown(proposal_path, proposal_content)

    print(f"[curate] Selected {len(selected)} proposals from {len(candidates)} candidates")
    print(f"[curate] Proposal written to: {proposal_path}")
    print(f"[curate] Review and run `companion memory-apply` to confirm.")
    print()
    for i, item in enumerate(selected, 1):
        print(f"  {i}. [{item['category']}] {item['text'][:80]}")

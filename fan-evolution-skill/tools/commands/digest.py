"""
digest — Extract memory candidates from recent archives and activity.

Scans archive-packages from the last N hours, extracts potential
memory-worthy items (decisions, preferences, relationship moments,
project milestones, emotional patterns).

Output: AUTOMATION/MEMORY_CANDIDATES.md
"""

import os
import re
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, write_markdown,
    now_iso, now_local, generate_id, ensure_dir, get_llm_client
)


# Implicit signal patterns (subtler emotional/behavioral cues)
IMPLICIT_SIGNAL_PATTERNS = [
    (r"(?i)(whatever|fine|let it go|doesn'?t matter|who cares)", "resignation"),
    (r"(算了|就这样吧|随便|无所谓|不管了)", "resignation"),
    (r"(?i)(your call|I'?ll leave it to you|you decide|up to you)", "delegation"),
    (r"(你看着办|你决定|交给你|听你的)", "delegation"),
    (r"(?i)(tired|exhausted|done with|can'?t anymore|burned? out)", "fatigue"),
    (r"(累了|不想|够了|太多了|受不了|撑不住)", "fatigue"),
    (r"(?i)(interesting|wonder|curious|how come|why does)", "curiosity"),
    (r"(有意思|为什么|怎么回事|好奇|奇怪)", "curiosity"),
    (r"(?i)(stop|don'?t|no way|enough|back off)", "boundary"),
    (r"(别|不要|不行|不可以|住手|停)", "boundary"),
]


def extract_candidates_from_archive(content, archive_name):
    """
    Extract memory candidate lines from an archive.
    Looks for:
    - Lines with strong signals (decisions, preferences, milestones)
    - Implicit signals (resignation, delegation, fatigue, curiosity, boundary)
    - Context window: adjacent lines to strong-signal lines
    - Reminder completions
    - Project state changes
    """
    candidates = []
    lines = content.split("\n")

    # Heuristics for memory-worthy content
    signal_patterns = [
        (r"(?i)(decided|chose|picked|selected|committed)", "decision"),
        (r"(决定|选择|定了|确认|敲定)", "decision"),
        (r"(?i)\b(prefer|like|love|hate|dislike|want)\b", "preference"),
        (r"(喜欢|讨厌|偏好|想要|希望)", "preference"),
        (r"(?i)(finished|completed|shipped|deployed|launched)", "milestone"),
        (r"(完成|搞定|上线|发布|交付|做完)", "milestone"),
        (r"(?i)(learned|realized|discovered|understood)", "insight"),
        (r"(发现|原来|明白了|想通了|学到|意识到)", "insight"),
        (r"(?i)(blocked|stuck|frustrated|struggling)", "challenge"),
        (r"(卡住|崩溃|烦|难受|搞不定|头疼)", "challenge"),
        (r"(?i)(happy|excited|proud|relieved|grateful)", "emotion"),
        (r"(开心|高兴|感动|心暖|放松|舒服|感谢)", "emotion"),
    ]

    # All patterns (implicit first for priority over broad explicit patterns)
    all_patterns = IMPLICIT_SIGNAL_PATTERNS + signal_patterns

    # First pass: find lines with direct signals and track their indices
    signal_indices = set()
    line_data = []  # (stripped_line, category_or_none)

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        line_data.append(line)
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        if len(line) < 10:
            continue

        for pattern, category in all_patterns:
            if re.search(pattern, line):
                signal_indices.add(i)
                candidates.append({
                    "text": line,
                    "category": category,
                    "source": archive_name,
                    "extracted_at": now_iso(),
                })
                break  # One category per line is enough

    # Second pass: context window — include ±2 adjacent lines of strong-signal lines
    context_groups = {}  # parent_idx -> list of neighbor lines
    for idx in signal_indices:
        for offset in [-2, -1, 1, 2]:
            neighbor = idx + offset
            if 0 <= neighbor < len(line_data) and neighbor not in signal_indices:
                neighbor_line = line_data[neighbor]
                if (neighbor_line and not neighbor_line.startswith("#")
                        and not neighbor_line.startswith("---") and len(neighbor_line) >= 10):
                    if idx not in context_groups:
                        context_groups[idx] = []
                    if (neighbor, neighbor_line) not in [(n, l) for n, l in context_groups[idx]]:
                        context_groups[idx].append((neighbor, neighbor_line))

    # Add context lines (merged per parent, marked as context)
    for parent_idx, neighbors in context_groups.items():
        parent_text = line_data[parent_idx]
        # Sort neighbors by position
        neighbors.sort(key=lambda x: x[0])
        # Merge multiple context lines into one candidate
        merged_text = "\n".join(line for _, line in neighbors)
        candidates.append({
            "text": merged_text,
            "category": "context",
            "source": archive_name,
            "extracted_at": now_iso(),
            "context_of": parent_text[:50],
            "context_lines": len(neighbors),
        })

    return candidates


# LLM-enhanced signal extraction
LLM_DIGEST_SYSTEM_PROMPT = """你是一个记忆提取引擎。从以下对话/文档内容中，提取值得长期记住的信息。每条信息标注类别。

类别说明：
- decision：重要决定
- preference：个人偏好/喜好
- milestone：里程碑/完成
- insight：领悟/发现
- challenge：困难/卡点
- emotion：情绪表达
- resignation：放弃/妥协
- delegation：委托/信任
- fatigue：疲惫
- boundary：边界/拒绝
- curiosity：好奇

要求：
- 输出JSON数组
- 每条格式：{"text": "原文或概括", "category": "类别", "importance": 1-10}
- importance 1=琐碎 10=极其重要
- 只输出JSON，不要其他文字"""


def extract_candidates_with_llm(content, archive_name, llm_client):
    """
    Use LLM to extract memory candidates from content.

    Returns list of candidate dicts, or None if LLM fails (caller should fallback).
    """
    if not llm_client or not llm_client.is_available():
        return None

    # Truncate content to avoid token limits (roughly 6000 chars)
    truncated = content[:6000]
    if len(content) > 6000:
        truncated += "\n... (truncated)"

    user_prompt = f"来源文件: {archive_name}\n\n内容:\n{truncated}"

    result = llm_client.chat_json(LLM_DIGEST_SYSTEM_PROMPT, user_prompt)
    if result is None:
        return None

    if not isinstance(result, list):
        return None

    candidates = []
    for item in result:
        if not isinstance(item, dict):
            continue
        text = item.get("text", "").strip()
        category = item.get("category", "other").strip()
        importance = item.get("importance", 5)
        if not text:
            continue
        # Validate category
        valid_categories = {
            "decision", "preference", "milestone", "insight", "challenge",
            "emotion", "resignation", "delegation", "fatigue", "boundary",
            "curiosity", "context", "other"
        }
        if category not in valid_categories:
            category = "other"
        # Normalize importance to int 1-10
        try:
            importance = max(1, min(10, int(importance)))
        except (ValueError, TypeError):
            importance = 5

        candidates.append({
            "text": text,
            "category": category,
            "source": archive_name,
            "extracted_at": now_iso(),
            "importance": importance,
            "method": "llm",
        })

    return candidates if candidates else None


def cmd_digest(args, root):
    """Execute the digest command."""
    config = load_config(root)
    hours = args.hours
    limit = args.limit

    # Initialize LLM client
    llm_client = get_llm_client(root)
    use_llm = llm_client is not None and llm_client.is_available()
    method_label = "llm" if use_llm else "regex"

    archive_dir = os.path.join(root, "AUTOMATION", "archive-packages")
    cutoff = datetime.now() - timedelta(hours=hours)

    all_candidates = []

    # Scan recent archives
    if os.path.isdir(archive_dir):
        for fname in sorted(os.listdir(archive_dir), reverse=True):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(archive_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    continue
            except OSError:
                continue

            content = read_markdown(fpath)
            candidates = None
            if use_llm:
                candidates = extract_candidates_with_llm(content, fname, llm_client)
            if candidates is None:
                candidates = extract_candidates_from_archive(content, fname)
                for c in candidates:
                    c["method"] = "regex"
            all_candidates.extend(candidates)

    # Scan conversations directory
    conversations_dir = os.path.join(root, "AUTOMATION", "conversations")
    if os.path.isdir(conversations_dir):
        for fname in sorted(os.listdir(conversations_dir), reverse=True):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(conversations_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    continue
            except OSError:
                continue
            content = read_markdown(fpath)
            candidates = None
            if use_llm:
                candidates = extract_candidates_with_llm(content, fname, llm_client)
            if candidates is None:
                candidates = extract_candidates_from_archive(content, fname)
                for c in candidates:
                    c["method"] = "regex"
            all_candidates.extend(candidates)

    # Also scan the environment snapshot for recent signals
    snapshot = read_markdown(os.path.join(root, "AUTOMATION", "ENVIRONMENT_SNAPSHOT.md"))
    if snapshot:
        snap_candidates = None
        if use_llm:
            snap_candidates = extract_candidates_with_llm(snapshot, "ENVIRONMENT_SNAPSHOT", llm_client)
        if snap_candidates is None:
            snap_candidates = extract_candidates_from_archive(snapshot, "ENVIRONMENT_SNAPSHOT")
            for c in snap_candidates:
                c["method"] = "regex"
        all_candidates.extend(snap_candidates)

    # Deduplicate by text similarity
    seen_texts = set()
    unique_candidates = []
    for c in all_candidates:
        key = c["text"][:50].lower()
        if key not in seen_texts:
            seen_texts.add(key)
            unique_candidates.append(c)

    # Limit
    unique_candidates = unique_candidates[:limit]

    # Build output
    lines = [
        "# Memory Candidates",
        "",
        f"Generated: {now_local()}",
        f"Window: last {hours} hours",
        f"Candidates found: {len(unique_candidates)}",
        "",
        "---",
        "",
    ]

    # Group by category
    categories = {}
    for c in unique_candidates:
        cat = c.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(c)

    for cat, items in sorted(categories.items()):
        lines.append(f"## {cat.title()} ({len(items)})")
        lines.append("")
        for item in items:
            lines.append(f"- {item['text']}")
            lines.append(f"  _source: {item['source']}_")
        lines.append("")

    lines.append("---")
    lines.append(f"*Digest by companion at {now_iso()}*")

    output = "\n".join(lines)

    # Write candidates file
    candidates_path = os.path.join(root, "AUTOMATION", "MEMORY_CANDIDATES.md")
    write_markdown(candidates_path, output)

    print(f"[digest] Method: {method_label}")
    print(f"[digest] Scanned archives from last {hours}h")
    print(f"[digest] Found {len(unique_candidates)} unique candidates")
    print(f"[digest] Written to: {candidates_path}")

    # Print summary
    for cat, items in sorted(categories.items()):
        print(f"  {cat}: {len(items)}")

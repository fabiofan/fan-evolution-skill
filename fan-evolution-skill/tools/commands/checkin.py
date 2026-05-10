"""
check-in — Analyze interaction patterns and suggest proactive outreach.

Reads RELATIONSHIP_TIMELINE.md and checks:
1. If last interaction was too long ago → suggest check-in
2. If recent interactions are all work/collaboration → suggest adding warmth

Output: Advice text appended to DAILY_ACCUMULATION_DRAFT.md
"""

import os
import re
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, append_markdown, write_markdown,
    now_iso, now_local, get_llm_client
)


def parse_timeline_entries(content):
    """Parse timeline entries with dates and types."""
    entries = []
    current_date = None

    for line in content.split("\n"):
        line = line.strip()
        # Detect date headers like "## 2025-05-08 14:30:00 — Daily Timeline Entry"
        date_match = re.match(r"^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
        if date_match:
            try:
                current_date = datetime.strptime(date_match.group(1), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                current_date = None
            continue

        # Detect event type lines like "- **gratitude**: ..."
        type_match = re.match(r"^-\s+\*\*(\w+)\*\*:", line)
        if type_match and current_date:
            entries.append({
                "date": current_date,
                "type": type_match.group(1).lower(),
                "text": line,
            })

    return entries


def deduplicate_checkin(draft_path, new_advice):
    """Replace today's check-in if one already exists, otherwise append."""
    content = read_markdown(draft_path)
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Find all check-in sections and check if the last one is from today
    pattern = re.compile(r"(\n\n## Check-in Analysis \u2014 (\d{4}-\d{2}-\d{2}).*?)(?=\n\n## |\Z)", re.DOTALL)
    matches = list(pattern.finditer(content))

    if matches:
        last_match = matches[-1]
        last_date = last_match.group(2)
        if last_date == today_str:
            # Replace the last check-in with the new one
            updated = content[:last_match.start()] + new_advice + content[last_match.end():]
            write_markdown(draft_path, updated)
            return True

    # No existing today entry — append
    append_markdown(draft_path, new_advice)
    return False


def detect_language(content, config):
    """Determine output language based on config and content.

    Config 'language' field: 'zh', 'en', or 'auto' (default).
    Auto mode: if Chinese characters make up >30% of non-whitespace, use zh.
    """
    lang = config.get("language", "auto")
    if lang in ("zh", "en"):
        return lang
    # Auto-detect from content
    if not content:
        return "en"
    non_ws = re.sub(r'\s', '', content)
    if not non_ws:
        return "en"
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', non_ws))
    ratio = chinese_chars / len(non_ws)
    return "zh" if ratio > 0.3 else "en"


LLM_CHECKIN_SYSTEM_PROMPT = """你是一个关系健康分析师。根据最近的互动时间线和记忆，判断是否需要主动联系对方。

考虑：
- 上次互动距今多久？
- 最近互动的深度和温度？
- 对方可能在忙什么（从记忆中推断）？
- 如果需要联系，给出具体话题建议
- 如果不需要，解释为什么（不是所有沉默都需要打破）

用中文回答，简洁明了，200字以内。"""


def generate_checkin_with_llm(timeline_entries, memory_blocks, llm_client, config):
    """
    Generate AI-powered check-in analysis.

    Returns advice text or None if LLM fails.
    """
    if not llm_client or not llm_client.is_available():
        return None

    # Build user prompt from recent timeline and memory
    parts = []
    if timeline_entries:
        recent = timeline_entries[-10:]  # last 10 entries
        entry_texts = []
        for e in recent:
            date_str = e["date"].strftime("%Y-%m-%d %H:%M") if isinstance(e.get("date"), datetime) else str(e.get("date", ""))
            entry_texts.append(f"{date_str} [{e.get('type', '?')}]: {e.get('text', '')[:100]}")
        parts.append("最近时间线：\n" + "\n".join(entry_texts))

    if memory_blocks:
        parts.append(f"\n相关记忆：\n{memory_blocks[:2000]}")

    if not parts:
        return None

    user_prompt = "\n".join(parts)
    return llm_client.chat(LLM_CHECKIN_SYSTEM_PROMPT, user_prompt)


def cmd_checkin(args, root):
    """Execute the check-in command."""
    config = load_config(root)
    companion_name = config.get("companion_name", "companion")

    relationship_config = config.get("relationship", {})
    checkin_interval = relationship_config.get("checkin_interval_days", 3)

    # Initialize LLM client
    llm_client = get_llm_client(root)

    timeline_path = os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md")
    draft_path = os.path.join(root, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md")

    content = read_markdown(timeline_path)

    # Determine output language
    lang = detect_language(content, config)

    if not content.strip():
        advice = (
            f"\n\n## Check-in Analysis \u2014 {now_local()}\n\n"
            f"No relationship timeline found. Consider running `companion timeline` first, "
            f"then check-in can analyze interaction patterns.\n\n"
        )
        deduplicate_checkin(draft_path, advice)
        print("[check-in] No timeline data available.")
        print(f"[check-in] Suggestion written to: {draft_path}")
        return

    entries = parse_timeline_entries(content)
    now = datetime.now()

    # Try LLM-powered analysis first
    if llm_client and llm_client.is_available():
        memory_content = read_markdown(os.path.join(root, "MEMORY.md"))
        llm_advice = generate_checkin_with_llm(entries, memory_content, llm_client, config)
        if llm_advice:
            advice = (
                f"\n\n## Check-in Analysis \u2014 {now_local()} [AI-powered]\n\n"
                f"{llm_advice}\n\n"
            )
            deduplicate_checkin(draft_path, advice)
            print(f"[check-in] Analyzed {len(entries)} timeline entries [AI-powered]")
            print(f"[check-in] Appended to: {draft_path}")
            return

    # Fallback: rule-based analysis
    suggestions = []

    # Check 1: Last interaction gap
    if entries:
        last_entry_date = max(e["date"] for e in entries)
        gap = now - last_entry_date
        if gap > timedelta(days=checkin_interval):
            if lang == "zh":
                suggestions.append(
                    f"\u8ddd\u79bb\u4e0a\u6b21\u4e92\u52a8\u5df2\u7ecf {gap.days} \u5929\u4e86\u3002"
                    f"\u53ef\u4ee5\u4e3b\u52a8\u8054\u7cfb\u4e00\u4e0b\u2014\u2014"
                    f"\u804a\u804a\u8fd1\u51b5\uff0c\u56de\u987e\u4e00\u4e0b\u4e0a\u6b21\u7684\u8bdd\u9898\u3002"
                )
            else:
                suggestions.append(
                    f"It's been {gap.days} days since the last timeline entry. "
                    f"Consider a proactive check-in \u2014 ask how things are going, "
                    f"reference something from your last interaction."
                )
    else:
        suggestions.append(
            "No parseable timeline entries found. The relationship tracking "
            "may need attention."
        )

    # Check 2: Relationship balance — are all recent entries purely work?
    if entries:
        recent_entries = [e for e in entries if (now - e["date"]) <= timedelta(days=7)]
        if recent_entries:
            types_found = set(e["type"] for e in recent_entries)
            warmth_types = {"gratitude", "emotion", "anticipation", "continuity", "repair"}
            work_types = {"collaboration", "milestone"}

            has_warmth = bool(types_found & warmth_types)
            all_work = types_found.issubset(work_types)

            if all_work and not has_warmth:
                if lang == "zh":
                    suggestions.append(
                        "\u6700\u8fd1\u7684\u4e92\u52a8\u5168\u662f\u5de5\u4f5c\u76f8\u5173"
                        "\uff08\u534f\u4f5c/\u91cc\u7a0b\u7891\uff09\u3002"
                        "\u5173\u7cfb\u53ef\u80fd\u5728\u8d8b\u5411\u5de5\u5177\u5316\u3002"
                        "\u8bd5\u8bd5\u8868\u8fbe\u611f\u8c22\u3001\u804a\u70b9\u975e\u5de5\u4f5c\u7684\u4e8b\u3001"
                        "\u6216\u56de\u5fc6\u4e00\u4e2a\u5171\u540c\u7ecf\u5386\u3002"
                    )
                else:
                    suggestions.append(
                        "Recent interactions are all collaboration/milestone (pure work). "
                        "The relationship may be trending toward tool-mode. "
                        "Consider adding warmth: express appreciation, recall a shared moment, "
                        "or ask about something non-work."
                    )

    # Build output
    if suggestions:
        advice_lines = [
            f"\n\n## Check-in Analysis \u2014 {now_local()} [rule-based]\n",
        ]
        for s in suggestions:
            advice_lines.append(f"- \U0001f4a1 {s}")
        advice_lines.append("")
        advice = "\n".join(advice_lines)
    else:
        if lang == "zh":
            advice = (
                f"\n\n## Check-in Analysis \u2014 {now_local()}\n\n"
                f"\u4e92\u52a8\u6a21\u5f0f\u770b\u8d77\u6765\u5f88\u5065\u5eb7\uff0c"
                f"\u4e0d\u9700\u8981\u989d\u5916\u884c\u52a8\u3002\n\n"
            )
        else:
            advice = (
                f"\n\n## Check-in Analysis \u2014 {now_local()}\n\n"
                f"Interaction patterns look healthy. No action needed.\n\n"
            )

    replaced = deduplicate_checkin(draft_path, advice)

    print(f"[check-in] Analyzed {len(entries)} timeline entries")
    if suggestions:
        print(f"[check-in] {len(suggestions)} suggestion(s):")
        for s in suggestions:
            print(f"  \u2192 {s[:80]}")
    else:
        print("[check-in] Interaction patterns look healthy.")
    print(f"[check-in] Appended to: {draft_path}")

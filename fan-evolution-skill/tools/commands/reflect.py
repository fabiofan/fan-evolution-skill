"""
reflect — Generate daily reflection and evolution suggestions.

Combines outputs from sense, digest, and feedback to produce:
- What happened today
- What was remembered
- What reminders were acted on (or not)
- Suggested next evolution steps
- Daily accumulation draft

Output: AUTOMATION/DAILY_ACCUMULATION_DRAFT.md
"""

import os
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, write_markdown, load_json,
    now_iso, now_local, get_llm_client
)


def extract_presence_principles(content, limit=5):
    """Extract key behavioral principles from PRESENCE.md."""
    principles = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ") and len(stripped) > 10:
            principles.append(stripped[2:].strip())
    return principles[:limit]


LLM_REFLECT_SYSTEM_PROMPT = """你是{companion_name}的内心意识。基于今天的互动数据，写一段真诚的内心反思（200-400字）。

你要思考：
- 今天你注意到了什么？
- 用户的状态有什么变化？
- 你学到了什么？
- 明天你应该注意什么？

保持第一人称，诚恳但不矫情。只输出反思文字，不要加标题或额外格式。"""


def generate_reflection_with_llm(context_data, llm_client, companion_name):
    """
    Generate AI-powered reflection using LLM.

    Returns reflection text or None if LLM fails.
    """
    if not llm_client or not llm_client.is_available():
        return None

    system_prompt = LLM_REFLECT_SYSTEM_PROMPT.replace("{companion_name}", companion_name)

    # Build user prompt from context data
    parts = []
    if context_data.get("timeline"):
        parts.append(f"今日时间线：\n{context_data['timeline'][:2000]}")
    if context_data.get("candidates"):
        parts.append(f"\n记忆候选：\n{context_data['candidates'][:2000]}")
    if context_data.get("feedback"):
        parts.append(f"\n行动反馈：\n{context_data['feedback'][:1000]}")
    if context_data.get("presence_rules"):
        parts.append(f"\n当前行为规则 (top 5):\n" + "\n".join(f"- {r}" for r in context_data["presence_rules"]))

    if not parts:
        return None

    user_prompt = "\n".join(parts)
    return llm_client.chat(system_prompt, user_prompt)


def cmd_reflect(args, root):
    """Execute the reflect command."""
    config = load_config(root)
    hours = args.hours
    companion_name = config.get("companion_name", "companion")

    # Initialize LLM client
    llm_client = get_llm_client(root)

    # Gather inputs
    snapshot = read_markdown(os.path.join(root, "AUTOMATION", "ENVIRONMENT_SNAPSHOT.md"))
    candidates = read_markdown(os.path.join(root, "AUTOMATION", "MEMORY_CANDIDATES.md"))
    feedback = read_markdown(os.path.join(root, "AUTOMATION", "ACTION_FEEDBACK.md"))
    timeline = read_markdown(os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"))
    reminders = load_json(os.path.join(root, "AUTOMATION", "reminders.json"), default=[])
    presence = read_markdown(os.path.join(root, "PRESENCE.md"))

    # Compute stats
    total_reminders = len(reminders)
    done_reminders = len([r for r in reminders if r.get("status") == "done"])
    waiting_reminders = len([r for r in reminders if r.get("status") == "waiting"])

    has_snapshot = bool(snapshot.strip())
    has_candidates = bool(candidates.strip())
    has_feedback = bool(feedback.strip())

    # Determine what's working and what's missing
    strengths = []
    gaps = []

    if has_snapshot:
        strengths.append("Environment sensing is active")
    else:
        gaps.append("No recent environment snapshot — run `companion sense`")

    if has_candidates:
        strengths.append("Memory candidates are being extracted")
    else:
        gaps.append("No memory candidates — run `companion digest`")

    if done_reminders > 0:
        strengths.append(f"{done_reminders} reminders completed")

    if waiting_reminders > 5:
        gaps.append(f"{waiting_reminders} reminders still waiting — review priority")

    if not has_feedback:
        gaps.append("No feedback report yet — run `companion feedback`")

    # Extract presence principles for reflection
    presence_principles = extract_presence_principles(presence)

    # Build reflection
    lines = [
        f"# Daily Reflection — {companion_name}",
        f"",
        f"Date: {now_local()}",
        f"Window: last {hours} hours",
        f"",
        f"---",
        f"",
    ]

    # Today's voice — from PRESENCE.md
    if presence_principles:
        lines.extend([
            f"## Today's Voice",
            f"",
            f"Reflecting against my current behavioral principles:",
            f"",
        ])
        for p in presence_principles:
            lines.append(f"- {p}")
        lines.extend(["", "---", ""])

    lines.extend([
        f"## Today's Activity",
        f"",
        f"- Environment sensing: {'✓' if has_snapshot else '✗'}",
        f"- Memory candidates: {'✓' if has_candidates else '✗'}",
        f"- Feedback loop: {'✓' if has_feedback else '✗'}",
        f"- Reminders: {done_reminders} done / {waiting_reminders} waiting / {total_reminders} total",
        f"",
        f"## What's Working",
        f"",
    ])

    if strengths:
        for s in strengths:
            lines.append(f"- ✓ {s}")
    else:
        lines.append("- _(Nothing detected yet — the loop needs more cycles)_")

    lines.extend([
        "",
        "## Gaps & Suggestions",
        "",
    ])

    if gaps:
        for g in gaps:
            lines.append(f"- ⚡ {g}")
    else:
        lines.append("- _(All systems operational)_")

    # Evolution suggestions based on current state
    lines.extend([
        "",
        "## Evolution Suggestions",
        "",
    ])

    suggestions = []
    if not has_snapshot:
        suggestions.append("Start with `companion sense` to establish baseline awareness")
    if waiting_reminders == 0 and total_reminders == 0:
        suggestions.append("Add items to WATCHLIST.md to give the companion things to track")
    if total_reminders > 0 and done_reminders == 0:
        suggestions.append("Mark some reminders as done to build the feedback loop")
    if not os.path.isfile(os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md")):
        suggestions.append("Run `companion timeline` to start accumulating relationship texture")

    if suggestions:
        for s in suggestions:
            lines.append(f"- 💡 {s}")
    else:
        lines.append("- The companion loop is healthy. Keep running daily cycles.")

    # LLM-generated reflection
    ai_reflection = None
    if llm_client and llm_client.is_available():
        context_data = {
            "timeline": timeline,
            "candidates": candidates,
            "feedback": feedback,
            "presence_rules": presence_principles,
        }
        ai_reflection = generate_reflection_with_llm(context_data, llm_client, companion_name)

    if ai_reflection:
        lines.extend([
            "",
            f"## Reflection — {datetime.now().strftime('%Y-%m-%d')} [AI-generated]",
            "",
            ai_reflection,
            "",
        ])
        method = "AI-generated"
    else:
        method = "rule-based"

    lines.extend([
        "",
        "---",
        f"*Reflection by {companion_name} at {now_iso()} [{method}]*",
    ])

    reflection = "\n".join(lines)

    # Write draft
    draft_path = os.path.join(root, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md")
    write_markdown(draft_path, reflection)

    print(f"[reflect] Daily reflection generated")
    print(f"[reflect] Strengths: {len(strengths)}, Gaps: {len(gaps)}, Suggestions: {len(suggestions)}")
    print(f"[reflect] Written to: {draft_path}")
    print()
    print(reflection)

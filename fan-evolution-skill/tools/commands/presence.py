"""
presence — Manage PRESENCE.md behavioral rules.

Commands:
  companion presence --list-rules             List current rules (structured)
  companion presence --add-rule "..."         Add a new rule (with optional --priority, --context)

Maintains dual format:
  - PRESENCE.md (human-readable markdown)
  - AUTOMATION/presence_rules.json (structured, machine-readable)
"""

import os
import sys
import re
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import read_markdown, write_markdown, load_json, save_json, now_iso, now_local, generate_id, ensure_dir


def load_presence_rules(root):
    """Load structured rules from presence_rules.json."""
    rules_path = os.path.join(root, "AUTOMATION", "presence_rules.json")
    return load_json(rules_path, default=[])


def save_presence_rules(root, rules):
    """Save structured rules to presence_rules.json."""
    rules_path = os.path.join(root, "AUTOMATION", "presence_rules.json")
    ensure_dir(os.path.dirname(rules_path))
    save_json(rules_path, rules)


def sync_md_from_rules(root, rules):
    """Regenerate PRESENCE.md from the structured rules list."""
    presence_path = os.path.join(root, "PRESENCE.md")

    lines = [
        "# PRESENCE",
        "",
        f"How I show up in conversation. Updated: {now_local()}",
        "",
        "## Behavioral Rules",
        "",
    ]

    # Sort by priority (high first)
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 3), reverse=True)
    for rule in sorted_rules:
        ctx = rule.get("context", "always")
        priority = rule.get("priority", 3)
        text = rule.get("text", "")
        if ctx != "always":
            lines.append(f"- [{priority}] ({ctx}) {text}")
        else:
            lines.append(f"- [{priority}] {text}")

    lines.append("")
    write_markdown(presence_path, "\n".join(lines))


def extract_rules(content):
    """Extract behavioral rules from PRESENCE.md content (legacy support)."""
    rules = []
    in_rules_section = False

    for line in content.split("\n"):
        stripped = line.strip()
        # Detect rules section (lines starting with - or numbered lists)
        if stripped.startswith("## "):
            in_rules_section = "rule" in stripped.lower() or "behavior" in stripped.lower() or "guideline" in stripped.lower()
            continue
        if in_rules_section and stripped.startswith("- "):
            rules.append(stripped[2:].strip())
        elif not in_rules_section and stripped.startswith("- "):
            # Also pick up any bullet points as potential rules
            rules.append(stripped[2:].strip())

    # If no structured rules found, extract key sentences
    if not rules:
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                if len(stripped) > 10:
                    rules.append(stripped)

    return rules


def get_key_principles(content, limit=5):
    """Extract the top N key principles from PRESENCE.md for reflection use."""
    rules = extract_rules(content)
    return rules[:limit]


def get_key_principles_from_json(root, limit=5):
    """Get top N rules by priority from JSON store."""
    rules = load_presence_rules(root)
    if not rules:
        return []
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 3), reverse=True)
    return [r["text"] for r in sorted_rules[:limit]]


def add_rule(root, rule_text, priority=3, context="always"):
    """Add a new rule to both JSON and markdown."""
    rules = load_presence_rules(root)

    new_rule = {
        "id": generate_id("rule"),
        "text": rule_text,
        "priority": priority,
        "context": context,
        "added_at": now_iso(),
    }
    rules.append(new_rule)

    save_presence_rules(root, rules)
    sync_md_from_rules(root, rules)
    return new_rule


def cmd_presence(args, root):
    """Execute the presence command."""
    presence_path = os.path.join(root, "PRESENCE.md")

    if args.list_rules:
        rules = load_presence_rules(root)

        # Fallback: if JSON is empty, try to parse from markdown
        if not rules:
            content = read_markdown(presence_path)
            if not content.strip():
                print("[presence] PRESENCE.md is empty or not found.")
                print(f"[presence] Expected at: {presence_path}")
                return
            text_rules = extract_rules(content)
            if not text_rules:
                print("[presence] No rules found.")
                return
            print(f"[presence] Current behavioral rules ({len(text_rules)}) — from markdown (no JSON yet):")
            print()
            for i, rule in enumerate(text_rules, 1):
                print(f"  {i}. {rule}")
            return

        # Structured output from JSON
        sorted_rules = sorted(rules, key=lambda r: r.get("priority", 3), reverse=True)
        print(f"[presence] Current behavioral rules ({len(sorted_rules)}):")
        print()
        for i, rule in enumerate(sorted_rules, 1):
            ctx = rule.get("context", "always")
            priority = rule.get("priority", 3)
            ctx_str = f" ({ctx})" if ctx != "always" else ""
            print(f"  {i}. [P{priority}]{ctx_str} {rule['text']}")
        print()

    elif args.add_rule:
        priority = getattr(args, 'priority', 3) or 3
        context = getattr(args, 'context', "always") or "always"
        new_rule = add_rule(root, args.add_rule, priority=priority, context=context)
        print(f"[presence] Added rule: {args.add_rule}")
        print(f"[presence] Priority: {priority}, Context: {context}")
        print(f"[presence] ID: {new_rule['id']}")
        print(f"[presence] Updated: {presence_path} + AUTOMATION/presence_rules.json")

    else:
        # Default: show summary
        rules = load_presence_rules(root)
        if rules:
            sorted_rules = sorted(rules, key=lambda r: r.get("priority", 3), reverse=True)
            print(f"[presence] PRESENCE rules: {len(rules)} total")
            print(f"[presence] Top principles:")
            for r in sorted_rules[:3]:
                print(f"  • {r['text'][:80]}")
        else:
            content = read_markdown(presence_path)
            if not content.strip():
                print("[presence] PRESENCE.md not found. Run `companion init` first.")
                return
            text_rules = extract_rules(content)
            print(f"[presence] PRESENCE.md loaded ({len(content)} chars)")
            print(f"[presence] Rules found: {len(text_rules)}")
            if text_rules:
                print(f"[presence] Top principles:")
                for r in text_rules[:3]:
                    print(f"  • {r[:80]}")

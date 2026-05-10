"""
memory-decay — Intelligent tiered memory management.

Three-layer memory model:
  - core: Never decays. High-value blocks (decision/milestone/preference/emotion
    with score>=6, or any block referenced >=3 times).
  - active: Normal blocks. Referenced blocks reset their timer. If referenced
    >=3 times within decay_days, auto-upgrade to core.
  - fading: Low-value blocks (context/other with score<4). Only moved to cold
    storage after decay_days without any reference.

Supports --dry-run to preview without writing.
"""

import os
import re
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_config, read_markdown, write_markdown, append_markdown,
    now_iso, now_local, ensure_dir
)


# Categories considered high-value for core tier
CORE_CATEGORIES = {"decision", "milestone", "preference", "emotion"}
# Categories considered low-value for fading tier
FADING_CATEGORIES = {"context", "other"}


def parse_memory_blocks(content):
    """Parse MEMORY.md into structured blocks with IDs, metadata, and text."""
    blocks = []
    block_pattern = re.compile(
        r"(<!-- MEMORY_BLOCK id=(\S+) date=(\S+)(.*?)-->)(.*?)(<!-- /MEMORY_BLOCK -->)",
        re.DOTALL
    )
    for match in block_pattern.finditer(content):
        attrs_str = match.group(4)
        block = {
            "id": match.group(2),
            "date": match.group(3),
            "full_match": match.group(0),
            "content": match.group(5).strip(),
            "open_tag": match.group(1),
            "attrs_str": attrs_str,
        }
        # Parse optional metadata from attrs
        tier_match = re.search(r"tier=(\S+)", attrs_str)
        block["tier"] = tier_match.group(1) if tier_match else "active"

        ref_match = re.search(r"reference_count=(\d+)", attrs_str)
        block["reference_count"] = int(ref_match.group(1)) if ref_match else 0

        last_ref_match = re.search(r"last_referenced=(\S+)", attrs_str)
        block["last_referenced"] = last_ref_match.group(1) if last_ref_match else None

        score_match = re.search(r"score=(\d+)", attrs_str)
        block["score"] = int(score_match.group(1)) if score_match else 0

        # Extract category from content (e.g. ### [decision] ...)
        cat_match = re.search(r"###\s+\[(\w+)\]", block["content"])
        block["category"] = cat_match.group(1).lower() if cat_match else "other"

        # Parse source
        source_match = re.search(r"source=(\S+)", attrs_str)
        block["source"] = source_match.group(1) if source_match else ""

        blocks.append(block)
    return blocks


def extract_key_nouns(text):
    """Extract key nouns from text for fallback matching.

    English: capitalized words (excluding sentence-start), quoted words,
             camelCase/PascalCase technical terms.
    Chinese: quoted content, digit+Chinese combos (e.g. "15年"),
             standalone English words within Chinese text.
    """
    nouns = set()
    if not text:
        return nouns

    # English: PascalCase / camelCase (at least one lowercase followed by uppercase)
    for m in re.finditer(r'\b([a-z]+[A-Z][a-zA-Z]*|[A-Z][a-z]+[A-Z][a-zA-Z]*)\b', text):
        nouns.add(m.group(0))

    # English: Capitalized words NOT at sentence start
    # Split into sentences, skip first word of each
    _quote_bracket_chars = '"\'\'\u201c\u201d\u300c\u300d()[]{}'
    sentences = re.split(r'[.!?。！？]\s*', text)
    for sent in sentences:
        words = sent.split()
        for i, word in enumerate(words):
            clean = word.strip('.,;:!?\'"()[]{}\u201c\u201d\u300c\u300d')
            if not clean or not clean[0].isupper() or not clean.isalpha() or len(clean) < 2:
                continue
            # Skip sentence-start word (index 0) even after stripping quotes
            if i == 0:
                continue
            nouns.add(clean)

    # Quoted content (both English and Chinese quotes)
    for m in re.finditer(r'["\']([^"\']+)["\']', text):
        nouns.add(m.group(1).strip())
    for m in re.finditer(r'[\u201c\u300c]([^\u201d\u300d]+)[\u201d\u300d]', text):
        nouns.add(m.group(1).strip())

    # Chinese: digit + Chinese unit combos like "15年", "3个月"
    # Truncate at the first particle (的了地得过着们) and strip trailing particles
    _particles = set('了的地得过着们')
    for m in re.finditer(r'\d+[\u4e00-\u9fff]+', text):
        combo = m.group(0)
        # Find first particle position (after the digits) and truncate
        digit_end = 0
        for i, ch in enumerate(combo):
            if ch.isdigit():
                digit_end = i + 1
            else:
                break
        chinese_part = combo[digit_end:]
        # Truncate at first particle occurrence
        for i, ch in enumerate(chinese_part):
            if ch in _particles:
                chinese_part = chinese_part[:i]
                break
        combo = combo[:digit_end] + chinese_part
        # Must retain at least digit + 1 Chinese char
        if combo and re.search(r'\d', combo) and re.search(r'[\u4e00-\u9fff]', combo):
            nouns.add(combo)

    # English words embedded in Chinese text (standalone, 2+ chars)
    # Only match when actually adjacent to Chinese characters
    for m in re.finditer(r'(?<=[\u4e00-\u9fff])[A-Za-z]{2,}(?=[\u4e00-\u9fff])', text):
        nouns.add(m.group(0))

    # Filter out very short nouns (single char) and common words
    nouns = {n for n in nouns if len(n) >= 2}
    return nouns


def is_block_referenced(block, reference_texts, combined_refs_lower=None):
    """Check if a block's content appears in reference texts.

    Fast path: first 30 chars of content checked against combined_refs_lower
    (if provided) for O(1) substring lookup, else iterate reference_texts.
    Fallback: key nouns extracted from the block content.
    Note: key-noun fallback only prevents false decay; it does NOT
    increment reference_count (to avoid false upgrades).

    Args:
        block: Memory block dict with 'content' key.
        reference_texts: List of reference text strings.
        combined_refs_lower: Optional pre-computed '\n'.join(reference_texts).lower()
            for fast substring checks. If None, falls back to iterating reference_texts.
    """
    key = block["content"][:30].lower()
    if not key:
        return False

    # Fast path: first 30 chars match
    if combined_refs_lower is not None:
        if key in combined_refs_lower:
            return True
    else:
        for text in reference_texts:
            if key in text.lower():
                return True

    # Fallback: key nouns matching
    nouns = extract_key_nouns(block["content"])
    if not nouns:
        return False
    if combined_refs_lower is None:
        combined_refs_lower = "\n".join(reference_texts).lower()
    for noun in nouns:
        if noun.lower() in combined_refs_lower:
            return True
    return False


def gather_reference_texts(root, days):
    """Gather text from recent archives, conversations, and timeline."""
    texts = []
    cutoff = datetime.now() - timedelta(days=days)

    # Archives
    archive_dir = os.path.join(root, "AUTOMATION", "archive-packages")
    if os.path.isdir(archive_dir):
        for fname in os.listdir(archive_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(archive_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime >= cutoff:
                    texts.append(read_markdown(fpath))
            except OSError:
                continue

    # Conversations
    conversations_dir = os.path.join(root, "AUTOMATION", "conversations")
    if os.path.isdir(conversations_dir):
        for fname in os.listdir(conversations_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(conversations_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime >= cutoff:
                    texts.append(read_markdown(fpath))
            except OSError:
                continue

    # Timeline
    timeline_path = os.path.join(root, "AUTOMATION", "RELATIONSHIP_TIMELINE.md")
    if os.path.isfile(timeline_path):
        texts.append(read_markdown(timeline_path))

    return texts


def determine_initial_tier(category, score):
    """Determine the initial tier for a new memory block."""
    if category in CORE_CATEGORIES and score >= 6:
        return "core"
    if category in FADING_CATEGORIES and score < 4:
        return "fading"
    return "active"


def rebuild_block_tag(block):
    """Rebuild the opening MEMORY_BLOCK comment tag with updated metadata."""
    parts = [f"<!-- MEMORY_BLOCK id={block['id']} date={block['date']}"]
    if block.get("source"):
        parts.append(f" source={block['source']}")
    parts.append(f" tier={block['tier']}")
    parts.append(f" reference_count={block['reference_count']}")
    if block.get("last_referenced"):
        parts.append(f" last_referenced={block['last_referenced']}")
    if block.get("score", 0) > 0:
        parts.append(f" score={block['score']}")
    parts.append(" -->")
    return "".join(parts)


def rebuild_full_block(block):
    """Rebuild a full memory block string with updated metadata."""
    open_tag = rebuild_block_tag(block)
    return f"{open_tag}\n{block['content']}\n<!-- /MEMORY_BLOCK -->"


def cmd_memory_decay(args, root):
    """Execute the memory-decay command."""
    config = load_config(root)
    dry_run = args.dry_run

    mem_gov = config.get("memory_governance", {})
    decay_days = mem_gov.get("decay_days", 30)

    memory_path = os.path.join(root, "MEMORY.md")
    archive_path = os.path.join(root, "AUTOMATION", "MEMORY_ARCHIVE.md")

    content = read_markdown(memory_path)
    if not content.strip():
        print("[memory-decay] MEMORY.md is empty.")
        return

    blocks = parse_memory_blocks(content)
    if not blocks:
        print("[memory-decay] No memory blocks found in MEMORY.md.")
        return

    # Gather reference texts from the decay window
    reference_texts = gather_reference_texts(root, decay_days)
    # Pre-compute combined lowercase for O(1) substring lookups
    combined_refs_lower = "\n".join(reference_texts).lower()
    today = now_iso().split("T")[0]

    # Phase 1: Update reference counts and tiers
    upgraded = []
    to_archive = []
    kept = []

    for block in blocks:
        # Count real references: how many reference_texts contain this block's key
        key = block["content"][:30].lower()
        real_ref_count = 0
        if key:
            for text in reference_texts:
                if key in text.lower():
                    real_ref_count += 1
        # Update reference_count to reflect true frequency (never regress)
        block["reference_count"] = max(block["reference_count"], real_ref_count)

        referenced = is_block_referenced(block, reference_texts, combined_refs_lower=combined_refs_lower)

        if referenced:
            block["last_referenced"] = today

        # Tier logic
        if block["tier"] == "core":
            # Core never decays
            kept.append(block)
        elif block["tier"] == "active":
            if referenced and block["reference_count"] >= 3:
                # Upgrade to core
                block["tier"] = "core"
                upgraded.append(block)
                kept.append(block)
            elif referenced:
                # Reset timer (last_referenced already updated)
                kept.append(block)
            else:
                # Not referenced but still active — keep
                kept.append(block)
        elif block["tier"] == "fading":
            if referenced:
                # Referenced fading block — promote to active, reset timer
                block["tier"] = "active"
                kept.append(block)
            else:
                # Check if it's been too long since last reference
                last_ref = block.get("last_referenced")
                block_date = block.get("date", "")
                ref_date_str = last_ref or block_date.split("T")[0] if block_date else None

                should_archive = False
                if ref_date_str:
                    try:
                        ref_date = datetime.strptime(ref_date_str[:10], "%Y-%m-%d")
                        if (datetime.now() - ref_date) > timedelta(days=decay_days):
                            should_archive = True
                    except ValueError:
                        should_archive = True
                else:
                    should_archive = True

                if should_archive:
                    to_archive.append(block)
                else:
                    kept.append(block)
        else:
            # Unknown tier — treat as active
            block["tier"] = "active"
            kept.append(block)

        # Note: No separate auto-promote catch-all needed here.
        # If reference_count >= 3 via real_ref_count, the fast path in
        # is_block_referenced will always return True (same key substring),
        # so the tier=="active" branch above already handles the upgrade.

    print(f"[memory-decay] {'DRY RUN — ' if dry_run else ''}Scanning {len(blocks)} blocks")
    print(f"[memory-decay] Decay window: {decay_days} days")
    print(f"[memory-decay] Core (never decay): {sum(1 for b in kept if b['tier'] == 'core')}")
    print(f"[memory-decay] Active: {sum(1 for b in kept if b['tier'] == 'active')}")
    print(f"[memory-decay] Fading (still within window): {sum(1 for b in kept if b['tier'] == 'fading')}")
    print(f"[memory-decay] To archive (cold storage): {len(to_archive)}")
    if upgraded:
        print(f"[memory-decay] Upgraded to core: {len(upgraded)}")
        for b in upgraded:
            print(f"  ↑ {b['id']}: referenced {b['reference_count']} times")

    if to_archive:
        print()
        for block in to_archive:
            print(f"  → archive: {block['id']}: {block['content'][:60]}")

    if dry_run:
        print(f"\n[memory-decay] DRY RUN complete. {len(to_archive)} blocks would be archived.")
        return

    # Write archived blocks to cold storage
    if to_archive:
        ensure_dir(os.path.dirname(archive_path))
        archive_entry = f"\n## Archived at {now_local()}\n\n"
        for block in to_archive:
            archive_entry += f"{block['full_match']}\n\n"
        append_markdown(archive_path, archive_entry)

    # Rebuild MEMORY.md with updated metadata for kept blocks
    # Strategy: replace each block's full_match with the rebuilt version
    updated_content = content
    for block in kept:
        new_block = rebuild_full_block(block)
        updated_content = updated_content.replace(block["full_match"], new_block)

    # Remove archived blocks
    for block in to_archive:
        updated_content = updated_content.replace(block["full_match"], "")

    # Clean up multiple blank lines
    updated_content = re.sub(r"\n{4,}", "\n\n\n", updated_content)
    write_markdown(memory_path, updated_content)

    print(f"\n[memory-decay] Updated MEMORY.md ({len(kept)} blocks remain)")
    if to_archive:
        print(f"[memory-decay] Archived {len(to_archive)} blocks to: {archive_path}")

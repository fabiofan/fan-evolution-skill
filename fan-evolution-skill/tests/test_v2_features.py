"""
Tests for v2.0.0 features:
- Implicit signal extraction in digest
- Time decay and frequency scoring in curate
- Memory decay logic
- Check-in analysis logic
- Presence JSON dual-format
- Auto-confirm threshold in memory-apply
- Version number

Run with:
  python3 -m unittest discover tests/
  python3 -m pytest tests/test_v2_features.py
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timedelta

# Add tools/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from utils import VERSION
from commands.digest import extract_candidates_from_archive, IMPLICIT_SIGNAL_PATTERNS
from commands.curate import (
    parse_candidates, score_candidate, compute_frequency_bonus,
    compute_time_decay, extract_date_from_source
)
from commands.memory_decay import parse_memory_blocks, is_block_referenced
from commands.checkin import parse_timeline_entries
from commands.presence import load_presence_rules, add_rule


class TestVersion(unittest.TestCase):
    """Test version number."""

    def test_version_is_3_0_0(self):
        """VERSION should be 3.0.0."""
        self.assertEqual(VERSION, "3.0.0")


class TestImplicitSignals(unittest.TestCase):
    """Test implicit signal detection in digest."""

    def test_resignation_english(self):
        """Should detect English resignation signals."""
        content = "Whatever, I don't care anymore about this approach."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "resignation" for c in candidates))

    def test_resignation_chinese(self):
        """Should detect Chinese resignation signals."""
        content = "算了，就这样吧，不改了。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "resignation" for c in candidates))

    def test_delegation_english(self):
        """Should detect English delegation signals."""
        content = "Your call on the architecture, I'll leave it to you."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "delegation" for c in candidates))

    def test_delegation_chinese(self):
        """Should detect Chinese delegation signals."""
        content = "这个你看着办吧，我信任你的判断。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "delegation" for c in candidates))

    def test_fatigue_english(self):
        """Should detect English fatigue signals."""
        content = "I'm so tired of debugging this issue all day."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "fatigue" for c in candidates))

    def test_fatigue_chinese(self):
        """Should detect Chinese fatigue signals."""
        content = "累了，今天真的够了，不想再看代码。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "fatigue" for c in candidates))

    def test_curiosity_english(self):
        """Should detect English curiosity signals."""
        content = "That's really interesting, I wonder why it works this way."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "curiosity" for c in candidates))

    def test_curiosity_chinese(self):
        """Should detect Chinese curiosity signals."""
        content = "有意思，为什么这个架构能扛住这么大的并发？"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "curiosity" for c in candidates))

    def test_boundary_english(self):
        """Should detect English boundary signals."""
        content = "Stop sending me notifications about this, don't do that."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "boundary" for c in candidates))

    def test_boundary_chinese(self):
        """Should detect Chinese boundary signals."""
        content = "别再提这件事了，不要再发消息给我了。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "boundary" for c in candidates))

    def test_context_window_captures_adjacent(self):
        """Should capture adjacent lines as context."""
        content = "This is line one about the project setup.\nI decided to use Rust for performance.\nThis is the follow-up explanation of why."
        candidates = extract_candidates_from_archive(content, "test.md")
        # Should have the signal line + context lines
        context_items = [c for c in candidates if c.get("category") == "context"]
        self.assertTrue(len(context_items) > 0)

    def test_context_has_parent_reference(self):
        """Context items should reference their parent."""
        content = "Setup the development environment.\nI decided to switch to the new toolchain.\nThe migration path looks clear."
        candidates = extract_candidates_from_archive(content, "test.md")
        context_items = [c for c in candidates if c.get("category") == "context"]
        for ctx in context_items:
            self.assertIn("context_of", ctx)


class TestCurateV2(unittest.TestCase):
    """Test curate v2 features: frequency, time decay, project relevance."""

    def test_extract_date_from_source_standard(self):
        """Should extract date from standard filename."""
        date = extract_date_from_source("2025-05-08_143022.md")
        self.assertIsNotNone(date)
        self.assertEqual(date.year, 2025)
        self.assertEqual(date.month, 5)
        self.assertEqual(date.day, 8)

    def test_extract_date_from_source_none(self):
        """Should return None for non-date filenames."""
        date = extract_date_from_source("random_archive.md")
        self.assertIsNone(date)

    def test_extract_date_from_source_empty(self):
        """Should handle None source."""
        date = extract_date_from_source(None)
        self.assertIsNone(date)

    def test_frequency_bonus_single(self):
        """Single occurrence should give no frequency bonus."""
        candidates = [
            {"text": "I decided to use TypeScript for the new project", "category": "decision", "weight": 5},
            {"text": "Something completely different here", "category": "insight", "weight": 4},
        ]
        bonus = compute_frequency_bonus(candidates[0], candidates)
        self.assertEqual(bonus, 0)

    def test_frequency_bonus_repeated(self):
        """Repeated similar content should give frequency bonus."""
        candidates = [
            {"text": "I decided to use TypeScript for this", "category": "decision", "weight": 5},
            {"text": "I decided to use TypeScript for this", "category": "decision", "weight": 5},
            {"text": "I decided to use TypeScript for this", "category": "decision", "weight": 5},
        ]
        bonus = compute_frequency_bonus(candidates[0], candidates)
        self.assertEqual(bonus, 4)  # (3-1) * 2

    def test_time_decay_recent(self):
        """Recent sources should not be penalized."""
        today = datetime.now().strftime("%Y-%m-%d")
        candidate = {"text": "test", "source": f"{today}_120000.md"}
        decay = compute_time_decay(candidate)
        self.assertEqual(decay, 0)

    def test_time_decay_old(self):
        """Sources older than 7 days should get -2."""
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        candidate = {"text": "test", "source": f"{old_date}_120000.md"}
        decay = compute_time_decay(candidate)
        self.assertEqual(decay, -2)

    def test_time_decay_medium(self):
        """Sources 3-7 days old should get -1."""
        med_date = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        candidate = {"text": "test", "source": f"{med_date}_120000.md"}
        decay = compute_time_decay(candidate)
        self.assertEqual(decay, -1)

    def test_score_with_all_candidates(self):
        """score_candidate should accept all_candidates parameter."""
        candidates = [
            {"text": "I decided to use TypeScript for this project work", "category": "decision", "weight": 5},
        ]
        score = score_candidate(candidates[0], all_candidates=candidates)
        self.assertIsInstance(score, int)
        self.assertGreater(score, 0)


class TestMemoryDecay(unittest.TestCase):
    """Test memory decay logic."""

    def test_parse_memory_blocks(self):
        """Should parse memory blocks from content."""
        content = """# Memory

<!-- MEMORY_BLOCK id=mem-001 date=2025-05-01T00:00:00Z source=prop-001 -->
### [decision] 2025-05-01

Decided to use Rust.

<!-- /MEMORY_BLOCK -->

<!-- MEMORY_BLOCK id=mem-002 date=2025-05-05T00:00:00Z source=prop-002 -->
### [milestone] 2025-05-05

Shipped v1.0

<!-- /MEMORY_BLOCK -->
"""
        blocks = parse_memory_blocks(content)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["id"], "mem-001")
        self.assertEqual(blocks[1]["id"], "mem-002")
        self.assertIn("Decided to use Rust", blocks[0]["content"])
        self.assertIn("Shipped v1.0", blocks[1]["content"])

    def test_parse_memory_blocks_empty(self):
        """Should return empty list for no blocks."""
        blocks = parse_memory_blocks("# Memory\n\nNo blocks here.")
        self.assertEqual(len(blocks), 0)

    def test_is_block_referenced_yes(self):
        """Should detect when block content is referenced."""
        block = {"content": "Decided to use Rust for the backend"}
        references = ["In our last meeting, Decided to use Rust for the backend was confirmed."]
        self.assertTrue(is_block_referenced(block, references))

    def test_is_block_referenced_no(self):
        """Should detect when block content is NOT referenced."""
        block = {"content": "Old decision about Python framework"}
        references = ["Today we talked about the new Rust migration."]
        self.assertFalse(is_block_referenced(block, references))

    def test_is_block_referenced_empty_content(self):
        """Should handle empty block content."""
        block = {"content": ""}
        references = ["Some text here"]
        self.assertFalse(is_block_referenced(block, references))


class TestCheckin(unittest.TestCase):
    """Test check-in analysis logic."""

    def test_parse_timeline_entries_basic(self):
        """Should parse timeline entries with dates and types."""
        content = """# Relationship Timeline

## 2025-05-08 14:30:00 — Daily Timeline Entry

Events detected: 3

- **gratitude**: Thank you so much for helping!
- **collaboration**: We refactored the auth module together.
- **milestone**: First deployment without issues!

---
"""
        entries = parse_timeline_entries(content)
        self.assertEqual(len(entries), 3)
        types = [e["type"] for e in entries]
        self.assertIn("gratitude", types)
        self.assertIn("collaboration", types)
        self.assertIn("milestone", types)

    def test_parse_timeline_entries_empty(self):
        """Should return empty list for empty content."""
        entries = parse_timeline_entries("")
        self.assertEqual(len(entries), 0)

    def test_parse_timeline_entries_no_events(self):
        """Should return empty for content without events."""
        content = "# Timeline\n\nJust some text, no events.\n"
        entries = parse_timeline_entries(content)
        self.assertEqual(len(entries), 0)

    def test_parse_timeline_multiple_dates(self):
        """Should handle multiple date sections."""
        content = """## 2025-05-06 10:00:00 — Daily Timeline Entry

- **collaboration**: Worked on the API.

## 2025-05-08 14:30:00 — Daily Timeline Entry

- **gratitude**: Thanks for the help!
"""
        entries = parse_timeline_entries(content)
        self.assertEqual(len(entries), 2)
        # Check dates are different
        dates = set(e["date"].day for e in entries)
        self.assertEqual(len(dates), 2)


class TestPresenceV2(unittest.TestCase):
    """Test presence v2 JSON dual-format."""

    def test_load_rules_empty(self):
        """Should return empty list when no rules file exists."""
        rules = load_presence_rules("/nonexistent/path")
        self.assertEqual(rules, [])

    def test_add_rule_creates_structure(self):
        """Should create structured rule with priority and context."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create minimal config
            config = {"companion_name": "test"}
            config_path = os.path.join(tmp_dir, "companion_config.json")
            with open(config_path, "w") as f:
                json.dump(config, f)

            # Create AUTOMATION dir
            os.makedirs(os.path.join(tmp_dir, "AUTOMATION"))

            new_rule = add_rule(tmp_dir, "Always acknowledge emotions first", priority=5, context="always")
            self.assertEqual(new_rule["text"], "Always acknowledge emotions first")
            self.assertEqual(new_rule["priority"], 5)
            self.assertEqual(new_rule["context"], "always")
            self.assertTrue(new_rule["id"].startswith("rule-"))
            self.assertIn("added_at", new_rule)

            # Verify it was saved
            rules = load_presence_rules(tmp_dir)
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0]["text"], "Always acknowledge emotions first")

    def test_add_multiple_rules_sorted_by_priority(self):
        """Should maintain multiple rules sorted by priority."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = {"companion_name": "test"}
            config_path = os.path.join(tmp_dir, "companion_config.json")
            with open(config_path, "w") as f:
                json.dump(config, f)
            os.makedirs(os.path.join(tmp_dir, "AUTOMATION"))

            add_rule(tmp_dir, "Low priority rule", priority=1, context="always")
            add_rule(tmp_dir, "High priority rule", priority=5, context="when_tired")
            add_rule(tmp_dir, "Medium priority rule", priority=3, context="always")

            rules = load_presence_rules(tmp_dir)
            self.assertEqual(len(rules), 3)

            # Check PRESENCE.md was created with sorted rules
            with open(os.path.join(tmp_dir, "PRESENCE.md")) as f:
                presence_content = f.read()
            self.assertIn("High priority rule", presence_content)
            self.assertIn("when_tired", presence_content)


class TestMemoryApplyAuto(unittest.TestCase):
    """Test memory-apply auto-confirm logic."""

    def test_parse_proposals_with_score(self):
        """Should parse score from proposals."""
        from commands.memory_apply import parse_proposals
        content = """### Proposal 1: prop-20250508-abc123

- **Category**: decision
- **Score**: 8
- **Content**: Decided to use Rust
- **Status**: pending
"""
        proposals = parse_proposals(content)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["score"], 8)
        self.assertEqual(proposals[0]["status"], "pending")

    def test_parse_proposals_without_score(self):
        """Should handle proposals without score field (default 0)."""
        from commands.memory_apply import parse_proposals
        content = """### Proposal 1: prop-20250508-abc123

- **Category**: decision
- **Content**: Decided to use Rust
- **Status**: pending
"""
        proposals = parse_proposals(content)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["score"], 0)


if __name__ == "__main__":
    unittest.main()

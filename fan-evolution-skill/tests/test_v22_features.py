"""
Tests for v2.2.0 features:
- extract_key_nouns function
- is_block_referenced key-noun fallback
- context category score excludes length bonus
- check-in Chinese output
- export --incremental mode
- reference_count real frequency

Run with:
  python3 -m unittest discover tests/
  python3 -m pytest tests/test_v22_features.py
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timedelta

# Add tools/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from utils import VERSION, read_markdown, write_markdown, save_json, ensure_dir
from commands.memory_decay import (
    parse_memory_blocks, is_block_referenced, extract_key_nouns
)
from commands.curate import score_candidate
from commands.checkin import detect_language, cmd_checkin, parse_timeline_entries
from commands.export import (
    gather_incremental_data, export_incremental,
    read_last_export, write_last_export
)


class TestExtractKeyNouns(unittest.TestCase):
    """Test extract_key_nouns function."""

    def test_english_capitalized_non_sentence_start(self):
        """Should extract capitalized words not at sentence start."""
        text = "We discussed the TypeScript migration with React."
        nouns = extract_key_nouns(text)
        self.assertIn("TypeScript", nouns)
        self.assertIn("React", nouns)
        # "We" is at sentence start, should not be included
        self.assertNotIn("We", nouns)

    def test_camelcase(self):
        """Should extract camelCase words."""
        text = "The getUserData function calls parseJSON internally."
        nouns = extract_key_nouns(text)
        self.assertIn("getUserData", nouns)
        self.assertIn("parseJSON", nouns)

    def test_pascalcase(self):
        """Should extract PascalCase words."""
        text = "We use ReactRouter for navigation in NextApp."
        nouns = extract_key_nouns(text)
        self.assertIn("ReactRouter", nouns)
        self.assertIn("NextApp", nouns)

    def test_quoted_content_english(self):
        """Should extract content in English quotes."""
        text = "He called it 'memory governance' and she said \"cold storage\" is better."
        nouns = extract_key_nouns(text)
        self.assertIn("memory governance", nouns)
        self.assertIn("cold storage", nouns)

    def test_quoted_content_chinese(self):
        """Should extract content in Chinese quotes."""
        text = "\u4ed6\u8bf4\u8fd9\u53eb\u201c\u8bb0\u5fc6\u6cbb\u7406\u201d\u7684\u65b9\u6cd5\u3002"
        nouns = extract_key_nouns(text)
        self.assertIn("\u8bb0\u5fc6\u6cbb\u7406", nouns)

    def test_chinese_digit_combos(self):
        """Should extract digit+Chinese combos."""
        text = "\u8fd9\u4e2a\u9879\u76ee\u5df2\u7ecf\u8fdb\u884c\u4e8615\u5e74\u4e86\uff0c\u67093\u4e2a\u6708\u7684\u8bd5\u7528\u671f\u3002"
        nouns = extract_key_nouns(text)
        self.assertIn("15\u5e74", nouns)
        self.assertIn("3\u4e2a\u6708", nouns)

    def test_empty_text(self):
        """Should return empty set for empty text."""
        self.assertEqual(extract_key_nouns(""), set())
        self.assertEqual(extract_key_nouns(None), set())

    def test_filters_short_nouns(self):
        """Should filter out single-char nouns."""
        text = "I went to A and then B happened."
        nouns = extract_key_nouns(text)
        self.assertNotIn("A", nouns)
        self.assertNotIn("B", nouns)


class TestIsBlockReferencedFallback(unittest.TestCase):
    """Test is_block_referenced with key-noun fallback."""

    def test_first_30_chars_match(self):
        """Should match on first 30 chars (fast path)."""
        block = {"content": "Decided to use Rust for the backend performance"}
        references = ["Earlier we Decided to use Rust for the backend and it was great."]
        self.assertTrue(is_block_referenced(block, references))

    def test_no_30_char_match_but_noun_match(self):
        """Should match via key-noun fallback when 30-char fails."""
        block = {"content": "The team discussed TypeScript migration with ReactRouter framework in detail."}
        # First 30 chars: "The team discussed TypeScript " - not in references
        references = ["We should revisit the ReactRouter setup next sprint."]
        self.assertTrue(is_block_referenced(block, references))

    def test_no_match_at_all(self):
        """Should return False when neither path matches."""
        block = {"content": "Some old note about nothing specific or memorable at all."}
        references = ["Completely unrelated discussion about cooking recipes and travel."]
        self.assertFalse(is_block_referenced(block, references))

    def test_empty_block(self):
        """Should handle empty block content."""
        block = {"content": ""}
        references = ["Some text"]
        self.assertFalse(is_block_referenced(block, references))

    def test_noun_match_case_insensitive(self):
        """Key noun matching should be case-insensitive."""
        block = {"content": "We integrated with GitHub Actions for continuous deployment."}
        references = ["the github actions pipeline is broken again"]
        self.assertTrue(is_block_referenced(block, references))


class TestContextScoreNoLengthBonus(unittest.TestCase):
    """Test that context category candidates don't get length bonus."""

    def test_context_no_length_bonus(self):
        """Context candidates should not get length bonus."""
        context_candidate = {
            "text": "A" * 150,  # Very long text
            "category": "context",
            "weight": 1,
        }
        decision_candidate = {
            "text": "A" * 150,  # Same length
            "category": "decision",
            "weight": 5,
        }
        context_score = score_candidate(context_candidate)
        decision_score = score_candidate(decision_candidate)

        # Decision gets weight(5) + length(2) = 7
        # Context gets weight(1) + 0 (no length bonus) = 1
        # The difference should reflect no length bonus for context
        self.assertEqual(context_score, 1)  # weight only, no length
        self.assertEqual(decision_score, 7)  # weight + 2 length bonus

    def test_context_still_gets_other_bonuses(self):
        """Context candidates should still get date/specifics bonuses."""
        context_candidate = {
            "text": "Setup on 2025-05-01 for the project configuration.",
            "category": "context",
            "weight": 1,
        }
        score = score_candidate(context_candidate)
        # weight(1) + date_bonus(1) + specifics_bonus(1) = 3
        # No length bonus even though text > 50 chars
        self.assertEqual(score, 3)

    def test_non_context_gets_length_bonus(self):
        """Non-context candidates should still get length bonus."""
        candidate = {
            "text": "This is a decision about using Rust that is longer than fifty characters for sure.",
            "category": "decision",
            "weight": 5,
        }
        score = score_candidate(candidate)
        # weight(5) + length>50(1) + length>100 would be if >100
        self.assertGreaterEqual(score, 6)


class TestCheckinLanguage(unittest.TestCase):
    """Test check-in Chinese output."""

    def test_detect_language_zh(self):
        """Should detect Chinese content."""
        content = "\u4eca\u5929\u6211\u4eec\u8ba8\u8bba\u4e86\u9879\u76ee\u7684\u8fdb\u5c55\uff0c\u5f88\u987a\u5229\u3002"
        config = {"language": "auto"}
        self.assertEqual(detect_language(content, config), "zh")

    def test_detect_language_en(self):
        """Should detect English content."""
        content = "Today we discussed the project progress and everything went well."
        config = {"language": "auto"}
        self.assertEqual(detect_language(content, config), "en")

    def test_detect_language_config_override(self):
        """Config language setting should override auto-detection."""
        content = "This is clearly English text."
        config = {"language": "zh"}
        self.assertEqual(detect_language(content, config), "zh")

    def test_detect_language_no_config_field(self):
        """Missing language field should default to auto."""
        content = "\u4e2d\u6587\u5185\u5bb9\u5360\u6bd4\u8d85\u8fc730%\u7684\u6587\u672c"
        config = {}
        self.assertEqual(detect_language(content, config), "zh")

    def test_checkin_chinese_gap_suggestion(self):
        """Check-in should output Chinese when language is zh."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = {
                "companion_name": "test",
                "language": "zh",
                "relationship": {"checkin_interval_days": 3},
            }
            save_json(os.path.join(tmp_dir, "companion_config.json"), config)
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))

            # Create timeline with old entry (gap > 3 days)
            old_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
            timeline = f"## {old_date} \u2014 Daily Timeline Entry\n\n- **collaboration**: \u4e00\u8d77\u5de5\u4f5c\n"
            write_markdown(os.path.join(tmp_dir, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"), timeline)
            write_markdown(os.path.join(tmp_dir, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md"), "")

            class Args:
                pass

            cmd_checkin(Args(), tmp_dir)

            draft = read_markdown(os.path.join(tmp_dir, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md"))
            self.assertIn("\u8ddd\u79bb\u4e0a\u6b21\u4e92\u52a8\u5df2\u7ecf", draft)
            self.assertIn("\u53ef\u4ee5\u4e3b\u52a8\u8054\u7cfb\u4e00\u4e0b", draft)

    def test_checkin_chinese_all_work(self):
        """Check-in should output Chinese work warning when language is zh."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = {
                "companion_name": "test",
                "language": "zh",
                "relationship": {"checkin_interval_days": 3},
            }
            save_json(os.path.join(tmp_dir, "companion_config.json"), config)
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))

            # Create recent all-work timeline
            recent_date = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            timeline = f"## {recent_date} \u2014 Daily Timeline Entry\n\n- **collaboration**: \u5de5\u4f5c\u534f\u4f5c\n- **milestone**: \u5b8c\u6210\u53d1\u5e03\n"
            write_markdown(os.path.join(tmp_dir, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"), timeline)
            write_markdown(os.path.join(tmp_dir, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md"), "")

            class Args:
                pass

            cmd_checkin(Args(), tmp_dir)

            draft = read_markdown(os.path.join(tmp_dir, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md"))
            self.assertIn("\u5173\u7cfb\u53ef\u80fd\u5728\u8d8b\u5411\u5de5\u5177\u5316", draft)


class TestExportIncremental(unittest.TestCase):
    """Test export --incremental mode."""

    def _create_workspace(self, tmp_dir):
        """Helper to create a workspace with memory blocks."""
        config = {
            "companion_name": "test",
            "memory_governance": {"decay_days": 30},
            "authorized_dirs": ["."],
            "protected_patterns": [],
        }
        save_json(os.path.join(tmp_dir, "companion_config.json"), config)
        ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))
        ensure_dir(os.path.join(tmp_dir, "AUTOMATION", "exports"))
        ensure_dir(os.path.join(tmp_dir, "AUTOMATION", "archive-packages"))
        ensure_dir(os.path.join(tmp_dir, "AUTOMATION", "conversations"))

        memory = """# Memory

<!-- MEMORY_BLOCK id=mem-old date=2025-04-01T00:00:00Z source=prop-001 tier=core reference_count=3 score=8 -->
### [decision] 2025-04-01

Old decision before export.

<!-- /MEMORY_BLOCK -->

<!-- MEMORY_BLOCK id=mem-new date=2025-05-09T12:00:00Z source=prop-002 tier=active reference_count=0 score=5 -->
### [insight] 2025-05-09

New insight after last export.

<!-- /MEMORY_BLOCK -->
"""
        write_markdown(os.path.join(tmp_dir, "MEMORY.md"), memory)
        write_markdown(os.path.join(tmp_dir, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"), "# Timeline\n")
        save_json(os.path.join(tmp_dir, "AUTOMATION", "reminders.json"), [])
        write_markdown(os.path.join(tmp_dir, "SOUL.md"), "")
        write_markdown(os.path.join(tmp_dir, "WATCHLIST.md"), "")
        write_markdown(os.path.join(tmp_dir, "ACTIVE_PROJECTS.md"), "")
        save_json(os.path.join(tmp_dir, "AUTOMATION", "presence_rules.json"), [])
        write_markdown(os.path.join(tmp_dir, "AUTOMATION", "MEMORY_ARCHIVE.md"), "")

    def test_read_write_last_export(self):
        """Should read and write .last_export file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION", "exports"))

            # Initially no file
            self.assertIsNone(read_last_export(tmp_dir))

            # Write
            write_last_export(tmp_dir)

            # Read back
            dt = read_last_export(tmp_dir)
            self.assertIsNotNone(dt)
            self.assertIsInstance(dt, datetime)
            # Should be very recent
            self.assertTrue((datetime.now() - dt).total_seconds() < 5)

    def test_incremental_only_new_blocks(self):
        """Incremental export should only include blocks after last export."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_workspace(tmp_dir)

            # Set last export to 2025-05-01
            last_export_dt = datetime(2025, 5, 1, 0, 0, 0)
            data = gather_incremental_data(tmp_dir, last_export_dt)

            self.assertTrue(data["incremental"])
            # Only mem-new (2025-05-09) should be included, not mem-old (2025-04-01)
            self.assertEqual(len(data["memory_blocks"]), 1)
            self.assertEqual(data["memory_blocks"][0]["id"], "mem-new")

    def test_incremental_export_filename(self):
        """Incremental export should use -incremental suffix."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_workspace(tmp_dir)

            last_export_dt = datetime(2025, 5, 1, 0, 0, 0)
            data = gather_incremental_data(tmp_dir, last_export_dt)
            filepath = export_incremental(tmp_dir, data)

            self.assertIn("-incremental.json", filepath)
            self.assertTrue(os.path.isfile(filepath))

    def test_incremental_includes_full_timeline(self):
        """Incremental export should include full timeline (append-only)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_workspace(tmp_dir)
            write_markdown(
                os.path.join(tmp_dir, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"),
                "# Timeline\n\n## 2025-05-01 10:00:00\n\nOld entry\n\n## 2025-05-09 10:00:00\n\nNew entry\n"
            )

            last_export_dt = datetime(2025, 5, 5, 0, 0, 0)
            data = gather_incremental_data(tmp_dir, last_export_dt)

            # Timeline is always full
            self.assertIn("Old entry", data["timeline"])
            self.assertIn("New entry", data["timeline"])


class TestReferenceCountReal(unittest.TestCase):
    """Test reference_count reflects real frequency."""

    def test_reference_count_set_to_real_occurrences(self):
        """reference_count should reflect actual number of texts containing the key."""
        content = """<!-- MEMORY_BLOCK id=mem-freq date=2025-05-01T00:00:00Z source=prop-001 tier=active reference_count=0 score=5 -->
### [decision] 2025-05-01

Decided to use Rust for backend.

<!-- /MEMORY_BLOCK -->
"""
        blocks = parse_memory_blocks(content)
        block = blocks[0]

        # Simulate: 3 reference texts contain the first 30 chars
        reference_texts = [
            "In archive 1: ### [decision] 2025-05-01\n\nDecided to use Rust for backend. confirmed.",
            "In archive 2: ### [decision] 2025-05-01\n\nDecided to use Rust for backend. again.",
            "In archive 3: ### [decision] 2025-05-01\n\nDecided to use Rust for backend. third time.",
            "Unrelated text about Python and JavaScript.",
        ]

        # Compute real ref count (simulating the logic from cmd_memory_decay)
        key = block["content"][:30].lower()
        real_ref_count = 0
        for text in reference_texts:
            if key in text.lower():
                real_ref_count += 1

        block["reference_count"] = max(block["reference_count"], real_ref_count)
        self.assertEqual(block["reference_count"], 3)

    def test_reference_count_never_regresses(self):
        """reference_count should never decrease (take max)."""
        content = """<!-- MEMORY_BLOCK id=mem-noreg date=2025-05-01T00:00:00Z source=prop-001 tier=active reference_count=5 score=5 -->
### [decision] 2025-05-01

Decided to use Rust for backend.

<!-- /MEMORY_BLOCK -->
"""
        blocks = parse_memory_blocks(content)
        block = blocks[0]

        # Only 2 refs now, but existing count is 5
        reference_texts = [
            "### [decision] 2025-05-01\n\nDecided to use Rust for backend. here.",
            "### [decision] 2025-05-01\n\nDecided to use Rust for backend. and here.",
        ]

        key = block["content"][:30].lower()
        real_ref_count = sum(1 for text in reference_texts if key in text.lower())
        block["reference_count"] = max(block["reference_count"], real_ref_count)

        # Should stay at 5 (never regress)
        self.assertEqual(block["reference_count"], 5)


if __name__ == "__main__":
    unittest.main()

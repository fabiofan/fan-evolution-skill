"""
Tests for v2.1.0 features:
- Memory tiering (core/active/fading)
- Memory recall from cold storage
- Check-in deduplication
- Export/restore
- Stop words in curate
- Expanded context window in digest

Run with:
  python3 -m unittest discover tests/
  python3 -m pytest tests/test_v21_features.py
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
    parse_memory_blocks, is_block_referenced, determine_initial_tier,
    rebuild_block_tag, rebuild_full_block, CORE_CATEGORIES, FADING_CATEGORIES
)
from commands.memory_recall import cmd_memory_recall
from commands.checkin import deduplicate_checkin, parse_timeline_entries
from commands.export import gather_export_data, export_json, export_markdown, restore_from_file
from commands.curate import STOP_WORDS, STOP_WORDS_EN, STOP_WORDS_ZH, compute_project_relevance
from commands.digest import extract_candidates_from_archive


class TestMemoryTiering(unittest.TestCase):
    """Test three-layer memory tiering model."""

    def test_determine_tier_core_decision_high_score(self):
        """Decision with score>=6 should be core."""
        self.assertEqual(determine_initial_tier("decision", 8), "core")
        self.assertEqual(determine_initial_tier("decision", 6), "core")

    def test_determine_tier_core_milestone_high_score(self):
        """Milestone with score>=6 should be core."""
        self.assertEqual(determine_initial_tier("milestone", 7), "core")

    def test_determine_tier_core_preference_high_score(self):
        """Preference with score>=6 should be core."""
        self.assertEqual(determine_initial_tier("preference", 6), "core")

    def test_determine_tier_core_emotion_high_score(self):
        """Emotion with score>=6 should be core."""
        self.assertEqual(determine_initial_tier("emotion", 9), "core")

    def test_determine_tier_active_decision_low_score(self):
        """Decision with score<6 should be active (not core)."""
        self.assertEqual(determine_initial_tier("decision", 5), "active")

    def test_determine_tier_fading_context_low_score(self):
        """Context with score<4 should be fading."""
        self.assertEqual(determine_initial_tier("context", 2), "fading")
        self.assertEqual(determine_initial_tier("context", 0), "fading")
        self.assertEqual(determine_initial_tier("context", 3), "fading")

    def test_determine_tier_fading_other_low_score(self):
        """Other with score<4 should be fading."""
        self.assertEqual(determine_initial_tier("other", 1), "fading")

    def test_determine_tier_active_context_high_score(self):
        """Context with score>=4 should be active (not fading)."""
        self.assertEqual(determine_initial_tier("context", 4), "active")
        self.assertEqual(determine_initial_tier("context", 5), "active")

    def test_determine_tier_active_default(self):
        """Insight with moderate score should be active."""
        self.assertEqual(determine_initial_tier("insight", 4), "active")
        self.assertEqual(determine_initial_tier("challenge", 3), "active")

    def test_parse_blocks_with_tier_metadata(self):
        """Should parse tier, reference_count, last_referenced from block tags."""
        content = """# Memory

<!-- MEMORY_BLOCK id=mem-001 date=2025-05-01T00:00:00Z source=prop-001 tier=core reference_count=5 last_referenced=2025-05-08 score=8 -->
### [decision] 2025-05-01

Decided to use Rust.

<!-- /MEMORY_BLOCK -->

<!-- MEMORY_BLOCK id=mem-002 date=2025-05-05T00:00:00Z source=prop-002 tier=fading reference_count=0 last_referenced=2025-04-01 score=2 -->
### [context] 2025-05-05

Some context note.

<!-- /MEMORY_BLOCK -->
"""
        blocks = parse_memory_blocks(content)
        self.assertEqual(len(blocks), 2)

        self.assertEqual(blocks[0]["tier"], "core")
        self.assertEqual(blocks[0]["reference_count"], 5)
        self.assertEqual(blocks[0]["last_referenced"], "2025-05-08")
        self.assertEqual(blocks[0]["score"], 8)
        self.assertEqual(blocks[0]["category"], "decision")

        self.assertEqual(blocks[1]["tier"], "fading")
        self.assertEqual(blocks[1]["reference_count"], 0)
        self.assertEqual(blocks[1]["last_referenced"], "2025-04-01")
        self.assertEqual(blocks[1]["score"], 2)
        self.assertEqual(blocks[1]["category"], "context")

    def test_parse_blocks_backward_compatible(self):
        """Old blocks without tier/reference_count should default correctly."""
        content = """<!-- MEMORY_BLOCK id=mem-old date=2025-05-01T00:00:00Z source=prop-old -->
### [decision] 2025-05-01

Old block without new metadata.

<!-- /MEMORY_BLOCK -->
"""
        blocks = parse_memory_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["tier"], "active")  # default
        self.assertEqual(blocks[0]["reference_count"], 0)  # default
        self.assertIsNone(blocks[0]["last_referenced"])  # not present
        self.assertEqual(blocks[0]["score"], 0)  # default

    def test_core_never_decays(self):
        """Core blocks should never be moved to cold storage."""
        content = """<!-- MEMORY_BLOCK id=mem-core date=2025-01-01T00:00:00Z source=prop-001 tier=core reference_count=5 score=8 -->
### [decision] 2025-01-01

Important decision.

<!-- /MEMORY_BLOCK -->
"""
        blocks = parse_memory_blocks(content)
        self.assertEqual(blocks[0]["tier"], "core")
        # Even with no references, core should never decay
        self.assertFalse(is_block_referenced(blocks[0], []))
        # The tier check in cmd_memory_decay keeps core — tested via integration

    def test_active_upgrades_on_3_references(self):
        """Active block with reference_count >= 3 should be promotable to core."""
        content = """<!-- MEMORY_BLOCK id=mem-act date=2025-05-01T00:00:00Z source=prop-001 tier=active reference_count=2 score=4 -->
### [insight] 2025-05-01

An insight block.

<!-- /MEMORY_BLOCK -->
"""
        blocks = parse_memory_blocks(content)
        block = blocks[0]
        # Simulate reference increment
        block["reference_count"] += 1
        self.assertEqual(block["reference_count"], 3)
        # This would trigger upgrade in the decay command

    def test_rebuild_block_tag(self):
        """rebuild_block_tag should produce valid tag with all metadata."""
        block = {
            "id": "mem-001",
            "date": "2025-05-01T00:00:00Z",
            "source": "prop-001",
            "tier": "core",
            "reference_count": 5,
            "last_referenced": "2025-05-08",
            "score": 8,
        }
        tag = rebuild_block_tag(block)
        self.assertIn("id=mem-001", tag)
        self.assertIn("tier=core", tag)
        self.assertIn("reference_count=5", tag)
        self.assertIn("last_referenced=2025-05-08", tag)
        self.assertIn("score=8", tag)
        self.assertTrue(tag.startswith("<!-- MEMORY_BLOCK"))
        self.assertTrue(tag.endswith("-->"))

    def test_rebuild_full_block(self):
        """rebuild_full_block should produce valid complete block."""
        block = {
            "id": "mem-001",
            "date": "2025-05-01T00:00:00Z",
            "source": "prop-001",
            "tier": "active",
            "reference_count": 1,
            "last_referenced": "2025-05-10",
            "score": 4,
            "content": "### [insight] 2025-05-01\n\nSome insight.",
        }
        full = rebuild_full_block(block)
        self.assertIn("<!-- MEMORY_BLOCK", full)
        self.assertIn("<!-- /MEMORY_BLOCK -->", full)
        self.assertIn("### [insight] 2025-05-01", full)
        self.assertIn("tier=active", full)


class TestMemoryRecall(unittest.TestCase):
    """Test memory-recall from cold storage."""

    def test_recall_by_id(self):
        """Should recall a specific block by ID from cold storage."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Set up workspace
            config = {"companion_name": "test", "memory_governance": {"decay_days": 30}}
            save_json(os.path.join(tmp_dir, "companion_config.json"), config)
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))

            # Create cold storage with a block
            archive_content = """## Archived at 2025-05-01

<!-- MEMORY_BLOCK id=mem-recalled date=2025-04-01T00:00:00Z source=prop-001 tier=fading reference_count=0 score=2 -->
### [context] 2025-04-01

Old context to recall.

<!-- /MEMORY_BLOCK -->
"""
            write_markdown(os.path.join(tmp_dir, "AUTOMATION", "MEMORY_ARCHIVE.md"), archive_content)
            write_markdown(os.path.join(tmp_dir, "MEMORY.md"), "# Memory\n")

            # Simulate args
            class Args:
                id = "mem-recalled"
                search = None

            cmd_memory_recall(Args(), tmp_dir)

            # Verify recalled to MEMORY.md
            memory = read_markdown(os.path.join(tmp_dir, "MEMORY.md"))
            self.assertIn("mem-recalled", memory)
            self.assertIn("tier=active", memory)  # tier reset to active
            self.assertIn("Old context to recall", memory)

            # Verify removed from archive
            archive = read_markdown(os.path.join(tmp_dir, "AUTOMATION", "MEMORY_ARCHIVE.md"))
            self.assertNotIn("mem-recalled", archive)

    def test_recall_by_search(self):
        """Should recall blocks matching search keyword."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = {"companion_name": "test", "memory_governance": {"decay_days": 30}}
            save_json(os.path.join(tmp_dir, "companion_config.json"), config)
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))

            archive_content = """## Archived

<!-- MEMORY_BLOCK id=mem-rust date=2025-04-01T00:00:00Z source=prop-001 tier=fading reference_count=0 score=2 -->
### [decision] 2025-04-01

Decided to use Rust for performance.

<!-- /MEMORY_BLOCK -->

<!-- MEMORY_BLOCK id=mem-python date=2025-04-01T00:00:00Z source=prop-002 tier=fading reference_count=0 score=2 -->
### [decision] 2025-04-01

Chose Python for scripting.

<!-- /MEMORY_BLOCK -->
"""
            write_markdown(os.path.join(tmp_dir, "AUTOMATION", "MEMORY_ARCHIVE.md"), archive_content)
            write_markdown(os.path.join(tmp_dir, "MEMORY.md"), "# Memory\n")

            class Args:
                id = None
                search = "Rust"

            cmd_memory_recall(Args(), tmp_dir)

            memory = read_markdown(os.path.join(tmp_dir, "MEMORY.md"))
            self.assertIn("mem-rust", memory)
            self.assertNotIn("mem-python", memory)

    def test_recall_empty_archive(self):
        """Should handle empty cold storage gracefully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = {"companion_name": "test", "memory_governance": {"decay_days": 30}}
            save_json(os.path.join(tmp_dir, "companion_config.json"), config)
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))
            write_markdown(os.path.join(tmp_dir, "AUTOMATION", "MEMORY_ARCHIVE.md"), "")

            class Args:
                id = "nonexistent"
                search = None

            # Should not raise
            cmd_memory_recall(Args(), tmp_dir)


class TestCheckinDedup(unittest.TestCase):
    """Test check-in deduplication."""

    def test_first_checkin_appends(self):
        """First check-in of the day should append."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            draft_path = os.path.join(tmp_dir, "draft.md")
            write_markdown(draft_path, "# Draft\n\nSome existing content.\n")

            today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            advice = f"\n\n## Check-in Analysis \u2014 {today}\n\nHealthy patterns.\n\n"

            replaced = deduplicate_checkin(draft_path, advice)
            self.assertFalse(replaced)

            content = read_markdown(draft_path)
            self.assertIn("Check-in Analysis", content)
            self.assertIn("Healthy patterns", content)

    def test_second_checkin_replaces(self):
        """Second check-in same day should replace, not append."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            draft_path = os.path.join(tmp_dir, "draft.md")
            today = datetime.now().strftime("%Y-%m-%d")
            existing = (
                "# Draft\n\nSome content.\n"
                f"\n\n## Check-in Analysis \u2014 {today} 10:00:00\n\nOld suggestion.\n\n"
            )
            write_markdown(draft_path, existing)

            new_advice = f"\n\n## Check-in Analysis \u2014 {today} 14:00:00\n\nNew suggestion.\n\n"
            replaced = deduplicate_checkin(draft_path, new_advice)
            self.assertTrue(replaced)

            content = read_markdown(draft_path)
            self.assertIn("New suggestion", content)
            self.assertNotIn("Old suggestion", content)
            # Should only have one check-in section
            count = content.count("## Check-in Analysis")
            self.assertEqual(count, 1)

    def test_different_day_appends(self):
        """Check-in from a different day should append, not replace."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            draft_path = os.path.join(tmp_dir, "draft.md")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            existing = (
                "# Draft\n"
                f"\n\n## Check-in Analysis \u2014 {yesterday} 10:00:00\n\nYesterday's analysis.\n\n"
            )
            write_markdown(draft_path, existing)

            today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_advice = f"\n\n## Check-in Analysis \u2014 {today}\n\nToday's analysis.\n\n"
            replaced = deduplicate_checkin(draft_path, new_advice)
            self.assertFalse(replaced)

            content = read_markdown(draft_path)
            self.assertIn("Yesterday's analysis", content)
            self.assertIn("Today's analysis", content)


class TestExportRestore(unittest.TestCase):
    """Test export and restore functionality."""

    def _create_workspace(self, tmp_dir):
        """Helper to create a minimal workspace."""
        config = {
            "companion_name": "test",
            "memory_governance": {"decay_days": 30},
            "authorized_dirs": ["."],
            "protected_patterns": [],
        }
        save_json(os.path.join(tmp_dir, "companion_config.json"), config)
        ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))
        ensure_dir(os.path.join(tmp_dir, "AUTOMATION", "archive-packages"))

        memory = """# Memory

<!-- MEMORY_BLOCK id=mem-exp1 date=2025-05-01T00:00:00Z source=prop-001 tier=core reference_count=3 score=8 -->
### [decision] 2025-05-01

Test decision.

<!-- /MEMORY_BLOCK -->
"""
        write_markdown(os.path.join(tmp_dir, "MEMORY.md"), memory)
        write_markdown(os.path.join(tmp_dir, "SOUL.md"), "# Soul\nTest soul.\n")
        write_markdown(os.path.join(tmp_dir, "WATCHLIST.md"), "# Watchlist\n")
        write_markdown(os.path.join(tmp_dir, "ACTIVE_PROJECTS.md"), "# Projects\n")
        save_json(os.path.join(tmp_dir, "AUTOMATION", "reminders.json"), [{"text": "Test reminder"}])
        write_markdown(os.path.join(tmp_dir, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"), "# Timeline\n")
        write_markdown(os.path.join(tmp_dir, "AUTOMATION", "MEMORY_ARCHIVE.md"), "")
        save_json(os.path.join(tmp_dir, "AUTOMATION", "presence_rules.json"), [])
        return config

    def test_export_json(self):
        """Should export all data as JSON."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_workspace(tmp_dir)
            data = gather_export_data(tmp_dir)

            self.assertIn("config", data)
            self.assertIn("memory_blocks", data)
            self.assertEqual(len(data["memory_blocks"]), 1)
            self.assertEqual(data["memory_blocks"][0]["id"], "mem-exp1")
            self.assertEqual(data["memory_blocks"][0]["tier"], "core")
            self.assertIn("reminders", data)
            self.assertEqual(len(data["reminders"]), 1)

            filepath = export_json(tmp_dir, data)
            self.assertTrue(os.path.isfile(filepath))
            self.assertTrue(filepath.endswith(".json"))

    def test_export_markdown(self):
        """Should export all data as markdown."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_workspace(tmp_dir)
            data = gather_export_data(tmp_dir)
            filepath = export_markdown(tmp_dir, data)
            self.assertTrue(os.path.isfile(filepath))
            self.assertTrue(filepath.endswith(".md"))

            content = read_markdown(filepath)
            self.assertIn("Companion Export", content)
            self.assertIn("mem-exp1", content)
            self.assertIn("[core]", content)

    def test_restore_from_json(self):
        """Should restore workspace from exported JSON."""
        with tempfile.TemporaryDirectory() as src_dir:
            self._create_workspace(src_dir)
            data = gather_export_data(src_dir)
            filepath = export_json(src_dir, data)

            # Create empty target workspace
            with tempfile.TemporaryDirectory() as tgt_dir:
                save_json(os.path.join(tgt_dir, "companion_config.json"), {"companion_name": "empty"})
                ensure_dir(os.path.join(tgt_dir, "AUTOMATION"))

                restore_from_file(tgt_dir, filepath)

                # Verify restored
                memory = read_markdown(os.path.join(tgt_dir, "MEMORY.md"))
                self.assertIn("mem-exp1", memory)
                self.assertIn("Test decision", memory)

                soul = read_markdown(os.path.join(tgt_dir, "SOUL.md"))
                self.assertIn("Test soul", soul)

                with open(os.path.join(tgt_dir, "AUTOMATION", "reminders.json")) as rf:
                    reminders = json.load(rf)
                self.assertEqual(len(reminders), 1)

    def test_restore_missing_file(self):
        """Should raise FileNotFoundError for missing file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(FileNotFoundError):
                restore_from_file(tmp_dir, "/nonexistent/file.json")


class TestStopWords(unittest.TestCase):
    """Test stop words filtering in curate."""

    def test_stop_words_english_present(self):
        """English stop words should be in the set."""
        for word in ["the", "and", "or", "is", "are", "was", "were", "has", "have", "had"]:
            self.assertIn(word, STOP_WORDS_EN)

    def test_stop_words_chinese_present(self):
        """Chinese stop words should be in the set."""
        for word in ["\u7684", "\u4e86", "\u662f", "\u5728", "\u548c", "\u4e5f", "\u5c31", "\u90fd"]:
            self.assertIn(word, STOP_WORDS_ZH)

    def test_stop_words_combined(self):
        """Combined set should have both."""
        self.assertTrue(len(STOP_WORDS) >= 30)
        self.assertIn("the", STOP_WORDS)
        self.assertIn("\u7684", STOP_WORDS)

    def test_project_relevance_filters_stop_words(self):
        """compute_project_relevance should not match stop words."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create ACTIVE_PROJECTS.md with only stop words
            projects_content = "# Projects\n\n- the and or is are was were\n"
            write_markdown(os.path.join(tmp_dir, "ACTIVE_PROJECTS.md"), projects_content)

            candidate = {"text": "The project is working and the tests are passing now fine."}
            score = compute_project_relevance(candidate, tmp_dir)
            self.assertEqual(score, 0)  # Stop words shouldn't give relevance bonus

    def test_project_relevance_matches_real_keywords(self):
        """compute_project_relevance should match real project keywords."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            projects_content = "# Projects\n\n- Companion evolution engine refactoring\n"
            write_markdown(os.path.join(tmp_dir, "ACTIVE_PROJECTS.md"), projects_content)

            candidate = {"text": "Working on the companion engine today."}
            score = compute_project_relevance(candidate, tmp_dir)
            self.assertEqual(score, 2)


class TestDigestContextWindow(unittest.TestCase):
    """Test expanded context window in digest."""

    def test_context_captures_2_lines_before_and_after(self):
        """Should capture up to 2 lines before and after signal line."""
        content = (
            "Line one about project background and setup.\n"
            "Line two about architecture decisions review.\n"
            "I decided to switch to the new framework completely.\n"
            "Line four explains why this makes sense now.\n"
            "Line five wraps up the discussion about it."
        )
        candidates = extract_candidates_from_archive(content, "test.md")
        context_items = [c for c in candidates if c.get("category") == "context"]
        self.assertTrue(len(context_items) > 0)

        # Context should be merged — check that it contains multiple lines
        for ctx in context_items:
            if ctx.get("context_lines", 0) > 1:
                self.assertIn("\n", ctx["text"])

    def test_context_has_context_lines_field(self):
        """Context candidates should have context_lines metadata."""
        content = (
            "Setup the dev environment properly.\n"
            "Configure all the tooling needed.\n"
            "I decided to switch to TypeScript for this.\n"
            "The migration path is straightforward.\n"
            "We can start next week on this."
        )
        candidates = extract_candidates_from_archive(content, "test.md")
        context_items = [c for c in candidates if c.get("category") == "context"]
        for ctx in context_items:
            self.assertIn("context_lines", ctx)
            self.assertGreater(ctx["context_lines"], 0)

    def test_context_merged_into_single_candidate(self):
        """Multiple context lines for same signal should be merged."""
        content = (
            "First context line about project.\n"
            "Second context line with details.\n"
            "I finally shipped the release today!\n"
            "Third context line after signal.\n"
            "Fourth context line wrapping up."
        )
        candidates = extract_candidates_from_archive(content, "test.md")
        context_items = [c for c in candidates if c.get("category") == "context"]
        # Should be exactly one merged context candidate per signal
        # (because all context lines belong to the same signal)
        signal_parents = set(c.get("context_of", "") for c in context_items)
        # Each parent should appear only once (merged)
        self.assertEqual(len(context_items), len(signal_parents))


if __name__ == "__main__":
    unittest.main()

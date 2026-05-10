"""
Tests for v2.3.0 features:
- extract_key_nouns quote-handling fix
- is_block_referenced combined_refs_lower parameter
- incremental export conversations with content
- restore_from_file handling incremental format

Run with:
  python3 -m unittest discover tests/
  python3 -m pytest tests/test_v23_features.py
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
from commands.export import (
    gather_incremental_data, export_incremental, restore_from_file
)


class TestExtractKeyNounsQuoteFix(unittest.TestCase):
    """Test that extract_key_nouns handles quoted sentence starts correctly."""

    def test_quoted_sentence_start_not_extracted(self):
        """Sentence-start word in quotes should not be extracted as standalone noun."""
        text = '"Hello World" is a great program.'
        nouns = extract_key_nouns(text)
        # "Hello" alone should NOT be in nouns (it's sentence-start)
        self.assertNotIn("Hello", nouns)
        # "Hello World" IS extracted by quoted-content regex (intentional)
        self.assertIn("Hello World", nouns)
        # "World" is second word, capitalized -> should be extracted
        self.assertIn("World", nouns)

    def test_parenthesized_sentence_start_not_extracted(self):
        """Words at sentence start wrapped in parens should not be extracted."""
        text = "(React) is a JavaScript framework. Vue is also popular."
        nouns = extract_key_nouns(text)
        # "React" at sentence start even with parens -> excluded
        self.assertNotIn("React", nouns)
        # "Vue" is not at sentence start of second sentence (it IS sentence start)
        self.assertNotIn("Vue", nouns)
        # "JavaScript" is not at sentence start -> included
        self.assertIn("JavaScript", nouns)

    def test_normal_mid_sentence_capitalized_still_works(self):
        """Non-sentence-start capitalized words still extracted correctly."""
        text = "We use Docker and Kubernetes in production."
        nouns = extract_key_nouns(text)
        self.assertIn("Docker", nouns)
        self.assertIn("Kubernetes", nouns)
        self.assertNotIn("We", nouns)

    def test_multiple_sentences_with_quotes(self):
        """Multiple sentences with quoted words at start."""
        text = '"Python" rocks. I prefer "TypeScript" over JavaScript.'
        nouns = extract_key_nouns(text)
        # "Python" is extracted via quoted-content regex (intentional)
        self.assertIn("Python", nouns)
        # "TypeScript" is in quotes mid-sentence -> extracted via quoted-content regex
        self.assertIn("TypeScript", nouns)
        # "JavaScript" mid-sentence -> extracted
        self.assertIn("JavaScript", nouns)

    def test_sentence_start_capitalized_not_extracted_without_quotes(self):
        """Sentence-start capitalized word (no quotes) should NOT be noun-extracted."""
        text = "Hello everyone. World domination is the goal."
        nouns = extract_key_nouns(text)
        # "Hello" is sentence-start of first sentence
        self.assertNotIn("Hello", nouns)
        # "World" is sentence-start of second sentence
        self.assertNotIn("World", nouns)


class TestIsBlockReferencedCombinedRefs(unittest.TestCase):
    """Test is_block_referenced with combined_refs_lower parameter."""

    def test_with_combined_refs_lower_fast_path(self):
        """Should use combined_refs_lower for fast path when provided."""
        block = {"content": "Decided to use Rust for the backend performance project."}
        reference_texts = ["earlier we decided to use rust for the backend and it worked."]
        combined = "\n".join(reference_texts).lower()
        self.assertTrue(is_block_referenced(block, reference_texts, combined_refs_lower=combined))

    def test_with_combined_refs_lower_no_match(self):
        """Should return False when combined_refs_lower has no match."""
        block = {"content": "Some unique content that won't appear anywhere else in the world."}
        reference_texts = ["Completely unrelated text about cooking."]
        combined = "\n".join(reference_texts).lower()
        self.assertFalse(is_block_referenced(block, reference_texts, combined_refs_lower=combined))

    def test_without_combined_refs_lower_backward_compat(self):
        """Should work without combined_refs_lower (backward compatibility)."""
        block = {"content": "Decided to use Rust for the backend performance project."}
        reference_texts = ["earlier we decided to use rust for the backend and it worked."]
        # No combined_refs_lower parameter
        self.assertTrue(is_block_referenced(block, reference_texts))

    def test_noun_fallback_uses_combined_refs_lower(self):
        """Noun fallback should use combined_refs_lower when provided."""
        block = {"content": "The team discussed TypeScript migration with ReactRouter framework in detail."}
        # First 30 chars won't match
        reference_texts = ["We should revisit the ReactRouter setup next sprint."]
        combined = "\n".join(reference_texts).lower()
        self.assertTrue(is_block_referenced(block, reference_texts, combined_refs_lower=combined))


class TestIncrementalExportConversationContent(unittest.TestCase):
    """Test that incremental export includes conversation file content."""

    def _create_workspace(self, tmp_dir):
        """Helper to create a workspace."""
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

<!-- MEMORY_BLOCK id=mem-1 date=2025-05-09T12:00:00Z source=prop-001 tier=active reference_count=0 score=5 -->
### [insight] 2025-05-09

Test insight.

<!-- /MEMORY_BLOCK -->
"""
        write_markdown(os.path.join(tmp_dir, "MEMORY.md"), memory)
        write_markdown(os.path.join(tmp_dir, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"), "# Timeline\n")
        save_json(os.path.join(tmp_dir, "AUTOMATION", "reminders.json"), [])

    def test_conversations_include_content(self):
        """Incremental export should include filename and content for conversations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_workspace(tmp_dir)

            # Create a conversation file
            conv_content = "# Conversation 2025-05-09\n\nWe discussed the new feature.\n"
            conv_path = os.path.join(tmp_dir, "AUTOMATION", "conversations", "conv-2025-05-09.md")
            write_markdown(conv_path, conv_content)

            last_export_dt = datetime(2025, 5, 1, 0, 0, 0)
            data = gather_incremental_data(tmp_dir, last_export_dt)

            self.assertTrue(len(data["conversations"]) >= 1)
            conv = data["conversations"][0]
            self.assertIsInstance(conv, dict)
            self.assertEqual(conv["filename"], "conv-2025-05-09.md")
            self.assertIn("We discussed the new feature", conv["content"])

    def test_conversations_empty_when_none_new(self):
        """Incremental export should have empty conversations if none are new."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self._create_workspace(tmp_dir)

            # Create a conversation with old mtime
            conv_path = os.path.join(tmp_dir, "AUTOMATION", "conversations", "conv-old.md")
            write_markdown(conv_path, "# Old conversation\n")
            # Set mtime to before last_export
            old_time = datetime(2025, 4, 1, 0, 0, 0).timestamp()
            os.utime(conv_path, (old_time, old_time))

            last_export_dt = datetime(2025, 5, 1, 0, 0, 0)
            data = gather_incremental_data(tmp_dir, last_export_dt)

            self.assertEqual(len(data["conversations"]), 0)


class TestRestoreFromFileIncremental(unittest.TestCase):
    """Test restore_from_file handles incremental format."""

    def test_restore_incremental_conversations(self):
        """Should restore conversation files from incremental backup."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))

            # Create an incremental export file
            incremental_data = {
                "export_date": "2025-05-09 12:00:00",
                "incremental": True,
                "since": "2025-05-01T00:00:00",
                "config": {"companion_name": "test"},
                "memory_blocks": [],
                "reminders": [],
                "timeline": "# Timeline\n",
                "archives": [],
                "conversations": [
                    {
                        "filename": "conv-2025-05-09.md",
                        "content": "# Conversation\n\nHello world.\n",
                    },
                    {
                        "filename": "conv-2025-05-10.md",
                        "content": "# Conversation 2\n\nGoodbye world.\n",
                    },
                ],
            }
            export_path = os.path.join(tmp_dir, "incremental-export.json")
            save_json(export_path, incremental_data)

            # Also need a config file for restore_from_file to write
            save_json(os.path.join(tmp_dir, "companion_config.json"), {"companion_name": "test"})

            restore_from_file(tmp_dir, export_path)

            # Check conversations were restored
            conv_dir = os.path.join(tmp_dir, "AUTOMATION", "conversations")
            self.assertTrue(os.path.isdir(conv_dir))

            conv1 = read_markdown(os.path.join(conv_dir, "conv-2025-05-09.md"))
            self.assertIn("Hello world", conv1)

            conv2 = read_markdown(os.path.join(conv_dir, "conv-2025-05-10.md"))
            self.assertIn("Goodbye world", conv2)

    def test_restore_incremental_skips_legacy_format(self):
        """Should handle legacy format (filename-only strings) gracefully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))

            # Legacy format: conversations is just a list of filenames
            incremental_data = {
                "export_date": "2025-05-09 12:00:00",
                "incremental": True,
                "since": "2025-05-01T00:00:00",
                "config": {"companion_name": "test"},
                "memory_blocks": [],
                "reminders": [],
                "timeline": "",
                "archives": [],
                "conversations": ["conv-old.md"],  # legacy string format
            }
            export_path = os.path.join(tmp_dir, "legacy-export.json")
            save_json(export_path, incremental_data)
            save_json(os.path.join(tmp_dir, "companion_config.json"), {"companion_name": "test"})

            # Should not crash
            restore_from_file(tmp_dir, export_path)

            # No conversation files written (string format has no content)
            conv_dir = os.path.join(tmp_dir, "AUTOMATION", "conversations")
            if os.path.isdir(conv_dir):
                self.assertEqual(len(os.listdir(conv_dir)), 0)

    def test_restore_full_export_still_works(self):
        """Full export restore should still work (no incremental flag)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            full_data = {
                "export_date": "2025-05-09 12:00:00",
                "config": {"companion_name": "test"},
                "memory_raw": "# Memory\n\nSome content.\n",
                "memory_blocks": [],
                "reminders": [{"text": "reminder1"}],
                "timeline": "# Timeline\n",
                "archives": [],
                "presence_rules": [],
                "soul": "# Soul\n",
                "watchlist": "",
                "active_projects": "",
                "cold_storage": "",
            }
            export_path = os.path.join(tmp_dir, "full-export.json")
            save_json(export_path, full_data)
            save_json(os.path.join(tmp_dir, "companion_config.json"), {"companion_name": "old"})
            ensure_dir(os.path.join(tmp_dir, "AUTOMATION"))

            restore_from_file(tmp_dir, export_path)

            memory = read_markdown(os.path.join(tmp_dir, "MEMORY.md"))
            self.assertIn("Some content", memory)


class TestVersionNumber(unittest.TestCase):
    """Test version number is 3.0.0."""

    def test_version(self):
        """VERSION should be 3.0.0."""
        self.assertEqual(VERSION, "3.0.0")


if __name__ == "__main__":
    unittest.main()

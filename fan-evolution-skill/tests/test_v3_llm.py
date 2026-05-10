"""
Tests for v3.0.0 LLM integration features:
- LLMClient initialization and availability checks
- LLMClient.chat returns None without API key
- LLMClient.chat_json JSON parsing (good + bad input)
- digest fallback: LLM returns None → regex used
- reflect fallback: LLM unavailable → rule-based output
- checkin fallback: LLM unavailable → rule-based output
- understand command: no LLM → helpful message
- understand command: with LLM → output produced
- config template has llm section
- get_llm_client factory function

Run with:
  python3 -m unittest discover tests/
  python3 -m pytest tests/test_v3_llm.py
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from io import StringIO

# Add tools/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from utils import VERSION, get_llm_client, load_config, write_markdown, save_json, ensure_dir
from llm import LLMClient
from commands.digest import extract_candidates_with_llm, extract_candidates_from_archive
from commands.reflect import generate_reflection_with_llm
from commands.checkin import generate_checkin_with_llm
from commands.understand import cmd_understand


def make_workspace(tmpdir, llm_enabled=False, api_key_env="OPENAI_API_KEY"):
    """Create a minimal companion workspace for testing."""
    config = {
        "companion_name": "test-companion",
        "authorized_dirs": ["."],
        "protected_patterns": ["*.key"],
        "reminder_policy": {"must_max_per_day": 3, "gentle_max_per_day": 5},
        "memory_governance": {"require_confirmation": True, "auto_confirm_threshold": 7, "decay_days": 30},
        "language": "auto",
        "relationship": {"checkin_interval_days": 3},
        "llm": {
            "enabled": llm_enabled,
            "api_base": "https://api.openai.com/v1",
            "api_key_env": api_key_env,
            "model": "gpt-4o-mini",
            "fallback_to_regex": True,
            "max_tokens": 2000,
            "temperature": 0.3,
            "timeout_seconds": 30,
        },
        "created_at": "2025-05-01T00:00:00Z",
    }
    config_path = os.path.join(tmpdir, "companion_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)

    # Create required files
    write_markdown(os.path.join(tmpdir, "SOUL.md"), "# Soul\nTest companion")
    write_markdown(os.path.join(tmpdir, "PRESENCE.md"), "# Presence\n- Be kind\n- Be present\n- Listen first")
    write_markdown(os.path.join(tmpdir, "MEMORY.md"), "# Memory\n")
    write_markdown(os.path.join(tmpdir, "WATCHLIST.md"), "# Watchlist\n")
    write_markdown(os.path.join(tmpdir, "ACTIVE_PROJECTS.md"), "# Active Projects\n")
    ensure_dir(os.path.join(tmpdir, "AUTOMATION", "archive-packages"))
    ensure_dir(os.path.join(tmpdir, "AUTOMATION", "conversations"))
    save_json(os.path.join(tmpdir, "AUTOMATION", "reminders.json"), [])

    return tmpdir


class TestLLMClientInit(unittest.TestCase):
    """Test LLMClient initialization and availability."""

    def test_init_with_empty_config(self):
        """LLMClient should initialize with empty config (disabled)."""
        client = LLMClient({})
        self.assertFalse(client.enabled)
        self.assertFalse(client.is_available())

    def test_init_with_disabled_config(self):
        """LLMClient should respect enabled=false."""
        config = {"llm": {"enabled": False, "api_key_env": "OPENAI_API_KEY"}}
        client = LLMClient(config)
        self.assertFalse(client.is_available())

    def test_init_with_enabled_but_no_key(self):
        """LLMClient enabled but no env var set → not available."""
        config = {"llm": {"enabled": True, "api_key_env": "NONEXISTENT_KEY_XYZ_123"}}
        client = LLMClient(config)
        self.assertTrue(client.enabled)
        self.assertFalse(client.is_available())

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test-key"})
    def test_init_with_enabled_and_key(self):
        """LLMClient enabled + env var present → available."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)
        self.assertTrue(client.is_available())

    def test_default_values(self):
        """LLMClient should use sensible defaults."""
        config = {"llm": {"enabled": True}}
        client = LLMClient(config)
        self.assertEqual(client.model, "gpt-4o-mini")
        self.assertEqual(client.timeout, 30)
        self.assertEqual(client.temperature, 0.3)
        self.assertEqual(client.max_tokens, 2000)
        self.assertTrue(client.fallback_to_regex)

    def test_custom_model(self):
        """LLMClient should accept custom model name."""
        config = {"llm": {"enabled": True, "model": "claude-3-haiku"}}
        client = LLMClient(config)
        self.assertEqual(client.model, "claude-3-haiku")


class TestLLMClientChat(unittest.TestCase):
    """Test LLMClient.chat behavior without real API."""

    def test_chat_returns_none_without_key(self):
        """chat() should return None when no API key is available."""
        config = {"llm": {"enabled": True, "api_key_env": "NONEXISTENT_KEY_XYZ_123"}}
        client = LLMClient(config)
        result = client.chat("system", "user")
        self.assertIsNone(result)

    def test_chat_returns_none_when_disabled(self):
        """chat() should return None when LLM is disabled."""
        config = {"llm": {"enabled": False}}
        client = LLMClient(config)
        result = client.chat("system", "user")
        self.assertIsNone(result)

    def test_chat_json_returns_none_without_key(self):
        """chat_json() should return None when no API key is available."""
        config = {"llm": {"enabled": True, "api_key_env": "NONEXISTENT_KEY_XYZ_123"}}
        client = LLMClient(config)
        result = client.chat_json("system", "user")
        self.assertIsNone(result)


class TestLLMClientChatJSON(unittest.TestCase):
    """Test LLMClient.chat_json parsing logic."""

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_parse_clean_json_array(self):
        """chat_json should parse a clean JSON array response."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        mock_response = json.dumps([
            {"text": "decided to use Python", "category": "decision", "importance": 8}
        ])

        with patch.object(client, 'chat', return_value=mock_response):
            result = client.chat_json("sys", "usr")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "decision")

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_parse_markdown_fenced_json(self):
        """chat_json should handle ```json fenced blocks."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        mock_response = '```json\n[{"text": "hello", "category": "emotion"}]\n```'

        with patch.object(client, 'chat', return_value=mock_response):
            result = client.chat_json("sys", "usr")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["text"], "hello")

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_parse_garbage_returns_none(self):
        """chat_json should return None for unparseable garbage."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        with patch.object(client, 'chat', return_value="This is not JSON at all"):
            result = client.chat_json("sys", "usr")
        self.assertIsNone(result)

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_parse_json_with_surrounding_text(self):
        """chat_json should extract JSON from surrounding text."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        mock_response = 'Here are the results:\n[{"text": "hi", "category": "emotion"}]\nDone.'

        with patch.object(client, 'chat', return_value=mock_response):
            result = client.chat_json("sys", "usr")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["text"], "hi")

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_chat_returns_none_propagates(self):
        """chat_json should return None when chat() returns None."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        with patch.object(client, 'chat', return_value=None):
            result = client.chat_json("sys", "usr")
        self.assertIsNone(result)


class TestDigestFallback(unittest.TestCase):
    """Test digest LLM → regex fallback."""

    def test_extract_candidates_with_llm_no_client(self):
        """extract_candidates_with_llm returns None with no client."""
        result = extract_candidates_with_llm("some content", "test.md", None)
        self.assertIsNone(result)

    def test_extract_candidates_with_llm_unavailable(self):
        """extract_candidates_with_llm returns None when client not available."""
        config = {"llm": {"enabled": True, "api_key_env": "NONEXISTENT_KEY_XYZ_123"}}
        client = LLMClient(config)
        result = extract_candidates_with_llm("some content", "test.md", client)
        self.assertIsNone(result)

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_extract_candidates_with_llm_bad_response(self):
        """extract_candidates_with_llm returns None on non-list response."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        with patch.object(client, 'chat_json', return_value="not a list"):
            result = extract_candidates_with_llm("content", "test.md", client)
        self.assertIsNone(result)

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_extract_candidates_with_llm_success(self):
        """extract_candidates_with_llm processes valid LLM output."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        mock_result = [
            {"text": "decided to learn Rust", "category": "decision", "importance": 8},
            {"text": "feeling tired today", "category": "fatigue", "importance": 4},
        ]

        with patch.object(client, 'chat_json', return_value=mock_result):
            result = extract_candidates_with_llm("content", "test.md", client)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["method"], "llm")
        self.assertEqual(result[0]["category"], "decision")
        self.assertEqual(result[0]["importance"], 8)

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_extract_candidates_invalid_category_normalized(self):
        """Invalid categories should be normalized to 'other'."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        mock_result = [
            {"text": "some text", "category": "INVALID_CAT", "importance": 5},
        ]

        with patch.object(client, 'chat_json', return_value=mock_result):
            result = extract_candidates_with_llm("content", "test.md", client)
        self.assertEqual(result[0]["category"], "other")

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_extract_candidates_importance_clamped(self):
        """Importance should be clamped to 1-10."""
        config = {"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3"}}
        client = LLMClient(config)

        mock_result = [
            {"text": "text1", "category": "emotion", "importance": 15},
            {"text": "text2", "category": "emotion", "importance": -3},
            {"text": "text3", "category": "emotion", "importance": "abc"},
        ]

        with patch.object(client, 'chat_json', return_value=mock_result):
            result = extract_candidates_with_llm("content", "test.md", client)
        self.assertEqual(result[0]["importance"], 10)
        self.assertEqual(result[1]["importance"], 1)
        self.assertEqual(result[2]["importance"], 5)  # default on parse failure

    def test_digest_cmd_fallback_to_regex(self):
        """cmd_digest should work without LLM (regex fallback)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=False)
            # Add an archive with signal content
            archive_dir = os.path.join(tmpdir, "AUTOMATION", "archive-packages")
            archive_content = "I decided to switch to TypeScript for the project.\n"
            write_markdown(os.path.join(archive_dir, "test-archive.md"), archive_content)

            from commands.digest import cmd_digest

            class Args:
                hours = 24
                limit = 120

            # Should not crash
            cmd_digest(Args(), tmpdir)
            # Should have produced candidates
            candidates_path = os.path.join(tmpdir, "AUTOMATION", "MEMORY_CANDIDATES.md")
            self.assertTrue(os.path.isfile(candidates_path))


class TestReflectFallback(unittest.TestCase):
    """Test reflect LLM fallback."""

    def test_generate_reflection_no_client(self):
        """generate_reflection_with_llm returns None without client."""
        result = generate_reflection_with_llm({}, None, "test")
        self.assertIsNone(result)

    def test_generate_reflection_unavailable_client(self):
        """generate_reflection_with_llm returns None when client not available."""
        config = {"llm": {"enabled": True, "api_key_env": "NONEXISTENT_KEY_XYZ_123"}}
        client = LLMClient(config)
        result = generate_reflection_with_llm({"timeline": "some data"}, client, "test")
        self.assertIsNone(result)

    def test_reflect_cmd_works_without_llm(self):
        """cmd_reflect should produce output without LLM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=False)
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "ENVIRONMENT_SNAPSHOT.md"), "snapshot")
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "MEMORY_CANDIDATES.md"), "candidates")

            from commands.reflect import cmd_reflect

            class Args:
                hours = 24
                limit = 120

            cmd_reflect(Args(), tmpdir)
            draft_path = os.path.join(tmpdir, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md")
            self.assertTrue(os.path.isfile(draft_path))
            content = open(draft_path).read()
            self.assertIn("rule-based", content)


class TestCheckinFallback(unittest.TestCase):
    """Test check-in LLM fallback."""

    def test_generate_checkin_no_client(self):
        """generate_checkin_with_llm returns None without client."""
        result = generate_checkin_with_llm([], "", None, {})
        self.assertIsNone(result)

    def test_generate_checkin_unavailable_client(self):
        """generate_checkin_with_llm returns None when client not available."""
        config = {"llm": {"enabled": True, "api_key_env": "NONEXISTENT_KEY_XYZ_123"}}
        client = LLMClient(config)
        result = generate_checkin_with_llm([], "", client, {})
        self.assertIsNone(result)

    def test_checkin_cmd_works_without_llm(self):
        """cmd_checkin should produce output without LLM (rule-based)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=False)
            # Add timeline with old entry
            old_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
            timeline = f"## {old_date} — Daily Timeline Entry\n\n- **collaboration**: worked on project\n"
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"), timeline)
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md"), "")

            from commands.checkin import cmd_checkin

            class Args:
                pass

            cmd_checkin(Args(), tmpdir)
            draft_path = os.path.join(tmpdir, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md")
            content = open(draft_path).read()
            self.assertIn("rule-based", content)


class TestUnderstandCommand(unittest.TestCase):
    """Test understand command behavior."""

    def test_understand_no_llm_shows_message(self):
        """understand should show config instructions without LLM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=False)

            class Args:
                file = None
                text = "Hello, how are you?"

            captured = StringIO()
            sys.stdout = captured
            try:
                cmd_understand(Args(), tmpdir)
            finally:
                sys.stdout = sys.__stdout__

            output = captured.getvalue()
            self.assertIn("requires LLM support", output)
            self.assertIn("api_key_env", output)

    def test_understand_no_input_shows_usage(self):
        """understand should show usage when no input provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=True)

            class Args:
                file = None
                text = None

            captured = StringIO()
            sys.stdout = captured
            try:
                cmd_understand(Args(), tmpdir)
            finally:
                sys.stdout = sys.__stdout__

            output = captured.getvalue()
            self.assertIn("--file", output)
            self.assertIn("--text", output)

    def test_understand_file_not_found(self):
        """understand should handle missing file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=True)

            class Args:
                file = "/nonexistent/path/to/file.md"
                text = None

            captured = StringIO()
            sys.stdout = captured
            try:
                cmd_understand(Args(), tmpdir)
            finally:
                sys.stdout = sys.__stdout__

            output = captured.getvalue()
            self.assertIn("not found", output)

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_understand_with_llm_success(self):
        """understand should output analysis when LLM works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=True, api_key_env="TEST_LLM_KEY_V3")

            # Write a test file
            test_file = os.path.join(tmpdir, "test_convo.md")
            write_markdown(test_file, "user: I'm feeling overwhelmed.\ncompanion: I hear you.")

            class Args:
                file = test_file
                text = None

            # Mock the LLM call
            with patch('commands.understand.get_llm_client') as mock_get:
                mock_client = MagicMock()
                mock_client.is_available.return_value = True
                mock_client.model = "gpt-4o-mini"
                mock_client.chat.return_value = "## 情绪走向\nOverwhelmed → supported"
                mock_get.return_value = mock_client

                captured = StringIO()
                sys.stdout = captured
                try:
                    cmd_understand(Args(), tmpdir)
                finally:
                    sys.stdout = sys.__stdout__

                output = captured.getvalue()
                self.assertIn("Deep Understanding", output)
                self.assertIn("情绪走向", output)


class TestGetLLMClientFactory(unittest.TestCase):
    """Test get_llm_client factory function."""

    def test_returns_none_for_missing_config(self):
        """get_llm_client returns None when config not found."""
        result = get_llm_client("/nonexistent/path")
        self.assertIsNone(result)

    def test_returns_none_when_disabled(self):
        """get_llm_client returns None when llm.enabled is False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=False)
            result = get_llm_client(tmpdir)
            self.assertIsNone(result)

    def test_returns_client_when_enabled(self):
        """get_llm_client returns LLMClient when enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=True)
            result = get_llm_client(tmpdir)
            self.assertIsNotNone(result)
            self.assertIsInstance(result, LLMClient)


class TestLLMClientStatusSummary(unittest.TestCase):
    """Test status_summary output."""

    def test_disabled_status(self):
        """status_summary when disabled."""
        client = LLMClient({"llm": {"enabled": False}})
        self.assertEqual(client.status_summary(), "LLM: disabled")

    @patch.dict(os.environ, {"TEST_LLM_KEY_V3": "sk-test"})
    def test_enabled_with_key_status(self):
        """status_summary when enabled with key."""
        client = LLMClient({"llm": {"enabled": True, "api_key_env": "TEST_LLM_KEY_V3", "model": "gpt-4o"}})
        summary = client.status_summary()
        self.assertIn("enabled", summary)
        self.assertIn("gpt-4o", summary)

    def test_enabled_no_key_status(self):
        """status_summary when enabled but no key."""
        client = LLMClient({"llm": {"enabled": True, "api_key_env": "NONEXISTENT_XYZ"}})
        summary = client.status_summary()
        self.assertIn("no API key", summary)


class TestConfigTemplate(unittest.TestCase):
    """Test that config template includes LLM section."""

    def test_template_has_llm_section(self):
        """templates/companion_config.json should have llm section."""
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "templates", "companion_config.json"
        )
        with open(template_path) as f:
            config = json.load(f)
        self.assertIn("llm", config)
        self.assertIn("enabled", config["llm"])
        self.assertIn("api_base", config["llm"])
        self.assertIn("api_key_env", config["llm"])
        self.assertIn("model", config["llm"])
        self.assertIn("fallback_to_regex", config["llm"])
        self.assertIn("max_tokens", config["llm"])
        self.assertIn("temperature", config["llm"])
        self.assertIn("timeout_seconds", config["llm"])


class TestRunLLMStatus(unittest.TestCase):
    """Test that run command shows LLM status."""

    def test_run_shows_llm_disabled(self):
        """run should print LLM status line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_workspace(tmpdir, llm_enabled=False)
            # Create minimum files for run to not crash on first step
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "ENVIRONMENT_SNAPSHOT.md"), "")
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "MEMORY_CANDIDATES.md"), "")
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "ACTION_FEEDBACK.md"), "")
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "RELATIONSHIP_TIMELINE.md"), "")
            write_markdown(os.path.join(tmpdir, "AUTOMATION", "DAILY_ACCUMULATION_DRAFT.md"), "")

            from commands.run import cmd_run

            class Args:
                hours = 1
                limit = 10

            captured = StringIO()
            sys.stdout = captured
            try:
                cmd_run(Args(), tmpdir)
            finally:
                sys.stdout = sys.__stdout__

            output = captured.getvalue()
            self.assertIn("LLM: disabled", output)


if __name__ == "__main__":
    unittest.main()

"""
Basic tests for the companion evolution engine.

Covers:
- utils.py core functions
- digest signal extraction (English + Chinese)
- curate parsing and scoring
- timeline event extraction (English + Chinese)

Run with:
  python3 -m unittest discover tests/
  python3 -m pytest tests/
"""

import os
import sys
import json
import tempfile
import unittest

# Add tools/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from utils import generate_id, is_protected, load_json, save_json
from commands.digest import extract_candidates_from_archive
from commands.curate import parse_candidates, score_candidate
from commands.timeline import extract_timeline_events


class TestUtils(unittest.TestCase):
    """Test utils.py core functions."""

    def test_generate_id_prefix(self):
        """generate_id should produce IDs with the given prefix."""
        id1 = generate_id("mem")
        self.assertTrue(id1.startswith("mem-"))
        id2 = generate_id("prop")
        self.assertTrue(id2.startswith("prop-"))

    def test_generate_id_uniqueness(self):
        """generate_id should produce unique IDs (within reason)."""
        ids = set(generate_id("test") for _ in range(10))
        # Due to timestamp granularity, they might collide within the same second
        # But the format should be consistent
        for id_ in ids:
            self.assertRegex(id_, r"^test-\d{14}-[a-f0-9]{6}$")

    def test_is_protected_matches(self):
        """is_protected should match protected patterns."""
        patterns = ["*.key", "*.pem", "*password*", "*/node_modules/*"]
        self.assertTrue(is_protected("/home/user/secret.key", patterns))
        self.assertTrue(is_protected("/etc/ssl/cert.pem", patterns))
        self.assertTrue(is_protected("/app/password_store.txt", patterns))
        self.assertTrue(is_protected("/project/node_modules/pkg/index.js", patterns))

    def test_is_protected_no_match(self):
        """is_protected should not match non-protected files."""
        patterns = ["*.key", "*.pem", "*password*"]
        self.assertFalse(is_protected("/home/user/readme.md", patterns))
        self.assertFalse(is_protected("/project/src/main.py", patterns))
        self.assertFalse(is_protected("/docs/guide.txt", patterns))

    def test_load_json_missing_file(self):
        """load_json should return default when file is missing."""
        result = load_json("/nonexistent/path/data.json", default=[])
        self.assertEqual(result, [])
        result = load_json("/nonexistent/path/data.json", default={})
        self.assertEqual(result, {})

    def test_save_and_load_json(self):
        """save_json and load_json should roundtrip correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            data = {"name": "test", "items": [1, 2, 3], "nested": {"key": "value"}}
            save_json(tmp_path, data)
            loaded = load_json(tmp_path)
            self.assertEqual(loaded, data)
        finally:
            os.unlink(tmp_path)

    def test_save_json_creates_dirs(self):
        """save_json should create parent directories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "sub", "dir", "data.json")
            save_json(path, {"test": True})
            self.assertTrue(os.path.isfile(path))
            loaded = load_json(path)
            self.assertEqual(loaded, {"test": True})


class TestDigest(unittest.TestCase):
    """Test digest signal extraction."""

    def test_extract_english_decision(self):
        """Should detect English decision signals."""
        content = "I decided to switch to the new framework.\nSome random line."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "decision" for c in candidates))

    def test_extract_english_preference(self):
        """Should detect English preference signals."""
        content = "I really prefer dark mode for coding.\nAnother line here."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "preference" for c in candidates))

    def test_extract_english_milestone(self):
        """Should detect English milestone signals."""
        content = "We finally shipped the new release today!"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "milestone" for c in candidates))

    def test_extract_english_insight(self):
        """Should detect English insight signals."""
        content = "I realized the bug was in the config parser."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "insight" for c in candidates))

    def test_extract_english_challenge(self):
        """Should detect English challenge signals."""
        content = "I'm stuck on this auth integration problem."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "challenge" for c in candidates))

    def test_extract_english_emotion(self):
        """Should detect English emotion signals."""
        content = "I'm really happy with how the project turned out."
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "emotion" for c in candidates))

    def test_extract_chinese_decision(self):
        """Should detect Chinese decision signals."""
        content = "最终决定用 React 来做前端。\n其他一些内容。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "decision" for c in candidates))

    def test_extract_chinese_preference(self):
        """Should detect Chinese preference signals."""
        content = "我比较喜欢用 VS Code 写代码。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "preference" for c in candidates))

    def test_extract_chinese_milestone(self):
        """Should detect Chinese milestone signals."""
        content = "新版本终于上线了，用户反馈很好。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "milestone" for c in candidates))

    def test_extract_chinese_insight(self):
        """Should detect Chinese insight signals."""
        content = "我发现这个问题的根本原因是配置文件写错了。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "insight" for c in candidates))

    def test_extract_chinese_challenge(self):
        """Should detect Chinese challenge signals."""
        content = "这个接口的认证搞不定，卡住了两天了。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "challenge" for c in candidates))

    def test_extract_chinese_emotion(self):
        """Should detect Chinese emotion signals."""
        content = "今天天气真好，心情很开心，终于可以休息了。"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertTrue(any(c["category"] == "emotion" for c in candidates))

    def test_skip_short_lines(self):
        """Should skip lines shorter than 10 chars."""
        content = "short\nok\nyes"
        candidates = extract_candidates_from_archive(content, "test.md")
        self.assertEqual(len(candidates), 0)

    def test_skip_headers_and_separators(self):
        """Should skip headers and separator lines."""
        content = "# I decided this\n---\nI decided to use Python for this project."
        candidates = extract_candidates_from_archive(content, "test.md")
        # Only the last line should be captured
        self.assertEqual(len(candidates), 1)
        self.assertIn("Python", candidates[0]["text"])


class TestCurate(unittest.TestCase):
    """Test curate parsing and scoring."""

    def test_parse_candidates_basic(self):
        """parse_candidates should extract items from markdown."""
        content = """# Memory Candidates

## Decision (2)

- I decided to switch to TypeScript for the new project
  _source: archive_001.md_
- We chose PostgreSQL over MySQL for the backend
  _source: archive_002.md_

## Milestone (1)

- Successfully deployed v2.0 to production
  _source: archive_003.md_
"""
        candidates = parse_candidates(content)
        self.assertEqual(len(candidates), 3)
        # Check categories
        decisions = [c for c in candidates if c["category"] == "decision"]
        milestones = [c for c in candidates if c["category"] == "milestone"]
        self.assertEqual(len(decisions), 2)
        self.assertEqual(len(milestones), 1)

    def test_parse_candidates_empty(self):
        """parse_candidates should handle empty content."""
        candidates = parse_candidates("")
        self.assertEqual(len(candidates), 0)

    def test_score_candidate_weight(self):
        """score_candidate should use category weight."""
        decision = {"text": "Short decision text here", "category": "decision", "weight": 5}
        emotion = {"text": "Short emotion text here", "category": "emotion", "weight": 2}
        self.assertGreater(score_candidate(decision), score_candidate(emotion))

    def test_score_candidate_length_bonus(self):
        """score_candidate should give bonus for longer texts."""
        short = {"text": "Short text", "category": "decision", "weight": 5}
        long = {"text": "A much longer description that provides significantly more context about the decision that was made", "category": "decision", "weight": 5}
        self.assertGreater(score_candidate(long), score_candidate(short))

    def test_score_candidate_date_bonus(self):
        """score_candidate should give bonus for dates."""
        no_date = {"text": "Decided to use TypeScript", "category": "decision", "weight": 5}
        with_date = {"text": "On 2024-01-15 decided to use TypeScript", "category": "decision", "weight": 5}
        self.assertGreater(score_candidate(with_date), score_candidate(no_date))

    def test_score_candidate_specifics_bonus(self):
        """score_candidate should give bonus for technical specifics."""
        generic = {"text": "Made a decision about the thing today", "category": "decision", "weight": 5}
        specific = {"text": "Decided to refactor the API layer for better performance", "category": "decision", "weight": 5}
        self.assertGreater(score_candidate(specific), score_candidate(generic))


class TestTimeline(unittest.TestCase):
    """Test timeline event extraction."""

    def test_extract_english_gratitude(self):
        """Should detect English gratitude signals."""
        content = "Thank you so much for helping me with that bug!"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "gratitude" for e in events))

    def test_extract_english_trust(self):
        """Should detect English trust signals."""
        content = "I really trust your judgment on architecture decisions."
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "trust" for e in events))

    def test_extract_english_collaboration(self):
        """Should detect English collaboration signals."""
        content = "Together we refactored the entire auth module."
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "collaboration" for e in events))

    def test_extract_english_milestone(self):
        """Should detect English milestone signals."""
        content = "This is the first time we deployed without issues!"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "milestone" for e in events))

    def test_extract_english_repair(self):
        """Should detect English repair signals."""
        content = "I'm sorry I missed the meeting yesterday."
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "repair" for e in events))

    def test_extract_english_anticipation(self):
        """Should detect English anticipation signals."""
        content = "I really hope the new version works well in production."
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "anticipation" for e in events))

    def test_extract_english_continuity(self):
        """Should detect English continuity signals."""
        content = "Remember when we first started this project last year?"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "continuity" for e in events))

    def test_extract_chinese_gratitude(self):
        """Should detect Chinese gratitude signals."""
        content = "谢谢你帮我解决了那个棘手的问题。"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "gratitude" for e in events))

    def test_extract_chinese_trust(self):
        """Should detect Chinese trust signals."""
        content = "这件事就靠你了，我很放心交给你。"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "trust" for e in events))

    def test_extract_chinese_collaboration(self):
        """Should detect Chinese collaboration signals."""
        content = "我们一起把这个模块重构完了，效果很好。"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "collaboration" for e in events))

    def test_extract_chinese_milestone(self):
        """Should detect Chinese milestone signals."""
        content = "这是第一次上线没有任何问题，太棒了！"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "milestone" for e in events))

    def test_extract_chinese_repair(self):
        """Should detect Chinese repair signals."""
        content = "对不起，昨天的会议我忘记参加了。"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "repair" for e in events))

    def test_extract_chinese_anticipation(self):
        """Should detect Chinese anticipation signals."""
        content = "很期待明天的新版本发布，应该会很顺利。"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "anticipation" for e in events))

    def test_extract_chinese_continuity(self):
        """Should detect Chinese continuity signals."""
        content = "上次你提到的那个方案，我觉得可以试试。"
        events = extract_timeline_events(content, "test.md")
        self.assertTrue(any(e["type"] == "continuity" for e in events))

    def test_skip_short_lines(self):
        """Should skip lines shorter than 15 chars."""
        content = "Thank you\nOk good"
        events = extract_timeline_events(content, "test.md")
        self.assertEqual(len(events), 0)


if __name__ == "__main__":
    unittest.main()

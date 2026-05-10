"""
LLM integration layer for companion.
Uses urllib.request (stdlib) to call OpenAI-compatible APIs.
Falls back to None if LLM is unavailable.
"""

import json
import os
import urllib.request
import urllib.error


class LLMClient:
    """Unified client for OpenAI-compatible LLM APIs."""

    def __init__(self, config):
        """
        Initialize from config dict.

        Expected config structure:
        {
            "llm": {
                "enabled": true,
                "api_base": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-4o-mini",
                "fallback_to_regex": true,
                "max_tokens": 2000,
                "temperature": 0.3,
                "timeout_seconds": 30
            }
        }
        """
        llm_config = config.get("llm", {})
        self.enabled = llm_config.get("enabled", False)
        self.api_base = llm_config.get("api_base", "https://api.openai.com/v1").rstrip("/")
        self.api_key_env = llm_config.get("api_key_env", "OPENAI_API_KEY")
        self.model = llm_config.get("model", "gpt-4o-mini")
        self.fallback_to_regex = llm_config.get("fallback_to_regex", True)
        self.max_tokens = llm_config.get("max_tokens", 2000)
        self.temperature = llm_config.get("temperature", 0.3)
        self.timeout = llm_config.get("timeout_seconds", 30)

        # Resolve API key from environment
        self._api_key = os.environ.get(self.api_key_env, "") if self.api_key_env else ""

    @property
    def api_key(self):
        """Return the resolved API key (read fresh from env each time)."""
        return os.environ.get(self.api_key_env, "") if self.api_key_env else ""

    def is_available(self) -> bool:
        """Check if LLM is enabled and API key exists."""
        if not self.enabled:
            return False
        if not self.api_key:
            return False
        return True

    def chat(self, system_prompt: str, user_prompt: str,
             temperature=None, max_tokens=None) -> "str | None":
        """
        Send a chat completion request.

        Returns response text or None on failure.
        """
        if not self.is_available():
            return None

        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temp,
            "max_tokens": tokens,
        }

        try:
            url = f"{self.api_base}/chat/completions"
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return None

        except (urllib.error.URLError, urllib.error.HTTPError,
                OSError, json.JSONDecodeError, KeyError, IndexError,
                TimeoutError):
            return None

    def chat_json(self, system_prompt: str, user_prompt: str,
                  temperature=None, max_tokens=None):
        """
        Send a chat completion request and parse JSON response.

        Returns parsed dict/list or None on failure.
        """
        result = self.chat(system_prompt, user_prompt, temperature, max_tokens)
        if result is None:
            return None

        # Try to extract JSON from the response (handles ```json blocks)
        text = result.strip()
        if text.startswith("```"):
            # Remove markdown code fence
            lines = text.split("\n")
            # Skip first line (```json) and last line (```)
            inner_lines = []
            started = False
            for line in lines:
                if not started:
                    if line.strip().startswith("```"):
                        started = True
                        continue
                elif line.strip() == "```":
                    break
                else:
                    inner_lines.append(line)
            text = "\n".join(inner_lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON array or object in the text
            for start_char, end_char in [("[", "]"), ("{", "}")]:
                start = text.find(start_char)
                end = text.rfind(end_char)
                if start != -1 and end != -1 and end > start:
                    try:
                        return json.loads(text[start:end + 1])
                    except json.JSONDecodeError:
                        continue
            return None

    def test_connection(self) -> "tuple[bool, str]":
        """
        Test API connectivity with a minimal request.

        Returns (success: bool, message: str).
        """
        if not self.enabled:
            return False, "LLM disabled in config"
        if not self.api_key:
            return False, f"API key not found in env var: {self.api_key_env}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5,
        }

        try:
            url = f"{self.api_base}/chat/completions"
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True, f"Connected to {self.api_base} with model {self.model}"
                return False, f"HTTP {resp.status}"

        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, f"Connection failed: {e.reason}"
        except (OSError, TimeoutError) as e:
            return False, f"Connection error: {e}"

    def status_summary(self) -> str:
        """Return a one-line status string for display."""
        if not self.enabled:
            return "LLM: disabled"
        if not self.api_key:
            return f"LLM: enabled but no API key ({self.api_key_env} not set)"
        return f"LLM: enabled ({self.model} via {self.api_base})"

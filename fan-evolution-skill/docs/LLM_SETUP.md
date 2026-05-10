# LLM Setup Guide

## Overview

Companion v3.0.0 supports optional LLM integration to enhance signal extraction (digest),
reflections, check-in analysis, and deep conversation understanding.

**LLM is NOT required.** Without it, all commands fall back to regex-based analysis.
When configured, it augments the companion's understanding with AI-powered insights.

## Configuration

Add/modify the `llm` section in your `companion_config.json`:

```json
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
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Master switch for LLM features |
| `api_base` | string | `https://api.openai.com/v1` | API endpoint (OpenAI-compatible) |
| `api_key_env` | string | `OPENAI_API_KEY` | Name of environment variable holding the API key |
| `model` | string | `gpt-4o-mini` | Model name to use |
| `fallback_to_regex` | bool | `true` | Fall back to regex when LLM fails |
| `max_tokens` | int | `2000` | Max response tokens |
| `temperature` | float | `0.3` | Generation temperature (lower = more focused) |
| `timeout_seconds` | int | `30` | Request timeout |

## Provider Setup

### OpenAI (GPT-4o / GPT-4o-mini)

```bash
export OPENAI_API_KEY="sk-..."
```

Config:
```json
{
  "llm": {
    "enabled": true,
    "api_base": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "model": "gpt-4o-mini"
  }
}
```

### Anthropic (Claude) via OpenAI-compatible proxy

Use an OpenAI-compatible proxy like [LiteLLM](https://github.com/BerriAI/litellm)
or [one-api](https://github.com/songquanpeng/one-api):

```bash
export ANTHROPIC_PROXY_KEY="your-proxy-key"
```

Config:
```json
{
  "llm": {
    "enabled": true,
    "api_base": "https://your-proxy.example.com/v1",
    "api_key_env": "ANTHROPIC_PROXY_KEY",
    "model": "claude-3-haiku-20240307"
  }
}
```

### OpenRouter (multiple models)

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

Config:
```json
{
  "llm": {
    "enabled": true,
    "api_base": "https://openrouter.ai/api/v1",
    "api_key_env": "OPENROUTER_API_KEY",
    "model": "anthropic/claude-3-haiku"
  }
}
```

### Ollama (local, no API key needed)

Run Ollama locally:
```bash
ollama run llama3.1
```

Config:
```json
{
  "llm": {
    "enabled": true,
    "api_base": "http://localhost:11434/v1",
    "api_key_env": "",
    "model": "llama3.1"
  }
}
```

Note: Set `api_key_env` to empty string `""` for Ollama (no key required).
The companion will still check `is_available()` — for Ollama, update the check or
set a dummy env var:

```bash
export OLLAMA_KEY="dummy"
```

```json
"api_key_env": "OLLAMA_KEY"
```

### DeepSeek

```bash
export DEEPSEEK_API_KEY="sk-..."
```

Config:
```json
{
  "llm": {
    "enabled": true,
    "api_base": "https://api.deepseek.com/v1",
    "api_key_env": "DEEPSEEK_API_KEY",
    "model": "deepseek-chat"
  }
}
```

### Groq (fast inference)

```bash
export GROQ_API_KEY="gsk_..."
```

Config:
```json
{
  "llm": {
    "enabled": true,
    "api_base": "https://api.groq.com/openai/v1",
    "api_key_env": "GROQ_API_KEY",
    "model": "llama-3.1-70b-versatile"
  }
}
```

## Verification

After configuration:

```bash
# Check that companion sees the LLM config
python3 tools/companion.py status

# Run doctor to verify API key is in environment
python3 tools/companion.py doctor

# Test with understand command
python3 tools/companion.py understand --text "I decided to learn Rust today."
```

## Troubleshooting

### "LLM: enabled but no API key"
- Check that the environment variable named in `api_key_env` is exported
- Run `echo $OPENAI_API_KEY` to verify

### "LLM request failed"
- Check network connectivity
- Verify `api_base` URL is correct
- Check model name is valid for your provider
- Increase `timeout_seconds` for slow connections

### Fallback behavior
When `fallback_to_regex` is `true` (default), any LLM failure silently falls
back to regex-based extraction. The output will show `method: regex` in digest
and `[rule-based]` in reflect/check-in.

## Cost Considerations

The companion uses small, focused prompts (typically <2000 tokens input).
With `gpt-4o-mini`, a full daily loop costs approximately:
- digest: ~$0.001 per archive scanned
- reflect: ~$0.0005 per run
- check-in: ~$0.0005 per run
- understand: ~$0.002 per analysis

Total daily cost: typically under $0.01 for normal usage.

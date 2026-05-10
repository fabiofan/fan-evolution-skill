"""
understand — Deep analysis of a conversation or text using LLM.

Produces:
- Emotional trajectory (start → middle → end)
- Implicit needs (what wasn't said directly)
- Relationship dynamics (drawing closer or pulling apart, and why)
- Memory suggestions (what's worth remembering, and why)

This command requires LLM support. Without an API key, it outputs a helpful message.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_config, read_markdown, get_llm_client


LLM_UNDERSTAND_SYSTEM_PROMPT = """你是一个对话深度分析引擎。分析以下对话/文本内容，输出四个维度的洞察。

请严格按以下格式输出：

## 情绪走向
描述对话中情绪的变化轨迹（开始→中间→结束），注意微妙的情绪转折点。

## 隐含需求
用户没有直接说出来，但在表达的深层需求是什么？（安全感、被理解、被认可、独处空间、控制感等）

## 关系动态
这段对话对关系的影响——是拉近还是疏远？哪些时刻是转折点？为什么？

## 记忆建议
哪些内容值得长期记住？为什么这些内容重要？给出具体建议。

保持分析准确、简洁、有洞察力。避免泛泛而谈。"""


def cmd_understand(args, root):
    """Execute the understand command."""
    config = load_config(root)

    # Get input text
    text = None
    source = None

    if hasattr(args, 'file') and args.file:
        filepath = args.file
        if not os.path.isabs(filepath):
            filepath = os.path.join(root, filepath)
        if not os.path.isfile(filepath):
            print(f"[understand] Error: file not found: {filepath}")
            return
        text = read_markdown(filepath)
        source = os.path.basename(filepath)
    elif hasattr(args, 'text') and args.text:
        text = args.text
        source = "inline-text"
    else:
        print("[understand] Error: provide --file or --text")
        print("  Usage: companion understand --file <conversation_file>")
        print("  Usage: companion understand --text \"...\"")
        return

    if not text or not text.strip():
        print("[understand] Error: input is empty")
        return

    # Check LLM availability
    llm_client = get_llm_client(root)
    if not llm_client or not llm_client.is_available():
        print("[understand] This command requires LLM support.")
        print()
        print("  To enable LLM, configure in companion_config.json:")
        print('    "llm": {')
        print('      "enabled": true,')
        print('      "api_base": "https://api.openai.com/v1",')
        print('      "api_key_env": "OPENAI_API_KEY",')
        print('      "model": "gpt-4o-mini"')
        print("    }")
        print()
        print("  Then set the environment variable:")
        print("    export OPENAI_API_KEY=sk-...")
        return

    # Truncate to avoid token limits
    truncated = text[:8000]
    if len(text) > 8000:
        truncated += "\n... (truncated)"

    user_prompt = f"来源: {source}\n\n内容:\n{truncated}"

    print(f"[understand] Analyzing: {source} ({len(text)} chars)")
    print(f"[understand] Using: {llm_client.model}")
    print()

    result = llm_client.chat(LLM_UNDERSTAND_SYSTEM_PROMPT, user_prompt,
                             temperature=0.4, max_tokens=2000)

    if result is None:
        print("[understand] LLM request failed. Check your API key and network.")
        return

    print(f"# Deep Understanding — {source}")
    print()
    print(result)

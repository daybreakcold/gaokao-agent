#!/usr/bin/env python3
"""
高考志愿填报规划 Agent —— 命令行多轮对话版。
模型: DeepSeek（OpenAI 兼容接口）

用法:
    export DEEPSEEK_API_KEY="sk-..."
    python gaokao_agent.py

    # 直接带一句话开场
    python gaokao_agent.py --text "我是江苏考生，2024年，物化生，620分，位次1.2万"

环境准备:
    pip install openai
    export DEEPSEEK_API_KEY="sk-..."          # platform.deepseek.com 获取

说明:
    - 系统提示词从同目录 system_prompt.md 读取，便于随时调整规则。
    - 多轮对话：程序会保留上下文，输入 exit / quit / 退出 结束。
"""

import argparse
import json
import os
import sys
from pathlib import Path

from openai import OpenAI, APIError, AuthenticationError, RateLimitError

import web_tools as wt  # 联网工具：web_search / read_url

PROMPT_FILE = Path(__file__).with_name("system_prompt.md")

# 默认开场白（对应系统提示词 第 21 节）
GREETING = (
    "我可以帮你做一版高考志愿填报方案。为了避免误判，请先提供以下信息："
    "省份、高考年份、总分、全省位次、选科组合、批次、想去的城市、想学的专业、"
    "不能接受的专业、是否服从调剂、是否接受中外合作或民办本科、家庭预算、"
    "未来更看重就业还是考研。拿到这些信息后，我会按冲、稳、保、垫给你做一版完整方案。"
)


def load_system_prompt() -> str:
    if not PROMPT_FILE.exists():
        sys.exit(f"错误：未找到系统提示词文件 {PROMPT_FILE}")
    return PROMPT_FILE.read_text(encoding="utf-8")


def reply_with_tools(client: OpenAI, messages: list, *, model: str,
                     temperature: float, use_web: bool = True, max_rounds: int = 6) -> str:
    """一轮回复：联网开启时按需调用 web_search / read_url；关闭时仅用模型知识。"""
    if not use_web:
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
        )
        text = resp.choices[0].message.content or ""
        print(text)
        return text
    resp = None
    for _ in range(max_rounds):
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
            tools=wt.TOOLS, tool_choice="auto",
        )
        msg = resp.choices[0].message
        tcs = msg.tool_calls or []
        if not tcs:
            text = msg.content or ""
            print(text)
            return text
        messages.append({
            "role": "assistant", "content": msg.content or "",
            "tool_calls": [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name,
                                         "arguments": tc.function.arguments}}
                           for tc in tcs],
        })
        for tc in tcs:
            try:
                a = json.loads(tc.function.arguments or "{}")
            except Exception:
                a = {}
            label = a.get("query") or a.get("url") or ""
            action = "联网检索" if tc.function.name == "web_search" else "读取网页"
            print(f"  🔍 {action}：{label}", file=sys.stderr, flush=True)
            result = wt.run_tool(tc.function.name, a)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    # 轮次用尽：强制不带工具汇总；若仍无有效答案则用确定性兜底
    messages.append({"role": "user", "content":
        "联网检索暂时不可用。请不要再调用工具，直接基于你已有的知识作答："
        "明确标注为非官方数据、提醒以省考试院/阳光高考官方发布为准，"
        "并给出查询官方数据的具体步骤；不要输出‘让我尝试’这类过渡语。"})
    try:
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
            tools=wt.TOOLS, tool_choice="none",
        )
        text = resp.choices[0].message.content or ""
    except Exception:
        text = ""
    if len(text.strip()) < 40:
        text = wt.SEARCH_UNAVAILABLE_MSG
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="高考志愿填报规划 Agent（DeepSeek）")
    parser.add_argument("--text", help="开场直接发送的一句话")
    parser.add_argument("--model", default="deepseek-v4-pro",
                        help="模型 ID（默认 deepseek-v4-pro；更快用 deepseek-v4-flash）")
    parser.add_argument("--base-url",
                        default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                        help="API 地址（默认 https://api.deepseek.com）")
    parser.add_argument("--temperature", type=float, default=0.4,
                        help="采样温度（默认 0.4）")
    parser.add_argument("--no-web", action="store_true",
                        help="关闭联网搜索（仅用模型已有知识作答）")
    args = parser.parse_args()

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        sys.exit("错误：未设置 DEEPSEEK_API_KEY。请到 platform.deepseek.com 获取并 export。")

    client = OpenAI(api_key=api_key, base_url=args.base_url)
    addendum = wt.WEB_OFF_NOTE if args.no_web else wt.TOOL_ADDENDUM
    messages = [{"role": "system", "content": load_system_prompt() + addendum}]

    print("🎓 高考志愿填报规划 Agent（DeepSeek）")
    print("   输入 exit / quit / 退出 结束对话。\n")
    print(f"Agent：{GREETING}\n")

    # 处理开场参数
    pending = args.text

    while True:
        if pending is not None:
            user_input = pending
            pending = None
            print(f"你：{user_input}\n")
        else:
            try:
                user_input = input("你：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见，祝填报顺利。")
                return
            print()

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"} or user_input in {"退出", "结束"}:
            print("再见，祝填报顺利。")
            return

        messages.append({"role": "user", "content": user_input})
        print("Agent：", flush=True)
        try:
            reply = reply_with_tools(client, messages, model=args.model,
                                     temperature=args.temperature, use_web=not args.no_web)
        except AuthenticationError:
            sys.exit("\n错误：API Key 无效。请检查 DEEPSEEK_API_KEY。")
        except RateLimitError:
            print("\n（触发限流，请稍后重试）")
            messages.pop()
            continue
        except APIError as e:
            print(f"\n（API 错误：{e}）")
            messages.pop()
            continue
        messages.append({"role": "assistant", "content": reply})
        print()


if __name__ == "__main__":
    main()

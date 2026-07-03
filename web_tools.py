#!/usr/bin/env python3
"""
联网工具模块 —— 为 Agent 提供 web_search / read_url 两个工具（纯标准库）。

- web_search(query)：默认用 DuckDuckGo（无需 Key）；若 .env 配了 TAVILY_API_KEY，
  则优先用 Tavily（对 LLM 更友好、结果更准）。
- read_url(url)：抓取网页并提取正文，便于核对官方页面。

对外暴露：TOOLS（OpenAI 工具定义）、run_tool(name, args)、TOOL_ADDENDUM（系统提示词补充）。
"""

import http.client
import json
import os
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SKIP_TAGS = {"script", "style", "noscript", "template", "svg",
             "nav", "footer", "aside", "header", "form", "button", "iframe"}
BLOCK_TAGS = {"p", "div", "section", "article", "li", "br", "h1", "h2",
              "h3", "h4", "h5", "h6", "tr", "blockquote", "pre"}


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = 0
        self._in_title = False
        self.title = ""
        self._chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip > 0:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        if tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
            return
        t = data.strip()
        if t:
            self._chunks.append(t)

    def get_text(self):
        raw = " ".join(self._chunks)
        lines = [ln.strip() for ln in raw.split("\n")]
        return "\n".join(ln for ln in lines if ln)


def _http_get(url, timeout=20, data=None, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    resp = urllib.request.urlopen(req, timeout=timeout)
    try:
        raw = resp.read()
    except http.client.IncompleteRead as e:
        raw = e.partial  # 连接被中途截断时，使用已收到的部分
    finally:
        resp.close()
    charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def extract_main_text(html):
    p = _Extractor()
    p.feed(html)
    return p.get_text(), p.title.strip()


def fetch_url(url, timeout=20, max_chars=6000):
    """读取网页正文。"""
    if not (url.startswith("http://") or url.startswith("https://")):
        return "错误：url 必须以 http:// 或 https:// 开头"
    html = _http_get(url, timeout=timeout)
    text, title = extract_main_text(html)
    out = f"标题：{title}\n来源：{url}\n\n{text}" if title else f"来源：{url}\n\n{text}"
    return out[:max_chars]


def _strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    return _unescape(s).strip()


def _unescape(s):
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&#x27;", "'").replace("&#39;", "'")
             .replace("&nbsp;", " "))


def _decode_ddg_link(href):
    """DuckDuckGo 结果链接常是 //duckduckgo.com/l/?uddg=<编码后的真实地址>。"""
    if "uddg=" in href:
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            return urllib.parse.unquote(m.group(1))
    if href.startswith("//"):
        return "https:" + href
    return href


def _search_duckduckgo(query, n, timeout):
    data = urllib.parse.urlencode({"q": query, "kl": "cn-zh"}).encode()
    html = _http_get("https://html.duckduckgo.com/html/", timeout=timeout, data=data)
    results = []
    # 每条结果：标题链接 result__a，摘要 result__snippet
    titles = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
    for i, (href, title) in enumerate(titles[:n]):
        results.append({
            "title": _strip_tags(title),
            "url": _decode_ddg_link(href),
            "snippet": _strip_tags(snippets[i]) if i < len(snippets) else "",
        })
    return results


def _search_tavily(query, n, timeout):
    key = os.getenv("TAVILY_API_KEY")
    body = json.dumps({
        "api_key": key, "query": query, "max_results": n,
        "search_depth": "basic", "include_answer": False,
    }).encode()
    raw = _http_get("https://api.tavily.com/search", timeout=timeout, data=body,
                    headers={"Content-Type": "application/json"})
    data = json.loads(raw)
    return [{"title": r.get("title", ""), "url": r.get("url", ""),
             "snippet": r.get("content", "")} for r in data.get("results", [])[:n]]


def web_search(query, n=5, timeout=20, retries=3):
    """联网搜索，返回 [{title,url,snippet}]。网络抖动时自动重试。"""
    query = (query or "").strip()
    if not query:
        return []
    if os.getenv("TAVILY_API_KEY"):
        try:
            return _search_tavily(query, n, timeout)
        except Exception:
            pass  # 回退到 DuckDuckGo
    last_err = None
    for _ in range(max(1, retries)):
        try:
            res = _search_duckduckgo(query, n, timeout)
            if res:
                return res
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    return []


# ── 供 LLM 调用的工具定义（OpenAI 格式）─────────────────────────────
TOOLS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "联网搜索最新信息。用于查询高考招生计划、投档线、最低录取位次、"
                       "一分一段表、招生章程、院校专业组、选科要求等官方或权威数据。"
                       "返回若干条标题、链接和摘要。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string",
                      "description": "搜索关键词，尽量具体，包含省份、年份、院校/专业、"
                                     "以及‘投档线/最低位次/招生计划/一分一段’等"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_url",
        "description": "读取指定网页链接的正文内容，用于深入核对搜索结果里的官方页面"
                       "（省考试院、教育部阳光高考平台、院校招生网等）。",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "要读取的网页完整链接"}},
            "required": ["url"]}}},
]


# 联网开关关闭时，替换 TOOL_ADDENDUM 注入系统提示词
WEB_OFF_NOTE = """

---

## 当前状态：联网已关闭

本轮无法联网检索。请直接基于你已有的知识作答，并遵守：
1. 涉及具体招生计划、投档线、最低位次等数据时，明确标注为“非官方、可能过时”，提醒以省考试院 / 教育部阳光高考平台 / 院校官方招生网的最新发布为准。
2. 不要假装调用工具，也不要输出 web_search、read_url 之类的伪工具调用文本。
3. 仍缺少省份 / 位次 / 选科等关键信息时，先索要信息。
"""


# 联网完全不可用时的确定性兜底答复（不依赖模型）
SEARCH_UNAVAILABLE_MSG = (
    "⚠️ 当前联网检索暂时不可用，无法实时核实官方录取数据。\n\n"
    "请通过以下**官方渠道**查询最准确的数据：\n"
    "1. **省考试院官网**：查当年「普通高校招生本科批投档线」公告。\n"
    "2. **教育部阳光高考平台**（gaokao.chsi.com.cn）：查院校录取数据。\n"
    "3. **目标院校本科招生网**：查历年录取分数与位次。\n\n"
    "你也可以把已知的省份、年份、分数、全省位次、选科组合发给我，"
    "我可以先基于公开规律做**非官方的参考性**冲/稳/保/垫分析（最终须以官方发布为准）。"
)


def run_tool(name, args):
    """执行工具，返回字符串结果（喂回给模型）。"""
    try:
        if name == "web_search":
            res = web_search(args.get("query", ""))
            if not res:
                return "（未检索到结果，可能是网络受限。请基于已有知识谨慎作答，并提醒以官方数据为准。）"
            return json.dumps(res, ensure_ascii=False)
        if name == "read_url":
            return fetch_url(args.get("url", ""))
        return f"未知工具：{name}"
    except Exception as e:
        return f"工具执行失败：{e}"


# ── 系统提示词补充：告诉模型如何使用联网工具 ─────────────────────
TOOL_ADDENDUM = """

---

## 联网能力（重要）

你现在具备联网工具：
- web_search(query)：搜索最新信息（招生计划、投档线、最低录取位次、一分一段表、招生章程、专业组、选科要求等）。
- read_url(url)：读取某个网页的正文，用于核对官方来源（省考试院、教育部阳光高考平台、院校官方招生网）。

使用要求：
1. 当需要当年或最新的招生计划、投档线、最低录取位次等**具体数据**时，必须先用 web_search 检索，再用 read_url 打开权威来源核实，不要凭记忆编造数据。
2. 数据来源优先级：省考试院 / 教育部阳光高考平台 / 院校官方招生网 > 第三方数据平台（仅供参考）。
3. 在结论中标注数据来源与年份；若联网后仍无法确认，明确说明“需以官方最新发布为准”。
4. 不要为了调用工具而调用：属于通用解释、信息已足够、或仍缺少省份/位次/选科等关键输入时，直接回答或先索要信息。
"""

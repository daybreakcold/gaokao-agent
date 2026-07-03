#!/usr/bin/env python3
"""
高考志愿填报规划 Agent —— 网页对话版（DeepSeek）

启动:
    export DEEPSEEK_API_KEY="sk-..."
    .venv/bin/python web_app.py
    # 然后浏览器打开 http://127.0.0.1:8010

功能:
    - 多轮对话：前端维护历史，逐轮发送
    - 流式输出：边生成边显示
    - 左侧「考生信息」表单：一键拼成规范输入发给 Agent
    - 系统提示词从 system_prompt.md 读取
    - API Key 只在服务端使用，不发送到浏览器
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from openai import OpenAI, APIError, AuthenticationError, RateLimitError

import web_tools as wt  # 联网工具：web_search / read_url

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8010"))
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
PROMPT_FILE = Path(__file__).with_name("system_prompt.md")

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


BASE_PROMPT = load_system_prompt()

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>高考志愿填报规划 Agent</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root { --accent:#1d4ed8; --accent2:#0ea5e9; --bg:#eef2f7; --card:#fff;
          --border:#e3e6ea; --muted:#6b7280; --chong:#dc2626; --wen:#16a34a;
          --bao:#2563eb; --dian:#7c3aed; }
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;
         background:var(--bg); color:#1f2328; height:100vh; display:flex; flex-direction:column; }
  header { padding:14px 22px; background:linear-gradient(90deg,var(--accent),var(--accent2)); color:#fff; }
  header h1 { margin:0; font-size:17px; display:flex; align-items:center; gap:8px; }
  header p { margin:3px 0 0; font-size:12px; opacity:.9; }
  .layout { flex:1; display:grid; grid-template-columns:300px 1fr; min-height:0; }
  @media (max-width:820px){ .layout{ grid-template-columns:1fr; } .side{ display:none; } }

  /* 左侧：考生信息表单 */
  .side { background:var(--card); border-right:1px solid var(--border); padding:16px; overflow:auto; }
  .side h2 { margin:0 0 4px; font-size:14px; }
  .side .tip { color:var(--muted); font-size:12px; margin:0 0 12px; }
  .field { margin-bottom:10px; }
  .field label { display:block; font-size:12px; color:var(--muted); margin-bottom:4px; }
  .field input, .field select { width:100%; padding:8px 10px; border:1px solid var(--border);
        border-radius:8px; font-size:13px; font-family:inherit; outline:none; }
  .field input:focus, .field select:focus { border-color:var(--accent); }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  .fillbtn { width:100%; margin-top:6px; background:var(--accent); color:#fff; border:0;
        border-radius:8px; padding:10px; font-size:14px; cursor:pointer; }

  /* 右侧：对话 */
  .chat { display:flex; flex-direction:column; min-height:0; }
  .msgs { flex:1; overflow:auto; padding:22px; }
  .msg { max-width:760px; margin:0 auto 16px; display:flex; gap:10px; }
  .msg .avatar { width:30px; height:30px; border-radius:8px; flex:0 0 30px; display:flex;
        align-items:center; justify-content:center; font-size:16px; }
  .msg.user .avatar { background:#dbeafe; }
  .msg.bot .avatar { background:linear-gradient(135deg,var(--accent),var(--accent2)); }
  .bubble { background:var(--card); border:1px solid var(--border); border-radius:12px;
        padding:12px 14px; font-size:14px; line-height:1.7; overflow:auto; }
  .msg.user .bubble { background:#eff4ff; }
  .bubble table { border-collapse:collapse; width:100%; margin:10px 0; }
  .bubble th, .bubble td { border:1px solid var(--border); padding:6px 8px; font-size:12px; text-align:left; }
  .bubble th { background:#f0f3f7; }
  .bubble h2 { font-size:15px; margin:16px 0 8px; border-bottom:1px solid var(--border); padding-bottom:4px; }
  .bubble h3 { font-size:14px; margin:12px 0 6px; }
  .badge { display:inline-block; color:#fff; border-radius:6px; padding:1px 8px; font-size:12px; margin-right:4px; }
  .b-chong{background:var(--chong);} .b-wen{background:var(--wen);} .b-bao{background:var(--bao);} .b-dian{background:var(--dian);}
  .spin { display:inline-block; width:13px; height:13px; border:2px solid #cbd5e1; border-top-color:var(--accent);
          border-radius:50%; animation:r .7s linear infinite; vertical-align:middle; }
  @keyframes r { to { transform:rotate(360deg); } }
  .searchlog { color:#64748b; font-size:12px; line-height:1.7; background:#f1f5f9;
        border:1px solid #e2e8f0; border-radius:8px; padding:8px 10px; margin-bottom:8px; }
  .searchlog.live { color:#1d4ed8; }

  .composer { border-top:1px solid var(--border); background:var(--card); padding:12px 22px; }
  .composer .inner { max-width:760px; margin:0 auto; display:flex; gap:10px; align-items:flex-end; }
  textarea { flex:1; resize:none; border:1px solid var(--border); border-radius:10px; padding:10px 12px;
        font-size:14px; line-height:1.5; font-family:inherit; outline:none; max-height:160px; }
  textarea:focus { border-color:var(--accent); }
  .send { background:var(--accent); color:#fff; border:0; border-radius:10px; padding:10px 20px;
        font-size:14px; cursor:pointer; }
  .send:disabled { opacity:.5; cursor:not-allowed; }
  .disclaimer { max-width:760px; margin:6px auto 0; color:var(--muted); font-size:11px; text-align:center; }
  .webbar { max-width:760px; margin:0 auto 8px; display:flex; justify-content:flex-end; }
  .switch { display:inline-flex; align-items:center; gap:8px; cursor:pointer; user-select:none; }
  .switch input { display:none; }
  .switch .track { width:38px; height:22px; border-radius:999px; background:#cbd5e1; position:relative; transition:background .15s; }
  .switch .knob { position:absolute; top:2px; left:2px; width:18px; height:18px; border-radius:50%; background:#fff;
        transition:left .15s; box-shadow:0 1px 3px rgba(0,0,0,.25); }
  .switch input:checked + .track { background:var(--accent); }
  .switch input:checked + .track .knob { left:18px; }
  .switch .swlabel { font-size:12px; color:#475569; }
</style>
</head>
<body>
<header>
  <h1>🎓 高考志愿填报规划 Agent</h1>
  <p>冲 / 稳 / 保 / 垫 分层方案 · 以位次为核心 · 数据驱动、不承诺录取 · 模型：DeepSeek V4</p>
</header>
<div class="layout">
  <!-- 左侧考生信息表单 -->
  <aside class="side">
    <h2>考生信息</h2>
    <p class="tip">填好后点「整理并发送」，会自动拼成规范输入。也可直接在右侧聊天。</p>
    <div class="field"><label>省份</label><input id="f_prov" placeholder="如 江苏"></div>
    <div class="grid2">
      <div class="field"><label>高考年份</label><input id="f_year" placeholder="2025"></div>
      <div class="field"><label>批次</label><input id="f_batch" placeholder="本科批"></div>
    </div>
    <div class="grid2">
      <div class="field"><label>总分</label><input id="f_score" placeholder="620"></div>
      <div class="field"><label>全省位次</label><input id="f_rank" placeholder="12000"></div>
    </div>
    <div class="field"><label>选科组合</label><input id="f_subj" placeholder="物理+化学+生物"></div>
    <div class="field"><label>想去的城市</label><input id="f_city" placeholder="南京 / 上海"></div>
    <div class="field"><label>想学的专业</label><input id="f_major" placeholder="计算机 / 电子信息"></div>
    <div class="field"><label>不能接受的专业</label><input id="f_nomajor" placeholder="如 化学、生物"></div>
    <div class="grid2">
      <div class="field"><label>服从调剂</label>
        <select id="f_adjust"><option value="">未定</option><option>是</option><option>否</option></select></div>
      <div class="field"><label>家庭预算</label><input id="f_budget" placeholder="公办为主"></div>
    </div>
    <div class="grid2">
      <div class="field"><label>中外合作</label>
        <select id="f_sino"><option value="">未定</option><option>接受</option><option>不接受</option></select></div>
      <div class="field"><label>民办本科</label>
        <select id="f_priv"><option value="">未定</option><option>接受</option><option>不接受</option></select></div>
    </div>
    <div class="field"><label>更看重</label>
      <select id="f_goal">
        <option value="">未定</option><option>就业</option><option>考研</option>
        <option>考公考编</option><option>稳录取</option><option>冲名校</option>
      </select></div>
    <div class="field"><label>风险偏好</label>
      <select id="f_risk">
        <option value="">默认（平衡型）</option><option>稳健型</option><option>平衡型</option><option>进取型</option>
      </select></div>
    <button class="fillbtn" id="fill">整理并发送</button>
  </aside>

  <!-- 右侧对话 -->
  <section class="chat">
    <div class="msgs" id="msgs"></div>
    <div class="composer">
      <div class="webbar">
        <label class="switch" title="关闭后本轮不联网，仅用模型已有知识作答">
          <input type="checkbox" id="webtoggle" checked>
          <span class="track"><span class="knob"></span></span>
          <span class="swlabel">🌐 联网搜索</span>
        </label>
      </div>
      <div class="inner">
        <textarea id="input" rows="1" placeholder="补充信息或提问，Enter 发送，Shift+Enter 换行..."></textarea>
        <button class="send" id="send">发送</button>
      </div>
      <div class="disclaimer">本工具仅提供参考建议，不构成录取承诺。最终须以省考试院官方招生计划、专业组代码与投档结果为准。</div>
    </div>
  </section>
</div>
<script>
  const GREETING = %GREETING%;
  const msgsEl = document.getElementById('msgs');
  const inputEl = document.getElementById('input');
  const sendEl = document.getElementById('send');
  const history = [];   // {role, content}

  function escapeHtml(s){ return (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

  function addMsg(role, html){
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + (role === 'user' ? 'user' : 'bot');
    wrap.innerHTML = '<div class="avatar">' + (role === 'user' ? '🧑' : '🎓') +
      '</div><div class="bubble">' + html + '</div>';
    msgsEl.appendChild(wrap);
    msgsEl.scrollTop = msgsEl.scrollHeight;
    return wrap.querySelector('.bubble');
  }

  // 给“冲/稳/保/垫”染色
  function colorize(md){
    let h = marked.parse(md);
    h = h.replace(/冲刺|冲（|^冲$/g, m => '<span class="badge b-chong">'+m+'</span>');
    return h;
  }

  addMsg('bot', marked.parse(GREETING));

  async function send(text){
    text = (text || '').trim();
    if (!text) return;
    addMsg('user', marked.parse(text));
    history.push({ role:'user', content:text });
    inputEl.value = ''; autoGrow();
    sendEl.disabled = true;
    const bubble = addMsg('bot', '<span class="spin"></span>');
    let raw = '';
    try {
      const res = await fetch('/api/chat', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ messages: history, web: document.getElementById('webtoggle').checked })
      });
      if (!res.ok) {
        const d = await res.json().catch(()=>({}));
        bubble.innerHTML = '<span style="color:#b91c1c">' + (d.error || ('出错了 HTTP '+res.status)) + '</span>';
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      const SEP = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        raw += dec.decode(value, { stream:true });
        const idx = raw.indexOf(SEP);
        if (idx < 0) {
          // 仍在联网检索：显示临时进度
          bubble.innerHTML = '<div class="searchlog live">' +
            escapeHtml(raw).replace(/\\n/g,'<br>') + '<span class="spin"></span></div>';
        } else {
          const prog = raw.slice(0, idx), ans = raw.slice(idx + 1);
          let html = '';
          if (prog.trim()) html += '<div class="searchlog">' +
            escapeHtml(prog).replace(/\\n/g,'<br>') + '</div>';
          html += marked.parse(ans);
          bubble.innerHTML = html;
        }
        msgsEl.scrollTop = msgsEl.scrollHeight;
      }
      const sepIdx = raw.indexOf(SEP);
      const answer = sepIdx < 0 ? raw : raw.slice(sepIdx + 1);
      history.push({ role:'assistant', content:answer });   // 历史只存答案，不含检索进度
    } catch (e) {
      bubble.innerHTML = '<span style="color:#b91c1c">请求失败：' + e.message + '</span>';
    } finally {
      sendEl.disabled = false;
      inputEl.focus();
    }
  }

  // 表单 → 规范输入
  document.getElementById('fill').onclick = () => {
    const v = id => (document.getElementById(id).value || '').trim();
    const rows = [
      ['省份', v('f_prov')], ['高考年份', v('f_year')], ['批次', v('f_batch')],
      ['总分', v('f_score')], ['全省位次', v('f_rank')], ['选科组合', v('f_subj')],
      ['想去的城市', v('f_city')], ['想学的专业', v('f_major')], ['不能接受的专业', v('f_nomajor')],
      ['是否服从调剂', v('f_adjust')], ['家庭预算', v('f_budget')],
      ['是否接受中外合作', v('f_sino')], ['是否接受民办本科', v('f_priv')],
      ['更看重', v('f_goal')], ['风险偏好', v('f_risk')],
    ].filter(r => r[1]);
    if (!rows.length) { inputEl.focus(); return; }
    const text = '以下是我的考生信息：\\n' + rows.map(r => '- ' + r[0] + '：' + r[1]).join('\\n');
    send(text);
  };

  function autoGrow(){ inputEl.style.height = 'auto'; inputEl.style.height = Math.min(inputEl.scrollHeight,160)+'px'; }
  inputEl.addEventListener('input', autoGrow);
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(inputEl.value); }
  });
  sendEl.onclick = () => send(inputEl.value);
  inputEl.focus();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_chunk(self, data: bytes):
        self.wfile.write(f"{len(data):X}\r\n".encode())
        self.wfile.write(data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def _end_chunks(self):
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = PAGE.replace("%GREETING%", json.dumps(GREETING, ensure_ascii=False))
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"Not Found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/api/chat":
            self._send(404, b"Not Found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._send(400, json.dumps({"error": f"请求解析失败：{e}"}).encode(), "application/json")
            return

        client_msgs = payload.get("messages") or []
        model = payload.get("model") or "deepseek-v4-pro"
        use_web = payload.get("web", True)          # 联网开关，默认开
        tool_kw = {"tools": wt.TOOLS, "tool_choice": "auto"} if use_web else {}
        if not client_msgs:
            self._send(400, json.dumps({"error": "对话内容为空"}).encode(), "application/json")
            return

        # 只保留 role/content，并按联网开关注入对应的系统提示词
        clean = [{"role": m.get("role"), "content": m.get("content", "")}
                 for m in client_msgs if m.get("role") in ("user", "assistant")]
        sys_content = BASE_PROMPT + (wt.TOOL_ADDENDUM if use_web else wt.WEB_OFF_NOTE)
        messages = [{"role": "system", "content": sys_content}] + clean

        # 第一轮模型调用放在 JSON 错误保护里（可在发送 200 之前以 JSON 返回错误）
        api = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=BASE_URL)
        try:
            resp = api.chat.completions.create(
                model=model, messages=messages, temperature=0.4, **tool_kw,
            )
        except AuthenticationError:
            self._send(401, json.dumps({"error": "API Key 无效，请检查 DEEPSEEK_API_KEY"}).encode(), "application/json")
            return
        except RateLimitError:
            self._send(429, json.dumps({"error": "触发限流，请稍后重试"}).encode(), "application/json")
            return
        except APIError as e:
            self._send(502, json.dumps({"error": f"API 错误：{e}"}).encode(), "application/json")
            return
        except Exception as e:
            self._send(500, json.dumps({"error": f"服务器错误：{e}"}).encode(), "application/json")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        # 工具调用循环：进度用  之前的文本传给前端（临时提示），
        #  之后才是正式答案，便于前端区分、且不污染对话历史。
        MAX_ROUNDS = 6
        try:
            final = ""
            exhausted = True
            for _ in range(MAX_ROUNDS):
                msg = resp.choices[0].message
                tcs = msg.tool_calls or []
                if not tcs:
                    final = msg.content or ""
                    exhausted = False
                    break
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
                    self._write_chunk(f"🔍 {action}：{label}\n".encode("utf-8"))
                    result = wt.run_tool(tc.function.name, a)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                resp = api.chat.completions.create(
                    model=model, messages=messages, temperature=0.4,
                    tools=wt.TOOLS, tool_choice="auto",
                )
            if exhausted:
                # 轮次用尽仍想调工具：强制不带工具汇总；若仍无有效答案则用确定性兜底
                messages.append({"role": "user", "content":
                    "联网检索暂时不可用。请不要再调用工具，直接基于你已有的知识作答："
                    "明确标注为非官方数据、提醒以省考试院/阳光高考官方发布为准，"
                    "并给出查询官方数据的具体步骤；不要输出‘让我尝试’这类过渡语。"})
                try:
                    resp = api.chat.completions.create(
                        model=model, messages=messages, temperature=0.4,
                        tools=wt.TOOLS, tool_choice="none",
                    )
                    final = resp.choices[0].message.content or ""
                except Exception:
                    final = ""
                if len(final.strip()) < 40:
                    final = wt.SEARCH_UNAVAILABLE_MSG
            self._write_chunk(b"\x01")  # 分隔符：之后为正式答案
            for i in range(0, len(final), 80):
                self._write_chunk(final[i:i + 80].encode("utf-8"))
            self._end_chunks()
        except Exception as e:
            try:
                self._write_chunk(f"\x01（生成出错：{e}）".encode("utf-8"))
                self._end_chunks()
            except Exception:
                pass


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        sys.exit("错误：未设置 DEEPSEEK_API_KEY。请先 export DEEPSEEK_API_KEY=...")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"✅ 高考志愿填报 Agent 已启动： http://{HOST}:{PORT}")
    print("   功能：多轮对话 / 流式输出 / 左侧考生信息表单。按 Ctrl-C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()

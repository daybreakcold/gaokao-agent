# 🎓 高考志愿填报规划 Agent

一个**数据驱动、以位次为核心**的高考志愿填报对话 Agent。它不是简单推荐学校，而是基于考生的省份、年份、分数、位次、选科、批次、专业/城市偏好、家庭预算和风险承受能力，生成可解释、可验证、可调整的「冲 / 稳 / 保 / 垫」分层志愿方案，并提示调剂、滑档、退档等风险。

> ⚠️ 本工具仅提供参考建议，**不承诺录取结果**。最终须以考生所在省考试院官方招生计划、院校专业组代码、选科要求与实际投档结果为准。

📖 详细文档：[启动文档](docs/启动文档.md)（本地运行、常见问题） · [部署文档](docs/部署文档.md)（systemd / Nginx / Docker 服务器部署）

---

## ☕ 请作者喝杯奶茶

如果这个项目帮到了你或你家孩子填志愿，欢迎打赏支持开源～

<p align="center">
  <img src="assets/donate-wechat.png" alt="微信打赏二维码" width="220">
  &nbsp;&nbsp;
  <img src="assets/donate-alipay.jpg" alt="支付宝打赏二维码" width="220">
  <br>
  <sub>微信 / 支付宝 扫码打赏</sub>
</p>

---

## 目录结构

| 文件 | 说明 |
|------|------|
| `system_prompt.md` | **Agent 的系统提示词**（角色、任务、边界、数据优先级、分析流程、输出格式等 22 节规则） |
| `web_app.py` | 网页对话版：多轮聊天 + 流式输出 + 左侧「考生信息」表单（纯标准库 HTTP 服务） |
| `gaokao_agent.py` | 命令行对话版（多轮、流式） |
| `web_tools.py` | **联网工具**：`web_search`（DuckDuckGo，无需 Key）/ `read_url`（抓取网页正文） |
| `start.sh` | 一键启动脚本：建虚拟环境、装依赖、开浏览器、启动网页服务 |
| `requirements.txt` | Python 依赖（`openai`） |
| `.env.example` | 环境变量模板，复制为 `.env` 后填入真实 Key |
| `.env` | 环境变量，存放 API Key（已被 `.gitignore` 忽略，**勿提交公开仓库**） |
| `design.pen` | 界面设计稿（用 Pencil 打开查看） |

---

## 快速开始（网页版）

### 1. 配置 API Key

复制模板并填入 DeepSeek API Key（[platform.deepseek.com](https://platform.deepseek.com) 获取）：

```bash
cp .env.example .env
# 编辑 .env，填入：
# DEEPSEEK_API_KEY=sk-你的key
```

`.env` 已被 `.gitignore` 忽略，不会被提交到仓库。

### 2. 一键启动

```bash
./start.sh
```

脚本会自动建 `.venv`、装依赖、打开浏览器，并启动服务于 <http://127.0.0.1:8010>（按 `Ctrl-C` 停止）。

> 改端口：`PORT=8020 ./start.sh`

### 网页功能
- **左侧考生信息表单**：填好省份/年份/分数/位次/选科等，点「整理并发送」自动拼成规范输入
- **多轮对话**：补充信息时 Agent 会沿用上下文，不重复询问
- **流式输出**：方案边生成边显示，支持 Markdown 表格
- API Key 只在服务端使用，不会发送到浏览器

---

## 命令行版

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="sk-..."

python gaokao_agent.py
# 或带开场：
python gaokao_agent.py --text "江苏 2025 物化生 628分 位次9800 想去南京学计算机 服从调剂"
```

输入 `exit` / `quit` / `退出` 结束对话。

---

## 🔍 联网能力

Agent 具备**实时联网**能力,会在需要当年/最新数据(招生计划、投档线、最低录取位次、一分一段、招生章程、专业组、选科要求等)时自动调用工具:

- `web_search(query)` —— 联网搜索(默认 DuckDuckGo,**无需 API Key**)
- `read_url(url)` —— 打开搜索到的官方页面读取正文核实(省考试院 / 阳光高考 / 院校招生网)

工作方式:
- 网页版会**实时显示检索进度**(如「🔍 联网检索:…」),检索完成后才输出正式答案;检索进度只是临时提示,不会进入对话历史。
- 命令行版的检索过程打印在 stderr。
- 优先采用官方来源,并在结论中提示「以官方最新发布为准」;若联网完全不可用,会给出**确定性的官方查询指引**兜底,绝不编造确定数据。

**联网开关**:网页版输入框上方有「🌐 联网搜索」开关(默认开),关闭后本轮仅用模型已有知识作答(并标注非官方);命令行版对应 `--no-web` 参数。

**搜索质量**:`.env` 配置 `TAVILY_API_KEY` 后会优先用 [Tavily](https://tavily.com)(对 LLM 更友好、更稳),否则回退到免费的 DuckDuckGo。(本项目已配置 Tavily。)

> 联网抓取仅用 Python 标准库(`urllib` + `html.parser`),无额外依赖。

## 设计理念（来自系统提示词）

- **必须有位次**：只给分数不给位次时，Agent 会要求补充位次，不会硬给方案。
- **信息不全只出「初步建议」**：缺省份/年份/位次/选科/批次等核心信息时，先列「需要补充的信息清单」，并显式列出所有假设。
- **冲稳保垫比例随风险偏好变化**：稳健 / 平衡 / 进取三档，默认平衡型。
- **客观提示专业风险**：医学、法学、计算机、师范、生化环材、土木、农林地矿等给出中立提醒，而非简单劝退。
- **合规话术**：不使用「一定能录取 / 保证上岸 / 百分百」等绝对化表达。

想调整规则、专业库或城市库，直接编辑 `system_prompt.md` 即可，代码会在启动时读取。

---

## 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek 鉴权（必需） | — |
| `DEEPSEEK_BASE_URL` | 接口地址 | `https://api.deepseek.com` |
| `TAVILY_API_KEY` | 联网搜索（可选，更优；不配则用免费 DuckDuckGo） | — |
| `HOST` | 网页服务监听地址（部署对外时设为 `0.0.0.0`） | `127.0.0.1` |
| `PORT` | 网页服务端口 | `8010` |

---

## 依赖
- Python 3.8+
- [`openai`](https://pypi.org/project/openai/) SDK（用其兼容接口对接 DeepSeek）

网页版仅用 Python 标准库搭建 HTTP 服务，无需额外 Web 框架。

# Claude Code Skill 使用文档

本项目除了网页版和命令行版，还提供 **Claude Code Skill** 形态（`.claude/skills/gaokao-planner/`）。在 [Claude Code](https://claude.com/claude-code) 中直接调用，**无需 DeepSeek / Tavily API Key，无需启动 Python 服务**。

---

## 1. 前置条件

| 项目 | 要求 |
|------|------|
| Claude Code | 已安装并登录（CLI、桌面应用或 IDE 插件均可） |
| Python / 依赖 | ❌ 不需要 |
| API Key | ❌ 不需要（联网检索由 Claude Code 内置的 WebSearch / WebFetch 完成） |

## 2. 安装

### 方式一：项目内使用（零安装）

Skill 已随仓库携带。在**本仓库目录**下打开 Claude Code 即可直接使用，无需任何操作。

### 方式二：全局安装（任意目录可用）

把 skill 复制到个人 skills 目录：

```bash
cp -R .claude/skills/gaokao-planner ~/.claude/skills/
```

卸载：删除该目录即可。

```bash
rm -rf ~/.claude/skills/gaokao-planner
```

> ⚠️ Skill 在**新开的 Claude Code 会话**中才会加载。安装后请重新启动会话（或新开一个会话）再使用。

## 3. 使用方式

### 3.1 斜杠命令调用（带考生信息）

```
/gaokao-planner 江苏 2026 物化生 628分 位次9800 想去南京学计算机 服从调剂
```

### 3.2 斜杠命令调用（不带参数）

```
/gaokao-planner
```

Agent 会先列出需要收集的信息清单（省份、年份、总分、全省位次、选科、批次、专业/城市偏好、是否服从调剂、家庭预算等）。

### 3.3 自然语言自动触发

不记得命令也没关系。直接用自然语言提问，Claude 会根据话题自动调用该 skill：

```
我家孩子今年高考620分，江苏物化生，位次大概12000，报什么志愿好？
```

```
位次9800能冲南京大学吗？
```

### 3.4 多轮对话补充信息

首次信息不全时，Agent 只会给「初步建议」并列出缺失信息清单。直接在对话中补充即可，Agent 会沿用上下文，不重复询问已提供的信息：

```
补充：位次9800，本科批，服从调剂，不接受生化环材，预算每年2万以内
```

## 4. 使用示例

一次完整的对话流程：

```
> /gaokao-planner 江苏 2026 物化生 628分 想学计算机

（Agent：缺少全省位次，先给方向性判断 + 要求补充位次）

> 位次9800，想去南京，服从调剂，不接受民办，预算不限

（Agent：联网检索江苏省考试院近三年投档数据 → 输出完整的
  冲/稳/保/垫分层方案，含志愿总表、逐档分析、专业与城市建议、
  滑档退档风险提醒、最终排序建议）

> 把方案导出成 Markdown 文件

（Claude Code 可直接写文件——这是网页版没有的能力）
```

## 5. 工作原理

| 环节 | 实现方式 |
|------|----------|
| 触发 | frontmatter 中的 `description` 描述适用场景，Claude 自动判断调用；也可 `/gaokao-planner` 手动调用 |
| 核心规则 | `SKILL.md`：角色、7 条硬性规则、四步工作流程、输出前自检 |
| 详细细则 | `references/` 按需加载，不常驻上下文 |
| 联网检索 | Claude Code 内置 WebSearch / WebFetch，优先省考试院、阳光高考等官方来源 |
| 多轮状态 | 会话上下文天然支持，无需额外代码 |

Skill 目录结构：

```
.claude/skills/gaokao-planner/
├── SKILL.md                        # 主文件：角色、硬性规则、工作流程
└── references/
    ├── analysis-rules.md           # 分析细则：数据优先级、校验、冲稳保垫策略、
    │                               #   院校/专业/城市筛选、风险等级、评分模型、特殊场景
    └── output-format.md            # 输出格式规范 + 合规话术
```

## 6. 与网页版 / 命令行版的对比

| | Skill 版 | 网页版 / 命令行版 |
|---|---|---|
| 面向用户 | 会用 Claude Code 的开发者 | 家长、考生等普通用户 |
| API Key | 不需要 | 需要 DeepSeek Key（Tavily 可选） |
| 部署 | 复制目录即装 | 建虚拟环境、装依赖、启动服务 |
| 联网检索 | WebSearch / WebFetch（内置） | DuckDuckGo / Tavily（自研 `web_tools.py`） |
| 额外能力 | 可读写本地文件（导出方案）、可调用 Bash 计算 | 流式网页界面、考生信息表单 |
| 模型 | Claude | DeepSeek |

两者互补：**网页版是产品，Skill 版是给开发者用户的效率工具**。

## 7. 维护说明

Skill 的规则内容由 `system_prompt.md` 拆分而来，两处**同源但独立**：

- 修改网页版 / 命令行版行为 → 编辑 `system_prompt.md`
- 修改 Skill 行为 → 编辑 `.claude/skills/gaokao-planner/` 下对应文件
- 大幅修改 `system_prompt.md` 后，建议同步更新 skill 的 `references/`（第 4–13、17–19 节对应 `analysis-rules.md`，第 14、20 节对应 `output-format.md`）

全局安装过的用户，更新仓库后需重新执行一次 `cp -R` 覆盖 `~/.claude/skills/` 中的旧版本。

## 8. 常见问题

**输入 `/gaokao-planner` 提示找不到命令**
Skill 只在会话启动时加载。确认 skill 目录存在（项目内 `.claude/skills/` 或全局 `~/.claude/skills/`）后，新开一个 Claude Code 会话。

**自然语言提问没有触发 skill**
话题需与高考志愿填报相关（分数、位次、志愿、冲稳保垫等）。不触发时可显式使用 `/gaokao-planner` 命令。

**担心数据不是最新的**
Agent 会联网检索当年招生计划与投档数据，并在结论中标注「以省考试院官方发布为准」；查不到的数据会明确说明并给出官方查询指引，不会编造。

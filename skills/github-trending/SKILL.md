---
name: github-trending
description: 当需要采集 GitHub 热门开源项目时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# GitHub Trending 采集技能

## 使用场景

当任务涉及以下需求时，使用此技能：
- 采集 GitHub Trending 热门项目
- 获取 AI/LLM/Agent 领域最新开源动态
- 收集特定编程语言的流行仓库

---

## 执行步骤

### 1. 搜索热门仓库
通过 GitHub Trending API 或页面获取热门项目列表：
- 目标语言：Python, Rust, JavaScript, TypeScript
- 时间范围：今日 trending
- 数据源：`https://github.com/trending`

### 2. 提取信息
对每个仓库提取以下字段：
- `name`: 项目名称
- `url`: GitHub 仓库地址
- `stars`: 当前 star 数
- `language`: 主要编程语言
- `topics`: 仓库标签（从页面提取）
- `description`: 项目原始描述

### 3. 内容过滤
**纳入标准**（任一匹配即保留）：
- 关键词：AI, LLM, Agent, RAG, DeepSeek, OpenAI, LangChain, Anthropic, Claude
- Topics 包含：machine-learning, nlp, chatbot, automation

**排除标准**：
- 标题包含 "Awesome"、"awesome-list"
- Topics 包含：list, collection, resources

### 4. 去重检查
- 使用 `Grep` 搜索 `knowledge/raw/` 目录历史文件
- 检查 `url` 字段是否已存在
- 跳过已采集的仓库

### 5. 撰写中文摘要
对每个项目生成中文摘要，遵循公式：

```
项目名 + 做什么 + 为什么值得关注
```

**示例**：
```
LangGraph — 用于构建有状态多Agent应用的框架，支持循环和流式处理
```

要求：
- 突出核心价值
- 50字以内
- 避免直译英文描述

### 6. 排序取 Top 15
- 按 `stars` 数降序排列
- 取前 15 个项目
- 若不足 15 个，全部保留

### 7. 输出 JSON
将结果写入 `knowledge/raw/github-trending-YYYY-MM-DD.json`

---

## 注意事项

1. **禁止修改已有文件**：使用 `Write` 工具而非 `Edit`
2. **超时设置**：WebFetch 请求超时设为 10 秒
3. **错误处理**：API 失败时记录日志，不影响其他条目
4. **时间格式**：`collected_at` 使用 ISO 8601 格式
5. **目录检查**：输出前确认 `knowledge/raw/` 目录存在

---

## 输出格式

```json
{
  "source": "github_trending",
  "skill": "github-trending",
  "collected_at": "2025-05-09T12:00:00Z",
  "items": [
    {
      "name": "langchain-ai/langgraph",
      "url": "https://github.com/langchain-ai/langgraph",
      "summary": "用于构建有状态多Agent应用的框架，支持循环和流式处理",
      "stars": 45000,
      "language": "Python",
      "topics": ["llm", "agent-framework", "langchain"]
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source` | string | Y | 固定值：`github_trending` |
| `skill` | string | Y | 固定值：`github-trending` |
| `collected_at` | string | Y | ISO 8601 格式时间戳 |
| `items` | array | Y | 项目列表 |
| `items[].name` | string | Y | 项目完整名称（owner/repo） |
| `items[].url` | string | Y | GitHub 仓库链接 |
| `items[].summary` | string | Y | 中文摘要（50字内） |
| `items[].stars` | number | Y | 当前 star 数 |
| `items[].language` | string | N | 主要编程语言 |
| `items[].topics` | array | N | 仓库标签数组 |

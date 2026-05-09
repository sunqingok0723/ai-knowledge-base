---
name: tech-summary
description: 当需要对采集的技术内容进行深度分析总结时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# 技术内容深度分析技能

## 使用场景

当任务涉及以下需求时，使用此技能：
- 对采集的 GitHub 项目进行深度分析
- 生成技术亮点、评分、标签建议
- 发现技术趋势和共同主题
- 输出结构化分析结果

---

## 执行步骤

### 1. 读取最新采集文件
- 使用 `Glob` 查找 `knowledge/raw/` 目录下最新文件
- 按修改时间排序，读取最新采集数据
- 解析 JSON 格式原始数据

### 2. 逐条深度分析
对每个项目生成以下分析内容：

#### 2.1 中文摘要（≤50字）
- 提炼核心价值
- 突出技术亮点
- 避免直译英文描述

#### 2.2 技术亮点（2-3个）
**要求：用事实说话**
- ✅ "支持 Python 3.12+ 异步并发"
- ✅ "集成 DeepSeek V3 API，成本降低 60%"
- ❌ "性能优秀"（空洞）
- ❌ "使用体验好"（主观）

#### 2.3 评分（1-10）+ 理由
**评分标准**：

| 分数 | 含义 | 理由示例 |
|------|------|----------|
| 9-10 | 改变格局 | 首个开源的 X 框架、突破性性能 |
| 7-8 | 直接有帮助 | 生产可用、解决实际痛点、文档完善 |
| 5-6 | 值得了解 | 技术思路新颖、但未成熟 |
| 1-4 | 可略过 | 纯演示、无实质内容 |

#### 2.4 标签建议（3-5个）
从标签池选择：
- `llm`, `agent`, `rag`, `langchain`
- `fine-tuning`, `prompt-engineering`
- `multimodal`, `embedding`, `vector-db`
- `deployment`, `api`, `tool`
- `tutorial`, `demo`, `production`

### 3. 趋势发现
分析所有项目后，提取：
- **共同主题**：本周出现 3+ 次的技术方向
- **新概念**：首次出现或快速兴起的技术
- **框架/工具**：值得关注的生态组件

### 4. 输出分析结果
将分析结果写入 `knowledge/analyzed/tech-summary-YYYY-MM-DD.json`

---

## 注意事项

1. **评分约束**：15 个项目中，9-10 分不超过 2 个
2. **禁止主观判断**：技术亮点必须有事实依据
3. **摘要长度**：严格控制在 50 字以内
4. **标签一致性**：与已有分析保持标签体系统一
5. **只读操作**：本技能仅读取数据，不修改原始采集文件

---

## 评分示例

### 9-10 分（改变格局）
```
LangGraph — 首个支持循环和流式的多Agent框架
评分: 9/10
理由: 填补 LangChain 生态空白，已有 500+ 生产案例
```

### 7-8 分（直接有帮助）
```
DeepSeek-TUI — 终端原生 DeepSeek 编码助手
评分: 7/10
理由: 解决 IDE 外编码场景，支持多文件并发编辑
```

### 5-6 分（值得了解）
```
LLM-Observer — 大模型调用可视化工具
评分: 6/10
理由: 监控思路新颖，但仅支持 OpenAI
```

### 1-4 分（可略过）
```
Hello-AI — LLM Hello World 示例集合
评分: 3/10
理由: 纯演示项目，无实质技术内容
```

---

## 输出格式

```json
{
  "source": "tech-summary",
  "skill": "tech-summary",
  "analyzed_at": "2025-05-09T14:30:00Z",
  "input_file": "github-trending-2025-05-09.json",
  "trends": {
    "common_themes": ["多Agent框架", "RAG优化工具"],
    "new_concepts": ["Agent编排协议"],
    "notable_tools": ["LangGraph", "LlamaIndex"]
  },
  "items": [
    {
      "name": "langchain-ai/langgraph",
      "url": "https://github.com/langchain-ai/langgraph",
      "summary": "首个支持循环和流式的多Agent框架",
      "highlights": [
        "支持有状态循环，填补 LangChain 空白",
        "已有 500+ 生产案例"
      ],
      "score": 9,
      "score_reason": "填补 LangChain 生态空白，已有 500+ 生产案例",
      "tags": ["agent", "llm", "langchain", "production"]
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source` | string | Y | 固定值：`tech-summary` |
| `skill` | string | Y | 固定值：`tech-summary` |
| `analyzed_at` | string | Y | ISO 8601 格式分析时间 |
| `input_file` | string | Y | 原始采集文件名 |
| `trends` | object | Y | 趋势发现结果 |
| `trends.common_themes` | array | Y | 共同主题列表 |
| `trends.new_concepts` | array | Y | 新概念列表 |
| `trends.notable_tools` | array | Y | 值得关注的工具 |
| `items` | array | Y | 分析项目列表 |
| `items[].name` | string | Y | 项目名称 |
| `items[].url` | string | Y | GitHub 链接 |
| `items[].summary` | string | Y | 中文摘要（≤50字） |
| `items[].highlights` | array | Y | 技术亮点（2-3个） |
| `items[].score` | number | Y | 评分（1-10） |
| `items[].score_reason` | string | Y | 评分理由 |
| `items[].tags` | array | Y | 标签建议（3-5个） |

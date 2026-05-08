# AI 知识库助手 - 项目规范文档

## 项目概述

本项目是一个自动化 AI 领域知识采集与管理系统，通过多 Agent 协作从 GitHub Trending 和 Hacker News 采集 AI/LLM/Agent 相关技术动态，经大模型分析处理后结构化存储，并支持多渠道（邮箱/飞书）自动分发。

## 技术栈

| 组件 | 版本/说明 |
|------|-----------|
| Python | 3.12+ |
| 大模型 | Claude Code + 国产大模型（DeepSeek/Qwen/GLM 等） |
| Agent 框架 | LangGraph（多 Agent 编排） |
| 数据采集 | OpenClaw（网页抓取与解析） |
| 数据存储 | JSON（结构化知识条目） |

## 编码规范

```python
# 命名规范
snake_case_for_variables  # 变量、函数、模块
PascalCaseForClasses      # 类名
UPPER_CASE_FOR_CONSTANTS  # 常量

# Docstring 风格（Google 风格）
def process_article(raw_data: dict) -> dict:
    """处理原始文章数据并生成结构化知识条目。

    Args:
        raw_data: 包含 title、url、content 等字段的原始数据字典。

    Returns:
        符合知识条目 JSON Schema 的结构化字典。

    Raises:
        ValueError: 当 raw_data 缺少必要字段时。
    """
    pass

# 日志规范（禁止裸 print）
import logging

logger = logging.getLogger(__name__)
logger.info("采集任务开始")
logger.error("解析失败: %s", error_msg)
```

- 遵循 [PEP 8](https://peps.python.org/pep-0008/)
- 函数返回类型必须使用类型注解
- 所有外部调用必须包含异常处理与日志记录

## 项目结构

```
ai-knowledge-base/
├── agents/               # Agent 定义目录
│   ├── collector/        # 采集 Agent
│   ├── analyzer/         # 分析 Agent
│   └── organizer/        # 整理 Agent
├── skills/               # 可复用技能模块
│   ├── scraping/         # 网页抓取技能
│   └── llm/              # LLM 调用技能
├── knowledge/
│   ├── raw/              # 原始采集数据
│   └── articles/         # 结构化知识条目（JSON）
├── config/               # 配置文件
├── tests/                # 测试用例
└── CLAUDE.md             # 本文档
```

## 知识条目 JSON 格式

```json
{
  "id": "20250430_gh_001",
  "title": "LangGraph v0.2 发布：多 Agent 协作增强",
  "source_url": "https://github.com/langchain-ai/langgraph/releases",
  "source": "github_trending",
  "summary": "LangGraph 发布 0.2 版本，新增支持...",
  "content": {
    "key_points": [
      "支持自定义 Agent 状态管理",
      "引入流式响应 API"
    ],
    "tech_tags": ["llm", "agent-framework", "langchain"],
    "difficulty": "intermediate"
  },
  "collected_at": "2025-04-30T08:30:00Z",
  "analyzed_at": "2025-04-30T09:15:00Z",
  "status": "published",
  "distributed_to": ["email", "feishu"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | Y | 唯一标识，格式：YYYYMMDD_{source}_{seq} |
| title | string | Y | 文章标题 |
| source_url | string | Y | 原文链接 |
| source | string | Y | 来源标识：github_trending / hacker_news |
| summary | string | Y | AI 生成的摘要（200字内） |
| content | object | Y | 结构化内容，包含 key_points、tech_tags 等 |
| collected_at | string | Y | ISO 8601 格式采集时间 |
| analyzed_at | string | N | ISO 8601 格式分析时间 |
| status | string | Y | 状态：pending / analyzed / published / rejected |
| distributed_to | array | N | 已分发的渠道列表 |

## Agent 角色概览

| Agent 名称 | 主要职责 | 输入 | 输出 | 频率 |
|------------|----------|------|------|------|
| **Collector** | 从 GitHub Trending / Hacker News 采集原始数据 | 定时触发 | raw/*.json | 每小时 |
| **Analyzer** | 调用大模型分析内容，生成结构化摘要 | raw/*.json | articles/*.json | 按需触发 |
| **Organizer** | 去重、分类、审核，准备分发内容 | articles/*.json | 待发布队列 | 每日汇总 |

## 红线（绝对禁止）

1. **禁止裸 print()**：所有输出必须通过 `logging` 模块
2. **禁止硬编码密钥**：使用环境变量或配置管理服务
3. **禁止未经验证的 URL 请求**：必须设置超时与重试上限
4. **禁止忽略 LLM 调用错误**：失败时记录原始输入用于重试
5. **禁止覆盖已发布知识条目**：id 冲突时自动生成新 id
6. **禁止向分发渠道发送未审核内容**：status 必须为 `published`

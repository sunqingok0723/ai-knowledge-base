# Issue #01: Collector Agent - GitHub Trending 采集

## 背景
需要从 GitHub Trending 自动采集 AI/LLM/Agent 相关技术动态，作为整个知识库系统的数据源。

## 职责范围
- 抓取 GitHub Trending 页面数据
- 过滤 AI/LLM/Agent 相关项目
- 存储原始数据到 `knowledge/raw/`

## 关键需求
1. **数据源**: GitHub Trending
2. **目标语言**: Python, Rust, JavaScript, TypeScript
3. **关键词过滤**: AI, LLM, Agent, RAG, DeepSeek, OpenAI, LangChain, Anthropic, Claude
4. **输出字段**: title, url, source, popularity, summary
5. **去重检查**: URL 无重复
6. **输出路径**: `knowledge/raw/github-{date}.json`

## Schema 定义

**单条数据**: [raw-article.json](../schemas/raw-article.json)
**批量输出**: [collector-batch.json](../schemas/collector-batch.json)

## 输出示例
```json
[
  {
    "title": "DeepSeek-TUI",
    "url": "https://github.com/Hmbown/DeepSeek-TUI",
    "source": "github_trending",
    "popularity": 5799,
    "summary": "Coding agent for DeepSeek models"
  }
]
```

## 质量标准
- 条目数量 ≥ 10 条
- 信息完整性检查
- URL 去重验证

## 执行频率
每小时执行一次

## 配置文件
→ 引用: `agents/collector/collector.md`

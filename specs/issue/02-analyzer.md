# Issue #02: Analyzer Agent - 内容分析与打标

## 背景
Collector 采集的是原始英文数据，需要分析处理生成中文摘要和技术标签，便于用户阅读和检索。

## 职责范围
- 读取 `knowledge/raw/` 采集数据
- 生成中文摘要
- 打技术标签（3-5个）
- 提取关键亮点（3-5条）
- 评定难度等级

## 关键需求
1. **数据输入**: `knowledge/raw/github-{date}.json`
2. **数据输出**: `knowledge/analyzed/github-{date}.json`
3. **摘要要求**: 100字内，中文，突出核心价值
4. **标签体系**: llm, agent, rag, langchain, fine-tuning, prompt-engineering, multimodal, embedding, vector-db, deployment, api, tool, tutorial, demo, production
5. **难度等级**: beginner, intermediate, advanced

## Schema 定义

**输入**: [collector-batch.json](../schemas/collector-batch.json)
**输出**: [analyzed-article.json](../schemas/analyzed-article.json), [analyzer-batch.json](../schemas/analyzer-batch.json)

## 输出示例
```json
[
  {
    "title": "DeepSeek-TUI",
    "url": "https://github.com/Hmbown/DeepSeek-TUI",
    "source": "github_trending",
    "popularity": 5799,
    "summary": "DeepSeek 模型的终端编码助手，支持流式输出和多文件编辑",
    "tags": ["agent", "llm", "tool", "terminal"],
    "key_points": [
      "支持 DeepSeek API 集成",
      "终端原生界面，操作流畅",
      "支持多文件并发编辑"
    ],
    "difficulty": "intermediate"
  }
]
```

## 质量标准
- 摘要质量：100字内，中文，突出核心价值
- 标签准确性：3-5个，与内容高度相关
- 亮点数量：3-5条，每条具体明确

## 执行频率
Collector 完成后自动触发

## 配置文件
→ 引用: `agents/analyzer/analyzer.md`

# Issue #03: Organizer Agent - Markdown 输出与分发

## 背景
Analyzer 输出的是结构化 JSON 数据，需要整理成用户友好的 Markdown 文档，并进行去重和分类。

## 职责范围
- 接收 Analyzer 分析结果
- URL 和标题去重检查
- 按标签分类整理
- 生成格式化 Markdown 文档

## 关键需求
1. **数据输入**: `knowledge/analyzed/github-{date}.json`
2. **数据输出**: `knowledge/docs/daily-{date}.md`
3. **去重策略**:
   - URL 去重：相同 URL 跳过
   - 标题相似度：>80% 相似度视为重复
4. **分类规则**:
   - LLM 相关：llm, fine-tuning, prompt-engineering
   - Agent 框架：agent, langchain, rag
   - 工具/服务：tool, api, deployment
   - 教程/示例：tutorial, demo
5. **排序规则**: 按热度（popularity）降序

## Schema 定义

**输入**: [analyzer-batch.json](../schemas/analyzer-batch.json)
**输出**: Markdown 文档（非 JSON）

## 输出格式
```markdown
# AI 知识库日报 {YYYY-MM-DD}

> 本日采集 GitHub Trending 中 AI/LLM/Agent 相关项目 {N} 个

---

## 🔥 热门项目 (Top 5)

### 1. [DeepSeek-TUI]({url}) ⭐ {popularity}
**标签**: {tag1} {tag2} | **难度**: {difficulty}

{summary}

**亮点**:
- {point1}
- {point2}
- {point3}

---

## 📦 Agent 框架

### [Project Name]({url}) ⭐ {popularity}
**标签**: {tags}

{summary}

---

## 🛠️ 工具与服务

...

---

## 📚 教程与示例

...

---

**采集时间**: {timestamp}
**数据来源**: GitHub Trending
```

## 质量标准
- 去重完整性：URL/标题双重检查
- 分类准确性：按 tags 正确分组
- Markdown 格式：符合模板规范
- 排序合理性：热度降序，Top 5 突出显示

## 执行频率
Analyzer 完成后自动触发

## 配置文件
→ 引用: `agents/organizer/organizer.md`

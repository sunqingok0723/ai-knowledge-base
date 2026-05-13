# skill: github-trending · 完整设计规范

## 要做什么

- 抓取 GitHub Trending Top 50 仓库
- 过滤 topics 包含 `ai|llm|agent|ml|machine-learning` 的项目
- 输出 JSON 数组到 stdout，字段：`[name, url, stars, topics, description]`

## 不做什么

- ❌ 不调用 GitHub API（rate limit 限制）→ 使用 HTML 解析
- ❌ 不存储数据库 → 只输出 stdout
- ❌ 不做去重 → 由 caller 处理
- ❌ 不做长期缓存 → 每次实时抓取

## 边界 & 验收

- ✅ 单次执行 < 10s
- ✅ 失败返回空数组，不抛异常
- ✅ 输出必须通过 JSON Schema 验证
- ✅ 支持 daily/weekly/monthly 时间范围

## 技术实现

- **抓取**: `requests` + `BeautifulSoup` 解析 HTML
- **过滤**: Topic 匹配 + 描述关键词兜底
- **日志**: 使用 `logging` 模块（禁止裸 print）
- **类型注解**: 所有函数必须有类型提示

## Description 触发词覆盖

### 中文表达
- 直接: "GitHub 热门"、"GitHub 趋势"、"GitHub 热榜"
- 动作: "抓取"、"爬取"、"获取"、"采集" + "trending"
- 上下文: "热门 AI 项目"、"GitHub 每日趋势"

### 英文表达
- 直接: "GitHub trending", "trending repos"
- 动作: "fetch trending", "get popular repos", "scrape GitHub"
- 上下文: "hot repositories", "trending projects"

### 组合触发
- "抓取 GitHub trending"
- "看看 GitHub 上什么在 trending"
- "爬取 GitHub 热门仓库"
- "Get trending AI repos"

## 验证测试

```bash
# 基础验证
skill-invoke github-trending | jq '. | length'  # 应 > 0
skill-invoke github-trending | jq '.[0].name'   # 应显示仓库名

# 时间范围验证
skill-invoke github-trending --since=weekly

# 失败场景（无网络）应返回 []
```

## 文件结构

```
github-trending/
├── SKILL.md                    # 主指令文档
├── EXAMPLES.md                 # 使用示例
└── scripts/
    └── fetch_github_trending.py  # 可执行脚本
```

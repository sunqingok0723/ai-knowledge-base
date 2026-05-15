#!/usr/bin/env python3
"""MCP Knowledge Server using official MCP SDK.

提供本地知识库搜索功能，使用 MCP 官方 SDK 实现。
"""

import json
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent


# ===== 知识库管理 =====

class KnowledgeBase:
    """知识库管理类。"""

    def __init__(self, articles_dir: str):
        """初始化知识库。

        Args:
            articles_dir: 文章目录路径
        """
        self.articles_dir = Path(articles_dir)
        self.articles: dict[str, dict[str, Any]] = {}
        self._load_articles()

    def _load_articles(self) -> None:
        """加载所有文章到内存。"""
        if not self.articles_dir.exists():
            print(f"[stderr] Knowledge directory not found: {self.articles_dir}", file=sys.stderr)
            return

        for json_file in self.articles_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    article = json.load(f)
                    article_id = article.get("id", json_file.stem)
                    self.articles[article_id] = article
            except (json.JSONDecodeError, IOError) as e:
                print(f"[stderr] Failed to load {json_file}: {e}", file=sys.stderr)

        print(f"[stderr] Loaded {len(self.articles)} articles from {self.articles_dir}", file=sys.stderr)

    def search(self, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        """按关键词搜索文章。

        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            匹配的文章列表
        """
        keyword_lower = keyword.lower()
        results = []

        for article_id, article in self.articles.items():
            # 搜索标题和摘要
            title = article.get("title", "").lower()
            summary = article.get("summary", "").lower()
            content = article.get("content", {})

            # 检查标题、摘要和标签
            score = 0
            if keyword_lower in title:
                score += 10
            if keyword_lower in summary:
                score += 5

            # 检查标签
            tags = content.get("tech_tags", [])
            if any(keyword_lower in tag.lower() for tag in tags):
                score += 3

            # 检查关键点
            key_points = content.get("key_points", [])
            if any(keyword_lower in point.lower() for point in key_points):
                score += 2

            if score > 0:
                results.append({
                    "id": article_id,
                    "title": article.get("title", ""),
                    "summary": article.get("summary", ""),
                    "source": article.get("source", ""),
                    "score": score,
                    "url": article.get("source_url", ""),
                })

        # 按分数排序，返回前 N 条
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        """获取文章完整内容。

        Args:
            article_id: 文章 ID

        Returns:
            文章内容，不存在时返回 None
        """
        return self.articles.get(article_id)

    def get_stats(self) -> dict[str, Any]:
        """获取知识库统计信息。

        Returns:
            统计信息字典
        """
        total = len(self.articles)

        # 来源分布
        sources: dict[str, int] = {}
        # 标签统计
        tags: dict[str, int] = {}
        # 状态分布
        statuses: dict[str, int] = {}

        for article in self.articles.values():
            # 统计来源
            source = article.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1

            # 统计状态
            status = article.get("status", "unknown")
            statuses[status] = statuses.get(status, 0) + 1

            # 统计标签
            content = article.get("content", {})
            tech_tags = content.get("tech_tags", [])
            for tag in tech_tags:
                tags[tag] = tags.get(tag, 0) + 1

        # 找出热门标签
        top_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_articles": total,
            "sources": sources,
            "statuses": statuses,
            "top_tags": [{"tag": k, "count": v} for k, v in top_tags],
            "unique_tags": len(tags),
        }


# 全局知识库实例（延迟加载）
_kb: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    """获取知识库实例（单例）。"""
    global _kb
    if _kb is None:
        # 默认路径：相对于脚本的 knowledge/articles/
        script_dir = Path(__file__).parent.parent
        articles_dir = script_dir / "knowledge" / "articles"
        _kb = KnowledgeBase(str(articles_dir))
    return _kb


# ===== 创建 MCP Server =====

server = Server("knowledge-server")

# 定义可用工具
TOOLS = [
    Tool(
        name="search_articles",
        description="按关键词搜索知识库文章",
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "limit": {
                    "type": "number",
                    "description": "返回结果数量限制（默认 5）",
                    "default": 5
                }
            },
            "required": ["keyword"]
        }
    ),
    Tool(
        name="get_article",
        description="获取文章完整内容",
        inputSchema={
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "文章 ID（如：20260514_github_123456）"
                }
            },
            "required": ["article_id"]
        }
    ),
    Tool(
        name="knowledge_stats",
        description="获取知识库统计信息",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
]


# ===== 注册处理器 =====

@server.list_tools()
def list_tools() -> list[Tool]:
    """列出可用工具。"""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理工具调用。"""
    kb = get_kb()

    if name == "search_articles":
        keyword = arguments.get("keyword", "")
        limit = arguments.get("limit", 5)

        if not keyword:
            return [TextContent(type="text", text="Error: keyword is required")]

        results = kb.search(keyword, limit)

        lines = [f"Found {len(results)} related articles:\n"]
        for r in results:
            lines.append(f"- {r['title']}")
            lines.append(f"  ID: {r['id']}")
            lines.append(f"  Summary: {r['summary'][:100]}...")
            lines.append(f"  Source: {r['source']}")
            lines.append(f"  Score: {r['score']}")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "get_article":
        article_id = arguments.get("article_id", "")

        if not article_id:
            return [TextContent(type="text", text="Error: article_id is required")]

        article = kb.get_article(article_id)

        if article is None:
            return [TextContent(type="text", text=f"Article not found: {article_id}")]

        # 格式化文章内容
        content = article.get("content", {})
        key_points = content.get("key_points", [])
        tech_tags = content.get("tech_tags", [])
        difficulty = content.get("difficulty", "unknown")
        rating = content.get("rating", 0)

        formatted = f"""Title: {article.get('title', '')}
ID: {article.get('id', '')}
Source: {article.get('source', '')}
URL: {article.get('source_url', '')}

Summary:
{article.get('summary', '')}

Key Points:
{chr(10).join(f'  - {p}' for p in key_points) if key_points else '  None'}

Tech Tags: {', '.join(tech_tags) if tech_tags else 'None'}
Difficulty: {difficulty}
Rating: {rating}/10

Collected: {article.get('collected_at', '')}
Analyzed: {article.get('analyzed_at', '')}
Status: {article.get('status', '')}"""

        return [TextContent(type="text", text=formatted)]

    elif name == "knowledge_stats":
        stats = kb.get_stats()

        # 构建来源分布文本
        source_lines = []
        for k, v in stats['sources'].items():
            source_lines.append(f"  - {k}: {v}")

        # 构建状态分布文本
        status_lines = []
        for k, v in stats['statuses'].items():
            status_lines.append(f"  - {k}: {v}")

        # 构建热门标签文本
        tag_lines = []
        for i, tag in enumerate(stats['top_tags']):
            tag_lines.append(f"  {i+1}. {tag['tag']}: {tag['count']} articles")

        formatted = f"""Knowledge Base Statistics:

Total Articles: {stats['total_articles']}
Unique Tags: {stats['unique_tags']}

Sources:
{chr(10).join(source_lines)}

Statuses:
{chr(10).join(status_lines)}

Top Tags (Top 10):
{chr(10).join(tag_lines)}"""

        return [TextContent(type="text", text=formatted)]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ===== 启动服务器 =====

if __name__ == "__main__":
    import asyncio

    # 预加载知识库
    kb = get_kb()
    print(f"[stderr] Knowledge base ready with {len(kb.articles)} articles", file=sys.stderr)

    # MCP SDK 需要 async 运行
    async def main():
        async with server.run(
            read_stream=sys.stdin,
            write_stream=sys.stdout,
        ):
            # 服务器正在运行，等待请求
            await server.__shutdown_event__.wait()

    asyncio.run(main())

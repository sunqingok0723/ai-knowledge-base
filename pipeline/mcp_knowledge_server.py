#!/usr/bin/env python3
"""MCP Server for AI Knowledge Base Search.

提供本地知识库搜索功能，使用 JSON-RPC 2.0 over stdio 协议。
"""

import json
import sys
from pathlib import Path
from typing import Any


# ===== 全局状态 =====

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


# 初始化知识库
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


# ===== JSON-RPC 2.0 处理 =====

def send_response(result: Any = None, id: Any = None, error: dict | None = None) -> None:
    """发送 JSON-RPC 响应。

    Args:
        result: 成功时的返回结果
        id: 请求 ID
        error: 错误信息
    """
    response = {
        "jsonrpc": "2.0",
        "id": id,
    }

    if error is not None:
        response["error"] = error
    else:
        response["result"] = result

    print(json.dumps(response, ensure_ascii=False))
    sys.stdout.flush()


def handle_request(request: dict[str, Any]) -> None:
    """处理 JSON-RPC 请求。

    Args:
        request: JSON-RPC 请求对象
    """
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    try:
        # initialize
        if method == "initialize":
            send_response({
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "mcp-knowledge-server",
                    "version": "1.0.0",
                },
                "capabilities": {
                    "tools": {},
                },
            }, id=request_id)

        # tools/list
        elif method == "tools/list":
            send_response({
                "tools": [
                    {
                        "name": "search_articles",
                        "description": "按关键词搜索知识库文章",
                        "inputSchema": {
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
                    },
                    {
                        "name": "get_article",
                        "description": "获取文章完整内容",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "article_id": {
                                    "type": "string",
                                    "description": "文章 ID（如：20260514_github_123456）"
                                }
                            },
                            "required": ["article_id"]
                        }
                    },
                    {
                        "name": "knowledge_stats",
                        "description": "获取知识库统计信息",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            }, id=request_id)

        # tools/call
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            kb = get_kb()

            if tool_name == "search_articles":
                keyword = arguments.get("keyword", "")
                limit = arguments.get("limit", 5)

                if not keyword:
                    send_response(error={
                        "code": -32602,
                        "message": "Invalid params: keyword is required"
                    }, id=request_id)
                    return

                results = kb.search(keyword, limit)
                # 格式化搜索结果
                result_lines = [f"Found {len(results)} related articles:\n"]
                for r in results:
                    result_lines.append(f"- {r['title']}")
                    result_lines.append(f"  ID: {r['id']}")
                    result_lines.append(f"  Summary: {r['summary'][:100]}...")
                    result_lines.append(f"  Source: {r['source']}")
                    result_lines.append(f"  Score: {r['score']}")
                    result_lines.append("")

                send_response({
                    "content": [
                        {
                            "type": "text",
                            "text": "\n".join(result_lines)
                        }
                    ]
                }, id=request_id)

            elif tool_name == "get_article":
                article_id = arguments.get("article_id", "")

                if not article_id:
                    send_response(error={
                        "code": -32602,
                        "message": "Invalid params: article_id is required"
                    }, id=request_id)
                    return

                article = kb.get_article(article_id)
                if article is None:
                    send_response(error={
                        "code": -32602,
                        "message": f"Article not found: {article_id}"
                    }, id=request_id)
                    return

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

                send_response({
                    "content": [
                        {
                            "type": "text",
                            "text": formatted
                        }
                    ]
                }, id=request_id)

            elif tool_name == "knowledge_stats":
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

                send_response({
                    "content": [
                        {
                            "type": "text",
                            "text": formatted
                        }
                    ]
                }, id=request_id)

            else:
                send_response(error={
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }, id=request_id)

        else:
            send_response(error={
                "code": -32601,
                "message": f"Method not found: {method}"
            }, id=request_id)

    except Exception as e:
        send_response(error={
            "code": -32603,
            "message": f"Internal error: {str(e)}"
        }, id=request_id)


def main() -> int:
    """MCP Server 主循环。"""
    print(f"[stderr] MCP Knowledge Server starting...", file=sys.stderr)
    print(f"[stderr] Reading from stdin, writing to stdout", file=sys.stderr)

    # 预加载知识库
    kb = get_kb()
    print(f"[stderr] Knowledge base ready with {len(kb.articles)} articles", file=sys.stderr)

    # 主循环：从 stdin 读取 JSON-RPC 请求
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            handle_request(request)
        except json.JSONDecodeError:
            send_response(error={
                "code": -32700,
                "message": "Parse error: Invalid JSON"
            })
        except Exception as e:
            send_response(error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            })

    return 0


if __name__ == "__main__":
    sys.exit(main())

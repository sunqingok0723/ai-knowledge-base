#!/usr/bin/env python3
"""MCP Server 交互式测试工具。

提供简单的命令行界面来测试 MCP Knowledge Server。
"""

import json
import subprocess
import sys
from pathlib import Path


def call_mcp(method: str, params: dict | None = None) -> dict:
    """调用 MCP Server。

    Args:
        method: JSON-RPC 方法名
        params: 方法参数

    Returns:
        响应结果
    """
    script_path = Path(__file__).parent / "mcp_knowledge_server.py"

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
    }
    if params:
        request["params"] = params

    proc = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        print(f"Error: {proc.stderr}", file=sys.stderr)
        return {}

    # 只解析 stdout 最后一行（JSON-RPC 响应）
    lines = proc.stdout.strip().split("\n")
    for line in reversed(lines):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue

    return {}


def main():
    """交互式主循环。"""
    print("=== MCP Knowledge Server Interactive Test ===\n")

    # 初始化
    print("[1] Initializing...")
    response = call_mcp("initialize")
    if response.get("result"):
        server_info = response["result"]["serverInfo"]
        print(f"   Connected to: {server_info['name']} v{server_info['version']}\n")
    else:
        print("   Failed to initialize\n")
        return 1

    # 列出工具
    print("[2] Listing tools...")
    response = call_mcp("tools/list")
    tools = response.get("result", {}).get("tools", [])
    print(f"   Available tools: {', '.join(t['name'] for t in tools)}\n")

    # 统计信息
    print("[3] Getting statistics...")
    response = call_mcp("tools/call", {
        "name": "knowledge_stats",
        "arguments": {}
    })
    content = response.get("result", {}).get("content", [{}])[0]
    print(content.get("text", "") + "\n")

    # 搜索
    print("[4] Searching for 'LLM' articles...")
    response = call_mcp("tools/call", {
        "name": "search_articles",
        "arguments": {"keyword": "LLM", "limit": 2}
    })
    content = response.get("result", {}).get("content", [{}])[0]
    search_text = content.get("text", "")
    # 只显示前 500 字符
    if len(search_text) > 500:
        search_text = search_text[:500] + "..."
    print(search_text + "\n")

    # 获取文章
    print("[5] Getting article details...")
    # 先搜索一个有效的 article_id
    response = call_mcp("tools/call", {
        "name": "search_articles",
        "arguments": {"keyword": "AI", "limit": 1}
    })
    search_text = response.get("result", {}).get("content", [{}])[0].get("text", "")

    if "ID: " in search_text:
        article_id = search_text.split("ID: ")[1].split("\n")[0].strip()
        print(f"   Fetching article: {article_id}")

        response = call_mcp("tools/call", {
            "name": "get_article",
            "arguments": {"article_id": article_id}
        })
        content = response.get("result", {}).get("content", [{}])[0]
        article_text = content.get("text", "")
        # 只显示前 800 字符
        if len(article_text) > 800:
            article_text = article_text[:800] + "..."
        print(article_text + "\n")
    else:
        print("   No articles found\n")

    print("=" * 50)
    print("All tests completed successfully!")

    return 0


if __name__ == "__main__":
    sys.exit(main())

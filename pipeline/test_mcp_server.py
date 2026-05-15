#!/usr/bin/env python3
"""MCP Server 测试脚本。

模拟 MCP 客户端，测试知识库服务器的功能。
"""

import json
import subprocess
import sys
from pathlib import Path

# 设置 UTF-8 编码输出
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def test_mcp_server():
    """测试 MCP Server 的各项功能。"""
    script_path = Path(__file__).parent / "mcp_knowledge_server.py"

    print("=== MCP Knowledge Server Test ===\n")

    # 启动 MCP Server
    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def send_request(method: str, params: dict | None = None, id: int = 1) -> dict:
        """发送 JSON-RPC 请求并返回响应。"""
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": id,
        }
        if params is not None:
            request["params"] = params

        request_json = json.dumps(request)
        print(f"→ 发送: {request_json}")

        proc.stdin.write(request_json + "\n")
        proc.stdin.flush()

        # 读取响应
        response_line = proc.stdout.readline().strip()
        if response_line:
            response = json.loads(response_line)
            print(f"← 接收: {json.dumps(response, ensure_ascii=False, indent=2)}\n")
            return response
        return {}

    try:
        # 测试 1: initialize
        print("【测试 1】初始化 (initialize)")
        response = send_request("initialize")
        assert response.get("result", {}).get("serverInfo", {}).get("name") == "mcp-knowledge-server"
        print("[OK] Initialize success\n")

        # 测试 2: tools/list
        print("【测试 2】列出工具 (tools/list)")
        response = send_request("tools/list")
        tools = response.get("result", {}).get("tools", [])
        assert len(tools) == 3
        tool_names = [t["name"] for t in tools]
        assert "search_articles" in tool_names
        assert "get_article" in tool_names
        assert "knowledge_stats" in tool_names
        print(f"[OK] Found {len(tools)} tools: {', '.join(tool_names)}\n")

        # 测试 3: knowledge_stats
        print("[Test 3] Statistics (knowledge_stats)")
        response = send_request("tools/call", {
            "name": "knowledge_stats",
            "arguments": {}
        }, id=3)
        content = response.get("result", {}).get("content", [{}])[0]
        stats_text = content.get("text", "")
        print(stats_text[:500] + "...\n")

        # 测试 4: search_articles
        print("[Test 4] Search articles (search_articles)")
        response = send_request("tools/call", {
            "name": "search_articles",
            "arguments": {
                "keyword": "LLM",
                "limit": 3
            }
        }, id=4)
        content = response.get("result", {}).get("content", [{}])[0]
        search_text = content.get("text", "")
        print(search_text[:500] + "...\n")

        # 测试 5: get_article (需要先获取一个有效的 article_id)
        print("[Test 5] Get article (get_article)")
        # 先搜索获取一个 article_id
        search_response = send_request("tools/call", {
            "name": "search_articles",
            "arguments": {
                "keyword": "AI",
                "limit": 1
            }
        }, id=5)
        search_text = search_response.get("result", {}).get("content", [{}])[0].get("text", "")

        # 从搜索结果中提取 ID (简单解析)
        if "ID: " in search_text:
            article_id = search_text.split("ID: ")[1].split("\n")[0].strip()
            print(f"Using article ID: {article_id}")

            response = send_request("tools/call", {
                "name": "get_article",
                "arguments": {
                    "article_id": article_id
                }
            }, id=6)
            content = response.get("result", {}).get("content", [{}])[0]
            print(content.get("text", "")[:800] + "...\n")
        else:
            print("[WARN] No article found, skipping get_article test\n")

        print("=" * 50)
        print("[OK] All tests passed!")

    except AssertionError as e:
        print(f"[FAIL] Test failed: {e}")
        return 1
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return 1
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait()

    return 0


if __name__ == "__main__":
    sys.exit(test_mcp_server())

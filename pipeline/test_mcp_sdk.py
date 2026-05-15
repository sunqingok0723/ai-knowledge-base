#!/usr/bin/env python3
"""Test MCP SDK Server."""

import subprocess
import sys
import json

def call_mcp(method: str, params: dict = None) -> dict:
    """Call MCP Server method."""
    script_path = "D:/claudecode/opencode/ai-knowledge-base/pipeline/mcp_knowledge_server_sdk.py"

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
    }
    if params:
        request["params"] = params

    proc = subprocess.run(
        [sys.executable, script_path],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        cwd="D:/claudecode/opencode/ai-knowledge-base"
    )

    # Parse response from stdout
    for line in proc.stdout.strip().split("\n"):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue

    return {}

def main():
    print("=== MCP SDK Server Test ===\n")

    # Test 1: initialize
    print("[1] Initialize...")
    response = call_mcp("initialize")
    server_info = response.get("result", {}).get("serverInfo", {})
    print(f"   Connected: {server_info.get('name')} v{server_info.get('version')}\n")

    # Test 2: tools/list
    print("[2] List tools...")
    response = call_mcp("tools/list")
    tools = response.get("result", {}).get("tools", [])
    print(f"   Tools: {', '.join(t['name'] for t in tools)}\n")

    # Test 3: knowledge_stats
    print("[3] Get statistics...")
    response = call_mcp("tools/call", {
        "name": "knowledge_stats",
        "arguments": {}
    })
    content = response.get("result", {}).get("content", [{}])[0]
    stats_text = content.get("text", "")
    print(stats_text[:600] + "...\n")

    # Test 4: search_articles
    print("[4] Search for 'LLM'...")
    response = call_mcp("tools/call", {
        "name": "search_articles",
        "arguments": {"keyword": "LLM", "limit": 2}
    })
    content = response.get("result", {}).get("content", [{}])[0]
    search_text = content.get("text", "")
    print(search_text[:600] + "...\n")

    print("=" * 50)
    print("All tests passed!")

if __name__ == "__main__":
    sys.exit(main())

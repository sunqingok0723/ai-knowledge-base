#!/usr/bin/env python3
"""
AI 知识库采集脚本 - 混合方案
GitHub API + Trending 多语言页面
"""

import requests
import re
import json
import os
from html.parser import HTMLParser
from html import unescape
from datetime import datetime
from typing import List, Dict, Set

# 配置
PROXY = os.environ.get('HTTP_PROXY', 'http://127.0.0.1:10792')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')  # 可选
TARGET_COUNT = 10

# AI 相关关键词（用于描述筛选）
AI_KEYWORDS = [
    'deepseek', 'agent', 'ai', 'llm', 'gpt', 'ml', 'machine learning',
    'rag', 'langchain', 'vector', 'embedding', 'transformer', 'openai',
    'anthropic', 'claude', 'gemini', 'diffusion', 'speculative',
    'copilot', 'chatbot', 'nlp', 'reinforcement', 'fine-tuning'
]

# Trending 语言列表（AI 项目较多的语言）
TRENDING_LANGUAGES = ['python', 'rust', 'javascript', 'typescript']


class ProxyManager:
    """代理管理器"""

    def __init__(self, proxy_url: str = None):
        self.proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

    def get(self, url: str, timeout: int = 30) -> requests.Response:
        """发送 GET 请求"""
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if GITHUB_TOKEN:
            headers['Authorization'] = f'token {GITHUB_TOKEN}'

        return requests.get(url, headers=headers, proxies=self.proxies, timeout=timeout)


def is_ai_related(text: str) -> bool:
    """判断文本是否与 AI 相关"""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in AI_KEYWORDS)


def collect_from_github_api(proxy_mgr: ProxyManager, limit: int = 20) -> List[Dict]:
    """
    方案 B: 使用 GitHub API 搜索 AI 相关仓库
    """
    print(f"[API] 正在从 GitHub API 搜索 AI 项目...")

    # 构建搜索查询（搜索 AI 相关主题）
    queries = [
        'topic:agent+language:python',
        'topic:llm+language:python',
        'topic:rag+language:python',
        'topic:langchain',
        'topic:openai'
    ]

    results = []
    seen_urls: Set[str] = set()

    for query in queries:
        if len(results) >= limit:
            break

        try:
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=10"
            response = proxy_mgr.get(url)

            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])

                for item in items:
                    repo_url = item['html_url']
                    if repo_url in seen_urls:
                        continue

                    seen_urls.add(repo_url)

                    # 提取信息
                    repo_path = item['full_name']
                    description = item.get('description', '')

                    # 检查是否 AI 相关
                    if not is_ai_related(repo_path + ' ' + description):
                        continue

                    results.append({
                        'title': item['full_name'],
                        'url': repo_url,
                        'source': 'github_api',
                        'popularity': item.get('stargazers_count', 0),
                        'summary': description or f"{item['full_name']} - GitHub 热门项目"
                    })

                    print(f"[API] [OK] {item['full_name']} ({item.get('stargazers_count', 0)} stars)")

            elif response.status_code == 403:
                print("[API] API 限流，切换到 Trending 页面采集")
                break

        except Exception as e:
            print(f"[API] 请求失败: {e}")

    print(f"[API] 共采集 {len(results)} 个项目")
    return results


def fetch_trending_page(proxy_mgr: ProxyManager, language: str = '') -> str:
    """获取 Trending 页面 HTML"""
    url = f"https://github.com/trending/{language}" if language else "https://github.com/trending"

    try:
        response = proxy_mgr.get(url)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"[Trending] 获取 {language or '整体'} 页面失败: {e}")

    return ''


def parse_trending_html(html: str, language: str = '') -> List[Dict]:
    """解析 Trending 页面 HTML"""
    if not html:
        return []

    articles = re.split(r'<article class="Box-row">', html)[1:]
    results = []

    for article in articles[:15]:  # 每页最多检查前 15 个
        repo_match = re.search(r'href="(/[^/]+/[^/"]+)"', article)
        if not repo_match:
            continue

        repo_path = repo_match.group(1)

        # 跳过非仓库链接
        if any(repo_path.startswith(f'/{p}') for p in ['trending', 'login', 'apps', 'sponsors']):
            continue

        # 提取仓库名称
        name_match = re.search(r'<span[^>]*class="text-normal"[^>]*>\s*([^/]+)\s*/\s*</span>\s*([^<]+)</a>', article)
        if name_match:
            username = unescape(name_match.group(1).strip())
            reponame = unescape(name_match.group(2).strip())
            repo_name = f"{username} / {reponame}"
        else:
            repo_name = repo_path.strip('/').replace('/', ' / ')

        # 提取描述
        desc_match = re.search(r'<p class="col-9[^"]*"[^>]*>([^<]+)</p>', article)
        description = ""
        if desc_match:
            description = desc_match.group(1).strip()
            description = unescape(description)
            description = ' '.join(description.split())
            description = description[:200]

        # 提取今日 stars
        stars_today_match = re.search(r'(\d+[,\d]*)\s*stars today', article)
        stars_today = int(stars_today_match.group(1).replace(',', '')) if stars_today_match else 0

        # 提取总 stars
        total_stars_match = re.search(r'stargazers.*?(\d+[,\d]+)</a>', article, re.DOTALL)
        total_stars = int(total_stars_match.group(1).replace(',', '')) if total_stars_match else 0

        # 使用今日 stars 作为热度指标
        popularity = stars_today if stars_today > 0 else total_stars

        if popularity > 0:
            # 检查是否 AI 相关（同时检查名称和描述）
            full_text = f"{repo_name} {description}".lower()
            if not any(kw in full_text for kw in AI_KEYWORDS):
                continue

            results.append({
                'title': repo_name,
                'url': f"https://github.com{repo_path}",
                'source': f'github_trending_{language}' if language else 'github_trending',
                'popularity': popularity,
                'summary': description or f"{repo_name} - GitHub Trending"
            })

    return results


def collect_from_trending(proxy_mgr: ProxyManager) -> List[Dict]:
    """
    方案 C: 从多个语言的 Trending 页面采集
    """
    print(f"[Trending] 正在从多语言 Trending 页面采集...")

    all_results = []
    seen_urls: Set[str] = set()

    # 采集整体 Trending 页面
    html = fetch_trending_page(proxy_mgr, '')
    results = parse_trending_html(html, '')
    for r in results:
        if r['url'] not in seen_urls:
            seen_urls.add(r['url'])
            all_results.append(r)
            print(f"[Trending] [OK] {r['title']} ({r['popularity']})")

    # 采集各语言 Trending 页面
    for lang in TRENDING_LANGUAGES:
        if len(all_results) >= 30:  # 收集足够多后再筛选
            break

        html = fetch_trending_page(proxy_mgr, lang)
        results = parse_trending_html(html, lang)

        for r in results:
            if r['url'] not in seen_urls:
                seen_urls.add(r['url'])
                all_results.append(r)
                print(f"[Trending/{lang}] [OK] {r['title']} ({r['popularity']})")

    print(f"[Trending] 共采集 {len(all_results)} 个项目")
    return all_results


def merge_and_rank(api_results: List[Dict], trending_results: List[Dict]) -> List[Dict]:
    """
    合并两个来源的结果并排序
    - API 结果按总 stars 排序
    - Trending 结果按今日 stars 排序
    - 去重后取 Top N
    """
    # 按来源分组
    by_source = {'github_api': api_results, 'github_trending': trending_results}

    # 去重（保留 API 版本）
    seen_urls: Set[str] = set()
    merged = []

    # 优先保留 API 结果
    for item in api_results:
        if item['url'] not in seen_urls:
            seen_urls.add(item['url'])
            merged.append(item)

    # 添加 Trending 结果
    for item in trending_results:
        if item['url'] not in seen_urls:
            seen_urls.add(item['url'])
            merged.append(item)

    # 按 popularity 排序
    merged.sort(key=lambda x: x['popularity'], reverse=True)

    # 取 Top N
    return merged[:TARGET_COUNT]


def main():
    """主函数"""
    print("=" * 60)
    print("AI 知识库采集 - GitHub API + Trending 混合方案")
    print("=" * 60)

    # 初始化代理管理器
    proxy_mgr = ProxyManager(PROXY)

    # 方案 B: GitHub API 采集
    api_results = collect_from_github_api(proxy_mgr, limit=20)

    # 如果 API 结果不足或失败，使用方案 C 补充
    if len(api_results) < TARGET_COUNT:
        print("\n[Trending] API 结果不足，启动 Trending 页面采集...")
        trending_results = collect_from_trending(proxy_mgr)
    else:
        trending_results = []

    # 合并并排序
    print("\n[合并] 正在合并和去重...")
    final_results = merge_and_rank(api_results, trending_results)

    # 添加采集时间
    collected_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    for item in final_results:
        item['collected_at'] = collected_at

    # 输出结果
    print(f"\n[OK] 采集完成！共获取 {len(final_results)} 个 AI 相关项目\n")

    output_file = f"knowledge/raw/github-trending-{datetime.now().strftime('%Y-%m-%d')}.json"
    os.makedirs('knowledge/raw', exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)

    print(f"[OK] 结果已保存至: {output_file}")

    # 打印结果摘要
    print("\n" + "=" * 60)
    print("采集结果摘要")
    print("=" * 60)
    for i, item in enumerate(final_results, 1):
        print(f"{i}. {item['title']}")
        print(f"   来源: {item['source']} | 热度: {item['popularity']}")

    return final_results


if __name__ == '__main__':
    main()

"""四步知识库自动化流水线。

采集 → 分析 → 整理 → 保存
"""

import argparse
import dataclasses
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from model_client import chat_with_retry, get_provider, LLMResponse

logger = logging.getLogger(__name__)


# ===== 常量定义 =====

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
RSS_SOURCES = {
    "hacker_news": "https://news.ycombinator.com/rss",
    "ai_blog": "https://blog.google/technology/ai/rss/",
}

DEFAULT_PROMPT_TEMPLATE = """分析以下 AI/LLM/Agent 相关内容，生成结构化摘要：

标题：{title}
链接：{url}
描述：{description}

请以 JSON 格式返回，包含以下字段：
{{
    "summary": "200字以内的中文摘要",
    "key_points": ["关键点1", "关键点2", "关键点3"],
    "tech_tags": ["llm", "agent", "rag"]（非技术文章至少用 ["general"]）,
    "difficulty": "beginner/intermediate/advanced",
    "rating": 1-10的推荐分数
}}
"""


# ===== 数据结构 =====

@dataclasses.dataclass
class RawItem:
    """原始采集条目。"""

    id: str
    source: str  # github / rss
    title: str
    url: str
    description: str
    collected_at: str

    def to_dict(self) -> dict:
        """转换为字典。"""
        return dataclasses.asdict(self)


@dataclasses.dataclass
class Article:
    """结构化知识条目。"""

    id: str
    title: str
    source_url: str
    source: str
    summary: str
    content: dict
    collected_at: str
    analyzed_at: str
    status: str = "pending"

    def to_dict(self) -> dict:
        """转换为字典。"""
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        """转换为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ===== Step 1: 采集 =====

async def collect_from_github(
    query: str = "llm OR agent OR rag",
    sort: str = "stars",
    per_page: int = 20,
    token: Optional[str] = None,
) -> list[RawItem]:
    """从 GitHub Search API 采集仓库信息。

    Args:
        query: 搜索关键词
        sort: 排序方式 (stars/forks/updated)
        per_page: 每页数量
        token: GitHub Personal Access Token (可选，提高速率限制)

    Returns:
        RawItem 列表
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    params = {
        "q": query,
        "sort": sort,
        "order": "desc",
        "per_page": per_page,
    }

    items = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(GITHUB_SEARCH_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            for repo in data.get("items", []):
                item = RawItem(
                    id=f"github_{repo['id']}",
                    source="github",
                    title=repo["name"],
                    url=repo["html_url"],
                    description=repo.get("description", ""),
                    collected_at=datetime.now(timezone.utc).isoformat(),
                )
                items.append(item)

            logger.info("GitHub 采集完成: %d 条", len(items))

    except httpx.HTTPError as e:
        logger.error("GitHub 采集失败: %s", e)

    return items


def parse_rss_xml(xml_content: str, source_name: str) -> list[RawItem]:
    """简易 RSS 解析器（使用正则表达式）。

    Args:
        xml_content: RSS XML 内容
        source_name: 来源标识

    Returns:
        RawItem 列表
    """
    items = []

    # 简易正则提取 <item> 内容
    item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
    title_pattern = re.compile(r"<title>(.*?)</title>", re.DOTALL)
    link_pattern = re.compile(r"<link>(.*?)</link>", re.DOTALL)
    desc_pattern = re.compile(r"<description>(.*?)</description>", re.DOTALL)

    # 清理 HTML 标签
    def strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()

    for match in item_pattern.finditer(xml_content):
        item_content = match.group(1)

        title_match = title_pattern.search(item_content)
        link_match = link_pattern.search(item_content)
        desc_match = desc_pattern.search(item_content)

        if title_match and link_match:
            title = strip_html(title_match.group(1))
            url = link_match.group(1).strip()
            description = ""
            if desc_match:
                description = strip_html(desc_match.group(1))

            items.append(RawItem(
                id=f"rss_{uuid.uuid4().hex[:8]}",
                source=source_name,
                title=title,
                url=url,
                description=description[:500],  # 限制描述长度
                collected_at=datetime.now(timezone.utc).isoformat(),
            ))

    return items


async def collect_from_rss(source_urls: dict[str, str]) -> list[RawItem]:
    """从 RSS 源采集文章。

    Args:
        source_urls: {source_name: url} 字典

    Returns:
        RawItem 列表
    """
    items = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for source_name, url in source_urls.items():
            try:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                source_items = parse_rss_xml(response.text, source_name)
                items.extend(source_items)

                logger.info("RSS %s 采集完成: %d 条", source_name, len(source_items))

            except httpx.HTTPError as e:
                logger.error("RSS %s 采集失败: %s", source_name, e)

    return items


def collect(sources: list[str], limit: int) -> list[RawItem]:
    """采集主函数（同步封装）。

    Args:
        sources: 数据源列表，可包含 github、rss
        limit: 采集数量限制

    Returns:
        RawItem 列表
    """
    import asyncio

    items = []

    if "github" in sources:
        github_items = asyncio.run(collect_from_github(per_page=limit))
        items.extend(github_items)

    if "rss" in sources:
        rss_items = asyncio.run(collect_from_rss(RSS_SOURCES))
        items.extend(rss_items)

    logger.info("采集完成: 共 %d 条", len(items))
    return items


# ===== Step 2: 分析 =====

def analyze_item(item: RawItem, provider, model: str = "deepseek-chat") -> Optional[dict]:
    """调用 LLM 分析单条内容。

    Args:
        item: 原始条目
        provider: LLM 提供商实例
        model: 模型名称

    Returns:
        分析结果字典，失败时返回 None
    """
    prompt = DEFAULT_PROMPT_TEMPLATE.format(
        title=item.title,
        url=item.url,
        description=item.description,
    )

    messages = [
        {"role": "system", "content": "你是一个 AI 技术分析专家，擅长提取关键信息和生成摘要。"},
        {"role": "user", "content": prompt},
    ]

    try:
        response: LLMResponse = chat_with_retry(
            provider=provider,
            messages=messages,
            model=model,
            temperature=0.3,
        )

        # 解析 JSON 响应
        content = response.content.strip()
        # 移除 markdown 代码块标记
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)

        result = json.loads(content)
        result["usage"] = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

        logger.info("分析完成: %s", item.title)
        return result

    except (json.JSONDecodeError, httpx.HTTPError) as e:
        logger.error("分析失败: %s - %s", item.title, e)
        return None


def analyze(items: list[RawItem], model: str = "deepseek-chat") -> list[Article]:
    """分析主函数。

    Args:
        items: 原始条目列表
        model: LLM 模型名称

    Returns:
        Article 列表
    """
    provider = get_provider()
    articles = []

    for item in items:
        analysis = analyze_item(item, provider, model)

        if analysis:
            article = Article(
                id=f"{datetime.now().strftime('%Y%m%d')}_{item.id}",
                title=item.title,
                source_url=item.url,
                source=item.source,
                summary=analysis.get("summary", ""),
                content={
                    "key_points": analysis.get("key_points", []),
                    "tech_tags": analysis.get("tech_tags") or ["general"],
                    "difficulty": analysis.get("difficulty", "intermediate"),
                    "rating": analysis.get("rating", 5),
                },
                collected_at=item.collected_at,
                analyzed_at=datetime.now(timezone.utc).isoformat(),
                status="analyzed",
            )
            articles.append(article)
        else:
            # 分析失败，保留原始数据
            article = Article(
                id=f"{datetime.now().strftime('%Y%m%d')}_{item.id}",
                title=item.title,
                source_url=item.url,
                source=item.source,
                summary=item.description[:200],
                content={
                    "key_points": [],
                    "tech_tags": ["general"],
                    "difficulty": "unknown",
                    "rating": 0,
                },
                collected_at=item.collected_at,
                analyzed_at=datetime.now(timezone.utc).isoformat(),
                status="failed",
            )
            articles.append(article)

    logger.info("分析完成: %d 篇文章", len(articles))
    return articles


# ===== Step 3: 整理 =====

def organize(articles: list[Article]) -> list[Article]:
    """去重 + 格式标准化 + 校验。

    Args:
        articles: 文章列表

    Returns:
        整理后的文章列表
    """
    # 去重（按 URL）
    seen_urls = set()
    unique_articles = []

    for article in articles:
        if article.source_url not in seen_urls:
            seen_urls.add(article.source_url)
            unique_articles.append(article)

    # 校验必填字段
    valid_articles = []
    for article in unique_articles:
        if article.title and article.source_url:
            article.status = "published"
            valid_articles.append(article)
        else:
            logger.warning("文章缺少必填字段: %s", article.id)
            article.status = "invalid"

    logger.info(
        "整理完成: 去重 %d → %d，有效 %d",
        len(articles),
        len(unique_articles),
        len(valid_articles),
    )

    return valid_articles


# ===== Step 4: 保存 =====

def save_raw(items: list[RawItem], output_dir: Path) -> None:
    """保存原始采集数据。

    Args:
        items: 原始条目列表
        output_dir: 输出目录
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for item in items:
        output_path = output_dir / f"{item.id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False, indent=2))

    logger.info("原始数据已保存: %s", output_dir)


def save_articles(articles: list[Article], output_dir: Path) -> None:
    """保存结构化文章。

    Args:
        articles: 文章列表
        output_dir: 输出目录
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for article in articles:
        output_path = output_dir / f"{article.id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(article.to_json())

    logger.info("文章已保存: %s (%d 篇)", output_dir, len(articles))


# ===== 主流水线 =====

def run_pipeline(
    sources: list[str],
    limit: int,
    dry_run: bool = False,
    output_base: Optional[Path] = None,
) -> int:
    """运行完整流水线。

    Args:
        sources: 数据源列表
        limit: 采集数量限制
        dry_run: 是否干跑模式
        output_base: 输出基础目录

    Returns:
        处理的文章数量
    """
    if output_base is None:
        output_base = Path(__file__).parent.parent / "knowledge"

    raw_dir = output_base / "raw"
    articles_dir = output_base / "articles"

    # Step 1: 采集
    logger.info("=" * 50)
    logger.info("Step 1: 采集 (sources=%s, limit=%d)", sources, limit)
    logger.info("=" * 50)

    raw_items = collect(sources, limit)

    if not raw_items:
        logger.warning("未采集到任何数据，流水线终止")
        return 0

    if not dry_run:
        save_raw(raw_items, raw_dir)

    # Step 2: 分析
    logger.info("=" * 50)
    logger.info("Step 2: 分析 (%d 条)", len(raw_items))
    logger.info("=" * 50)

    articles = analyze(raw_items)

    # Step 3: 整理
    logger.info("=" * 50)
    logger.info("Step 3: 整理")
    logger.info("=" * 50)

    articles = organize(articles)

    # Step 4: 保存
    logger.info("=" * 50)
    logger.info("Step 4: 保存")
    logger.info("=" * 50)

    if not dry_run:
        save_articles(articles, articles_dir)
    else:
        logger.info("[DRY RUN] 跳过保存文件")

    logger.info("=" * 50)
    logger.info("流水线完成: 共处理 %d 篇文章", len(articles))
    logger.info("=" * 50)

    return len(articles)


# ===== CLI 入口 =====

def main():
    """CLI 入口函数。"""
    parser = argparse.ArgumentParser(
        description="四步知识库自动化流水线: 采集 → 分析 → 整理 → 保存",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pipeline/pipeline.py --sources github,rss --limit 20
  python pipeline/pipeline.py --sources github --limit 5
  python pipeline/pipeline.py --sources rss --limit 10 --dry-run
  python pipeline/pipeline.py --verbose
        """,
    )

    parser.add_argument(
        "--sources",
        type=str,
        default="github,rss",
        help="数据源，逗号分隔: github, rss (默认: github,rss)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="采集数量限制 (默认: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式，不保存文件",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细日志",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出目录 (默认: ../knowledge)",
    )

    args = parser.parse_args()

    # 配置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 解析数据源
    sources = [s.strip() for s in args.sources.lower().split(",")]
    valid_sources = {"github", "rss"}
    invalid = set(sources) - valid_sources

    if invalid:
        parser.error(f"无效的数据源: {invalid}. 有效选项: {valid_sources}")

    # 运行流水线
    try:
        count = run_pipeline(
            sources=sources,
            limit=args.limit,
            dry_run=args.dry_run,
            output_base=args.output,
        )
        return 0
    except Exception as e:
        logger.exception("流水线执行失败: %s", e)
        return 1


if __name__ == "__main__":
    exit(main())

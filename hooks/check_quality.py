#!/usr/bin/env python3
"""知识条目质量评分脚本。

对知识条目 JSON 文件进行 5 维度质量评分，输出等级 A/B/C。
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ========== 配置常量 ==========

# 空洞词黑名单
BUZZWORDS_CN = [
    "赋能", "抓手", "闭环", "打通", "全链路", "底层逻辑",
    "颗粒度", "对齐", "拉通", "沉淀", "强大的", "革命性的",
    "极致", "落地", "抓手", "闭环", "赋能", "联动", "协同"
]

BUZZWORDS_EN = [
    "groundbreaking", "revolutionary", "game-changing", "cutting-edge",
    "innovative", "disruptive", "paradigm-shifting", "state-of-the-art",
    "best-in-class", "industry-leading", "next-generation"
]

# 技术关键词白名单（用于摘要质量加分）
TECH_KEYWORDS = [
    "llm", "gpt", "transformer", "agent", "langchain", "rag", "vector",
    "embedding", "fine-tuning", "推理", "训练", "模型", "框架", "api",
    "python", "javascript", "算法", "架构", "部署", "优化", "性能"
]

# 标准标签列表（用于标签精度评分）
STANDARD_TAGS = {
    "llm", "agent", "rag", "langchain", "python", "gpt", "transformer",
    "fine-tuning", "embedding", "vector-db", "knowledge-base", "tool-use",
    "code-generation", "framework", "tutorial", "deployment", "optimization",
    "multimodal", "vision", "nlp", "prompt", "completion", "chat"
}

# 必填格式字段
FORMAT_FIELDS = ["id", "title", "source_url", "status"]
TIMESTAMP_FIELDS = ["collected_at", "analyzed_at", "created_at", "updated_at"]

# 等级阈值
GRADE_A_THRESHOLD = 80
GRADE_B_THRESHOLD = 60

# ========== 数据结构 ==========


@dataclass
class DimensionScore:
    """单维度评分结果。

    Attributes:
        name: 维度名称。
        score: 得分。
        max_score: 满分。
        details: 评分详情说明。
    """
    name: str
    score: float
    max_score: int
    details: str = ""

    @property
    def percentage(self) -> float:
        """得分百分比。"""
        return (self.score / self.max_score) * 100 if self.max_score > 0 else 0


@dataclass
class QualityReport:
    """质量评分报告。

    Attributes:
        file_path: 文件路径。
        dimensions: 各维度评分列表。
        total_score: 总分。
        grade: 等级 A/B/C。
    """
    file_path: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    total_score: float = 0.0
    grade: str = "C"

    def __post_init__(self) -> None:
        """计算总分和等级。"""
        self.total_score = sum(d.score for d in self.dimensions)
        if self.total_score >= GRADE_A_THRESHOLD:
            self.grade = "A"
        elif self.total_score >= GRADE_B_THRESHOLD:
            self.grade = "B"
        else:
            self.grade = "C"


# ========== 评分函数 ==========


def score_summary_quality(data: dict[str, Any]) -> DimensionScore:
    """评分：摘要质量（25 分）。

    规则：
    - >= 50 字：满分 25
    - >= 20 字：基本分 15
    - < 20 字：0 分
    - 含技术关键词：每个 +2 分，最多 +5

    Args:
        data: 知识条目数据。

    Returns:
        摘要质量评分结果。
    """
    summary = data.get("summary", "")
    length = len(summary)
    score = 0.0
    details = []

    # 基础分
    if length >= 50:
        score = 25.0
        details.append(f"长度 {length} 字（>=50 满分）")
    elif length >= 20:
        score = 15.0
        details.append(f"长度 {length} 字（>=20 基本分）")
    else:
        score = 0.0
        details.append(f"长度 {length} 字（<20 无分）")

    # 技术关键词加分
    keyword_count = 0
    summary_lower = summary.lower()
    for keyword in TECH_KEYWORDS:
        if keyword.lower() in summary_lower:
            keyword_count += 1

    bonus = min(keyword_count * 2, 5)
    if bonus > 0:
        score += bonus
        details.append(f"含 {keyword_count} 个技术关键词，+{bonus:.0f} 分")

    # 限制满分
    score = min(score, 25.0)

    return DimensionScore(
        name="摘要质量",
        score=score,
        max_score=25,
        details="; ".join(details)
    )


def score_technical_depth(data: dict[str, Any]) -> DimensionScore:
    """评分：技术深度（25 分）。

    基于 score 字段（1-10）映射到 0-25。
    支持 score 在根目录或 content 内嵌。

    Args:
        data: 知识条目数据。

    Returns:
        技术深度评分结果。
    """
    raw_score = data.get("score")

    # 尝试从 content 中获取 score
    if raw_score is None:
        content = data.get("content", {})
        if isinstance(content, dict):
            raw_score = content.get("score")

    # 默认值处理
    if raw_score is None or not isinstance(raw_score, (int, float)):
        score = 12.5  # 默认中等分
        details = "无 score 字段，默认中等分"
    else:
        # 映射 1-10 到 0-25
        score = (raw_score / 10) * 25
        details = f"原始评分 {raw_score}/10"

    return DimensionScore(
        name="技术深度",
        score=score,
        max_score=25,
        details=details
    )


def score_format_compliance(data: dict[str, Any]) -> DimensionScore:
    """评分：格式规范（20 分）。

    5 个必填项各 4 分：id, title, source_url, status, 时间戳。

    Args:
        data: 知识条目数据。

    Returns:
        格式规范评分结果。
    """
    score = 0.0
    details = []

    # 检查基础字段
    for field_name in FORMAT_FIELDS:
        if field_name in data and data[field_name]:
            score += 4
        else:
            details.append(f"缺少 {field_name}")

    # 检查时间戳（至少一个）
    has_timestamp = any(data.get(ts) for ts in TIMESTAMP_FIELDS)
    if has_timestamp:
        score += 4
    else:
        details.append("缺少时间戳字段")

    if not details:
        details.append("格式完整")

    return DimensionScore(
        name="格式规范",
        score=score,
        max_score=20,
        details="; ".join(details) if details else "格式完整"
    )


def score_tag_precision(data: dict[str, Any]) -> DimensionScore:
    """评分：标签精度（15 分）。

    规则：
    - 1-3 个标签：满分 15
    - 4-6 个标签：10 分
    - 7+ 个标签：5 分
    - 0 个标签：0 分
    - 标签在标准列表中：每个 +1，最多 +3

    支持 tags 或 content.tech_tags。

    Args:
        data: 知识条目数据。

    Returns:
        标签精度评分结果。
    """
    tags = data.get("tags", [])

    # 尝试从 content 中获取 tech_tags
    if not tags or not isinstance(tags, list):
        content = data.get("content", {})
        if isinstance(content, dict):
            tags = content.get("tech_tags", [])

    if not isinstance(tags, list):
        tags = []

    tag_count = len(tags)
    score = 0.0
    details = []

    # 基础分（基于数量）
    if 1 <= tag_count <= 3:
        score = 15.0
        details.append(f"标签数量 {tag_count}（最佳）")
    elif 4 <= tag_count <= 6:
        score = 10.0
        details.append(f"标签数量 {tag_count}（偏多）")
    elif tag_count >= 7:
        score = 5.0
        details.append(f"标签数量 {tag_count}（过多）")
    else:
        score = 0.0
        details.append("无标签")

    # 标准标签加分
    valid_count = sum(1 for tag in tags if tag in STANDARD_TAGS)
    bonus = min(valid_count, 3)
    if bonus > 0:
        score = min(score + bonus, 15.0)
        details.append(f"{valid_count} 个标准标签，+{bonus}")

    return DimensionScore(
        name="标签精度",
        score=score,
        max_score=15,
        details="; ".join(details)
    )


def score_buzzword_detection(data: dict[str, Any]) -> DimensionScore:
    """评分：空洞词检测（15 分）。

    不含空洞词得满分，每个空洞词扣 3 分。

    Args:
        data: 知识条目数据。

    Returns:
        空洞词检测评分结果。
    """
    text = ""
    for field in ["title", "summary"]:
        value = data.get(field, "")
        if isinstance(value, str):
            text += value.lower()

    # 检查 content 中的字符串字段
    content = data.get("content", {})
    if isinstance(content, dict):
        for value in content.values():
            if isinstance(value, str):
                text += value.lower()

    found_buzzwords = []

    # 检测中文空洞词
    for buzzword in BUZZWORDS_CN:
        if buzzword in text:
            found_buzzwords.append(buzzword)

    # 检测英文空洞词
    for buzzword in BUZZWORDS_EN:
        if buzzword.lower() in text:
            found_buzzwords.append(buzzword)

    # 计算得分
    deduction = len(found_buzzwords) * 3
    score = max(15.0 - deduction, 0.0)

    if found_buzzwords:
        details = f"发现空洞词：{', '.join(set(found_buzzwords))}，-{deduction} 分"
    else:
        details = "无空洞词"

    return DimensionScore(
        name="空洞词检测",
        score=score,
        max_score=15,
        details=details
    )


def analyze_quality(data: dict[str, Any], file_path: Path) -> QualityReport:
    """分析单个文件的质量。

    Args:
        data: 知识条目数据。
        file_path: 文件路径。

    Returns:
        质量评分报告。
    """
    dimensions = [
        score_summary_quality(data),
        score_technical_depth(data),
        score_format_compliance(data),
        score_tag_precision(data),
        score_buzzword_detection(data),
    ]

    return QualityReport(
        file_path=str(file_path),
        dimensions=dimensions
    )


def load_and_analyze_file(file_path: Path) -> QualityReport | None:
    """加载并分析 JSON 文件。

    Args:
        file_path: JSON 文件路径。

    Returns:
        质量评分报告，失败返回 None。
    """
    if not file_path.exists():
        print(f"警告：文件不存在 {file_path}", file=sys.stderr)
        return None

    if file_path.suffix != ".json":
        print(f"警告：非 JSON 文件 {file_path}", file=sys.stderr)
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
        return analyze_quality(data, file_path)
    except json.JSONDecodeError as e:
        print(f"警告：JSON 解析失败 {file_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"警告：读取失败 {file_path}: {e}", file=sys.stderr)
        return None


def render_progress_bar(score: float, max_score: int, width: int = 20) -> str:
    """渲染可视化进度条。

    Args:
        score: 得分。
        max_score: 满分。
        width: 进度条宽度。

    Returns:
        进度条字符串。
    """
    ratio = score / max_score if max_score > 0 else 0
    filled = int(ratio * width)
    bar = "=" * filled + "-" * (width - filled)

    return f"[{bar}] {score:.1f}/{max_score}"


def render_report(report: QualityReport) -> str:
    """渲染质量报告。

    Args:
        report: 质量评分报告。

    Returns:
        格式化的报告字符串。
    """
    lines = [
        f"\n{'=' * 60}",
        f"文件：{report.file_path}",
        f"{'=' * 60}",
    ]

    # 各维度得分
    for dim in report.dimensions:
        lines.append(f"\n{dim.name} ({dim.max_score} 分)")
        lines.append(f"  {render_progress_bar(dim.score, dim.max_score)}")
        if dim.details:
            lines.append(f"    -> {dim.details}")

    # 总分和等级
    grade_symbol = {
        "A": "*",
        "B": "~",
        "C": "x",
    }.get(report.grade, "")

    lines.extend([
        f"\n{'-' * 60}",
        f"总分：{report.total_score:.1f}/100",
        f"等级：{grade_symbol}{report.grade}{grade_symbol}",
    ])

    return "\n".join(lines)


def render_summary(reports: list[QualityReport]) -> str:
    """渲染汇总报告。

    Args:
        reports: 所有质量报告列表。

    Returns:
        格式化的汇总字符串。
    """
    total = len(reports)
    grade_counts = {"A": 0, "B": 0, "C": 0}
    for report in reports:
        grade_counts[report.grade] += 1

    lines = [
        "\n" + "=" * 60,
        "质量评分汇总",
        "=" * 60,
        f"总文件数：{total}",
        f"  A 级：{grade_counts['A']} ({grade_counts['A']/total*100:.1f}%)" if total > 0 else "  A 级：0",
        f"  B 级：{grade_counts['B']} ({grade_counts['B']/total*100:.1f}%)" if total > 0 else "  B 级：0",
        f"  C 级：{grade_counts['C']} ({grade_counts['C']/total*100:.1f}%)" if total > 0 else "  C 级：0",
    ]

    return "\n".join(lines)


def expand_glob_patterns(patterns: list[str]) -> list[Path]:
    """展开通配符模式为具体文件路径。

    Args:
        patterns: 文件路径或通配符模式列表。

    Returns:
        展开后的文件路径列表。
    """
    files: list[Path] = []
    for pattern in patterns:
        path = Path(pattern)
        if "*" in pattern or "?" in pattern:
            matched = list(Path().glob(pattern))
            if not matched:
                print(f"警告：通配符 '{pattern}' 未匹配任何文件", file=sys.stderr)
            files.extend(matched)
        else:
            files.append(path)
    return files


def main() -> int:
    """主函数。

    Returns:
        0 表示无 C 级文件，1 表示存在 C 级文件。
    """
    parser = argparse.ArgumentParser(
        description="知识条目质量评分",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python hooks/check_quality.py knowledge/articles/2025-05-09-gh-hermes.json
  python hooks/check_quality.py knowledge/articles/*.json
        """
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="JSON 文件路径或通配符模式（如 *.json）"
    )

    args = parser.parse_args()

    # 展开通配符
    file_paths = expand_glob_patterns(args.files)

    if not file_paths:
        print("错误：未指定任何有效文件", file=sys.stderr)
        return 1

    # 分析所有文件
    reports: list[QualityReport] = []
    for file_path in file_paths:
        report = load_and_analyze_file(file_path)
        if report:
            reports.append(report)
            print(render_report(report))

    # 打印汇总
    if reports:
        print(render_summary(reports))

    # 检查是否有 C 级
    has_grade_c = any(r.grade == "C" for r in reports) if reports else False
    return 1 if has_grade_c else 0


if __name__ == "__main__":
    sys.exit(main())

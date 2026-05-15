#!/usr/bin/env python3
"""JSON 知识条目校验脚本。

校验知识条目 JSON 文件的格式和内容完整性。
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# 必填字段定义：字段名 -> 类型（按 CLAUDE.md 规范）
REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
    "source_url": str,
    "source": str,
    "summary": str,
    "content": dict,
    "collected_at": str,
    "status": str,
}

# 状态枚举（按 CLAUDE.md 规范）
VALID_STATUSES = {"pending", "analyzed", "published", "rejected"}

# 受众枚举
VALID_AUDIENCES = {"beginner", "intermediate", "advanced"}

# ID 格式正则: YYYYMMDD_{source}_{seq}
ID_PATTERN = re.compile(r"^\d{8}_.+_[A-Za-z0-9]+$")

# URL 格式正则
URL_PATTERN = re.compile(r"^https?://.+")


def validate_id_format(id_value: str) -> list[str]:
    """校验 ID 格式是否符合 YYYYMMDD_{source}_{seq}。

    Args:
        id_value: 待校验的 ID 字符串。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors: list[str] = []
    if not ID_PATTERN.match(id_value):
        errors.append(f"ID 格式错误：'{id_value}'，应为 'YYYYMMDD_source_seq' 格式")
    return errors


def validate_url(url: str) -> list[str]:
    """校验 URL 格式。

    Args:
        url: 待校验的 URL 字符串。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors: list[str] = []
    if not URL_PATTERN.match(url):
        errors.append(f"URL 格式错误：'{url}'，应以 http:// 或 https:// 开头")
    return errors


def validate_summary(summary: str) -> list[str]:
    """校验摘要长度。

    Args:
        summary: 摘要文本。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors: list[str] = []
    if len(summary) < 20:
        errors.append(f"摘要过短：当前 {len(summary)} 字，最少需要 20 字")
    return errors


def validate_tags(tags: list) -> list[str]:
    """校验标签。

    Args:
        tags: 标签列表。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors: list[str] = []
    if len(tags) < 1:
        errors.append("标签数量不足：至少需要 1 个标签")
    return errors


def validate_optional_fields(data: dict[str, Any]) -> list[str]:
    """校验可选字段（在 content 对象中）。

    Args:
        data: 数据字典。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors: list[str] = []

    content = data.get("content", {})
    if not isinstance(content, dict):
        return errors

    if "score" in content:
        score = content["score"]
        if not isinstance(score, (int, float)):
            errors.append(f"content.score 类型错误：应为数字，实际为 {type(score).__name__}")
        elif not (1 <= score <= 10):
            errors.append(f"content.score 范围错误：当前 {score}，应在 1-10 之间")

    if "difficulty" in content:
        difficulty = content["difficulty"]
        if difficulty not in VALID_AUDIENCES:
            errors.append(
                f"content.difficulty 值错误：'{difficulty}'，"
                f"应为 {', '.join(sorted(VALID_AUDIENCES))} 之一"
            )

    return errors


def validate_entry(data: dict[str, Any], file_path: Path) -> list[str]:
    """校验单个知识条目。

    Args:
        data: 知识条目数据字典。
        file_path: 文件路径（用于错误信息）。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors: list[str] = []
    prefix = f"[{file_path.name}]"

    # 校验必填字段的存在性和类型
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"{prefix} 缺少必填字段：{field}")
            continue

        actual_type = type(data[field])
        if actual_type != expected_type:
            errors.append(
                f"{prefix} 字段 '{field}' 类型错误："
                f"期望 {expected_type.__name__}，实际 {actual_type.__name__}"
            )

    # 如果有基本错误，先返回，避免后续校验报错
    if errors:
        return errors

    # 校验 ID 格式
    errors.extend(validate_id_format(data["id"]))

    # 校验 status 枚举
    if data["status"] not in VALID_STATUSES:
        errors.append(
            f"{prefix} status 值错误：'{data['status']}'，"
            f"应为 {', '.join(sorted(VALID_STATUSES))} 之一"
        )

    # 校验 URL 格式
    errors.extend(validate_url(data["source_url"]))

    # 校验摘要长度
    errors.extend(validate_summary(data["summary"]))

    # 校验标签数量（检查 content.tech_tags）
    content = data.get("content", {})
    if isinstance(content, dict):
        tags = content.get("tech_tags", [])
    else:
        tags = []
    errors.extend(validate_tags(tags))

    # 校验可选字段（在 content 中）
    errors.extend(validate_optional_fields(data))

    return errors


def load_and_validate_file(file_path: Path) -> list[str]:
    """加载并校验 JSON 文件。

    Args:
        file_path: JSON 文件路径。

    Returns:
        错误信息列表，空列表表示通过。
    """
    errors: list[str] = []

    # 检查文件是否存在
    if not file_path.exists():
        return [f"文件不存在：{file_path}"]

    # 检查文件扩展名
    if file_path.suffix != ".json":
        return [f"文件扩展名错误：{file_path}，应为 .json 文件"]

    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return [f"[{file_path.name}] JSON 解析失败：{e}"]
    except Exception as e:
        return [f"[{file_path.name}] 读取失败：{e}"]

    # 校验数据
    errors.extend(validate_entry(data, file_path))

    return errors


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

        # 检查是否为通配符
        if "*" in pattern or "?" in pattern:
            matched = list(Path().glob(pattern))
            if not matched:
                print(f"警告：通配符 '{pattern}' 未匹配任何文件", file=sys.stderr)
            files.extend(matched)
        else:
            files.append(path)

    return files


def print_summary(all_errors: dict[str, list[str]], total_files: int) -> None:
    """打印校验汇总统计。

    Args:
        all_errors: 文件路径到错误列表的映射。
        total_files: 总文件数。
    """
    failed_files = len(all_errors)
    passed_files = total_files - failed_files

    print("\n" + "=" * 50)
    print("校验汇总")
    print("=" * 50)
    print(f"总文件数：{total_files}")
    print(f"通过：{passed_files}")
    print(f"失败：{failed_files}")

    if all_errors:
        print("\n失败文件详情：")
        for file_path, errors in all_errors.items():
            print(f"\n{file_path}:")
            for error in errors:
                print(f"  - {error}")


def main() -> int:
    """主函数。

    Returns:
        0 表示所有文件校验通过，1 表示至少有一个文件校验失败。
    """
    parser = argparse.ArgumentParser(
        description="校验知识条目 JSON 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python hooks/validate_json.py knowledge/articles/2025-05-09-gh-hermes.json
  python hooks/validate_json.py knowledge/articles/*.json
  python hooks/validate_json.py article1.json article2.json
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

    # 校验所有文件
    all_errors: dict[str, list[str]] = {}

    for file_path in file_paths:
        errors = load_and_validate_file(file_path)
        if errors:
            all_errors[str(file_path)] = errors

    # 打印汇总
    print_summary(all_errors, len(file_paths))

    # 返回退出码
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())

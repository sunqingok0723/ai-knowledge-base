#!/usr/bin/env python3
"""自动安装 Git pre-commit hooks。

安装完成后，每次 git commit 时会自动校验 knowledge/articles/*.json 文件。
"""

import shutil
from pathlib import Path


# Pre-commit hook 脚本内容
HOOK_SCRIPT = '''#!/usr/bin/env python
"""Git pre-commit hook: 校验和质检知识条目 JSON 文件。"""

import subprocess
import sys
from pathlib import Path


def get_staged_json_files() -> list[Path]:
    """获取暂存区中的 JSON 文件。

    Returns:
        暂存的 JSON 文件路径列表。
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return []

    files = []
    for line in result.stdout.strip().split("\\n"):
        if line and line.endswith(".json") and "knowledge/articles" in line:
            files.append(Path(line))

    return files


def run_hook(hook_name: str, script_path: str, files: list[Path]) -> bool:
    """运行 hook 脚本。

    Args:
        hook_name: Hook 名称。
        script_path: 脚本路径。
        files: 待检验的文件列表。

    Returns:
        True 表示通过，False 表示失败。
    """
    if not files:
        return True

    print(f"\\n{'=' * 60}")
    print(f"运行 {hook_name}...")
    print(f"{'=' * 60}")

    file_args = [str(f) for f in files]
    result = subprocess.run(
        [sys.executable, script_path] + file_args,
        capture_output=False,
    )

    return result.returncode == 0


def main() -> None:
    """主函数。"""
    staged_files = get_staged_json_files()

    if not staged_files:
        return 0

    print(f"\\n[*] Found {len(staged_files)} knowledge entry files to validate")

    # 运行格式校验
    if not run_hook("JSON Format Validation", "hooks/validate_json.py", staged_files):
        print("\\n[FAIL] Format validation failed, commit aborted")
        print("   Please fix errors and commit again")
        return 1

    # 运行质量检查
    if not run_hook("Quality Score Check", "hooks/check_quality.py", staged_files):
        print("\\n[FAIL] Quality check failed (Grade C found), commit aborted")
        print("   Please improve quality and commit again")
        return 1

    print("\\n[OK] All validations passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def install_hook() -> None:
    """安装 pre-commit hook。"""
    repo_root = Path(__file__).parent.parent
    hooks_dir = repo_root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hook_file = hooks_dir / "pre-commit"

    # 写入 hook 脚本
    hook_file.write_text(HOOK_SCRIPT, encoding="utf-8")

    print(f"[OK] Pre-commit hook installed to: {hook_file}")
    print("\\nHook features:")
    print("   - Auto-validate knowledge/articles/*.json format")
    print("   - Auto-check quality scores (reject Grade C)")
    print("\\nTips:")
    print("   - Use 'git commit --no-verify' to skip hook")
    print("   - Modify scripts in hooks/ to update rules")


def main() -> None:
    """主函数。"""
    install_hook()


if __name__ == "__main__":
    main()

"""
Lint output parsing for various linters.

Supports:
- ruff (Python)
- eslint (JavaScript/TypeScript)
- golangci-lint (Go)
- clippy (Rust)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable

from cert_code.models import Language, LintResults


@dataclass
class LinterConfig:
    """Configuration for a linter."""

    command: list[str]
    tool: str
    parser: str


# Default linters by language
DEFAULT_LINTERS: dict[Language, LinterConfig] = {
    Language.PYTHON: LinterConfig(
        command=["ruff", "check", "--output-format=json", "."],
        tool="ruff",
        parser="parse_ruff",
    ),
    Language.JAVASCRIPT: LinterConfig(
        command=["eslint", "--format=json", "."],
        tool="eslint",
        parser="parse_eslint",
    ),
    Language.TYPESCRIPT: LinterConfig(
        command=["eslint", "--format=json", "."],
        tool="eslint",
        parser="parse_eslint",
    ),
    Language.GO: LinterConfig(
        command=["golangci-lint", "run", "--out-format=json"],
        tool="golangci-lint",
        parser="parse_golangci",
    ),
    Language.RUST: LinterConfig(
        command=["cargo", "clippy", "--message-format=json"],
        tool="clippy",
        parser="parse_clippy",
    ),
}


def run_lint(
    command: str | None = None,
    language: Language | None = None,
    timeout: int = 60,
    cwd: str | None = None,
) -> LintResults:
    """
    Run linter and parse results.

    Args:
        command: Explicit lint command (overrides auto-detection)
        language: Language for auto-detection
        timeout: Lint timeout in seconds
        cwd: Working directory

    Returns:
        LintResults with parsed information
    """
    # Determine command
    if command:
        cmd = command.split() if isinstance(command, str) else command
        tool = cmd[0] if cmd else "unknown"
    elif language and language in DEFAULT_LINTERS:
        config = DEFAULT_LINTERS[language]
        cmd = config.command
        tool = config.tool
    else:
        return LintResults(passed=True, tool="none")

    # Run linter
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        output = result.stdout + "\n" + result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired:
        return LintResults(
            passed=False,
            error_count=1,
            errors=[{"message": f"Lint timeout after {timeout}s"}],
            tool=tool,
        )
    except FileNotFoundError:
        return LintResults(
            passed=True,
            tool=f"{tool} (not found)",
        )
    except Exception as e:
        return LintResults(
            passed=False,
            error_count=1,
            errors=[{"message": f"Error running linter: {e}"}],
            tool=tool,
        )

    # Parse results
    parser_func = _get_parser(tool)
    return parser_func(output, returncode, tool)


def parse_ruff(output: str, returncode: int, tool: str) -> LintResults:
    """Parse ruff JSON output."""
    errors = []
    warnings = []

    try:
        # Try to parse JSON output
        data = json.loads(output)
        for issue in data:
            entry = {
                "file": issue.get("filename", ""),
                "line": issue.get("location", {}).get("row", 0),
                "column": issue.get("location", {}).get("column", 0),
                "code": issue.get("code", ""),
                "message": issue.get("message", ""),
            }
            if issue.get("code", "").startswith("E") or issue.get("code", "").startswith("F"):
                errors.append(entry)
            else:
                warnings.append(entry)
    except json.JSONDecodeError:
        # Fallback to line counting
        error_count = output.count("error")
        warning_count = output.count("warning")
        return LintResults(
            passed=returncode == 0,
            error_count=error_count,
            warning_count=warning_count,
            tool=tool,
        )

    return LintResults(
        passed=len(errors) == 0,
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors[:50],  # Limit to 50 errors
        tool=tool,
    )


def parse_eslint(output: str, returncode: int, tool: str) -> LintResults:
    """Parse eslint JSON output."""
    errors = []
    warnings = []

    try:
        data = json.loads(output)
        for file_result in data:
            for message in file_result.get("messages", []):
                entry = {
                    "file": file_result.get("filePath", ""),
                    "line": message.get("line", 0),
                    "column": message.get("column", 0),
                    "code": message.get("ruleId", ""),
                    "message": message.get("message", ""),
                }
                if message.get("severity") == 2:
                    errors.append(entry)
                else:
                    warnings.append(entry)
    except json.JSONDecodeError:
        # Fallback
        error_count = output.lower().count("error")
        warning_count = output.lower().count("warning")
        return LintResults(
            passed=returncode == 0,
            error_count=error_count,
            warning_count=warning_count,
            tool=tool,
        )

    return LintResults(
        passed=len(errors) == 0,
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors[:50],
        tool=tool,
    )


def parse_golangci(output: str, returncode: int, tool: str) -> LintResults:
    """Parse golangci-lint JSON output."""
    errors = []

    try:
        data = json.loads(output)
        for issue in data.get("Issues", []):
            errors.append(
                {
                    "file": issue.get("Pos", {}).get("Filename", ""),
                    "line": issue.get("Pos", {}).get("Line", 0),
                    "column": issue.get("Pos", {}).get("Column", 0),
                    "code": issue.get("FromLinter", ""),
                    "message": issue.get("Text", ""),
                }
            )
    except json.JSONDecodeError:
        error_count = len([line for line in output.split("\n") if line.strip()])
        return LintResults(
            passed=returncode == 0,
            error_count=error_count,
            tool=tool,
        )

    return LintResults(
        passed=len(errors) == 0,
        error_count=len(errors),
        errors=errors[:50],
        tool=tool,
    )


def parse_clippy(output: str, returncode: int, tool: str) -> LintResults:
    """Parse cargo clippy JSON output."""
    errors = []
    warnings = []

    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            if data.get("reason") == "compiler-message":
                message = data.get("message", {})
                level = message.get("level", "")
                entry = {
                    "file": message.get("spans", [{}])[0].get("file_name", "")
                    if message.get("spans")
                    else "",
                    "line": message.get("spans", [{}])[0].get("line_start", 0)
                    if message.get("spans")
                    else 0,
                    "code": message.get("code", {}).get("code", "") if message.get("code") else "",
                    "message": message.get("message", ""),
                }
                if level == "error":
                    errors.append(entry)
                elif level == "warning":
                    warnings.append(entry)
        except json.JSONDecodeError:
            continue

    return LintResults(
        passed=len(errors) == 0,
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors[:50],
        tool=tool,
    )


LintParserFunc = Callable[[str, int, str], LintResults]


def _get_parser(tool: str) -> LintParserFunc:
    """Get parser function for tool."""
    parsers: dict[str, LintParserFunc] = {
        "ruff": parse_ruff,
        "eslint": parse_eslint,
        "golangci-lint": parse_golangci,
        "clippy": parse_clippy,
    }
    return parsers.get(tool, _parse_generic_lint_output)


def _parse_generic_lint_output(output: str, returncode: int, tool: str) -> LintResults:
    """Generic fallback parser."""
    error_count = sum(1 for line in output.split("\n") if "error" in line.lower())
    warning_count = sum(1 for line in output.split("\n") if "warning" in line.lower())

    return LintResults(
        passed=returncode == 0,
        error_count=error_count,
        warning_count=warning_count,
        tool=tool,
    )

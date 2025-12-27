"""
Type checker output parsing.

Supports:
- mypy (Python)
- tsc (TypeScript)
- go vet (Go)
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Optional

from cert_code.models import Language, TypeCheckResults


@dataclass
class TypeCheckerConfig:
    """Configuration for a type checker."""

    command: list[str]
    tool: str
    parser: str


# Default type checkers by language
DEFAULT_TYPE_CHECKERS: dict[Language, TypeCheckerConfig] = {
    Language.PYTHON: TypeCheckerConfig(
        command=["mypy", "--no-error-summary", "."],
        tool="mypy",
        parser="parse_mypy",
    ),
    Language.TYPESCRIPT: TypeCheckerConfig(
        command=["tsc", "--noEmit"],
        tool="tsc",
        parser="parse_tsc",
    ),
    Language.GO: TypeCheckerConfig(
        command=["go", "vet", "./..."],
        tool="go vet",
        parser="parse_go_vet",
    ),
}


def run_typecheck(
    command: Optional[str] = None,
    language: Optional[Language] = None,
    timeout: int = 120,
    cwd: Optional[str] = None,
) -> TypeCheckResults:
    """
    Run type checker and parse results.

    Args:
        command: Explicit type check command (overrides auto-detection)
        language: Language for auto-detection
        timeout: Type check timeout in seconds
        cwd: Working directory

    Returns:
        TypeCheckResults with parsed information
    """
    # Determine command
    if command:
        cmd = command.split() if isinstance(command, str) else command
        tool = cmd[0] if cmd else "unknown"
    elif language and language in DEFAULT_TYPE_CHECKERS:
        config = DEFAULT_TYPE_CHECKERS[language]
        cmd = config.command
        tool = config.tool
    else:
        return TypeCheckResults(passed=True, tool="none")

    # Run type checker
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
        return TypeCheckResults(
            passed=False,
            error_count=1,
            errors=[{"message": f"Type check timeout after {timeout}s"}],
            tool=tool,
        )
    except FileNotFoundError:
        return TypeCheckResults(
            passed=True,
            tool=f"{tool} (not found)",
        )
    except Exception as e:
        return TypeCheckResults(
            passed=False,
            error_count=1,
            errors=[{"message": f"Error running type checker: {e}"}],
            tool=tool,
        )

    # Parse results
    parser = _get_parser(tool)
    return parser(output, returncode, tool)


def parse_mypy(output: str, returncode: int, tool: str) -> TypeCheckResults:
    """Parse mypy output."""
    # Mypy output format: file:line: error: message
    error_pattern = re.compile(r"^(.+):(\d+): error: (.+)$", re.MULTILINE)

    errors = []
    for match in error_pattern.finditer(output):
        errors.append(
            {
                "file": match.group(1),
                "line": int(match.group(2)),
                "message": match.group(3),
            }
        )

    return TypeCheckResults(
        passed=len(errors) == 0 and returncode == 0,
        error_count=len(errors),
        errors=errors[:50],
        tool=tool,
    )


def parse_tsc(output: str, returncode: int, tool: str) -> TypeCheckResults:
    """Parse TypeScript compiler output."""
    # TSC output format: file(line,col): error TSxxxx: message
    error_pattern = re.compile(r"^(.+)\((\d+),(\d+)\): error (TS\d+): (.+)$", re.MULTILINE)

    errors = []
    for match in error_pattern.finditer(output):
        errors.append(
            {
                "file": match.group(1),
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "code": match.group(4),
                "message": match.group(5),
            }
        )

    return TypeCheckResults(
        passed=len(errors) == 0 and returncode == 0,
        error_count=len(errors),
        errors=errors[:50],
        tool=tool,
    )


def parse_go_vet(output: str, returncode: int, tool: str) -> TypeCheckResults:
    """Parse go vet output."""
    # Go vet output format: file:line:col: message
    error_pattern = re.compile(r"^(.+):(\d+):(\d+): (.+)$", re.MULTILINE)

    errors = []
    for match in error_pattern.finditer(output):
        errors.append(
            {
                "file": match.group(1),
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "message": match.group(4),
            }
        )

    return TypeCheckResults(
        passed=len(errors) == 0 and returncode == 0,
        error_count=len(errors),
        errors=errors[:50],
        tool=tool,
    )


def _get_parser(tool: str):
    """Get parser function for tool."""
    parsers = {
        "mypy": parse_mypy,
        "tsc": parse_tsc,
        "go vet": parse_go_vet,
    }
    return parsers.get(tool, _parse_generic_typecheck_output)


def _parse_generic_typecheck_output(output: str, returncode: int, tool: str) -> TypeCheckResults:
    """Generic fallback parser."""
    error_count = sum(1 for line in output.split("\n") if "error" in line.lower())

    return TypeCheckResults(
        passed=returncode == 0,
        error_count=error_count,
        tool=tool,
    )

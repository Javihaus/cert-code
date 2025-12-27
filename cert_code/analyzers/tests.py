"""
Test result parsing for various frameworks.

Supports:
- pytest (Python)
- jest (JavaScript/TypeScript)
- go test (Go)
- cargo test (Rust)
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

from cert_code.models import TestResults


@dataclass
class TestRunnerConfig:
    """Configuration for a test runner."""

    command: list[str]
    framework: str
    parser: str  # Parser function name


# Default test runners by language
DEFAULT_TEST_RUNNERS: dict[str, TestRunnerConfig] = {
    "python": TestRunnerConfig(
        command=["pytest", "--tb=short", "-q"],
        framework="pytest",
        parser="parse_pytest",
    ),
    "javascript": TestRunnerConfig(
        command=["npm", "test", "--", "--json"],
        framework="jest",
        parser="parse_jest",
    ),
    "typescript": TestRunnerConfig(
        command=["npm", "test", "--", "--json"],
        framework="jest",
        parser="parse_jest",
    ),
    "go": TestRunnerConfig(
        command=["go", "test", "-json", "./..."],
        framework="go test",
        parser="parse_go_test",
    ),
    "rust": TestRunnerConfig(
        command=["cargo", "test", "--", "--format=json", "-Z", "unstable-options"],
        framework="cargo test",
        parser="parse_cargo_test",
    ),
}


def run_tests(
    command: Optional[str] = None,
    language: Optional[str] = None,
    timeout: int = 300,
    cwd: Optional[str] = None,
) -> TestResults:
    """
    Run tests and parse results.

    Args:
        command: Explicit test command (overrides auto-detection)
        language: Language for auto-detection
        timeout: Test timeout in seconds
        cwd: Working directory

    Returns:
        TestResults with parsed information
    """
    # Determine command
    if command:
        cmd = command.split() if isinstance(command, str) else command
        framework = "custom"
    elif language and language in DEFAULT_TEST_RUNNERS:
        config = DEFAULT_TEST_RUNNERS[language]
        cmd = config.command
        framework = config.framework
    else:
        # Try to detect
        cmd, framework = _detect_test_command()

    # Run tests
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
    except subprocess.TimeoutExpired as e:
        output = f"Test timeout after {timeout}s\n{e.stdout or ''}\n{e.stderr or ''}"
        returncode = -1
    except FileNotFoundError:
        return TestResults(
            passed=False,
            output=f"Test command not found: {cmd[0]}",
            framework=framework,
        )
    except Exception as e:
        return TestResults(
            passed=False,
            output=f"Error running tests: {e}",
            framework=framework,
        )

    # Parse results
    parser = _get_parser(framework)
    return parser(output, returncode, framework)


def parse_pytest(output: str, returncode: int, framework: str) -> TestResults:
    """Parse pytest output."""
    # Look for summary line: "X passed, Y failed, Z skipped"
    summary_pattern = re.compile(
        r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?(?:, (\d+) error)?"
    )

    passed_count = 0
    failed_count = 0
    skipped_count = 0

    match = summary_pattern.search(output)
    if match:
        passed_count = int(match.group(1) or 0)
        failed_count = int(match.group(2) or 0)
        skipped_count = int(match.group(3) or 0)
        error_count = int(match.group(4) or 0)
        failed_count += error_count

    total = passed_count + failed_count + skipped_count

    # Extract duration if present
    duration_ms = 0
    duration_match = re.search(r"in ([\d.]+)s", output)
    if duration_match:
        duration_ms = int(float(duration_match.group(1)) * 1000)

    return TestResults(
        passed=returncode == 0 and failed_count == 0,
        total=total,
        failed=failed_count,
        skipped=skipped_count,
        duration_ms=duration_ms,
        output=output,
        framework=framework,
    )


def parse_jest(output: str, returncode: int, framework: str) -> TestResults:
    """Parse Jest JSON output."""
    # Try to extract JSON
    try:
        # Jest JSON output might be mixed with other output
        json_start = output.find("{")
        json_end = output.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(output[json_start:json_end])

            return TestResults(
                passed=data.get("success", False),
                total=data.get("numTotalTests", 0),
                failed=data.get("numFailedTests", 0),
                skipped=data.get("numPendingTests", 0),
                duration_ms=int(
                    data.get("testResults", [{}])[0].get("endTime", 0)
                    - data.get("testResults", [{}])[0].get("startTime", 0)
                ),
                output=output,
                framework=framework,
            )
    except (json.JSONDecodeError, KeyError, IndexError):
        pass

    # Fallback to text parsing
    return _parse_generic_test_output(output, returncode, framework)


def parse_go_test(output: str, returncode: int, framework: str) -> TestResults:
    """Parse go test -json output."""
    passed_count = 0
    failed_count = 0
    skipped_count = 0
    duration_ms = 0

    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            action = event.get("Action")

            if action == "pass":
                passed_count += 1
            elif action == "fail":
                failed_count += 1
            elif action == "skip":
                skipped_count += 1

            # Extract elapsed time from final event
            if event.get("Elapsed"):
                duration_ms = int(event["Elapsed"] * 1000)

        except json.JSONDecodeError:
            continue

    total = passed_count + failed_count + skipped_count

    return TestResults(
        passed=returncode == 0 and failed_count == 0,
        total=total,
        failed=failed_count,
        skipped=skipped_count,
        duration_ms=duration_ms,
        output=output,
        framework=framework,
    )


def parse_cargo_test(output: str, returncode: int, framework: str) -> TestResults:
    """Parse cargo test output."""
    # Look for: "test result: ok. X passed; Y failed; Z ignored"
    result_pattern = re.compile(
        r"test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored"
    )

    match = result_pattern.search(output)
    if match:
        status = match.group(1)
        passed_count = int(match.group(2))
        failed_count = int(match.group(3))
        skipped_count = int(match.group(4))

        return TestResults(
            passed=status == "ok",
            total=passed_count + failed_count + skipped_count,
            failed=failed_count,
            skipped=skipped_count,
            output=output,
            framework=framework,
        )

    return _parse_generic_test_output(output, returncode, framework)


def _parse_generic_test_output(output: str, returncode: int, framework: str) -> TestResults:
    """Generic fallback parser."""
    return TestResults(
        passed=returncode == 0,
        output=output,
        framework=framework,
    )


def _detect_test_command() -> tuple[list[str], str]:
    """Detect test command from project files."""
    import os

    # Check for package.json (Node.js)
    if os.path.exists("package.json"):
        return ["npm", "test"], "npm"

    # Check for pytest/python
    if os.path.exists("pytest.ini") or os.path.exists("pyproject.toml"):
        return ["pytest", "--tb=short", "-q"], "pytest"

    # Check for go.mod
    if os.path.exists("go.mod"):
        return ["go", "test", "./..."], "go test"

    # Check for Cargo.toml
    if os.path.exists("Cargo.toml"):
        return ["cargo", "test"], "cargo test"

    # Default to pytest
    return ["pytest", "--tb=short", "-q"], "pytest"


def _get_parser(framework: str):
    """Get parser function for framework."""
    parsers = {
        "pytest": parse_pytest,
        "jest": parse_jest,
        "npm": parse_jest,  # npm test usually runs jest
        "go test": parse_go_test,
        "cargo test": parse_cargo_test,
    }
    return parsers.get(framework, _parse_generic_test_output)

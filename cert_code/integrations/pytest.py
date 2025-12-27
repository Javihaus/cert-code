"""
pytest integration for cert-code.

Provides detailed parsing of pytest output and
direct integration with pytest's plugin system.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cert_code.models import TestResults


@dataclass
class PytestTestCase:
    """A single pytest test case."""
    nodeid: str
    outcome: str  # passed, failed, skipped, error
    duration: float = 0.0
    longrepr: Optional[str] = None  # Failure representation
    markers: list[str] = field(default_factory=list)


@dataclass
class PytestReport:
    """Detailed pytest report."""
    tests: list[PytestTestCase]
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    exit_code: int = 0
    warnings: list[str] = field(default_factory=list)


class PytestIntegration:
    """Integration with pytest for running and parsing tests."""

    def __init__(
        self,
        args: Optional[list[str]] = None,
        cwd: Optional[str] = None,
        timeout: int = 300,
    ):
        self.args = args or []
        self.cwd = cwd
        self.timeout = timeout

    def run(self) -> TestResults:
        """
        Run pytest and return results.

        Uses pytest's JSON output for accurate parsing.
        """
        # Build command with JSON output
        cmd = ["pytest", "--tb=short", "-q", "--json-report", "--json-report-file=-"]
        cmd.extend(self.args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
            )

            # Try to parse JSON report
            report = self._parse_json_report(result.stdout)
            if report:
                return self._report_to_results(report, result.stdout)

            # Fall back to text parsing
            return self._parse_text_output(result.stdout, result.returncode)

        except FileNotFoundError:
            # pytest-json-report not installed, try without it
            return self._run_without_json()
        except subprocess.TimeoutExpired:
            return TestResults(
                passed=False,
                output=f"Test timeout after {self.timeout}s",
                framework="pytest",
            )

    def _run_without_json(self) -> TestResults:
        """Run pytest without JSON report plugin."""
        cmd = ["pytest", "--tb=short", "-q"]
        cmd.extend(self.args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
            )
            return self._parse_text_output(
                result.stdout + "\n" + result.stderr,
                result.returncode,
            )
        except subprocess.TimeoutExpired:
            return TestResults(
                passed=False,
                output=f"Test timeout after {self.timeout}s",
                framework="pytest",
            )
        except FileNotFoundError:
            return TestResults(
                passed=False,
                output="pytest not found",
                framework="pytest",
            )

    def _parse_json_report(self, output: str) -> Optional[PytestReport]:
        """Parse pytest-json-report output."""
        # Look for JSON in output
        try:
            # The JSON report is usually at the end
            json_start = output.rfind('{"created":')
            if json_start == -1:
                return None

            data = json.loads(output[json_start:])

            tests = []
            for test in data.get("tests", []):
                tests.append(PytestTestCase(
                    nodeid=test.get("nodeid", ""),
                    outcome=test.get("outcome", ""),
                    duration=test.get("duration", 0.0),
                    longrepr=test.get("longrepr"),
                ))

            summary = data.get("summary", {})

            return PytestReport(
                tests=tests,
                passed=summary.get("passed", 0),
                failed=summary.get("failed", 0),
                skipped=summary.get("skipped", 0),
                errors=summary.get("error", 0),
                duration=data.get("duration", 0.0),
                exit_code=data.get("exitcode", 0),
                warnings=data.get("warnings", []),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def _parse_text_output(self, output: str, returncode: int) -> TestResults:
        """Parse pytest text output."""
        # Look for summary line
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

        # Extract duration
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
            framework="pytest",
        )

    def _report_to_results(self, report: PytestReport, output: str) -> TestResults:
        """Convert PytestReport to TestResults."""
        return TestResults(
            passed=report.exit_code == 0 and report.failed == 0,
            total=report.passed + report.failed + report.skipped,
            failed=report.failed + report.errors,
            skipped=report.skipped,
            duration_ms=int(report.duration * 1000),
            output=output,
            framework="pytest",
        )

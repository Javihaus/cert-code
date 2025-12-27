"""
Jest integration for cert-code.

Provides detailed parsing of Jest output.
"""

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

from cert_code.models import TestResults


@dataclass
class JestTestCase:
    """A single Jest test case."""
    title: str
    fullName: str
    status: str  # passed, failed, pending
    duration: int = 0
    failureMessages: list[str] = field(default_factory=list)


@dataclass
class JestTestSuite:
    """A Jest test suite (file)."""
    name: str
    tests: list[JestTestCase]
    startTime: int = 0
    endTime: int = 0


@dataclass
class JestReport:
    """Complete Jest test report."""
    testSuites: list[JestTestSuite]
    numPassedTests: int = 0
    numFailedTests: int = 0
    numPendingTests: int = 0
    numTotalTests: int = 0
    startTime: int = 0
    success: bool = True


class JestIntegration:
    """Integration with Jest for running and parsing tests."""

    def __init__(
        self,
        args: Optional[list[str]] = None,
        cwd: Optional[str] = None,
        timeout: int = 300,
        use_npm: bool = True,
    ):
        self.args = args or []
        self.cwd = cwd
        self.timeout = timeout
        self.use_npm = use_npm

    def run(self) -> TestResults:
        """Run Jest and return results."""
        if self.use_npm:
            cmd = ["npm", "test", "--", "--json"]
        else:
            cmd = ["jest", "--json"]

        cmd.extend(self.args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
            )

            # Parse JSON output
            output = result.stdout + "\n" + result.stderr
            report = self._parse_json_output(output)

            if report:
                return self._report_to_results(report, output)

            # Fallback to basic parsing
            return self._parse_text_output(output, result.returncode)

        except subprocess.TimeoutExpired:
            return TestResults(
                passed=False,
                output=f"Test timeout after {self.timeout}s",
                framework="jest",
            )
        except FileNotFoundError:
            return TestResults(
                passed=False,
                output="npm/jest not found",
                framework="jest",
            )

    def _parse_json_output(self, output: str) -> Optional[JestReport]:
        """Parse Jest JSON output."""
        try:
            # Find the JSON object in output (might be mixed with other output)
            json_start = output.find('{"')
            json_end = output.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                return None

            data = json.loads(output[json_start:json_end])

            test_suites = []
            for suite_data in data.get("testResults", []):
                tests = []
                for test in suite_data.get("assertionResults", []):
                    tests.append(JestTestCase(
                        title=test.get("title", ""),
                        fullName=test.get("fullName", ""),
                        status=test.get("status", ""),
                        duration=test.get("duration", 0),
                        failureMessages=test.get("failureMessages", []),
                    ))

                test_suites.append(JestTestSuite(
                    name=suite_data.get("name", ""),
                    tests=tests,
                    startTime=suite_data.get("startTime", 0),
                    endTime=suite_data.get("endTime", 0),
                ))

            return JestReport(
                testSuites=test_suites,
                numPassedTests=data.get("numPassedTests", 0),
                numFailedTests=data.get("numFailedTests", 0),
                numPendingTests=data.get("numPendingTests", 0),
                numTotalTests=data.get("numTotalTests", 0),
                startTime=data.get("startTime", 0),
                success=data.get("success", False),
            )

        except (json.JSONDecodeError, KeyError):
            return None

    def _parse_text_output(self, output: str, returncode: int) -> TestResults:
        """Parse Jest text output as fallback."""
        return TestResults(
            passed=returncode == 0,
            output=output,
            framework="jest",
        )

    def _report_to_results(self, report: JestReport, output: str) -> TestResults:
        """Convert JestReport to TestResults."""
        # Calculate duration from test suites
        duration_ms = 0
        for suite in report.testSuites:
            duration_ms += suite.endTime - suite.startTime

        return TestResults(
            passed=report.success and report.numFailedTests == 0,
            total=report.numTotalTests,
            failed=report.numFailedTests,
            skipped=report.numPendingTests,
            duration_ms=duration_ms,
            output=output,
            framework="jest",
        )

"""
ESLint integration for cert-code.

Provides detailed parsing of ESLint output.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from cert_code.models import LintResults


@dataclass
class EslintMessage:
    """A single ESLint message."""

    rule_id: str | None  # ruleId in JSON
    severity: int  # 1 = warning, 2 = error
    message: str
    line: int
    column: int
    end_line: int | None = None  # endLine in JSON
    end_column: int | None = None  # endColumn in JSON
    fix: dict[str, Any] | None = None


@dataclass
class EslintFileResult:
    """ESLint results for a single file."""

    file_path: str  # filePath in JSON
    messages: list[EslintMessage]
    error_count: int = 0  # errorCount in JSON
    warning_count: int = 0  # warningCount in JSON
    fixable_error_count: int = 0  # fixableErrorCount in JSON
    fixable_warning_count: int = 0  # fixableWarningCount in JSON


@dataclass
class EslintReport:
    """Complete ESLint report."""

    results: list[EslintFileResult]
    error_count: int = 0  # errorCount in JSON
    warning_count: int = 0  # warningCount in JSON
    fixable_error_count: int = 0  # fixableErrorCount in JSON
    fixable_warning_count: int = 0  # fixableWarningCount in JSON


class EslintIntegration:
    """Integration with ESLint for linting."""

    def __init__(
        self,
        paths: list[str] | None = None,
        args: list[str] | None = None,
        cwd: str | None = None,
        timeout: int = 60,
    ):
        self.paths = paths or ["."]
        self.args = args or []
        self.cwd = cwd
        self.timeout = timeout

    def run(self) -> LintResults:
        """Run ESLint and return results."""
        cmd = ["eslint", "--format=json"]
        cmd.extend(self.args)
        cmd.extend(self.paths)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
            )

            output = result.stdout + "\n" + result.stderr

            # Parse JSON output
            report = self._parse_json_output(result.stdout)
            if report:
                return self._report_to_results(report)

            # Fallback
            return self._parse_fallback(output, result.returncode)

        except subprocess.TimeoutExpired:
            return LintResults(
                passed=False,
                error_count=1,
                errors=[{"message": f"Lint timeout after {self.timeout}s"}],
                tool="eslint",
            )
        except FileNotFoundError:
            return LintResults(
                passed=True,
                tool="eslint (not found)",
            )

    def _parse_json_output(self, output: str) -> EslintReport | None:
        """Parse ESLint JSON output."""
        try:
            data = json.loads(output)

            results = []
            total_errors = 0
            total_warnings = 0
            total_fixable_errors = 0
            total_fixable_warnings = 0

            for file_result in data:
                messages = []
                for msg in file_result.get("messages", []):
                    messages.append(
                        EslintMessage(
                            rule_id=msg.get("ruleId"),
                            severity=msg.get("severity", 1),
                            message=msg.get("message", ""),
                            line=msg.get("line", 0),
                            column=msg.get("column", 0),
                            end_line=msg.get("endLine"),
                            end_column=msg.get("endColumn"),
                            fix=msg.get("fix"),
                        )
                    )

                file_errors = file_result.get("errorCount", 0)
                file_warnings = file_result.get("warningCount", 0)

                results.append(
                    EslintFileResult(
                        file_path=file_result.get("filePath", ""),
                        messages=messages,
                        error_count=file_errors,
                        warning_count=file_warnings,
                        fixable_error_count=file_result.get("fixableErrorCount", 0),
                        fixable_warning_count=file_result.get("fixableWarningCount", 0),
                    )
                )

                total_errors += file_errors
                total_warnings += file_warnings
                total_fixable_errors += file_result.get("fixableErrorCount", 0)
                total_fixable_warnings += file_result.get("fixableWarningCount", 0)

            return EslintReport(
                results=results,
                error_count=total_errors,
                warning_count=total_warnings,
                fixable_error_count=total_fixable_errors,
                fixable_warning_count=total_fixable_warnings,
            )

        except (json.JSONDecodeError, KeyError):
            return None

    def _parse_fallback(self, output: str, returncode: int) -> LintResults:
        """Fallback parser for non-JSON output."""
        error_count = output.lower().count("error")
        warning_count = output.lower().count("warning")

        return LintResults(
            passed=returncode == 0,
            error_count=error_count,
            warning_count=warning_count,
            tool="eslint",
        )

    def _report_to_results(self, report: EslintReport) -> LintResults:
        """Convert EslintReport to LintResults."""
        errors = []

        for file_result in report.results:
            for msg in file_result.messages:
                if msg.severity == 2:  # Error
                    errors.append(
                        {
                            "file": file_result.file_path,
                            "line": msg.line,
                            "column": msg.column,
                            "code": msg.rule_id,
                            "message": msg.message,
                        }
                    )

        return LintResults(
            passed=report.error_count == 0,
            error_count=report.error_count,
            warning_count=report.warning_count,
            errors=errors[:50],
            tool="eslint",
        )

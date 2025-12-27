"""
ESLint integration for cert-code.

Provides detailed parsing of ESLint output.
"""

import json
import subprocess
from dataclasses import dataclass
from typing import Optional

from cert_code.models import LintResults


@dataclass
class EslintMessage:
    """A single ESLint message."""

    ruleId: Optional[str]
    severity: int  # 1 = warning, 2 = error
    message: str
    line: int
    column: int
    endLine: Optional[int] = None
    endColumn: Optional[int] = None
    fix: Optional[dict] = None


@dataclass
class EslintFileResult:
    """ESLint results for a single file."""

    filePath: str
    messages: list[EslintMessage]
    errorCount: int = 0
    warningCount: int = 0
    fixableErrorCount: int = 0
    fixableWarningCount: int = 0


@dataclass
class EslintReport:
    """Complete ESLint report."""

    results: list[EslintFileResult]
    errorCount: int = 0
    warningCount: int = 0
    fixableErrorCount: int = 0
    fixableWarningCount: int = 0


class EslintIntegration:
    """Integration with ESLint for linting."""

    def __init__(
        self,
        paths: Optional[list[str]] = None,
        args: Optional[list[str]] = None,
        cwd: Optional[str] = None,
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

    def _parse_json_output(self, output: str) -> Optional[EslintReport]:
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
                            ruleId=msg.get("ruleId"),
                            severity=msg.get("severity", 1),
                            message=msg.get("message", ""),
                            line=msg.get("line", 0),
                            column=msg.get("column", 0),
                            endLine=msg.get("endLine"),
                            endColumn=msg.get("endColumn"),
                            fix=msg.get("fix"),
                        )
                    )

                file_errors = file_result.get("errorCount", 0)
                file_warnings = file_result.get("warningCount", 0)

                results.append(
                    EslintFileResult(
                        filePath=file_result.get("filePath", ""),
                        messages=messages,
                        errorCount=file_errors,
                        warningCount=file_warnings,
                        fixableErrorCount=file_result.get("fixableErrorCount", 0),
                        fixableWarningCount=file_result.get("fixableWarningCount", 0),
                    )
                )

                total_errors += file_errors
                total_warnings += file_warnings
                total_fixable_errors += file_result.get("fixableErrorCount", 0)
                total_fixable_warnings += file_result.get("fixableWarningCount", 0)

            return EslintReport(
                results=results,
                errorCount=total_errors,
                warningCount=total_warnings,
                fixableErrorCount=total_fixable_errors,
                fixableWarningCount=total_fixable_warnings,
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
                            "file": file_result.filePath,
                            "line": msg.line,
                            "column": msg.column,
                            "code": msg.ruleId,
                            "message": msg.message,
                        }
                    )

        return LintResults(
            passed=report.errorCount == 0,
            error_count=report.errorCount,
            warning_count=report.warningCount,
            errors=errors[:50],
            tool="eslint",
        )

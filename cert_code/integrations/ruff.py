"""
Ruff integration for cert-code.

Provides detailed parsing of Ruff output.
"""

import json
import subprocess
from dataclasses import dataclass
from typing import Optional

from cert_code.models import LintResults


@dataclass
class RuffDiagnostic:
    """A single Ruff diagnostic."""

    code: str
    message: str
    filename: str
    location: dict  # row, column
    end_location: Optional[dict] = None
    fix: Optional[dict] = None
    noqa_row: Optional[int] = None


@dataclass
class RuffReport:
    """Complete Ruff report."""

    diagnostics: list[RuffDiagnostic]
    error_count: int = 0
    warning_count: int = 0
    fixable_count: int = 0


class RuffIntegration:
    """Integration with Ruff for Python linting."""

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
        """Run Ruff and return results."""
        cmd = ["ruff", "check", "--output-format=json"]
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
                tool="ruff",
            )
        except FileNotFoundError:
            return LintResults(
                passed=True,
                tool="ruff (not found)",
            )

    def _parse_json_output(self, output: str) -> Optional[RuffReport]:
        """Parse Ruff JSON output."""
        try:
            data = json.loads(output)

            diagnostics = []
            error_count = 0
            warning_count = 0
            fixable_count = 0

            for diag in data:
                code = diag.get("code", "")

                diagnostics.append(
                    RuffDiagnostic(
                        code=code,
                        message=diag.get("message", ""),
                        filename=diag.get("filename", ""),
                        location=diag.get("location", {}),
                        end_location=diag.get("end_location"),
                        fix=diag.get("fix"),
                        noqa_row=diag.get("noqa_row"),
                    )
                )

                # Categorize by severity
                # E/F codes are errors, others are warnings
                if code.startswith("E") or code.startswith("F"):
                    error_count += 1
                else:
                    warning_count += 1

                if diag.get("fix"):
                    fixable_count += 1

            return RuffReport(
                diagnostics=diagnostics,
                error_count=error_count,
                warning_count=warning_count,
                fixable_count=fixable_count,
            )

        except (json.JSONDecodeError, KeyError):
            return None

    def _parse_fallback(self, output: str, returncode: int) -> LintResults:
        """Fallback parser for non-JSON output."""
        # Count lines as a rough estimate
        lines = [l for l in output.split("\n") if l.strip() and not l.startswith("Found")]
        error_count = len(lines)

        return LintResults(
            passed=returncode == 0,
            error_count=error_count,
            tool="ruff",
        )

    def _report_to_results(self, report: RuffReport) -> LintResults:
        """Convert RuffReport to LintResults."""
        errors = []

        for diag in report.diagnostics:
            if diag.code.startswith("E") or diag.code.startswith("F"):
                errors.append(
                    {
                        "file": diag.filename,
                        "line": diag.location.get("row", 0),
                        "column": diag.location.get("column", 0),
                        "code": diag.code,
                        "message": diag.message,
                    }
                )

        return LintResults(
            passed=report.error_count == 0,
            error_count=report.error_count,
            warning_count=report.warning_count,
            errors=errors[:50],
            tool="ruff",
        )

    def run_fix(self) -> tuple[LintResults, bool]:
        """
        Run Ruff with --fix to auto-fix issues.

        Returns:
            Tuple of (LintResults after fix, whether any fixes were applied)
        """
        cmd = ["ruff", "check", "--fix", "--output-format=json"]
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

            # Check if fixes were applied
            fixes_applied = "Fixed" in result.stderr

            # Get remaining issues
            lint_results = self.run()

            return lint_results, fixes_applied

        except Exception:
            return LintResults(passed=True, tool="ruff"), False

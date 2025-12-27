"""
mypy integration for cert-code.

Provides detailed parsing of mypy output.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from cert_code.models import TypeCheckResults


@dataclass
class MypyError:
    """A single mypy error."""
    file: str
    line: int
    column: int
    severity: str  # error, note, warning
    message: str
    code: Optional[str] = None


@dataclass
class MypyReport:
    """Complete mypy report."""
    errors: list[MypyError]
    error_count: int = 0
    warning_count: int = 0
    note_count: int = 0


class MypyIntegration:
    """Integration with mypy for type checking."""

    def __init__(
        self,
        paths: Optional[list[str]] = None,
        args: Optional[list[str]] = None,
        cwd: Optional[str] = None,
        timeout: int = 120,
    ):
        self.paths = paths or ["."]
        self.args = args or []
        self.cwd = cwd
        self.timeout = timeout

    def run(self) -> TypeCheckResults:
        """Run mypy and return results."""
        # Try JSON output first
        cmd = ["mypy", "--output=json", "--no-error-summary"]
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

            # Try JSON parsing
            report = self._parse_json_output(result.stdout)
            if report:
                return self._report_to_results(report, output)

            # Fallback to text parsing
            return self._parse_text_output(output, result.returncode)

        except subprocess.TimeoutExpired:
            return TypeCheckResults(
                passed=False,
                error_count=1,
                errors=[{"message": f"Type check timeout after {self.timeout}s"}],
                tool="mypy",
            )
        except FileNotFoundError:
            return TypeCheckResults(
                passed=True,
                tool="mypy (not found)",
            )

    def _parse_json_output(self, output: str) -> Optional[MypyReport]:
        """Parse mypy JSON output."""
        errors = []
        error_count = 0
        warning_count = 0
        note_count = 0

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
                severity = data.get("severity", "error")

                error = MypyError(
                    file=data.get("file", ""),
                    line=data.get("line", 0),
                    column=data.get("column", 0),
                    severity=severity,
                    message=data.get("message", ""),
                    code=data.get("code"),
                )
                errors.append(error)

                if severity == "error":
                    error_count += 1
                elif severity == "warning":
                    warning_count += 1
                elif severity == "note":
                    note_count += 1

            except json.JSONDecodeError:
                continue

        if not errors and not output.strip():
            return None

        return MypyReport(
            errors=errors,
            error_count=error_count,
            warning_count=warning_count,
            note_count=note_count,
        )

    def _parse_text_output(self, output: str, returncode: int) -> TypeCheckResults:
        """Parse mypy text output."""
        # Pattern: file:line: error: message
        error_pattern = re.compile(r"^(.+):(\d+): (error|warning|note): (.+)$", re.MULTILINE)

        errors = []
        error_count = 0

        for match in error_pattern.finditer(output):
            severity = match.group(3)
            if severity == "error":
                error_count += 1
                errors.append({
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "message": match.group(4),
                })

        return TypeCheckResults(
            passed=error_count == 0 and returncode == 0,
            error_count=error_count,
            errors=errors[:50],
            tool="mypy",
        )

    def _report_to_results(self, report: MypyReport, output: str) -> TypeCheckResults:
        """Convert MypyReport to TypeCheckResults."""
        errors = [
            {
                "file": e.file,
                "line": e.line,
                "column": e.column,
                "message": e.message,
                "code": e.code,
            }
            for e in report.errors
            if e.severity == "error"
        ]

        return TypeCheckResults(
            passed=report.error_count == 0,
            error_count=report.error_count,
            errors=errors[:50],
            tool="mypy",
        )

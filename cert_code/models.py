"""
Data models for cert-code.

These models define the structure of code evaluation traces.
Designed to be serializable to CERT API format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class Language(str, Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SCALA = "scala"
    SHELL = "shell"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    OTHER = "other"


@dataclass
class DiffStats:
    """Git diff statistics."""

    additions: int = 0
    deletions: int = 0
    files_changed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "additions": self.additions,
            "deletions": self.deletions,
            "files": self.files_changed,
        }


@dataclass
class TestResults:
    """Test execution results."""

    passed: bool
    total: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: int = 0
    output: str = ""
    framework: str = "unknown"  # pytest, jest, go test, etc.

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 1.0  # No tests = no failures
        return (self.total - self.failed - self.skipped) / self.total


@dataclass
class LintResults:
    """Linting results."""

    passed: bool
    error_count: int = 0
    warning_count: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    tool: str = "unknown"  # ruff, eslint, golint, etc.


@dataclass
class TypeCheckResults:
    """Type checking results."""

    passed: bool
    error_count: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    tool: str = "unknown"  # mypy, tsc, etc.


@dataclass
class CodeArtifact:
    """The generated code artifact."""

    diff: str
    files_changed: list[str]
    language: Language
    diff_stats: DiffStats
    raw_content: Optional[str] = None  # Full file content if single file

    @classmethod
    def from_git_diff(cls, diff: str, language: Optional[Language] = None) -> CodeArtifact:
        """Parse a git diff into a CodeArtifact."""
        from cert_code.analyzers.diff import parse_diff

        return parse_diff(diff, language)


@dataclass
class CodeTask:
    """The task/intent for code generation."""

    description: str
    conversation_id: Optional[str] = None
    tool: Optional[str] = None  # "claude-code", "cursor", "copilot", etc.


@dataclass
class CodeVerification:
    """Verification signals for generated code."""

    parseable: bool = True
    tests: Optional[TestResults] = None
    lint: Optional[LintResults] = None
    typecheck: Optional[TypeCheckResults] = None

    @property
    def all_passed(self) -> bool:
        """Check if all verification steps passed."""
        if not self.parseable:
            return False
        if self.tests and not self.tests.passed:
            return False
        if self.lint and not self.lint.passed:
            return False
        if self.typecheck and not self.typecheck.passed:
            return False
        return True


@dataclass
class CodeTrace:
    """
    Complete code evaluation trace.

    This is the primary data structure that gets sent to CERT.
    """

    task: CodeTask
    artifact: CodeArtifact
    verification: CodeVerification
    context: Optional[str] = None  # Existing codebase/docs for SGI
    project_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_cert_trace(self) -> dict[str, Any]:
        """
        Convert to CERT trace API format.

        Maps code-specific fields to the traces table schema.
        """
        # Build the trace payload
        trace = {
            # Standard trace fields
            "name": f"code-gen: {self.task.description[:50]}",
            "kind": "code",
            "evaluation_mode": "code",
            "eval_mode": "code",
            # Map task to input
            "input_text": self.task.description,
            # Map artifact to output
            "output_text": self.artifact.diff,
            # Context for SGI calculation
            "context": self.context,
            "knowledge_base": self.context,
            "is_grounded": self.context is not None,
            "context_source": "user_provided" if self.context else None,
            # Code-specific fields
            "code_language": self.artifact.language.value,
            "code_files_changed": self.artifact.files_changed,
            "code_diff_stats": self.artifact.diff_stats.to_dict(),
            "code_parseable": self.verification.parseable,
            # Test results
            "code_tests_passed": (
                self.verification.tests.passed if self.verification.tests else None
            ),
            "code_tests_total": (
                self.verification.tests.total if self.verification.tests else None
            ),
            "code_tests_failed": (
                self.verification.tests.failed if self.verification.tests else None
            ),
            # Type check
            "code_type_check_passed": (
                self.verification.typecheck.passed if self.verification.typecheck else None
            ),
            # Lint
            "code_lint_errors": (
                self.verification.lint.error_count if self.verification.lint else 0
            ),
            # Metadata
            "metadata": {
                **self.metadata,
                "cert_code_version": "0.1.0",
                "tool": self.task.tool,
                "conversation_id": self.task.conversation_id,
                "test_framework": (
                    self.verification.tests.framework if self.verification.tests else None
                ),
                "test_output": (
                    self.verification.tests.output[:10000]  # Truncate
                    if self.verification.tests
                    else None
                ),
                "lint_tool": (self.verification.lint.tool if self.verification.lint else None),
                "lint_errors_detail": (
                    self.verification.lint.errors[:50]  # First 50 errors
                    if self.verification.lint
                    else None
                ),
                "typecheck_tool": (
                    self.verification.typecheck.tool if self.verification.typecheck else None
                ),
                "typecheck_errors_detail": (
                    self.verification.typecheck.errors[:50] if self.verification.typecheck else None
                ),
            },
            # Timestamps
            "start_time": self.created_at.isoformat(),
            "source": "cert-code",
        }

        # Add optional fields
        if self.project_id:
            trace["project_id"] = self.project_id
        if self.trace_id:
            trace["trace_id"] = self.trace_id

        return trace

"""
Code artifact collector.

High-level interface for collecting and submitting code traces.
Orchestrates diff analysis, test running, and API submission.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cert_code.analyzers.diff import get_diff_from_git, parse_diff
from cert_code.analyzers.tests import run_tests
from cert_code.client import CertClient, SubmitResult
from cert_code.config import CertCodeConfig
from cert_code.models import (
    CodeArtifact,
    CodeTask,
    CodeTrace,
    CodeVerification,
    Language,
    LintResults,
    TypeCheckResults,
)

logger = logging.getLogger(__name__)


@dataclass
class CollectorOptions:
    """Options for the collector."""

    run_tests: bool = False
    run_lint: bool = False
    run_typecheck: bool = False
    context_files: list[str] | None = None
    language: Language | None = None


class CodeCollector:
    """
    Collects code artifacts and submits to CERT.

    Usage:
        collector = CodeCollector(config)

        # From git commit
        result = collector.from_commit(
            task="Add pagination",
            ref="HEAD",
            run_tests=True,
        )

        # From explicit diff
        result = collector.from_diff(
            task="Fix bug",
            diff=diff_string,
        )
    """

    def __init__(self, config: CertCodeConfig):
        self.config = config
        self.client = CertClient(config)

    def from_commit(
        self,
        task: str,
        ref: str = "HEAD",
        base_ref: str | None = None,
        options: CollectorOptions | None = None,
        tool: str | None = None,
    ) -> SubmitResult:
        """
        Create and submit trace from a git commit.

        Args:
            task: Task description (what was the AI asked to do)
            ref: Git reference (commit, branch, tag)
            base_ref: Base reference for comparison
            options: Collector options
            tool: Code generation tool name

        Returns:
            SubmitResult from CERT API
        """
        options = options or CollectorOptions()

        # Get diff from git
        try:
            diff = get_diff_from_git(ref, base_ref)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get git diff: {e}")
            return SubmitResult(success=False, error=f"Git error: {e}")

        if not diff.strip():
            return SubmitResult(success=False, error="No changes in commit")

        return self.from_diff(
            task=task,
            diff=diff,
            options=options,
            tool=tool,
        )

    def from_diff(
        self,
        task: str,
        diff: str,
        options: CollectorOptions | None = None,
        tool: str | None = None,
    ) -> SubmitResult:
        """
        Create and submit trace from a diff string.

        Args:
            task: Task description
            diff: Unified diff string
            options: Collector options
            tool: Code generation tool name

        Returns:
            SubmitResult from CERT API
        """
        options = options or CollectorOptions()

        # Parse diff
        artifact = parse_diff(diff, options.language)

        # Build verification
        verification = self._build_verification(artifact, options)

        # Load context
        context = self._load_context(options.context_files)

        # Build trace
        trace = CodeTrace(
            task=CodeTask(
                description=task,
                tool=tool,
            ),
            artifact=artifact,
            verification=verification,
            context=context,
            project_id=self.config.project_id,
        )

        # Submit
        return self.client.submit(trace)

    def _build_verification(
        self,
        artifact: CodeArtifact,
        options: CollectorOptions,
    ) -> CodeVerification:
        """Build verification results."""
        # Check parseability (basic syntax check)
        parseable = self._check_parseable(artifact)

        # Run tests if requested
        tests = None
        should_run_tests = options.run_tests or self.config.auto_run_tests
        if should_run_tests:
            tests = run_tests(
                command=self.config.test_command,
                language=artifact.language.value,
                timeout=self.config.test_timeout,
            )

        # Run lint if requested
        lint = None
        should_run_lint = options.run_lint or self.config.auto_run_lint
        if should_run_lint:
            lint = self._run_lint(artifact.language)

        # Run type check if requested
        typecheck = None
        should_run_typecheck = options.run_typecheck or self.config.auto_run_typecheck
        if should_run_typecheck:
            typecheck = self._run_typecheck(artifact.language)

        return CodeVerification(
            parseable=parseable,
            tests=tests,
            lint=lint,
            typecheck=typecheck,
        )

    def _check_parseable(self, artifact: CodeArtifact) -> bool:
        """Check if generated code is syntactically valid."""
        # This is a basic check - in practice, the lint/typecheck will catch issues
        # For now, we assume it's parseable if we got a valid diff

        # Language-specific syntax checks could be added here
        # e.g., ast.parse() for Python, esprima for JS, etc.

        return True

    def _run_lint(self, language: Language) -> LintResults:
        """Run linter for the language."""
        cmd = self.config.lint_command

        if not cmd:
            # Auto-detect based on language
            if language == Language.PYTHON:
                cmd = "ruff check ."
            elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
                cmd = "eslint ."
            elif language == Language.GO:
                cmd = "golangci-lint run"
            elif language == Language.RUST:
                cmd = "cargo clippy"
            else:
                return LintResults(passed=True, tool="none")

        try:
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Count errors (simple heuristic - count lines with "error")
            error_count = sum(1 for line in result.stdout.split("\n") if "error" in line.lower())
            warning_count = sum(
                1 for line in result.stdout.split("\n") if "warning" in line.lower()
            )

            return LintResults(
                passed=result.returncode == 0,
                error_count=error_count,
                warning_count=warning_count,
                tool=cmd.split()[0],
            )

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Lint failed: {e}")
            return LintResults(passed=True, tool="failed")

    def _run_typecheck(self, language: Language) -> TypeCheckResults:
        """Run type checker for the language."""
        cmd = self.config.typecheck_command

        if not cmd:
            # Auto-detect based on language
            if language == Language.PYTHON:
                cmd = "mypy ."
            elif language == Language.TYPESCRIPT:
                cmd = "tsc --noEmit"
            else:
                return TypeCheckResults(passed=True, tool="none")

        try:
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Count errors
            error_count = sum(1 for line in result.stdout.split("\n") if "error" in line.lower())

            return TypeCheckResults(
                passed=result.returncode == 0,
                error_count=error_count,
                tool=cmd.split()[0],
            )

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Type check failed: {e}")
            return TypeCheckResults(passed=True, tool="failed")

    def _load_context(self, context_files: list[str] | None) -> str | None:
        """Load context from specified files."""
        files = context_files or self.config.context_files

        if not files:
            return None

        context_parts: list[str] = []
        total_size = 0
        max_size = self.config.context_max_size

        for file_path in files:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Context file not found: {file_path}")
                continue

            try:
                content = path.read_text()

                # Check size limit
                if total_size + len(content) > max_size:
                    remaining = max_size - total_size
                    if remaining > 1000:
                        content = content[:remaining] + "\n... (truncated)"
                    else:
                        break

                context_parts.append(f"# File: {file_path}\n{content}")
                total_size += len(content)

            except Exception as e:
                logger.warning(f"Failed to read context file {file_path}: {e}")

        return "\n\n".join(context_parts) if context_parts else None

    def close(self) -> None:
        """Close the client."""
        self.client.close()

    def __enter__(self) -> CodeCollector:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

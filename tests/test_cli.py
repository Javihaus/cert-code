"""
CLI tests for cert-code.

Tests the command-line interface functionality.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cert_code.cli import hook, init, main, status, submit


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestMainGroup:
    """Tests for the main CLI group."""

    def test_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "CERT Code" in result.output
        assert "submit" in result.output
        assert "init" in result.output
        assert "status" in result.output
        assert "hook" in result.output

    def test_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_config_file(self, runner, temp_dir):
        """Test that init creates a configuration file."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(init)
            assert result.exit_code == 0
            assert "Created configuration file" in result.output
            assert Path(".cert-code.toml").exists()

    def test_init_does_not_overwrite_without_force(self, runner, temp_dir):
        """Test that init doesn't overwrite existing config without --force."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create initial config
            Path(".cert-code.toml").write_text("# existing config")

            # Try to init again
            result = runner.invoke(init)
            assert result.exit_code == 1
            assert "already exists" in result.output

    def test_init_overwrites_with_force(self, runner, temp_dir):
        """Test that init overwrites existing config with --force."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create initial config
            Path(".cert-code.toml").write_text("# existing config")

            # Init with force
            result = runner.invoke(init, ["--force"])
            assert result.exit_code == 0
            assert "Created configuration file" in result.output


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_shows_table(self, runner):
        """Test that status shows a configuration table."""
        with patch.dict(os.environ, {"CERT_CODE_API_KEY": "test-key-12345678"}):
            result = runner.invoke(status)
            assert result.exit_code == 0
            assert "Status" in result.output
            assert "API" in result.output

    def test_status_shows_api_key_partial(self, runner):
        """Test that status shows partial API key."""
        with patch.dict(os.environ, {"CERT_CODE_API_KEY": "test-key-12345678"}):
            result = runner.invoke(status)
            assert "test-key" in result.output
            # Full key should not be visible
            assert "12345678" not in result.output


class TestSubmitCommand:
    """Tests for the submit command."""

    def test_submit_requires_task(self, runner):
        """Test that submit requires --task flag."""
        result = runner.invoke(submit)
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_submit_help(self, runner):
        """Test submit --help."""
        result = runner.invoke(submit, ["--help"])
        assert result.exit_code == 0
        assert "--task" in result.output
        assert "--diff" in result.output
        assert "--dry-run" in result.output
        assert "--language" in result.output

    def test_submit_dry_run_with_diff(self, runner, temp_dir):
        """Test submit with --dry-run and provided diff."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            sample_diff = """diff --git a/test.py b/test.py
new file mode 100644
--- /dev/null
+++ b/test.py
@@ -0,0 +1,3 @@
+def hello():
+    print("Hello, World!")
+    return True
"""
            result = runner.invoke(
                submit,
                [
                    "--task",
                    "Add hello function",
                    "--diff",
                    sample_diff,
                    "--dry-run",
                ],
            )
            assert result.exit_code == 0
            assert "DRY RUN" in result.output
            assert "hello" in result.output.lower() or "Add" in result.output

    def test_submit_language_choices(self, runner):
        """Test that submit accepts valid language choices."""
        result = runner.invoke(submit, ["--help"])
        assert "python" in result.output
        assert "javascript" in result.output
        assert "typescript" in result.output


class TestHookCommand:
    """Tests for the hook command."""

    def test_hook_help(self, runner):
        """Test hook --help."""
        result = runner.invoke(hook, ["--help"])
        assert result.exit_code == 0
        assert "post-commit" in result.output
        assert "pre-push" in result.output
        assert "--uninstall" in result.output

    def test_hook_type_choices(self, runner):
        """Test that hook accepts valid type choices."""
        result = runner.invoke(hook, ["--help"])
        # Verify the hook types are documented
        assert "post-commit" in result.output
        assert "pre-push" in result.output


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def test_full_workflow_dry_run(self, runner, temp_dir):
        """Test a complete workflow in dry-run mode."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Initialize configuration
            result = runner.invoke(init)
            assert result.exit_code == 0

            # Check status
            result = runner.invoke(status)
            assert result.exit_code == 0

            # Submit with dry-run
            sample_diff = """diff --git a/main.py b/main.py
--- /dev/null
+++ b/main.py
@@ -0,0 +1 @@
+print("test")
"""
            result = runner.invoke(
                submit,
                [
                    "--task",
                    "Add main.py",
                    "--diff",
                    sample_diff,
                    "--dry-run",
                ],
            )
            assert result.exit_code == 0

    def test_commands_accessible(self, runner):
        """Test that all main commands are accessible."""
        commands = ["init", "status", "submit", "hook"]
        for cmd in commands:
            result = runner.invoke(main, [cmd, "--help"])
            assert result.exit_code == 0, f"Command {cmd} failed"

"""
Tests for the CodeCollector.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from cert_code.collector import CodeCollector, CollectorOptions
from cert_code.config import CertCodeConfig
from cert_code.models import Language


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = CertCodeConfig()
    config.api_key = "test-api-key"
    config.project_id = "test-project"
    return config


@pytest.fixture
def sample_diff():
    """Sample git diff for testing."""
    return """diff --git a/src/utils.py b/src/utils.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/src/utils.py
@@ -0,0 +1,10 @@
+def add(a: int, b: int) -> int:
+    \"\"\"Add two numbers.\"\"\"
+    return a + b
+
+
+def subtract(a: int, b: int) -> int:
+    \"\"\"Subtract two numbers.\"\"\"
+    return a - b
"""


class TestCodeCollector:
    """Tests for CodeCollector."""

    def test_from_diff_parses_correctly(self, mock_config, sample_diff):
        """Test that from_diff correctly parses a diff."""
        with patch.object(CodeCollector, '__init__', lambda x, y: None):
            collector = CodeCollector.__new__(CodeCollector)
            collector.config = mock_config
            collector.client = Mock()
            collector.client.submit = Mock(return_value=Mock(success=True, trace_id="test-123"))

            result = collector.from_diff(
                task="Add utility functions",
                diff=sample_diff,
            )

            assert result.success
            assert result.trace_id == "test-123"
            collector.client.submit.assert_called_once()

    def test_collector_options_defaults(self):
        """Test CollectorOptions default values."""
        options = CollectorOptions()

        assert options.run_tests is False
        assert options.run_lint is False
        assert options.run_typecheck is False
        assert options.context_files is None
        assert options.language is None

    def test_collector_options_with_values(self):
        """Test CollectorOptions with custom values."""
        options = CollectorOptions(
            run_tests=True,
            run_lint=True,
            run_typecheck=True,
            language=Language.PYTHON,
        )

        assert options.run_tests is True
        assert options.run_lint is True
        assert options.run_typecheck is True
        assert options.language == Language.PYTHON

    def test_from_commit_no_changes(self, mock_config):
        """Test from_commit with no changes returns error."""
        with patch.object(CodeCollector, '__init__', lambda x, y: None):
            collector = CodeCollector.__new__(CodeCollector)
            collector.config = mock_config
            collector.client = Mock()

            with patch('cert_code.collector.get_diff_from_git', return_value=""):
                result = collector.from_commit(task="Test task")

            assert not result.success
            assert "No changes" in result.error

    def test_context_loading(self, mock_config, tmp_path):
        """Test context file loading."""
        # Create a test context file
        context_file = tmp_path / "context.md"
        context_file.write_text("# Test Context\n\nThis is test context.")

        with patch.object(CodeCollector, '__init__', lambda x, y: None):
            collector = CodeCollector.__new__(CodeCollector)
            collector.config = mock_config
            collector.config.context_files = []
            collector.config.context_max_size = 100000

            context = collector._load_context([str(context_file)])

            assert context is not None
            assert "Test Context" in context

    def test_context_file_not_found(self, mock_config):
        """Test context loading with missing file."""
        with patch.object(CodeCollector, '__init__', lambda x, y: None):
            collector = CodeCollector.__new__(CodeCollector)
            collector.config = mock_config
            collector.config.context_files = []
            collector.config.context_max_size = 100000

            context = collector._load_context(["/nonexistent/file.md"])

            assert context is None

    def test_context_size_limit(self, mock_config, tmp_path):
        """Test context size limiting."""
        # Create a large context file
        context_file = tmp_path / "large_context.md"
        context_file.write_text("x" * 10000)

        with patch.object(CodeCollector, '__init__', lambda x, y: None):
            collector = CodeCollector.__new__(CodeCollector)
            collector.config = mock_config
            collector.config.context_files = []
            collector.config.context_max_size = 1000  # Small limit

            context = collector._load_context([str(context_file)])

            assert context is not None
            assert len(context) <= 1100  # Some overhead for file header


class TestVerificationBuilding:
    """Tests for verification building."""

    def test_check_parseable_returns_true(self, mock_config, sample_diff):
        """Test that _check_parseable returns True for valid diff."""
        from cert_code.analyzers.diff import parse_diff

        with patch.object(CodeCollector, '__init__', lambda x, y: None):
            collector = CodeCollector.__new__(CodeCollector)
            collector.config = mock_config

            artifact = parse_diff(sample_diff)
            assert collector._check_parseable(artifact) is True

    def test_build_verification_without_checks(self, mock_config, sample_diff):
        """Test verification building without running checks."""
        from cert_code.analyzers.diff import parse_diff

        with patch.object(CodeCollector, '__init__', lambda x, y: None):
            collector = CodeCollector.__new__(CodeCollector)
            collector.config = mock_config
            collector.config.auto_run_tests = False
            collector.config.auto_run_lint = False
            collector.config.auto_run_typecheck = False

            artifact = parse_diff(sample_diff)
            options = CollectorOptions()

            verification = collector._build_verification(artifact, options)

            assert verification.parseable is True
            assert verification.tests is None
            assert verification.lint is None
            assert verification.typecheck is None

"""
Tests for the CERT API client.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import httpx

from cert_code.client import CertClient, CertAsyncClient, CertAPIError, SubmitResult
from cert_code.config import CertCodeConfig
from cert_code.models import (
    CodeArtifact,
    CodeTask,
    CodeTrace,
    CodeVerification,
    DiffStats,
    Language,
)


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = CertCodeConfig()
    config.api_key = "test-api-key"
    config.project_id = "test-project"
    config.api_url = "https://api.test.com/v1"
    return config


@pytest.fixture
def sample_trace():
    """Create a sample CodeTrace for testing."""
    return CodeTrace(
        task=CodeTask(
            description="Add a new utility function",
            tool="claude-code",
        ),
        artifact=CodeArtifact(
            diff="diff --git a/test.py b/test.py\n+new line",
            files_changed=["test.py"],
            language=Language.PYTHON,
            diff_stats=DiffStats(additions=1, deletions=0, files_changed=1),
        ),
        verification=CodeVerification(parseable=True),
        project_id="test-project",
    )


class TestCertClient:
    """Tests for CertClient."""

    def test_init_requires_api_key(self):
        """Test that client requires API key."""
        config = CertCodeConfig()
        config.api_key = None

        with pytest.raises(ValueError, match="API key is required"):
            CertClient(config)

    def test_init_with_valid_config(self, mock_config):
        """Test client initialization with valid config."""
        with patch('httpx.Client'):
            client = CertClient(mock_config)
            assert client.config == mock_config

    def test_build_headers(self, mock_config):
        """Test header building."""
        with patch('httpx.Client'):
            client = CertClient(mock_config)
            headers = client._build_headers()

            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-api-key"
            assert headers["Content-Type"] == "application/json"
            assert "User-Agent" in headers

    def test_submit_success(self, mock_config, sample_trace):
        """Test successful trace submission."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "trace-123",
            "evaluation": {"score": 0.95},
        }

        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = CertClient(mock_config)
            result = client.submit(sample_trace)

            assert result.success is True
            assert result.trace_id == "trace-123"
            assert result.evaluation == {"score": 0.95}

    def test_submit_unauthorized(self, mock_config, sample_trace):
        """Test submission with invalid API key."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.content = b'{"error": "Invalid API key"}'
        mock_response.json.return_value = {"error": "Invalid API key"}

        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = CertClient(mock_config)
            result = client.submit(sample_trace)

            assert result.success is False
            assert "401" in result.error

    def test_submit_network_error(self, mock_config, sample_trace):
        """Test submission with network error."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.post.side_effect = httpx.RequestError("Connection failed")
            mock_client_class.return_value = mock_client

            client = CertClient(mock_config)
            result = client.submit(sample_trace)

            assert result.success is False
            assert "Request failed" in result.error

    def test_context_manager(self, mock_config):
        """Test client as context manager."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            with CertClient(mock_config) as client:
                assert client is not None

            mock_client.close.assert_called_once()


class TestSubmitResult:
    """Tests for SubmitResult dataclass."""

    def test_success_result(self):
        result = SubmitResult(
            success=True,
            trace_id="test-123",
            evaluation={"score": 0.9},
        )

        assert result.success is True
        assert result.trace_id == "test-123"
        assert result.error is None

    def test_failure_result(self):
        result = SubmitResult(
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.trace_id is None
        assert result.error == "Something went wrong"


class TestCertAPIError:
    """Tests for CertAPIError exception."""

    def test_error_message(self):
        error = CertAPIError(401, "Unauthorized")

        assert error.status_code == 401
        assert error.message == "Unauthorized"
        assert "401" in str(error)
        assert "Unauthorized" in str(error)

    def test_error_with_details(self):
        error = CertAPIError(
            400,
            "Bad Request",
            details={"field": "task", "issue": "required"},
        )

        assert error.details == {"field": "task", "issue": "required"}


class TestCodeTraceConversion:
    """Tests for CodeTrace to API format conversion."""

    def test_to_cert_trace(self, sample_trace):
        """Test conversion to CERT API format."""
        payload = sample_trace.to_cert_trace()

        assert payload["kind"] == "code"
        assert payload["eval_mode"] == "code"
        assert payload["input_text"] == "Add a new utility function"
        assert payload["code_language"] == "python"
        assert payload["code_parseable"] is True
        assert "metadata" in payload

    def test_to_cert_trace_with_tests(self):
        """Test conversion includes test results."""
        from cert_code.models import TestResults

        trace = CodeTrace(
            task=CodeTask(description="Test task"),
            artifact=CodeArtifact(
                diff="diff",
                files_changed=["test.py"],
                language=Language.PYTHON,
                diff_stats=DiffStats(),
            ),
            verification=CodeVerification(
                parseable=True,
                tests=TestResults(
                    passed=True,
                    total=10,
                    failed=0,
                    framework="pytest",
                ),
            ),
        )

        payload = trace.to_cert_trace()

        assert payload["code_tests_passed"] is True
        assert payload["code_tests_total"] == 10
        assert payload["code_tests_failed"] == 0

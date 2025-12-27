"""
cert-code: Code generation evaluation for CERT Framework.

This package provides tools for evaluating AI-generated code artifacts
using the CERT (Comprehensive Evaluation and Reasoning Traces) framework.
"""

__version__ = "0.1.0"

from cert_code.models import (
    CodeArtifact,
    CodeTask,
    CodeTrace,
    CodeVerification,
    DiffStats,
    Language,
    LintResults,
    TestResults,
    TypeCheckResults,
)
from cert_code.collector import CodeCollector, CollectorOptions
from cert_code.client import CertClient, CertAsyncClient, SubmitResult
from cert_code.config import CertCodeConfig

__all__ = [
    # Version
    "__version__",
    # Models
    "CodeArtifact",
    "CodeTask",
    "CodeTrace",
    "CodeVerification",
    "DiffStats",
    "Language",
    "LintResults",
    "TestResults",
    "TypeCheckResults",
    # Core
    "CodeCollector",
    "CollectorOptions",
    "CertClient",
    "CertAsyncClient",
    "SubmitResult",
    "CertCodeConfig",
]

"""
Configuration management for cert-code.

Supports:
- Environment variables
- Config file (.cert-code.toml)
- CLI arguments (highest priority)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


CONFIG_FILE_NAME = ".cert-code.toml"
ENV_PREFIX = "CERT_CODE_"


@dataclass
class CertCodeConfig:
    """Configuration for cert-code."""

    # CERT API settings
    api_url: str = "https://cert-framework.dev/api/v1"
    api_key: Optional[str] = None

    # Project settings
    project_id: Optional[str] = None
    project_name: Optional[str] = None

    # Default behavior
    auto_detect_language: bool = True
    auto_run_tests: bool = False
    auto_run_lint: bool = False
    auto_run_typecheck: bool = False

    # Test configuration
    test_command: Optional[str] = None  # e.g., "pytest", "npm test"
    test_timeout: int = 300  # seconds

    # Lint configuration
    lint_command: Optional[str] = None  # e.g., "ruff check", "eslint"

    # Type check configuration
    typecheck_command: Optional[str] = None  # e.g., "mypy", "tsc --noEmit"

    # Context settings
    context_files: list[str] = field(default_factory=list)  # Files to include as context
    context_max_size: int = 100000  # Max context size in chars

    # Git settings
    git_hook_enabled: bool = False
    git_hook_type: str = "post-commit"  # post-commit, pre-push

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "CertCodeConfig":
        """
        Load configuration from multiple sources.

        Priority (highest to lowest):
        1. Environment variables
        2. Config file
        3. Defaults
        """
        config_dict: dict[str, Any] = {}

        # Load from config file
        if config_path is None:
            config_path = cls._find_config_file()

        if config_path and config_path.exists():
            with open(config_path, "rb") as f:
                file_config = tomllib.load(f)
                config_dict.update(cls._flatten_config(file_config))

        # Load from environment variables
        env_config = cls._load_from_env()
        config_dict.update(env_config)

        return cls(**config_dict)

    @classmethod
    def _find_config_file(cls) -> Optional[Path]:
        """Find config file by walking up from current directory."""
        current = Path.cwd()

        while current != current.parent:
            config_file = current / CONFIG_FILE_NAME
            if config_file.exists():
                return config_file
            current = current.parent

        # Check home directory
        home_config = Path.home() / CONFIG_FILE_NAME
        if home_config.exists():
            return home_config

        return None

    @classmethod
    def _flatten_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Flatten nested config to match dataclass fields."""
        result: dict[str, Any] = {}

        # Direct mappings
        if "api" in config:
            result["api_url"] = config["api"].get("url", result.get("api_url"))
            result["api_key"] = config["api"].get("key", result.get("api_key"))

        if "project" in config:
            result["project_id"] = config["project"].get("id")
            result["project_name"] = config["project"].get("name")

        if "behavior" in config:
            behavior = config["behavior"]
            result["auto_detect_language"] = behavior.get("auto_detect_language", True)
            result["auto_run_tests"] = behavior.get("auto_run_tests", False)
            result["auto_run_lint"] = behavior.get("auto_run_lint", False)
            result["auto_run_typecheck"] = behavior.get("auto_run_typecheck", False)

        if "test" in config:
            result["test_command"] = config["test"].get("command")
            result["test_timeout"] = config["test"].get("timeout", 300)

        if "lint" in config:
            result["lint_command"] = config["lint"].get("command")

        if "typecheck" in config:
            result["typecheck_command"] = config["typecheck"].get("command")

        if "context" in config:
            result["context_files"] = config["context"].get("files", [])
            result["context_max_size"] = config["context"].get("max_size", 100000)

        if "git" in config:
            result["git_hook_enabled"] = config["git"].get("hook_enabled", False)
            result["git_hook_type"] = config["git"].get("hook_type", "post-commit")

        return result

    @classmethod
    def _load_from_env(cls) -> dict[str, Any]:
        """Load configuration from environment variables."""
        result: dict[str, Any] = {}

        mappings = {
            "API_URL": "api_url",
            "API_KEY": "api_key",
            "PROJECT_ID": "project_id",
            "PROJECT_NAME": "project_name",
            "TEST_COMMAND": "test_command",
            "TEST_TIMEOUT": ("test_timeout", int),
            "LINT_COMMAND": "lint_command",
            "TYPECHECK_COMMAND": "typecheck_command",
            "AUTO_RUN_TESTS": ("auto_run_tests", lambda x: x.lower() in ("1", "true", "yes")),
            "AUTO_RUN_LINT": ("auto_run_lint", lambda x: x.lower() in ("1", "true", "yes")),
            "AUTO_RUN_TYPECHECK": ("auto_run_typecheck", lambda x: x.lower() in ("1", "true", "yes")),
        }

        for env_suffix, mapping in mappings.items():
            env_var = f"{ENV_PREFIX}{env_suffix}"
            value = os.environ.get(env_var)

            if value is not None:
                if isinstance(mapping, tuple):
                    field_name, converter = mapping
                    result[field_name] = converter(value)
                else:
                    result[mapping] = value

        return result

    def to_toml(self) -> str:
        """Generate TOML configuration string."""
        lines = [
            "# cert-code configuration",
            "# Generated by: cert-code init",
            "",
            "[api]",
            f'url = "{self.api_url}"',
            f'# key = "your-api-key"  # Or set CERT_CODE_API_KEY env var',
            "",
            "[project]",
            f'# id = "{self.project_id or "your-project-id"}"',
            f'# name = "{self.project_name or "my-project"}"',
            "",
            "[behavior]",
            f"auto_detect_language = {str(self.auto_detect_language).lower()}",
            f"auto_run_tests = {str(self.auto_run_tests).lower()}",
            f"auto_run_lint = {str(self.auto_run_lint).lower()}",
            f"auto_run_typecheck = {str(self.auto_run_typecheck).lower()}",
            "",
            "[test]",
            '# command = "pytest"  # or "npm test", "go test ./...", etc.',
            f"timeout = {self.test_timeout}",
            "",
            "[lint]",
            '# command = "ruff check"  # or "eslint", etc.',
            "",
            "[typecheck]",
            '# command = "mypy ."  # or "tsc --noEmit", etc.',
            "",
            "[context]",
            "# files = [\"README.md\", \"docs/api.md\"]  # Files to include as context for SGI",
            f"max_size = {self.context_max_size}",
            "",
            "[git]",
            f"hook_enabled = {str(self.git_hook_enabled).lower()}",
            f'hook_type = "{self.git_hook_type}"',
        ]
        return "\n".join(lines)

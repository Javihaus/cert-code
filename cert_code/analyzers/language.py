"""
Language detection utilities.

Provides comprehensive language detection from:
- File extensions
- File content analysis
- Project structure
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from cert_code.models import Language

# Shebang patterns for language detection
SHEBANG_PATTERNS: dict[str, Language] = {
    r"python": Language.PYTHON,
    r"node": Language.JAVASCRIPT,
    r"ruby": Language.RUBY,
    r"perl": Language.OTHER,
    r"bash": Language.SHELL,
    r"sh": Language.SHELL,
    r"zsh": Language.SHELL,
}

# File name patterns (without extension)
FILENAME_PATTERNS: dict[str, Language] = {
    "Makefile": Language.SHELL,
    "Dockerfile": Language.SHELL,
    "Jenkinsfile": Language.OTHER,
    "Rakefile": Language.RUBY,
    "Gemfile": Language.RUBY,
    "Podfile": Language.RUBY,
    "Vagrantfile": Language.RUBY,
}

# Project indicator files
PROJECT_INDICATORS: dict[str, Language] = {
    "pyproject.toml": Language.PYTHON,
    "setup.py": Language.PYTHON,
    "requirements.txt": Language.PYTHON,
    "Pipfile": Language.PYTHON,
    "package.json": Language.JAVASCRIPT,
    "tsconfig.json": Language.TYPESCRIPT,
    "go.mod": Language.GO,
    "Cargo.toml": Language.RUST,
    "pom.xml": Language.JAVA,
    "build.gradle": Language.JAVA,
    "Gemfile": Language.RUBY,
    "composer.json": Language.PHP,
    "Package.swift": Language.SWIFT,
    "build.sbt": Language.SCALA,
}


def detect_from_shebang(content: str) -> Optional[Language]:
    """Detect language from shebang line."""
    if not content.startswith("#!"):
        return None

    first_line = content.split("\n", 1)[0]

    for pattern, language in SHEBANG_PATTERNS.items():
        if re.search(pattern, first_line, re.IGNORECASE):
            return language

    return None


def detect_from_filename(filename: str) -> Optional[Language]:
    """Detect language from filename (without extension)."""
    basename = os.path.basename(filename)
    name_without_ext = basename.rsplit(".", 1)[0] if "." in basename else basename

    return FILENAME_PATTERNS.get(basename) or FILENAME_PATTERNS.get(name_without_ext)


def detect_project_language(directory: str = ".") -> Optional[Language]:
    """
    Detect primary language from project structure.

    Looks for project indicator files like package.json, pyproject.toml, etc.
    """
    path = Path(directory)

    # Check for indicator files
    for indicator, language in PROJECT_INDICATORS.items():
        if (path / indicator).exists():
            return language

    # Count files by extension
    from cert_code.analyzers.diff import EXTENSION_LANGUAGE_MAP

    language_counts: dict[Language, int] = {}

    for ext in EXTENSION_LANGUAGE_MAP:
        count = len(list(path.rglob(f"*{ext}")))
        if count > 0:
            lang = EXTENSION_LANGUAGE_MAP[ext]
            language_counts[lang] = language_counts.get(lang, 0) + count

    if language_counts:
        return max(language_counts, key=language_counts.get)  # type: ignore

    return None


def get_language_info(language: Language) -> dict:
    """
    Get information about a language.

    Returns dict with:
    - name: Human-readable name
    - extensions: Common file extensions
    - test_command: Default test command
    - lint_command: Default lint command
    - typecheck_command: Default type check command
    """
    info: dict[Language, dict] = {
        Language.PYTHON: {
            "name": "Python",
            "extensions": [".py", ".pyi"],
            "test_command": "pytest",
            "lint_command": "ruff check .",
            "typecheck_command": "mypy .",
        },
        Language.JAVASCRIPT: {
            "name": "JavaScript",
            "extensions": [".js", ".mjs", ".cjs", ".jsx"],
            "test_command": "npm test",
            "lint_command": "eslint .",
            "typecheck_command": None,
        },
        Language.TYPESCRIPT: {
            "name": "TypeScript",
            "extensions": [".ts", ".tsx"],
            "test_command": "npm test",
            "lint_command": "eslint .",
            "typecheck_command": "tsc --noEmit",
        },
        Language.GO: {
            "name": "Go",
            "extensions": [".go"],
            "test_command": "go test ./...",
            "lint_command": "golangci-lint run",
            "typecheck_command": "go vet ./...",
        },
        Language.RUST: {
            "name": "Rust",
            "extensions": [".rs"],
            "test_command": "cargo test",
            "lint_command": "cargo clippy",
            "typecheck_command": "cargo check",
        },
        Language.JAVA: {
            "name": "Java",
            "extensions": [".java"],
            "test_command": "mvn test",
            "lint_command": "checkstyle",
            "typecheck_command": None,
        },
        Language.RUBY: {
            "name": "Ruby",
            "extensions": [".rb"],
            "test_command": "rspec",
            "lint_command": "rubocop",
            "typecheck_command": "sorbet",
        },
        Language.PHP: {
            "name": "PHP",
            "extensions": [".php"],
            "test_command": "phpunit",
            "lint_command": "phpcs",
            "typecheck_command": "phpstan",
        },
    }

    return info.get(
        language,
        {
            "name": language.value.title(),
            "extensions": [],
            "test_command": None,
            "lint_command": None,
            "typecheck_command": None,
        },
    )

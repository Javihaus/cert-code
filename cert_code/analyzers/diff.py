"""
Git diff parsing and analysis.

Extracts structured information from git diffs:
- Files changed
- Additions/deletions
- Language detection
- Content extraction
"""

import re
from dataclasses import dataclass
from typing import Optional

from cert_code.models import CodeArtifact, DiffStats, Language


# File extension to language mapping
EXTENSION_LANGUAGE_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".pyi": Language.PYTHON,
    ".js": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".java": Language.JAVA,
    ".c": Language.C,
    ".h": Language.C,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".cxx": Language.CPP,
    ".hpp": Language.CPP,
    ".cs": Language.CSHARP,
    ".rb": Language.RUBY,
    ".php": Language.PHP,
    ".swift": Language.SWIFT,
    ".kt": Language.KOTLIN,
    ".kts": Language.KOTLIN,
    ".scala": Language.SCALA,
    ".sh": Language.SHELL,
    ".bash": Language.SHELL,
    ".zsh": Language.SHELL,
    ".sql": Language.SQL,
    ".html": Language.HTML,
    ".htm": Language.HTML,
    ".css": Language.CSS,
    ".scss": Language.CSS,
    ".sass": Language.CSS,
    ".less": Language.CSS,
}

# Patterns for parsing unified diff format
DIFF_FILE_PATTERN = re.compile(r"^diff --git a/(.+) b/(.+)$", re.MULTILINE)
DIFF_HUNK_PATTERN = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)
ADDITION_PATTERN = re.compile(r"^\+(?!\+\+)", re.MULTILINE)
DELETION_PATTERN = re.compile(r"^-(?!--)", re.MULTILINE)


@dataclass
class DiffFile:
    """A single file within a diff."""
    path: str
    old_path: Optional[str]
    additions: int
    deletions: int
    content: str
    language: Language


def detect_language(file_path: str) -> Language:
    """Detect programming language from file path."""
    # Extract extension
    if "." not in file_path:
        return Language.OTHER

    ext = "." + file_path.rsplit(".", 1)[-1].lower()
    return EXTENSION_LANGUAGE_MAP.get(ext, Language.OTHER)


def detect_primary_language(files: list[str]) -> Language:
    """
    Detect primary language from a list of files.

    Uses frequency analysis, prioritizing code files over config/docs.
    """
    if not files:
        return Language.OTHER

    # Count language occurrences
    language_counts: dict[Language, int] = {}

    # Priority weights - code files matter more than configs
    priority_extensions = {
        ".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp",
        ".cs", ".rb", ".php", ".swift", ".kt", ".scala"
    }

    for file_path in files:
        lang = detect_language(file_path)
        if lang == Language.OTHER:
            continue

        # Weight by priority
        ext = "." + file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        weight = 2 if ext in priority_extensions else 1

        language_counts[lang] = language_counts.get(lang, 0) + weight

    if not language_counts:
        return Language.OTHER

    # Return most common
    return max(language_counts, key=language_counts.get)  # type: ignore


def parse_diff(diff: str, language: Optional[Language] = None) -> CodeArtifact:
    """
    Parse a unified diff into a CodeArtifact.

    Args:
        diff: Unified diff string (from git diff, git show, etc.)
        language: Override language detection

    Returns:
        CodeArtifact with parsed information
    """
    files_changed: list[str] = []
    total_additions = 0
    total_deletions = 0

    # Extract file paths
    for match in DIFF_FILE_PATTERN.finditer(diff):
        new_path = match.group(2)
        if new_path not in files_changed:
            files_changed.append(new_path)

    # Count additions and deletions
    # Simple approach: count lines starting with + or - (excluding headers)
    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            total_additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            total_deletions += 1

    # Detect or use provided language
    detected_language = language or detect_primary_language(files_changed)

    diff_stats = DiffStats(
        additions=total_additions,
        deletions=total_deletions,
        files_changed=len(files_changed),
    )

    return CodeArtifact(
        diff=diff,
        files_changed=files_changed,
        language=detected_language,
        diff_stats=diff_stats,
    )


def extract_added_content(diff: str) -> str:
    """
    Extract only the added lines from a diff.

    Useful for focused analysis of what was generated.
    """
    added_lines: list[str] = []

    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            # Remove the leading +
            added_lines.append(line[1:])

    return "\n".join(added_lines)


def get_diff_from_git(
    ref: str = "HEAD",
    base_ref: Optional[str] = None,
    paths: Optional[list[str]] = None,
) -> str:
    """
    Get diff from git repository.

    Args:
        ref: Git reference (commit, branch, tag)
        base_ref: Base reference for comparison (if None, shows ref's changes)
        paths: Specific paths to include

    Returns:
        Unified diff string
    """
    import subprocess

    cmd = ["git"]

    if base_ref:
        # Diff between two refs
        cmd.extend(["diff", base_ref, ref])
    else:
        # Show changes in a single commit
        cmd.extend(["show", "--format=", ref])

    if paths:
        cmd.append("--")
        cmd.extend(paths)

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout

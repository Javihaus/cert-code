"""
Git utilities for hooks.

Provides helpers for extracting information from git commits.
"""

import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class CommitInfo:
    """Information about a git commit."""
    sha: str
    message: str
    author: str
    author_email: str
    timestamp: str


def get_commit_info(ref: str = "HEAD") -> Optional[CommitInfo]:
    """
    Get information about a commit.

    Args:
        ref: Git reference (commit SHA, branch, tag, HEAD)

    Returns:
        CommitInfo or None if not found
    """
    try:
        # Get commit info in a single call
        result = subprocess.run(
            [
                "git", "log", "-1",
                "--format=%H%n%s%n%an%n%ae%n%aI",
                ref
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        lines = result.stdout.strip().split("\n")
        if len(lines) >= 5:
            return CommitInfo(
                sha=lines[0],
                message=lines[1],
                author=lines[2],
                author_email=lines[3],
                timestamp=lines[4],
            )
    except subprocess.CalledProcessError:
        pass

    return None


def get_staged_diff() -> str:
    """
    Get the diff of staged changes.

    Returns:
        Unified diff string of staged changes
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""


def get_commit_diff(ref: str = "HEAD") -> str:
    """
    Get the diff introduced by a commit.

    Args:
        ref: Git reference

    Returns:
        Unified diff string
    """
    try:
        result = subprocess.run(
            ["git", "show", "--format=", ref],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""


def get_branch_name() -> Optional[str]:
    """Get the current branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def is_git_repo() -> bool:
    """Check if current directory is in a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_repo_root() -> Optional[str]:
    """Get the root directory of the git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

"""
Git hooks for cert-code.

Provides utilities for:
- Installing git hooks
- Running cert-code on commits
"""

from cert_code.hooks.install import install_hook, uninstall_hook, get_git_hooks_dir
from cert_code.hooks.git import get_commit_info, get_staged_diff, get_commit_diff

__all__ = [
    "install_hook",
    "uninstall_hook",
    "get_git_hooks_dir",
    "get_commit_info",
    "get_staged_diff",
    "get_commit_diff",
]

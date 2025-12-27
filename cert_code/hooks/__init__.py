"""
Git hooks for cert-code.

Provides utilities for:
- Installing git hooks
- Running cert-code on commits
"""

from cert_code.hooks.git import get_commit_diff, get_commit_info, get_staged_diff
from cert_code.hooks.install import get_git_hooks_dir, install_hook, uninstall_hook

__all__ = [
    "install_hook",
    "uninstall_hook",
    "get_git_hooks_dir",
    "get_commit_info",
    "get_staged_diff",
    "get_commit_diff",
]

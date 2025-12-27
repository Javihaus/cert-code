"""
Git hook installation utilities.
"""

import os
import stat
from pathlib import Path
from typing import Optional


HOOK_TEMPLATE = '''#!/bin/bash
# CERT Code - Automatic code evaluation hook
# Installed by: cert-code hook install

# Skip if CERT_CODE_SKIP is set
if [ "$CERT_CODE_SKIP" = "1" ]; then
    exit 0
fi

# Get task description from environment or commit message
if [ -z "$CERT_CODE_TASK" ]; then
    CERT_CODE_TASK=$(git log -1 --pretty=%B)
fi

# Run cert-code submit
cert-code submit \\
    --task "$CERT_CODE_TASK" \\
    --ref HEAD \\
    {extra_args}

# Don't fail the commit/push if submission fails
exit 0
'''


def get_git_hooks_dir() -> Optional[Path]:
    """Find the .git/hooks directory."""
    current = Path.cwd()

    while current != current.parent:
        git_dir = current / ".git"
        if git_dir.is_dir():
            hooks_dir = git_dir / "hooks"
            hooks_dir.mkdir(exist_ok=True)
            return hooks_dir
        current = current.parent

    return None


def install_hook(hook_type: str = "post-commit") -> bool:
    """
    Install a git hook.

    Args:
        hook_type: Type of hook (post-commit, pre-push)

    Returns:
        True if successful
    """
    hooks_dir = get_git_hooks_dir()
    if not hooks_dir:
        return False

    hook_path = hooks_dir / hook_type

    # Build extra args based on hook type
    extra_args = ""
    if hook_type == "pre-push":
        extra_args = "--run-tests"

    # Generate hook content
    hook_content = HOOK_TEMPLATE.format(extra_args=extra_args)

    # Write hook
    hook_path.write_text(hook_content)

    # Make executable
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return True


def uninstall_hook(hook_type: str = "post-commit") -> bool:
    """
    Remove a git hook.

    Args:
        hook_type: Type of hook to remove

    Returns:
        True if hook was removed
    """
    hooks_dir = get_git_hooks_dir()
    if not hooks_dir:
        return False

    hook_path = hooks_dir / hook_type

    if not hook_path.exists():
        return False

    # Check if it's our hook
    content = hook_path.read_text()
    if "CERT Code" not in content:
        return False

    hook_path.unlink()
    return True

"""Version and git commit utilities for debugging.

Provides git commit hash for error messages and logs to enable
precise version identification during debugging.
"""
import subprocess
from typing import Optional


def get_git_commit_hash(short: bool = True) -> str:
    """Get current git commit hash.

    Args:
        short: Return short hash (7 chars) if True, full hash if False

    Returns:
        Git commit hash or 'unknown' if not in git repo
    """
    try:
        cmd = ['git', 'rev-parse', '--short' if short else '', 'HEAD']
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=1
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return 'unknown'


def get_version_string() -> str:
    """Get version string for logging and error messages.

    Returns:
        String like "git:aa5f6bd" or "git:unknown"
    """
    commit = get_git_commit_hash(short=True)
    return f"git:{commit}"


def format_error_with_version(error_message: str) -> str:
    """Format error message with git commit hash for debugging.

    Args:
        error_message: The error message to format

    Returns:
        Error message with version appended

    Example:
        >>> format_error_with_version("Model is infeasible")
        "Model is infeasible [git:aa5f6bd]"
    """
    version = get_version_string()
    return f"{error_message} [{version}]"


# Module-level version (computed once at import)
VERSION_STRING = get_version_string()
GIT_COMMIT = get_git_commit_hash(short=True)
GIT_COMMIT_FULL = get_git_commit_hash(short=False)

"""Read-only git operations for /config directory.

SAFETY: Only git log, diff, rev-parse, and rev-list are allowed.
Never use shell=True. Never run write operations.
"""

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ALLOWED_GIT_COMMANDS = {"log", "diff", "diff-tree", "rev-parse", "rev-list", "show"}
GIT_TIMEOUT = 30


class GitError(Exception):
    """Raised when a git operation fails."""


@dataclass
class Changeset:
    changeset: str
    head_commit: str
    commit_count: int
    is_truncated: bool


def _run_git(args: list[str], cwd: str) -> str:
    """Run a git command safely. Only allowed read-only subcommands."""
    if not args:
        raise GitError("Empty git command")

    subcommand = args[0]
    if subcommand not in ALLOWED_GIT_COMMANDS:
        raise GitError(f"Git subcommand '{subcommand}' is not allowed")

    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=GIT_TIMEOUT,
        )
        if result.returncode != 0:
            raise GitError(f"git {subcommand} failed: {result.stderr.strip()}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise GitError(f"git {subcommand} timed out after {GIT_TIMEOUT}s")
    except FileNotFoundError:
        raise GitError("git is not installed")


def _check_is_git_repo(config_path: str):
    """Verify config_path is inside a git work tree."""
    output = _run_git(["rev-parse", "--is-inside-work-tree"], config_path)
    if output.strip() != "true":
        raise GitError("Git is not initialized in /config")


def _get_head_commit(config_path: str) -> str:
    return _run_git(["rev-parse", "HEAD"], config_path).strip()


def _commit_exists(commit: str, config_path: str) -> bool:
    """Check if a commit exists in history."""
    try:
        _run_git(["rev-list", "--count", commit, "--"], config_path)
        return True
    except GitError:
        return False


def _build_pathspec(excluded_paths: list[str]) -> list[str]:
    """Build git pathspec exclusions."""
    specs = []
    for path in excluded_paths:
        specs.append(f":!{path}")
    return specs


@dataclass
class CommitInfo:
    hash: str
    date: str
    message: str


def get_pending_commits(
    config_path: str,
    last_known_commit: str | None,
    excluded_paths: list[str],
) -> list[CommitInfo]:
    """Get list of commits since last run. Returns empty list if no repo or no changes."""
    try:
        _check_is_git_repo(config_path)
    except GitError:
        return []

    try:
        head = _get_head_commit(config_path)
    except GitError:
        return []

    pathspec = _build_pathspec(excluded_paths)

    if last_known_commit and _commit_exists(last_known_commit, config_path):
        if last_known_commit == head:
            return []
        range_arg = f"{last_known_commit}..{head}"
    else:
        range_arg = None

    try:
        if range_arg:
            log_output = _run_git(
                ["log", "--format=%H|%ai|%s", range_arg, "--no-color"]
                + (["--"] + pathspec if pathspec else []),
                config_path,
            ).strip()
        else:
            log_output = _run_git(
                ["log", "--format=%H|%ai|%s", "--no-color"]
                + (["--"] + pathspec if pathspec else []),
                config_path,
            ).strip()
    except GitError:
        return []

    if not log_output:
        return []

    commits = []
    for line in log_output.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append(CommitInfo(hash=parts[0].strip(), date=parts[1].strip(), message=parts[2].strip()))
    return commits


def get_changeset(
    config_path: str,
    last_known_commit: str | None,
    excluded_paths: list[str],
    max_diff_chars: int,
) -> Changeset | None:
    """Get changeset from git history.

    Returns None if no changes found.
    """
    _check_is_git_repo(config_path)
    head = _get_head_commit(config_path)

    pathspec = _build_pathspec(excluded_paths)

    # Determine diff range
    is_full_history = False
    if last_known_commit and _commit_exists(last_known_commit, config_path):
        if last_known_commit == head:
            logger.info("No new commits since last run")
            return None
        base = last_known_commit
    else:
        if last_known_commit:
            logger.warning(
                "Last known commit %s not found in history, diffing full history",
                last_known_commit,
            )
        is_full_history = True

    # Get commit info
    if is_full_history:
        commit_log = _run_git(
            ["log", "--format=%H | %ai | %s", "--no-color"] + (["--"] + pathspec if pathspec else []),
            config_path,
        ).strip()
    else:
        commit_log = _run_git(
            ["log", "--format=%H | %ai | %s", f"{base}..{head}", "--no-color"] + (["--"] + pathspec if pathspec else []),
            config_path,
        ).strip()

    commit_count = len(commit_log.splitlines()) if commit_log else 1

    # Get diffs — use two-arg form (git diff A B)
    if is_full_history:
        # No base commit — show all tracked content via diff-tree on root
        diff_stat = _run_git(
            ["diff-tree", "--stat", "--no-color", "--root", "-r", head] + (["--"] + pathspec if pathspec else []),
            config_path,
        ).strip()
        full_diff = _run_git(
            ["diff-tree", "--no-color", "--root", "-r", "-p", head] + (["--"] + pathspec if pathspec else []),
            config_path,
        ).strip()
    else:
        diff_stat = _run_git(
            ["diff", "--stat", "--no-color", base, head] + (["--"] + pathspec if pathspec else []),
            config_path,
        ).strip()
        full_diff = _run_git(
            ["diff", "--no-color", base, head] + (["--"] + pathspec if pathspec else []),
            config_path,
        ).strip()

    # Build changeset
    is_truncated = False
    if len(full_diff) > max_diff_chars:
        full_diff = full_diff[:max_diff_chars]
        full_diff += "\n\n[DIFF TRUNCATED — exceeded maximum size]"
        is_truncated = True
        logger.warning("Diff truncated to %d characters", max_diff_chars)

    changeset = f"""=== COMMIT INFO ===
{commit_log or '(no commit messages)'}

=== FILES CHANGED ===
{diff_stat or '(no file stats)'}

=== FULL DIFF ===
{full_diff or '(empty diff)'}"""

    if not full_diff or full_diff == "(empty diff)":
        logger.info("Empty diff, no changes to report")
        return None

    return Changeset(
        changeset=changeset,
        head_commit=head,
        commit_count=commit_count,
        is_truncated=is_truncated,
    )

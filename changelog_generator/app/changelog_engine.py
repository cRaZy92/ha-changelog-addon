"""Orchestrator: ties git reader -> OpenAI -> sensor updater."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from . import git_reader, openai_client, sensor_updater, state
from .config_manager import Config

logger = logging.getLogger(__name__)

CONFIG_PATH = "/config"


@dataclass
class GenerationResult:
    success: bool
    changelog: str
    error: str | None
    metadata: dict | None


def run_changelog_generation(config: Config) -> GenerationResult:
    """Main orchestration: git diff -> AI -> sensor -> state."""

    # 1. Check cooldown
    current_state = state.load_state()
    elapsed = state.seconds_since_last_run(current_state)
    if elapsed is not None and elapsed < config.cooldown_seconds:
        remaining = int(config.cooldown_seconds - elapsed)
        return GenerationResult(
            success=False,
            changelog="",
            error=f"Please wait {remaining} seconds before generating again.",
            metadata=None,
        )

    # 2. Get changeset from git
    try:
        changeset_result = git_reader.get_changeset(
            config_path=CONFIG_PATH,
            last_known_commit=current_state.get("last_run_commit"),
            excluded_paths=config.excluded_paths,
            max_diff_chars=config.max_diff_chars,
        )
    except git_reader.GitError as e:
        return GenerationResult(
            success=False,
            changelog="",
            error=str(e),
            metadata=None,
        )

    # 3. Check for changes
    if changeset_result is None:
        return GenerationResult(
            success=False,
            changelog="",
            error="No new changes since last run.",
            metadata=None,
        )

    # 4. Send to OpenAI
    ai_result = openai_client.generate_changelog(
        system_prompt=config.system_prompt,
        changeset=changeset_result.changeset,
        api_key=config.openai_api_key,
        model=config.openai_model,
    )

    if not ai_result.success:
        return GenerationResult(
            success=False,
            changelog="",
            error=f"OpenAI error: {ai_result.error}",
            metadata=None,
        )

    # 5. Build metadata
    generated_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "commit_count": changeset_result.commit_count,
        "head_commit": changeset_result.head_commit,
        "generated_at": generated_at,
        "model_used": config.openai_model,
        "tokens_used": ai_result.tokens_used,
        "is_truncated": changeset_result.is_truncated,
    }

    # 6. Update HA sensor (non-fatal if it fails)
    sensor_ok = sensor_updater.update_sensor(ai_result.changelog, metadata)
    if not sensor_ok:
        logger.warning("Sensor update failed, but changelog was generated successfully")

    # 7. Save state
    try:
        state.update_state_after_run(
            head_commit=changeset_result.head_commit,
            changelog=ai_result.changelog,
            metadata=metadata,
            history_count=config.history_count,
        )
    except Exception as e:
        logger.error("Failed to save state: %s", e)
        # Still return success — changelog was generated

    return GenerationResult(
        success=True,
        changelog=ai_result.changelog,
        error=None,
        metadata=metadata,
    )

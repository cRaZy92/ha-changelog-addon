"""Flask web server for ingress UI and API endpoints."""

import logging
import os
import sys

from flask import Flask, jsonify, render_template, request

from . import git_reader, openai_client, state
from .changelog_engine import CONFIG_PATH, run_changelog_generation, run_changelog_generation_selected
from .config_manager import load_config, mask_api_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)


@app.route("/")
def index():
    """Render main UI page."""
    ingress_path = request.headers.get("X-Ingress-Path", "")
    return render_template("index.html", ingress_path=ingress_path)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Trigger changelog generation."""
    try:
        config = load_config()
        if not config.openai_api_key:
            return jsonify({"success": False, "error": "OpenAI API key is not configured. Set it in addon options."}), 400

        # Allow model override and commit selection from request body
        body = request.get_json(silent=True) or {}
        if body.get("model"):
            config.openai_model = body["model"]

        selected_commits = body.get("selected_commits")

        logger.info("Changelog generation triggered (model: %s, selected: %s)",
                     config.openai_model, len(selected_commits) if selected_commits else "all")

        if selected_commits:
            result = run_changelog_generation_selected(config, selected_commits)
        else:
            result = run_changelog_generation(config)

        if result.success:
            return jsonify({
                "success": True,
                "changelog": result.changelog,
                "metadata": result.metadata,
            })
        else:
            return jsonify({
                "success": False,
                "error": result.error,
            })
    except Exception as e:
        logger.exception("Unexpected error during generation")
        return jsonify({"success": False, "error": f"Unexpected error: {e}"}), 500


@app.route("/api/status")
def api_status():
    """Get current status: last run info, cooldown state."""
    try:
        config = load_config()
        current_state = state.load_state()
        elapsed = state.seconds_since_last_run(current_state)

        cooldown_remaining = 0
        if elapsed is not None and elapsed < config.cooldown_seconds:
            cooldown_remaining = int(config.cooldown_seconds - elapsed)

        has_api_key = bool(config.openai_api_key)

        return jsonify({
            "last_run_commit": current_state.get("last_run_commit"),
            "last_run_time": current_state.get("last_run_time"),
            "cooldown_remaining": cooldown_remaining,
            "has_api_key": has_api_key,
            "model": config.openai_model,
            "system_prompt_tokens": git_reader.estimate_tokens(config.system_prompt),
            "max_diff_tokens": git_reader.estimate_tokens("x" * config.max_diff_chars),
        })
    except Exception as e:
        logger.exception("Error getting status")
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings")
def api_settings():
    """Get current settings (read-only). Settings are managed via HA addon configuration."""
    try:
        config = load_config()
        return jsonify({
            "openai_api_key_masked": mask_api_key(config.openai_api_key),
            "has_api_key": bool(config.openai_api_key),
            "openai_model": config.openai_model,
            "max_diff_chars": config.max_diff_chars,
            "excluded_paths": config.excluded_paths,
            "cooldown_seconds": config.cooldown_seconds,
            "history_count": config.history_count,
        })
    except Exception as e:
        logger.exception("Error getting settings")
        return jsonify({"error": str(e)}), 500


@app.route("/api/pending-commits")
def api_pending_commits():
    """Get commits that will be processed in next changelog generation."""
    try:
        config = load_config()
        current_state = state.load_state()
        commits = git_reader.get_pending_commits(
            config_path=CONFIG_PATH,
            last_known_commit=current_state.get("last_run_commit"),
            excluded_paths=config.excluded_paths,
        )
        return jsonify({
            "commits": [
                {"hash": c.hash, "date": c.date, "message": c.message}
                for c in commits
            ],
            "last_run_commit": current_state.get("last_run_commit"),
        })
    except Exception as e:
        logger.exception("Error getting pending commits")
        return jsonify({"error": str(e)}), 500


@app.route("/api/commit-diff/<commit_hash>")
def api_commit_diff(commit_hash):
    """Get diff and token estimate for a single commit."""
    try:
        config = load_config()
        diff = git_reader.get_commit_diff(
            config_path=CONFIG_PATH,
            commit_hash=commit_hash,
            excluded_paths=config.excluded_paths,
        )
        tokens = git_reader.estimate_tokens(diff)
        return jsonify({"diff": diff, "tokens": tokens})
    except git_reader.GitError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Error getting commit diff")
        return jsonify({"error": str(e)}), 500


@app.route("/api/models")
def api_models():
    """Fetch available chat models from OpenAI."""
    try:
        config = load_config()
        if not config.openai_api_key:
            return jsonify({"models": [], "error": "API key not configured"}), 400
        models = openai_client.list_models(config.openai_api_key)
        return jsonify({"models": models, "current": config.openai_model})
    except Exception as e:
        logger.exception("Error fetching models")
        return jsonify({"models": [], "error": str(e)}), 500


@app.route("/api/history")
def api_history():
    """Get past changelogs."""
    try:
        current_state = state.load_state()
        return jsonify({"history": current_state.get("history", [])})
    except Exception as e:
        logger.exception("Error getting history")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("INGRESS_PORT", 8099))
    logger.info("Starting Changelog Generator on port %d", port)
    app.run(host="0.0.0.0", port=port)

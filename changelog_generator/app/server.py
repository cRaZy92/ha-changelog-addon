"""Flask web server for ingress UI and API endpoints."""

import logging
import os
import sys

from flask import Flask, jsonify, render_template, request

from . import git_reader, state
from .changelog_engine import CONFIG_PATH, run_changelog_generation
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

        logger.info("Changelog generation triggered (model: %s)", config.openai_model)
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

"""Push changelog to Home Assistant sensor via Supervisor API."""

import logging
import os

import requests

logger = logging.getLogger(__name__)

SUPERVISOR_API = "http://supervisor/core/api"
SENSOR_ENTITY = "sensor.ha_changelog"


def update_sensor(changelog: str, metadata: dict) -> bool:
    """Create/update HA sensor with changelog content.

    Returns True on success, False on failure.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        logger.error("SUPERVISOR_TOKEN not available, cannot update sensor")
        return False

    url = f"{SUPERVISOR_API}/states/{SENSOR_ENTITY}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Sensor state limited to 255 chars — full changelog goes in attributes
    state = f"Updated {metadata['generated_at']}"
    if len(state) > 255:
        state = state[:255]

    payload = {
        "state": state,
        "attributes": {
            "friendly_name": "Config Changelog",
            "icon": "mdi:file-document-edit",
            "changelog": changelog,
            "commit_count": metadata["commit_count"],
            "head_commit": metadata["head_commit"],
            "generated_at": metadata["generated_at"],
            "model_used": metadata["model_used"],
            "tokens_used": metadata["tokens_used"],
        },
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            logger.info("Sensor %s updated successfully", SENSOR_ENTITY)
            return True
        else:
            logger.error("Failed to update sensor: %d %s", resp.status_code, resp.text[:200])
            return False
    except requests.RequestException as e:
        logger.error("Failed to reach HA API: %s", e)
        return False

import logging

from config import (
    get_slack_enabled,
    get_slack_snapshot_channel,
    get_slack_token,
)

_log = logging.getLogger("ngs_tracker.notifier")

_SLACK_API = "https://slack.com/api/chat.postMessage"


def _post(channel: str, text: str, blocks: list | None = None) -> tuple[bool, str]:
    """POST a message to the Slack API. Returns (success, error_message)."""
    try:
        import requests
    except ImportError:
        return False, "'requests' is not installed."

    token = get_slack_token()
    if not token:
        return False, "No Slack bot token configured."

    payload: dict = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks

    try:
        resp = requests.post(
            _SLACK_API,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok"):
            err = data.get("error", "unknown_error")
            _log.error("Slack API error: %s", err)
            return False, err
        return True, ""
    except Exception as exc:
        _log.error("Slack request failed: %s", exc)
        return False, str(exc)


def _snapshot_blocks(success: bool, detail: str) -> list:
    icon = ":white_check_mark:" if success else ":x:"
    header = f"{icon} *Snapshot {'succeeded' if success else 'failed'}*"
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"```{detail}```"}},
    ]


def send_snapshot_notification(success: bool, detail: str) -> bool:
    """Post a snapshot result to the configured snapshots channel.

    Only sends when Slack is enabled. Returns True on success.
    """
    if not get_slack_enabled():
        return False
    channel = get_slack_snapshot_channel()
    text = f"Snapshot {'succeeded' if success else 'failed'}: {detail}"
    ok, err = _post(channel, text, _snapshot_blocks(success, detail))
    if not ok:
        _log.warning("Could not send snapshot notification: %s", err)
    return ok


def test_notification(channel: str) -> tuple[bool, str]:
    """Send a test message to the given channel. Bypasses the enabled flag."""
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":wave: *NGS Tracker* is connected to this channel.",
            },
        }
    ]
    return _post(channel, "NGS Tracker test message.", blocks)

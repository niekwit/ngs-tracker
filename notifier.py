import logging

from config import (
    get_slack_enabled,
    get_slack_runs_channel,
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


_STATUS_ICON = {
    "completed": ":white_check_mark:",
    "failed": ":x:",
    "running": ":arrows_counterclockwise:",
    "pending": ":hourglass_flowing_sand:",
}


def _run_blocks(run) -> list:
    icon = _STATUS_ICON.get(run.status, ":bell:")
    header = f"{icon} *{run.workflow_name}* — {run.status.capitalize()}"

    lines = []
    lines.append(f"*Project:* {run.project.name}")
    lines.append(f"*Researcher:* {run.project.researcher.name}")
    if run.workflow_tag:
        lines.append(f"*Tag:* `{run.workflow_tag}`")
    lines.append(f"*System:* {run.workflow_system or 'snakemake'}")
    if run.created_by:
        lines.append(f"*Submitted by:* {run.created_by}")
    if run.runtime_seconds:
        h, rem = divmod(run.runtime_seconds, 3600)
        m, s = divmod(rem, 60)
        rt = f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")
        lines.append(f"*Runtime:* {rt}")
    if run.description:
        lines.append(f"*Description:* {run.description}")
    if run.tag_list:
        tags = "  ".join(f"`{t}`" for t in run.tag_list)
        lines.append(f"*Tags:* {tags}")

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
    ]


def send_run_notification(run) -> bool:
    """Post a workflow run submission notification to the runs channel.

    Only sends when Slack is enabled. Returns True on success.
    """
    if not get_slack_enabled():
        return False
    channel = get_slack_runs_channel()
    text = f"Workflow run: {run.workflow_name} — {run.status} (project: {run.project.name})"
    ok, err = _post(channel, text, _run_blocks(run))
    if not ok:
        _log.warning("Could not send run notification: %s", err)
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

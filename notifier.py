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


def _snapshot_blocks(
    success: bool, detail: str, rclone_error: str | None = None
) -> list:
    icon = ":white_check_mark:" if success else ":x:"
    header = f"{icon} *Snapshot {'succeeded' if success else 'failed'}*"
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"```{detail}```"}},
    ]
    if rclone_error is not None:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":x: *rclone sync failed*\n```{rclone_error}```",
                },
            }
        )
    return blocks


def send_snapshot_notification(
    success: bool, detail: str, rclone_error: str | None = None
) -> bool:
    """Post a snapshot result to the configured snapshots channel.

    Only sends when Slack is enabled. Returns True on success.
    rclone_error: if set, an extra block is appended showing the rclone failure.
    """
    if not get_slack_enabled():
        return False
    channel = get_slack_snapshot_channel()
    text = f"Snapshot {'succeeded' if success else 'failed'}: {detail}"
    if rclone_error is not None:
        text += " (rclone sync failed)"
    ok, err = _post(channel, text, _snapshot_blocks(success, detail, rclone_error))
    if not ok:
        _log.warning("Could not send snapshot notification: %s", err)
    return ok


def send_backup_reminder_notification(runs: list, reminder_days: int) -> bool:
    """Post a backup-overdue reminder to the workflow_runs channel.

    Only sends when Slack is enabled. Returns True on success.
    """
    if not get_slack_enabled():
        return False
    if not runs:
        return False

    from datetime import datetime

    now = datetime.utcnow()
    n = len(runs)
    header = f":warning: *Backup reminder* — {n} run{'s' if n != 1 else ''} {'have' if n != 1 else 'has'} no backup"

    lines = []
    for run in runs:
        days_old = (now - run.run_date).days
        lines.append(
            f"• *{run.project.name}* — `{run.workflow_name}` — "
            f"{run.status} {days_old} day{'s' if days_old != 1 else ''} ago"
        )

    body = "\n".join(lines)
    if len(body) > 2900:
        body = body[:2900] + "\n…(list truncated)"

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": body}},
    ]
    text = f"Backup reminder: {n} run(s) overdue (>{reminder_days} days, no backup recorded)"
    channel = get_slack_runs_channel()
    ok, err = _post(channel, text, blocks)
    if not ok:
        _log.warning("Could not send backup reminder notification: %s", err)
    return ok


_STATUS_ICON = {
    "completed": ":white_check_mark:",
    "failed": ":x:",
    "running": ":arrows_counterclockwise:",
    "pending": ":hourglass_flowing_sand:",
}


def _run_blocks(
    run, wf_url: str | None = None, errors: list[str] | None = None
) -> list:
    icon = _STATUS_ICON.get(run.status, ":bell:")
    header = f"{icon} *{run.workflow_name}* — {run.status.capitalize()}"

    lines = []
    lines.append(f"*Project:* {run.project.name}")
    lines.append(f"*Researcher:* {run.project.researcher.name}")
    if run.workflow_tag:
        lines.append(f"*Tag:* `{run.workflow_tag}`")
    lines.append(f"*System:* {run.workflow_system or 'snakemake'}")
    if wf_url:
        lines.append(f"*Workflow:* {wf_url}")
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

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
    ]

    if errors:
        blocks.append({"type": "divider"})
        for err in errors:
            # Slack section text limit: 3000 chars
            if len(err) > 2900:
                err = err[:2900] + "\n…(truncated)"
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{err}```"},
                }
            )

    return blocks


def send_run_notification(run, errors: list[str] | None = None) -> bool:
    """Post a workflow run submission notification to the runs channel.

    Only sends when Slack is enabled. Returns True on success.
    """
    if not get_slack_enabled():
        return False
    from config import load_workflows

    workflows = load_workflows()
    wf_url = next((w["url"] for w in workflows if w["name"] == run.workflow_name), None)
    channel = get_slack_runs_channel()
    text = f"Workflow run: {run.workflow_name} — {run.status} (project: {run.project.name})"
    ok, err = _post(channel, text, _run_blocks(run, wf_url=wf_url, errors=errors))
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


import re as _re


def channel_from_group_name(name: str) -> str:
    """Derive a Slack channel slug from a research group name.

    e.g. "James Nathan" → "james-nathan"
         "Nathan Lab (Cambridge)" → "nathan-lab-cambridge"
    """
    slug = name.lower()
    slug = _re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = _re.sub(r"[\s]+", "-", slug.strip())
    slug = _re.sub(r"-+", "-", slug)
    return slug


def build_run_message(
    run, samples: list | None = None, wf_url: str | None = None
) -> str:
    """Build the default mrkdwn message for a manual run notification."""
    researcher = run.project.researcher
    mention = (
        f"<@{researcher.slack_user_id}>"
        if researcher.slack_user_id
        else researcher.name
    )

    icon = _STATUS_ICON.get(run.status, ":bell:")
    lines = [
        f"Hi {mention},",
        "",
        f"Your *{run.project.name}* analysis (*{run.workflow_name}* — Run #{run.id}) is ready. {icon}",
        "",
    ]

    lines.append(f"• *Status:* {run.status.capitalize()}")
    lines.append(f"• *Date:* {run.run_date.strftime('%Y-%m-%d')}")

    if wf_url:
        lines.append(f"• *Workflow code:* {wf_url}")

    if run.workflow_tag:
        lines.append(f"• *Version:* `{run.workflow_tag}`")

    if run.description:
        lines.append(f"• *Description:* {run.description}")

    if samples:
        sample_names = ", ".join(s["name"] for s in samples[:10])
        if len(samples) > 10:
            sample_names += f" (+{len(samples) - 10} more)"
        lines.append(f"• *Samples:* {sample_names}")

    if run.shared_storage_path:
        lines.append(f"• *Data location:* `{run.shared_storage_path}`")

    lines += ["", "Please let me know if you have any questions."]
    return "\n".join(lines)


def send_manual_run_message(channel: str, message: str) -> tuple[bool, str]:
    """Post a manually composed run message. Bypasses the enabled flag."""
    return _post(channel, message)


def build_script_message(script) -> str:
    """Build the default mrkdwn message for a manual custom-analysis-script notification."""
    researcher = script.project.researcher
    mention = (
        f"<@{researcher.slack_user_id}>"
        if researcher.slack_user_id
        else researcher.name
    )

    lines = [
        f"Hi {mention},",
        "",
        f"Custom analysis results for *{script.project.name}* are ready. :bar_chart:",
        "",
        f"• *Script:* `{script.original_filename}`",
        f"• *Language:* {script.language}",
    ]

    if script.description:
        lines.append(f"• *Description:* {script.description}")

    if script.output_files:
        n = len(script.output_files)
        filenames = ", ".join(
            f"`{o.original_filename}`" for o in script.output_files[:5]
        )
        if n > 5:
            filenames += f" (+{n - 5} more)"
        lines.append(f"• *Output files ({n}):* {filenames}")

    if script.shared_storage_path:
        lines.append(f"• *Data location:* `{script.shared_storage_path}`")

    lines += ["", "Please let me know if you have any questions."]
    return "\n".join(lines)

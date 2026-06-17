# Slack Integration

## Current setup

NGS Tracker posts notifications to Slack via a **Bot Token** (`xoxb-…`).

### Slack app
- App name: **NGS Tracker** (workspace: NGS Tracker)
- App ID: `A0BBELQNL5S`
- Created at: [api.slack.com/apps](https://api.slack.com/apps)
- Bot Token Scopes: `chat:write`, `chat:write.public`

### What is notified
| Event | Channel |
|---|---|
| Snapshot succeeded | `#snapshots` |
| Snapshot failed | `#snapshots` |

Notifications fire on both manual ("Snapshot Now" button) and scheduled snapshots.

### Settings
Configured in NGS Tracker → Settings → Slack Notifications:
- Bot Token (stored in `~/.ngs-tracker/settings.json` as `slack_token`)
- Snapshots channel (default: `snapshots`)
- Enable/disable toggle
- Test button

### Important: private channels
`chat:write.public` only works for public channels. For private channels, the bot must be invited explicitly:

```
/invite @NGS Tracker
```

This is required for every private channel the bot should post to.

---

## Future plans

- Add an optional **Slack channel** field to each **Researcher** and/or **Project** record.
- When a workflow run is registered (via the REST API), post a notification to the relevant channel.
- This requires the bot to be invited to each project/user channel before it can post.
- No additional OAuth scopes are needed — the same bot token handles all channels.

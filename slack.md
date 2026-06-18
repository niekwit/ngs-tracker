# Slack Integration

## Current setup

NGS Tracker posts notifications to Slack via a **Bot Token** (`xoxb-…`).

### Slack app

- App name: **NGS Tracker** (workspace: NGS Tracker)
- App ID: `A0BBELQNL5S`
- Created at: [api.slack.com/apps](https://api.slack.com/apps)
- Bot Token Scopes: `chat:write`, `chat:write.public`

### What is notified

| Event              | Channel      |
| ------------------ | ------------ |
| Snapshot succeeded | `#snapshots` |
| Snapshot failed    | `#snapshots` |

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


### Option A — Manual Slack Member ID

Add an optional `Slack Member ID` field to each Researcher record. Users find their own ID in Slack via **Profile → ⋮ → Copy Member ID** (format: `U01ABCDEF`). The bot sends a DM by using this ID as the channel in `chat.postMessage`.

- No extra scopes needed — `chat:write` already covers DMs
- One-time manual lookup per researcher
- Researchers without an ID set simply don't receive DMs

### Option B — Automatic email lookup

Researchers already have an email field. The bot looks up the Slack Member ID automatically via the `users.lookupByEmail` API, so researchers never need to do anything.

- Requires two additional scopes: `users:read` and `users:read.email`
- Requires reinstalling the app to the workspace after adding the scopes
- Seamless — works as long as the researcher's email matches their Slack account

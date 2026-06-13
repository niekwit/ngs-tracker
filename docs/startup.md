# Running at startup

## Fedora / Ubuntu (systemd)

A systemd user service starts NGS Tracker automatically at login — or at boot if lingering is enabled.

**1. Find the full conda path**

```bash
which conda   # e.g. /home/niek/miniforge3/condabin/conda
```

Systemd user services do not source `.bashrc`, so `conda` will not be in `PATH` unless you use its absolute path.

**2. Create the service file**

Create `~/.config/systemd/user/ngs-tracker.service`:

```ini
[Unit]
Description=NGS Tracker
After=network.target

[Service]
WorkingDirectory=/path/to/ngs-tracker
ExecStart=/home/you/miniforge3/condabin/conda run -n ngs-tracker python app.py
Restart=on-failure

[Install]
WantedBy=default.target
```

**3. Enable and start**

```bash
systemctl --user daemon-reload
systemctl --user enable --now ngs-tracker
```

**4. Start at boot without a login session (optional)**

```bash
loginctl enable-linger $USER
```

**Useful commands**

```bash
systemctl --user status ngs-tracker     # check status
systemctl --user restart ngs-tracker    # restart manually
journalctl --user -u ngs-tracker -f     # live logs
```

---

## macOS (launchd)

A Launch Agent plist starts NGS Tracker automatically at login.

**1. Find the full conda path**

```bash
which conda   # e.g. /Users/you/miniforge3/condabin/conda
```

**2. Create the plist**

Create `~/Library/LaunchAgents/com.ngs-tracker.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ngs-tracker</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/you/miniforge3/condabin/conda</string>
    <string>run</string>
    <string>-n</string>
    <string>ngs-tracker</string>
    <string>python</string>
    <string>app.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/ngs-tracker</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/ngs-tracker.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/ngs-tracker.err</string>
</dict>
</plist>
```

**3. Load the agent**

```bash
launchctl load ~/Library/LaunchAgents/com.ngs-tracker.plist
```

The agent loads automatically on every subsequent login.

**Useful commands**

```bash
launchctl unload ~/Library/LaunchAgents/com.ngs-tracker.plist   # stop and disable
launchctl load   ~/Library/LaunchAgents/com.ngs-tracker.plist   # re-enable
tail -f /tmp/ngs-tracker.log                                     # live logs
```

---

## Windows (Task Scheduler)

**1. Find the full conda path**

Open **Anaconda Prompt** and run:

```bat
where conda
```

Note the path, e.g. `C:\Users\you\miniforge3\condabin\conda.bat`.

**2. Create a startup script**

Create `C:\path\to\ngs-tracker\start.bat`:

```bat
@echo off
"C:\Users\you\miniforge3\condabin\conda.bat" run -n ngs-tracker python app.py
```

**3. Register the task**

Open **PowerShell as Administrator**:

```powershell
$action  = New-ScheduledTaskAction `
    -Execute "C:\path\to\ngs-tracker\start.bat"
$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimitPT0S
Register-ScheduledTask `
    -TaskName "NGS Tracker" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force
```

**4. Start immediately**

```powershell
Start-ScheduledTask -TaskName "NGS Tracker"
```

**Useful commands**

```powershell
Stop-ScheduledTask       -TaskName "NGS Tracker"
Start-ScheduledTask      -TaskName "NGS Tracker"
Unregister-ScheduledTask -TaskName "NGS Tracker" -Confirm:$false
```

To capture logs, redirect output in `start.bat`:

```bat
@echo off
"C:\Users\you\miniforge3\condabin\conda.bat" run -n ngs-tracker python app.py >> "%TEMP%\ngs-tracker.log" 2>&1
```

---

```{note}
NGS Tracker uses roughly 40–80 MB RAM at idle — comparable to a terminal window.
```

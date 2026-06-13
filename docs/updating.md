# Updating

```bash
git pull

# Dependencies rarely change — re-run only if requirements.txt was updated:
pip install -r requirements.txt
```

Then restart the server. Database schema migrations are applied automatically on startup — no manual steps are needed.

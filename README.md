# FreshKart

FreshKart is a Flask and SQLite vegetable-market application.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ADMIN_USERNAME = "VIJAY"
$env:ADMIN_PASSWORD = "Freshkart@26"
python app.py
```

Open `http://127.0.0.1:5000`. The administrator creates customer and farmer
accounts from the admin interface.

## Deploy on Render

1. Connect this repository to Render and create a Blueprint from `render.yaml`.
2. Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` as secret environment values.
3. Wait for the first deployment, then sign in and create customer accounts.

The free Render configuration uses local SQLite storage, which is temporary.
Customer accounts, orders, uploaded product photos, and other changes may be lost
when the service restarts or redeploys. Use persistent storage and configure
`DATABASE_PATH` before relying on a hosted instance for real customer data.

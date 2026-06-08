# GoPro Remote -- Error Reporting Dashboard

A self-hosted error reporting system for the GoPro Remote for Garmin widget.
The widget collects 32-bit error codes in `ErrorManager.errorQueue` and POSTs
them here. An admin UI (local-network only) lets the developer inspect, filter,
and sort reports by version, camera model, error category, and build type.


## Dependencies

- Python 3.11+
- Node.js 22+ and npm


## Installation

1. Clone the repository
```bash
git clone https://github.com/ad220/gopro-remote-error-dashboard
cd gopro-remote-error-dashboard
```

2. Create your .env file and set your server url
```bash
cp frontend/.env.template frontend/.env
open frontend/.env
```

3. Run the install script
```bash
bash scripts/install.sh
```

The script builds the frontend into `backend/static/`, sets up a Python virtual
environment, and installs + enables the `gopro-dashboard` systemd service.


## Caddy configuration

```caddyfile
errors.example.com {
    root * /path/to/repo/backend/static
    file_server

    reverse_proxy /admin/* 127.0.0.1:8000
    reverse_proxy /report  127.0.0.1:8000
}
```

## Generating test data

```bash
cd backend
python src/seed_reports.py --url <url>
```

## API key workflow

Create one API key per app version from the admin UI.

The raw key is returned only once, as a raw hex key but also as the full url+key secret to put in the widget `include/secrets/Secret.mc` file.


## Architecture

```
Garmin watch  -->  POST /report  -->  FastAPI (port 8000)  -->  SQLite
|
Browser  <--  static files  <--  Caddy  <--  GET /admin/*
```
- `backend/src/api.py` -- all routes, error-code parsing, and admin endpoints
- `backend/src/database.py` -- SQLAlchemy models
- `frontend/src/` -- Vue 3 SPA (ErrorGrid, StatsPanel, VersionManager)
- Error codes follow a 32-bit layout: `[31-30 build][29-24 gopro_id][23-16 ec][15-0 data]`
- Daily SQLite backups are stored in `backend/src/backups/`
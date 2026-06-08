#!/bin/bash

echoln() {
    printf "\n$1\n\n"
}

echoln "building frontend..."
cd frontend/
npm install
npm run build

echoln "setting up backend..."
cd ../backend
mkdir -p data/backup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echoln "\n\ninstalling systemd service...\n"
cd ..
cat << EOF > scripts/gopro-dashboard.service
[Unit]
Description=GoPro remote error reporting dashboard
After=network.target caddy.service

[Service]
Type=exec
User=ad220
WorkingDirectory=$(pwd)/backend/src
ExecStart=.venv/bin/python src/main
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable scripts/gopro-dashboard.service

echoln "done !"
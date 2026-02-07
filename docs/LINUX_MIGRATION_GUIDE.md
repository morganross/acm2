# Linux Migration Guide

## Overview

This document outlines the changes required to migrate the ACM2 backend from Windows Server to AWS Linux.

## 1. Code Changes: None Required

The Python code is already cross-platform:

- Uses `pathlib.Path` for file paths
- Uses `sys.executable` for subprocess calls  
- Windows-specific `ProactorEventLoop` code in `app/main.py` is **conditional** (`if sys.platform == 'win32'`) - it simply won't execute on Linux

## 2. Deployment Changes Required

| Item | Windows (Current) | Linux (AWS) |
|------|-------------------|-------------|
| **Service Manager** | NSSM | systemd |
| **SSL Certs Path** | `C:\devlop\acm2\certs\` | `/opt/acm2/certs/` |
| **Working Directory** | `C:\devlop\acm2\acm2\` | `/opt/acm2/acm2/` |
| **Python** | `py` / `python.exe` | `python3` / venv |
| **Data Directory** | `C:\devlop\acm2\acm2\data\` | `/opt/acm2/acm2/data/` |

## 3. Create systemd Service

Replace NSSM with a systemd unit file:

```ini
# /etc/systemd/system/acm2.service
[Unit]
Description=ACM2 API Server
After=network.target

[Service]
Type=simple
User=acm2
WorkingDirectory=/opt/acm2/acm2
ExecStart=/opt/acm2/venv/bin/python -m cli
Environment="PATH=/opt/acm2/venv/bin"
EnvironmentFile=/opt/acm2/acm2/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 4. Deployment Steps

```bash
# 1. Create user and directory structure
sudo useradd -r -s /bin/false acm2
sudo mkdir -p /opt/acm2
sudo chown acm2:acm2 /opt/acm2
cd /opt/acm2

# 2. Clone repo
sudo -u acm2 git clone <repo-url> .

# 3. Create venv and install dependencies
sudo -u acm2 python3.11 -m venv venv
sudo -u acm2 ./venv/bin/pip install -e acm2/

# 4. Copy SSL certs
sudo mkdir -p /opt/acm2/certs
sudo cp /path/to/cloudflare.crt /opt/acm2/certs/
sudo cp /path/to/cloudflare.key /opt/acm2/certs/
sudo chown -R acm2:acm2 /opt/acm2/certs
sudo chmod 600 /opt/acm2/certs/cloudflare.key

# 5. Create .env file
sudo -u acm2 cp acm2/.env.example acm2/.env
# Edit with your keys:
# - ENCRYPTION_KEY
# - SEED_PRESET_ID
# - SEED_VERSION
# - ACM2_PLUGIN_SECRET

# 6. Create data directory
sudo -u acm2 mkdir -p /opt/acm2/acm2/data

# 7. Install & start service
sudo cp acm2.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable acm2
sudo systemctl start acm2

# 8. Check status
sudo systemctl status acm2
sudo journalctl -u acm2 -f
```

## 5. Port 443 Permission

On Linux, binding to port 443 requires one of these approaches:

### Option A: setcap (Recommended for direct binding)
```bash
sudo setcap 'cap_net_bind_service=+ep' /opt/acm2/venv/bin/python3.11
```

### Option B: Reverse Proxy (Recommended for production)

Use nginx or caddy as a reverse proxy:

```nginx
# /etc/nginx/sites-available/acm2
server {
    listen 443 ssl;
    server_name api.apicostx.com;

    ssl_certificate /opt/acm2/certs/cloudflare.crt;
    ssl_certificate_key /opt/acm2/certs/cloudflare.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

With this approach, update `cli.py` to use port 8000 instead of 443.

## 6. FilePromptForge Location

The FPF adapter expects FilePromptForge to be a sibling directory. Ensure the directory structure is:

```
/opt/acm2/
├── acm2/           # Main backend
├── FilePromptForge/ # FPF tool
├── certs/          # SSL certificates
└── venv/           # Python virtual environment
```

## 7. Environment Variables

Required in `/opt/acm2/acm2/.env`:

```dotenv
ENCRYPTION_KEY=<your-encryption-key>
SEED_PRESET_ID=86f721fc-742c-4489-9626-f148cb3d6209
SEED_VERSION=1.0.0
ACM2_PLUGIN_SECRET=<your-plugin-secret>
```

## 8. Firewall Configuration

```bash
# Allow HTTPS
sudo ufw allow 443/tcp

# Or with iptables
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

## 9. Log Files

Logs are written to `/opt/acm2/acm2/logs/`. Ensure the directory exists and is writable:

```bash
sudo -u acm2 mkdir -p /opt/acm2/acm2/logs
```

View logs with:
```bash
# Application logs
tail -f /opt/acm2/acm2/logs/acm2.log

# Systemd service logs
sudo journalctl -u acm2 -f
```

## Summary

The ACM2 codebase is already Linux-compatible. Migration requires:

1. ✅ No code changes needed
2. 🔧 Set up systemd service instead of NSSM
3. 🔧 Adjust file paths in deployment
4. 🔧 Handle port 443 binding (setcap or reverse proxy)
5. 🔧 Migrate SSL certificates and .env configuration

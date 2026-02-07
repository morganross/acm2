# Notes for Linux Installation (Read This First!)

These are critical details NOT fully covered in the other documentation files.

---

## 0. FIRST STEP: SSH Access and Prerequisites

Before anything else, you need SSH access to the server.

### Get credentials from user:
1. **Server IP address** (e.g., `54.71.183.56`)
2. **SSH key file** (`.pem` file) - should be in `linux/twentysix.pem` or user will provide

### Connect and install prerequisites:

```bash
# From Windows PowerShell (fix .pem permissions first):
icacls "C:\devlop\acm2\linux\twentysix.pem" /inheritance:r
icacls "C:\devlop\acm2\linux\twentysix.pem" /grant:r "Administrator:R"

# SSH to server (Amazon Linux uses ec2-user, Ubuntu uses ubuntu):
ssh -i C:\devlop\acm2\linux\twentysix.pem -o StrictHostKeyChecking=no ec2-user@SERVER_IP

# Install git (required for VS Code Agent mode):
sudo dnf install -y git           # Amazon Linux 2023
# OR
sudo apt install -y git           # Ubuntu/Debian

# Install VS Code tunnel (download CLI):
curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output vscode_cli.tar.gz
tar -xf vscode_cli.tar.gz
chmod +x code

# Start tunnel and authenticate:
./code tunnel --accept-server-license-terms

# Follow the GitHub authentication link, then install as service:
./code tunnel service install
sudo loginctl enable-linger $USER
```

### Verify tunnel is running:
```bash
./code tunnel status
# Should show: {"tunnel":{"name":"YOUR_TUNNEL_NAME"...},"service_installed":true}
```

Then connect from VS Code: `Ctrl+Shift+P` → "Remote-Tunnels: Connect to Tunnel" → select your tunnel name.

### CRITICAL: Open the correct folder!

**DO NOT open `/` as your workspace** - this causes Agent mode to hang trying to index the entire filesystem.

Instead:
1. Create the workspace folder: `sudo mkdir -p /opt/acm2 && sudo chown $USER:$USER /opt/acm2`
2. In VS Code: `Ctrl+Shift+P` → "File: Open Folder" → `/opt/acm2`

---

## 1. Python Version

Server requires **Python 3.11** specifically:

```bash
# Amazon Linux 2023:
sudo dnf install -y python3.11 python3.11-pip python3.11-devel

# Ubuntu/Debian:
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```

---

## 2. Working Directory Matters

The server **MUST** be started from `/opt/acm2/acm2/` (the inner acm2 folder) because it loads `.env` from the current directory.

```
/opt/acm2/           <- repo root (clone here)
├── acm2/            <- WORKING DIRECTORY (cd here to run)
│   ├── .env         <- environment file loaded from cwd
│   ├── cli.py       <- entry point
│   ├── app/         <- FastAPI application
│   └── data/        <- SQLite databases (user data)
├── certs/           <- SSL certificates (OUTER level)
├── FilePromptForge/ <- FPF tool (sibling directory)
├── linux/           <- Linux-specific scripts (this folder)
└── venv/            <- Python virtual environment
```

---

## 3. SSL Certificate Paths

The certs directory is at the **OUTER** level:

```
/opt/acm2/certs/cloudflare.crt
/opt/acm2/certs/cloudflare.key
```

**NOT** inside the acm2 folder. The code uses relative path `../certs/` from the working directory.

---

## 4. Database Migration from Windows

Copy the data folder from Windows to preserve user data:

```bash
# From the Linux server (Windows backend is at 16.144.148.159):
scp -i ~/twentysix.pem -r Administrator@16.144.148.159:'c:/devlop/acm2/acm2/data' /opt/acm2/acm2/

# Or from Windows (run in PowerShell):
scp -r c:\devlop\acm2\acm2\data ec2-user@NEW_LINUX_IP:/opt/acm2/acm2/
```

---

## 5. Frontend IP Address

The WordPress frontend is at **16.145.206.59** (not 35.88.196.59 which may appear in older docs).

To restart frontend Apache:
```bash
ssh ubuntu@16.145.206.59 'sudo /opt/bitnami/ctlscript.sh restart apache'
```

---

## 6. Cache Clearing on Linux

The bash equivalent of the PowerShell cache clearing:

```bash
# Clear Python bytecode caches
find /opt/acm2 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /opt/acm2 -name "*.pyc" -delete 2>/dev/null || true
```

---

## 7. SQLite WAL Checkpoint

Before stopping the server, checkpoint databases to prevent corruption:

```bash
# Checkpoint all user databases
for db in /opt/acm2/acm2/data/*.db; do
    sqlite3 "$db" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null || true
done
```

---

## 8. Encryption Key

Either copy from Windows `.env` or generate a new one:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**WARNING**: If you generate a new key, existing encrypted provider API keys in user databases will be unreadable!

---

## 9. Lightsail Firewall

You must open port 443 in **TWO** places:

1. **Lightsail Console** → Instance → Networking tab → Add rule: HTTPS (443)
2. **Instance firewall** (ufw): `sudo ufw allow 443/tcp`

The Lightsail console firewall is checked FIRST. If it's not open there, ufw rules don't matter.

---

## 10. Port 443 Binding

Linux requires special permission to bind to ports < 1024. Options:

### Option A: AmbientCapabilities (used in acm2.service)
The systemd service file includes `AmbientCapabilities=CAP_NET_BIND_SERVICE` which allows the service to bind to 443.

### Option B: setcap (for manual running)
```bash
sudo setcap 'cap_net_bind_service=+ep' /opt/acm2/venv/bin/python3.11
```

### Option C: Reverse proxy (production recommended)
Run uvicorn on port 8000, put nginx in front on 443. See `LINUX_MIGRATION_GUIDE.md`.

---

## 11. Quick Start Commands

```bash
# Clone repo
cd /opt
sudo git clone https://github.com/morganross/acm2.git
sudo chown -R $USER:$USER acm2

# Create venv
cd /opt/acm2
python3.11 -m venv venv
source venv/bin/activate
pip install -e acm2/

# Copy certs (from your local machine or download from Cloudflare)
mkdir -p certs
# ... copy cloudflare.crt and cloudflare.key here ...

# Create .env
cp linux/.env.example acm2/.env
nano acm2/.env  # Fill in ENCRYPTION_KEY and ACM2_PLUGIN_SECRET

# Install systemd service
sudo cp linux/acm2.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable acm2
sudo systemctl start acm2

# Check status
sudo systemctl status acm2
sudo journalctl -u acm2 -f
```

---

## 12. Troubleshooting

### Server won't start
```bash
# Check logs
sudo journalctl -u acm2 -n 50

# Common issues:
# - .env file missing or wrong path
# - SSL certs not found (check /opt/acm2/certs/)
# - Port 443 already in use
# - Python dependencies missing
```

### "SEED_PRESET_ID and SEED_VERSION are required"
You're not in the right directory or .env isn't being loaded:
```bash
cd /opt/acm2/acm2
cat .env  # Verify file exists and has values
```

### SSL errors
```bash
# Verify certs exist and are readable
ls -la /opt/acm2/certs/
# Should show cloudflare.crt and cloudflare.key
```

### Port already in use
```bash
sudo lsof -i :443
sudo kill <PID>
```

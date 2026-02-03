# ACM2 Fresh Install Guide

Complete step-by-step guide to deploy ACM2 from scratch on new servers.

---

## Prerequisites

Before starting, ensure you have:
- [ ] AWS Lightsail account
- [ ] Domain name (e.g., `apicostx.com`)
- [ ] Cloudflare account
- [ ] GitHub access to both repos:
  - `acm2` (backend)
  - `acm-wordpress-plugin` (frontend)

---

## Part 1: Create Backend Server (Windows)

### 1.1 Create AWS Lightsail Instance

1. Go to AWS Lightsail console
2. Create instance:
   - **Location**: Choose region (e.g., Oregon)
   - **Platform**: Windows
   - **Blueprint**: Windows Server 2022
   - **Instance plan**: $20/month minimum (4GB RAM recommended)
   - **Name**: `acm2-backend`
3. Wait for instance to start, note the **public IP address**

### 1.2 Initial Windows Setup

1. RDP into the server using Lightsail console
2. Set Administrator password
3. Install required software:

```powershell
# Install Chocolatey (package manager)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

# Install Python 3.11
choco install python311 -y

# Install Git
choco install git -y

# Install VS Code (optional but recommended)
choco install vscode -y

# Refresh environment
refreshenv
```

### 1.3 Clone Backend Repository

```powershell
cd C:\devlop
git clone https://github.com/YOUR_ORG/acm2.git
cd acm2
```

### 1.4 Install Python Dependencies

```powershell
cd C:\devlop\acm2\acm2
pip install -r requirements.txt
```

### 1.5 Create Environment File

Create `C:\devlop\acm2\acm2\.env`:

```env
# Plugin secret (generate a random string, share with WordPress)
ACM2_PLUGIN_SECRET=sk_plugin_YOUR_RANDOM_SECRET_HERE

# Database location
DATABASE_URL=sqlite+aiosqlite:///C:/Users/Administrator/.acm2/acm2.db

# Seed configuration
SEED_PRESET_ID=default
SEED_VERSION=1.0.0
```

### 1.6 Create Data Directories

```powershell
mkdir C:\devlop\acm2\acm2\data -Force
mkdir C:\Users\Administrator\.acm2 -Force
```

### 1.7 Open Windows Firewall Ports

```powershell
# HTTPS (443) - for production
New-NetFirewallRule -DisplayName "ACM2 Backend HTTPS (443)" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow

# HTTP (80) - optional, for testing without SSL
New-NetFirewallRule -DisplayName "ACM2 Backend HTTP (80)" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
```

### 1.8 Open AWS Security Group Ports

1. Go to Lightsail console → Networking tab
2. Add rules:
   - **HTTPS** (TCP 443) from any IP
   - **HTTP** (TCP 80) from any IP (optional)

### 1.9 Test Backend Startup

```powershell
cd C:\devlop\acm2\acm2
python -m uvicorn app.main:app --host 0.0.0.0 --port 80
```

Visit `http://YOUR_BACKEND_IP/api/v1/health` - should return `{"status": "ok"}`

---

## Part 2: Create Frontend Server (WordPress/Bitnami)

### 2.1 Create AWS Lightsail Instance

1. Go to AWS Lightsail console
2. Create instance:
   - **Location**: Same region as backend
   - **Platform**: Linux/Unix
   - **Blueprint**: WordPress (Bitnami)
   - **Instance plan**: $10/month minimum (2GB RAM)
   - **Name**: `acm2-frontend`
3. Wait for instance to start, note the **public IP address**

### 2.2 Get Bitnami Default Credentials

```bash
# SSH into the server
ssh -i YOUR_KEY.pem bitnami@FRONTEND_IP

# Get default WordPress password
cat /home/bitnami/bitnami_credentials
```

### 2.3 Create SSH User for Backend Access

```bash
# Create new user
sudo adduser backenddev
sudo passwd backenddev  # Set password, e.g., TempPass2026!

# Give sudo access
sudo usermod -aG sudo backenddev

# Allow password authentication (for SSH from backend)
sudo nano /etc/ssh/sshd_config
# Find and set: PasswordAuthentication yes
sudo systemctl restart sshd
```

### 2.4 Install Node.js

```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc

# Install Node.js 18+
nvm install 18
nvm use 18
```

### 2.5 Clone WordPress Plugin

```bash
cd /opt/bitnami/wordpress/wp-content/plugins/
sudo git clone https://github.com/YOUR_ORG/acm-wordpress-plugin.git
sudo chown -R bitnami:daemon acm-wordpress-plugin
sudo chmod -R 775 acm-wordpress-plugin
```

### 2.6 Build React UI

```bash
cd /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui
npm install
npm run build
```

### 2.7 Configure WordPress

1. Log into WordPress admin: `http://FRONTEND_IP/wp-admin`
2. Use credentials from step 2.2
3. Go to Plugins, activate "ACM2 Integration"

### 2.8 Edit wp-config.php

```bash
sudo nano /opt/bitnami/wordpress/wp-config.php
```

Add these lines BEFORE the `/* That's all, stop editing! */` comment:

```php
/* ACM2 Configuration */
define('WP_HOME', 'https://apicostx.com');
define('WP_SITEURL', 'https://apicostx.com');
define('ACM2_BACKEND_URL', 'https://api.apicostx.com');  // NO /api/v1 suffix!
define('ACM2_PLUGIN_SECRET', 'sk_plugin_YOUR_RANDOM_SECRET_HERE');  // Must match backend

/* Force HTTPS */
define('FORCE_SSL_ADMIN', true);
if (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {
    $_SERVER['HTTPS'] = 'on';
}
```

**IMPORTANT**: 
- `ACM2_BACKEND_URL` must NOT include `/api/v1` - the plugin adds it automatically
- `ACM2_PLUGIN_SECRET` must match the value in backend `.env`

---

## Part 3: Cloudflare & SSL Setup

Follow the detailed steps in [Install-frontend-CLOUDFLARE-SSL-SETUP.md](./Install-frontend-CLOUDFLARE-SSL-SETUP.md)

### Quick Summary:

1. **Add domain to Cloudflare**
2. **Update nameservers** at your registrar
3. **Add DNS A records**:
   - `@` → Frontend IP (proxied)
   - `api` → Backend IP (proxied)
4. **Generate Origin Certificate** (15 years)
5. **Set SSL mode to Full**
6. **Install certificates on both servers**

### Backend SSL Certificate Location

```powershell
# Create certs directory
mkdir C:\devlop\acm2\certs -Force

# Save certificate as: C:\devlop\acm2\certs\cloudflare.crt
# Save private key as: C:\devlop\acm2\certs\cloudflare.key
```

### Frontend SSL Certificate Location

```bash
# Save certificate as: /opt/bitnami/apache/conf/cloudflare.crt
# Save private key as: /opt/bitnami/apache/conf/cloudflare.key
```

---

## Part 4: Start Services

### 4.1 Backend - Create Startup Script

The `purge_and_restart.ps1` script handles:
- Stopping existing uvicorn
- Clearing Python cache
- Starting uvicorn with SSL

```powershell
cd C:\devlop\acm2
.\purge_and_restart.ps1
```

### 4.2 Backend - Set Up Auto-Start (Optional)

Create a scheduled task to start the backend on boot:
1. Open Task Scheduler
2. Create Basic Task: "ACM2 Backend"
3. Trigger: At startup
4. Action: Start a program
5. Program: `powershell.exe`
6. Arguments: `-ExecutionPolicy Bypass -File C:\devlop\acm2\purge_and_restart.ps1`

### 4.3 Frontend - Restart Apache

```bash
sudo /opt/bitnami/ctlscript.sh restart apache
```

---

## Part 5: Verification

### 5.1 Test Backend API

```
https://api.apicostx.com/api/v1/health
```

Should return: `{"status": "ok"}`

### 5.2 Test Frontend

```
https://apicostx.com
```

Should show WordPress site with SSL.

### 5.3 Test Plugin Integration

1. Log into WordPress as admin
2. Navigate to the ACM2 app page
3. Check browser console (F12) for any errors
4. Verify API calls use `https://api.apicostx.com`

### 5.4 Test User Creation

1. Create a new WordPress user
2. Log in as that user
3. Visit the ACM2 app
4. Plugin should automatically create backend user and API key

---

## Part 6: Security Hardening

### 6.1 WordPress Security

After fresh install, immediately:

```bash
# Remove default plugins if not needed
sudo rm -rf /opt/bitnami/wordpress/wp-content/plugins/akismet
sudo rm -rf /opt/bitnami/wordpress/wp-content/plugins/hello.php

# Set correct permissions
sudo find /opt/bitnami/wordpress -type d -exec chmod 755 {} \;
sudo find /opt/bitnami/wordpress -type f -exec chmod 644 {} \;
sudo chown -R bitnami:daemon /opt/bitnami/wordpress
```

### 6.2 Enable Two-Factor Authentication

Install and configure a 2FA plugin for all admin accounts.

### 6.3 Limit Login Attempts

Install a plugin like "Limit Login Attempts Reloaded".

### 6.4 Change Default URLs (Optional)

Consider changing:
- `wp-admin` to a custom admin URL
- `wp-login.php` to a custom login URL

### 6.5 Regular Backups

Set up automated backups using:
- Lightsail snapshots (both servers)
- WordPress backup plugin
- Offsite backup of databases

---

## Quick Reference

### Server IPs (Update with your actual IPs)

| Server | Role | IP |
|--------|------|-----|
| Frontend | WordPress | YOUR_FRONTEND_IP |
| Backend | FastAPI | YOUR_BACKEND_IP |

### Key File Locations

**Backend (Windows):**
- Code: `C:\devlop\acm2\`
- Data: `C:\devlop\acm2\acm2\data\`
- Certs: `C:\devlop\acm2\certs\`
- Env: `C:\devlop\acm2\acm2\.env`

**Frontend (Linux):**
- Plugin: `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/`
- Config: `/opt/bitnami/wordpress/wp-config.php`
- Certs: `/opt/bitnami/apache/conf/`
- Logs: `/opt/bitnami/apache/logs/`

### Important Commands

```bash
# Frontend - Restart Apache
sudo /opt/bitnami/ctlscript.sh restart apache

# Frontend - Rebuild React UI
cd /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui && npm run build

# Frontend - Check Apache logs
sudo tail -f /opt/bitnami/apache/logs/error_log
```

```powershell
# Backend - Start/Restart
cd C:\devlop\acm2; .\purge_and_restart.ps1

# Backend - Check logs
Get-Content C:\devlop\server.log -Tail 50
```

---

## Troubleshooting

### CORS Errors

1. Check `cors_origins` in `app/main.py` includes your domain
2. Ensure both `https://apicostx.com` AND `https://www.apicostx.com` are listed
3. Restart backend after changes

### 502 Bad Gateway

1. Check backend is running: `https://api.apicostx.com/api/v1/health`
2. Verify SSL certificate is correctly installed
3. Check Cloudflare SSL mode is "Full"

### "API Key not set" Errors

1. Check `ACM2_BACKEND_URL` in wp-config.php does NOT have `/api/v1`
2. Verify plugin secret matches between frontend and backend
3. Check WordPress user has ACM2 API key in user meta

### WordPress Redirect Loop

1. Ensure HTTPS detection code is in wp-config.php
2. Clear browser cache and cookies
3. Check Cloudflare SSL mode is "Full" not "Flexible"

---

## Related Documentation

- [Cloudflare SSL Setup](./Install-frontend-CLOUDFLARE-SSL-SETUP.md) - Detailed SSL/certificate setup
- [Main README](../README.md) - Architecture overview and development guide

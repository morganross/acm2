# Cloudflare SSL Setup Guide

This guide explains how to set up Cloudflare with Full SSL mode for both the WordPress frontend and the Uvicorn backend.

---

## Part 1: Cloudflare Setup (Do This First)

### 1.1 Add Your Domain to Cloudflare
- Go to cloudflare.com, sign up or log in
- Click "Add a Site", enter your domain
- Choose the Free plan

### 1.2 Update Your Domain's Nameservers
- Cloudflare will give you two nameservers (like `anna.ns.cloudflare.com`)
- Go to your domain registrar (GoDaddy, Namecheap, etc.) and replace the nameservers with Cloudflare's
- This can take up to 24 hours to propagate, but usually 15 minutes

### 1.3 Add DNS Records in Cloudflare
- Add an A record: your main domain pointing to your WordPress IP (16.145.206.59), with the orange cloud ON (proxied)
- Add an A record: `api` subdomain pointing to your backend IP (54.71.183.56), with the orange cloud ON (proxied)

### 1.4 Generate Origin Certificates
- Go to SSL/TLS section, then "Origin Server"
- Click "Create Certificate"
- Choose "Let Cloudflare generate a private key"
- For hostnames, add your main domain AND the api subdomain
- Choose 15 years validity
- Click Create
- **IMPORTANT:** You'll see a certificate and a private key. Copy BOTH and save them somewhere safe. The private key is only shown once!

### 1.5 Set SSL Mode to Full
- Go to SSL/TLS section, "Overview"
- Select "Full" (or "Full Strict" if you want extra validation)

---

## Part 2: Install Certificate on WordPress Server (Bitnami)

### 2.1 SSH into your WordPress server

```bash
ssh backenddev@16.145.206.59
```

### 2.2 Create certificate files

Create two new files in the Apache SSL directory:
- One file for the certificate (the longer block that starts with BEGIN CERTIFICATE)
- One file for the private key (the block that starts with BEGIN PRIVATE KEY)

```bash
sudo nano /opt/bitnami/apache/conf/server.crt
# Paste the certificate content

sudo nano /opt/bitnami/apache/conf/server.key
# Paste the private key content
```

### 2.3 Edit the Bitnami Apache SSL configuration

Edit the SSL configuration file (usually `/opt/bitnami/apache/conf/bitnami/bitnami.conf` or `/opt/bitnami/apache/conf/vhosts/wordpress-https-vhost.conf`) to point to your new certificate and key files.

Look for lines like:
```
SSLCertificateFile "/opt/bitnami/apache/conf/server.crt"
SSLCertificateKeyFile "/opt/bitnami/apache/conf/server.key"
```

### 2.4 Restart Apache

```bash
sudo /opt/bitnami/ctlscript.sh restart apache
```

### 2.5 Test

Visit your domain with https - you should see a valid Cloudflare certificate in your browser.

---

## Part 3: Install Certificate on Backend Server (Uvicorn)

### 3.1 SSH into your backend server

Connect to the Windows backend server via RDP or your preferred method.

### 3.2 Copy certificate files

Save the certificate and private key files to somewhere accessible, for example:
- `C:\devlop\acm2\certs\cloudflare.crt`
- `C:\devlop\acm2\certs\cloudflare.key`

### 3.3 Modify Uvicorn startup to include SSL

When starting uvicorn, add the SSL parameters:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 443 --ssl-keyfile C:\devlop\acm2\certs\cloudflare.key --ssl-certfile C:\devlop\acm2\certs\cloudflare.crt
```

Or if using a startup script, update it to include these parameters.

### 3.4 Update Windows Firewall

Make sure port 443 is open in Windows Firewall:
- Windows Defender Firewall → Advanced Settings
- Inbound Rules → New Rule
- Port → TCP 443 → Allow the connection

### 3.5 Update AWS Security Group

In AWS Console, make sure the security group for your backend EC2 instance allows inbound traffic on port 443.

### 3.6 Test

Visit your api subdomain health endpoint with https:
```
https://api.yourdomain.com/api/v1/health
```

---

## Part 4: Update WordPress Configuration

### 4.1 Edit wp-config.php

SSH into WordPress server and edit wp-config.php:

```bash
sudo nano /opt/bitnami/wordpress/wp-config.php
```

Update these lines:
```php
define('WP_HOME', 'https://yourdomain.com');
define('WP_SITEURL', 'https://yourdomain.com');
define('ACM2_BACKEND_URL', 'https://api.yourdomain.com/api/v1');
```

### 4.2 Force HTTPS (Optional but recommended)

Add this to wp-config.php to force HTTPS:
```php
define('FORCE_SSL_ADMIN', true);
if (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {
    $_SERVER['HTTPS'] = 'on';
}
```

---

## Part 5: Verification

1. **Visit your main domain** - should show https with a valid certificate
2. **Visit your api subdomain health endpoint** - should show https with a valid certificate
3. **Test the WordPress app** - login, run an execution, check that API calls work over https
4. **Check Cloudflare dashboard** - you should see traffic flowing through

---

## Troubleshooting

### Certificate errors in browser
- Make sure SSL mode in Cloudflare is set to "Full", not "Flexible"
- Check that the certificate files were saved correctly on the servers

### 502 Bad Gateway
- The backend server might not be running on the expected port
- Check that uvicorn is running with the SSL parameters

### Mixed content warnings
- Some resources might still be loading over HTTP
- Check browser developer tools Network tab for HTTP requests
- Update any hardcoded HTTP URLs in the codebase

### WordPress redirect loop
- Add the HTTPS detection snippet from Part 4.2
- Clear browser cache and cookies

---

## Security Notes

- Cloudflare Origin Certificates are only valid when traffic goes through Cloudflare
- If someone bypasses Cloudflare and hits your server directly, they'll see a certificate error (this is a feature, not a bug)
- Keep your private key files secure and never commit them to git
- Consider adding your server IPs to a .gitignore or using environment variables

---

## Server Reference

| Server | IP | Purpose | Port |
|--------|-----|---------|------|
| WordPress Frontend | 16.145.206.59 | Bitnami WordPress | 443 |
| Backend API | 54.71.183.56 | FastAPI/Uvicorn | 443 |

---

## Code Changes Made for SSL/Domain Support

The following changes were made to the codebase to support the new domain and SSL configuration:

### 1. CORS Origins Updated (`app/main.py`)

Added the production domain to the CORS allowed origins list:

```python
cors_origins = [
    # ... existing origins ...
    # Production domain (Cloudflare)
    "https://apicostx.com",
    "https://www.apicostx.com",
]
```

### 2. Backend Startup Script (`purge_and_restart.ps1`)

Updated to start uvicorn with SSL on port 443:

- Changed from `--port 80` to `--port 443`
- Added `--ssl-keyfile` and `--ssl-certfile` parameters
- Updated firewall check from port 80 to port 443

### 3. Certificate Files Location

Certificates are stored at:
- `C:\devlop\acm2\certs\cloudflare.crt` (certificate)
- `C:\devlop\acm2\certs\cloudflare.key` (private key)

### 4. WordPress Configuration (`wp-config.php`)

The following constants must be set:

```php
define('WP_HOME', 'https://apicostx.com');
define('WP_SITEURL', 'https://apicostx.com');
define('ACM2_BACKEND_URL', 'https://api.apicostx.com');  // NO /api/v1 - plugin adds it
define('FORCE_SSL_ADMIN', true);
```

**Important:** `ACM2_BACKEND_URL` should NOT include `/api/v1` - the plugin appends this automatically.

### 5. Windows Firewall Rule

A firewall rule was added:
- Name: `ACM2 Backend HTTPS (443)`
- Direction: Inbound
- Protocol: TCP
- Port: 443
- Action: Allow

### 6. AWS Security Group

Port 443 must be open in the backend EC2 instance's security group for inbound traffic.

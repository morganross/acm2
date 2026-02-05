# Comprehensive Investigation Report: ACM2 React Application Loading Failure

## Executive Summary

This report documents a comprehensive investigation into why the ACM2 React application fails to load in the WordPress admin interface, despite the ACM2 Settings page correctly showing "Connected to ACM2 API". The investigation reveals **TWO CRITICAL BUGS** that completely prevent the React application from rendering:

1. **Bug #1: JavaScript Global Variable Mismatch** - PHP sets `window.acm2Config` but React reads `window.acm2Data`
2. **Bug #2: DOM Element ID Mismatch** - PHP renders `<div id="root">` but React looks for `document.getElementById('acm2-root')`

Both bugs result in the React application silently failing to initialize, leaving users with a blank page.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Investigation Methodology](#investigation-methodology)
4. [Bug #1: JavaScript Global Variable Mismatch](#bug-1-javascript-global-variable-mismatch)
5. [Bug #2: DOM Element ID Mismatch](#bug-2-dom-element-id-mismatch)
6. [Historical Context and Vestigial Code](#historical-context-and-vestigial-code)
7. [Related Issues Discovered During Investigation](#related-issues-discovered-during-investigation)
8. [Root Cause Analysis](#root-cause-analysis)
9. [Recommended Fixes](#recommended-fixes)
10. [Verification Steps](#verification-steps)
11. [Appendices](#appendices)

---

## System Architecture Overview

### Two-Node Deployment Architecture

The ACM2 system operates on a two-server architecture:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLOUDFLARE CDN                              │
│                      (SSL Termination)                              │
│                    apicostx.com DNS Zone                            │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   WordPress   │   │   WordPress   │   │    ACM2       │
│   Frontend    │   │   Admin JS    │   │   Backend     │
│   16.145.206  │   │   (Browser)   │   │   54.71.183   │
│   .59         │   │               │   │   .56         │
│               │   │               │   │               │
│ Bitnami LAMP  │   │  React App    │   │ FastAPI/      │
│ Apache/PHP    │   │  in Browser   │   │ Uvicorn       │
│               │   │               │   │ Port 443      │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        │                   │                   │
        ▼                   ▼                   ▼
    WordPress           Direct HTTPS        Per-User
    REST API            to Backend          SQLite DBs
```

### Frontend Server (16.145.206.59)
- **OS**: Debian Linux (Bitnami Bitnami WordPress Stack)
- **Web Server**: Apache 2.4
- **Application**: WordPress with ACM2 Integration Plugin
- **Role**: Serves WordPress admin interface, hosts React application assets

### Backend Server (54.71.183.56 / api.apicostx.com)
- **OS**: Windows Server 2019 (AWS Lightsail)
- **Application**: FastAPI/Uvicorn
- **Port**: 443 (HTTPS with Cloudflare Origin Certificate)
- **Role**: API server, per-user SQLite database management

### Data Flow for React App Loading

1. User navigates to WordPress Admin → ACM2 → App
2. WordPress PHP renders the admin page shell
3. PHP calls `wp_localize_script()` to inject configuration
4. PHP renders a `<div>` container for React to mount
5. Browser loads React bundle (`index-*.js`)
6. React reads configuration from `window.*` global
7. React finds DOM container via `document.getElementById()`
8. React mounts and renders the application

---

## Investigation Methodology

### Files Examined

#### Frontend (WordPress Plugin)
| File | Purpose | Lines |
|------|---------|-------|
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/acm2-integration.php` | Main plugin entry point | ~250 |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php` | React app loader | ~120 |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-settings-page.php` | Settings page | ~140 |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/react-app/src/main.jsx` | React entry point | ~15 |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/react-app/src/App.jsx` | React App component | ~20 |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/react-app/src/services/api.js` | API client | ~60 |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/react-app/vite.config.js` | Vite build config | ~15 |

#### Backend (FastAPI)
| File | Purpose | Lines |
|------|---------|-------|
| `c:\devlop\acm2\acm2\app\main.py` | FastAPI app entry | ~280 |
| `c:\devlop\acm2\acm2\app\api\router.py` | API router | ~50 |
| `c:\devlop\acm2\acm2\app\api\endpoints\health.py` | Health endpoint | ~30 |
| `c:\devlop\acm2\acm2\app\api\endpoints\provider_keys.py` | Provider keys | ~100 |

### Access Methods
- **Frontend**: SSH via Paramiko with Ed25519 key authentication
- **Backend**: Direct file system access on Windows Server
- **Logs**: WordPress debug.log, Apache error.log, FastAPI console output

---

## Bug #1: JavaScript Global Variable Mismatch

### The Problem

The PHP code and React code use **different global variable names** for configuration:

**PHP Side** (`class-react-app.php`, line ~90):
```php
wp_localize_script('acm2-react-app', 'acm2Config', [
    'apiUrl' => $backend_url . '/api/v1',
    'nonce' => wp_create_nonce('wp_rest'),
    'currentUser' => wp_get_current_user()->user_login,
    'apiKey' => $acm2_api_key,
]);
```

**React Side** (`App.jsx`, line 5):
```javascript
const page = window.acm2Data?.page || 'runs';
```

**React Side** (`api.js`, line 10):
```javascript
const API_BASE = window.acm2Data.apiUrl.replace(/\/$/, '');
```

### Impact Analysis

When React loads:
1. `window.acm2Config` exists with the API URL and configuration
2. `window.acm2Data` is `undefined`
3. `App.jsx` reads `window.acm2Data?.page` → returns `undefined` → defaults to `'runs'`
4. `api.js` reads `window.acm2Data.apiUrl` → **THROWS UNCAUGHT ERROR**

The error is:
```
TypeError: Cannot read properties of undefined (reading 'apiUrl')
    at api.js:10
```

This error occurs immediately when the API client module loads, before any component renders. The error crashes the entire React application.

### Evidence

**PHP Source** (class-react-app.php):
```php
<?php
class ACM2_React_App {
    // ...
    public static function enqueue_react_app($hook) {
        // ...
        wp_localize_script('acm2-react-app', 'acm2Config', [
            'apiUrl' => $backend_url . '/api/v1',
            'nonce' => wp_create_nonce('wp_rest'),
            'currentUser' => wp_get_current_user()->user_login,
            'apiKey' => $acm2_api_key,
        ]);
    }
}
```

**React Source** (main.jsx):
```javascript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

const root = document.getElementById('acm2-root');
if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
```

**React Source** (api.js):
```javascript
const API_BASE = window.acm2Data.apiUrl.replace(/\/$/, '');

class ACM2Client {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    // ...
  }
}
```

---

## Bug #2: DOM Element ID Mismatch

### The Problem

The PHP code and React code use **different DOM element IDs**:

**PHP Side** (`class-react-app.php`, line ~110):
```php
public static function render_app_page() {
    ?>
    <style>
        #acm2-root {
            min-height: calc(100vh - 32px);
            background: #0f172a;
        }
    </style>
    <div class="wrap">
        <div id="root"></div>   <!-- ← RENDERS "root" -->
    </div>
    <?php
}
```

**React Side** (`main.jsx`, line 6):
```javascript
const root = document.getElementById('acm2-root');  // ← LOOKS FOR "acm2-root"
if (root) {
  ReactDOM.createRoot(root).render(/* ... */);
}
```

### Impact Analysis

When React loads:
1. PHP renders `<div id="root"></div>`
2. React calls `document.getElementById('acm2-root')`
3. Returns `null` (element doesn't exist)
4. The `if (root)` check fails
5. React **never calls `ReactDOM.createRoot()`**
6. Nothing is rendered - silent failure

This bug is particularly insidious because:
- No JavaScript error is thrown
- No console warning appears
- The page simply shows a blank dark background
- The browser's Developer Tools show the JS loaded successfully

### Evidence

**PHP Source** (class-react-app.php):
```php
public static function render_app_page() {
    ?>
    <style>
        /* Note: CSS targets #acm2-root but HTML has #root */
        #wpbody-content { padding: 0 !important; }
        #wpfooter { display: none; }
        .wrap { margin: 0 !important; padding: 0 !important; max-width: none !important; }
        #acm2-root {
            min-height: calc(100vh - 32px);
            background: #0f172a;
        }
    </style>
    <div class="wrap">
        <div id="root"></div>  <!-- WRONG ID! -->
    </div>
    <?php
}
```

**Vite Development Index** (react-app/index.html):
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ACM2 React App</title>
</head>
<body>
  <div id="acm2-root"></div>  <!-- CORRECT for development -->
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

### The CSS Red Herring

Note that the CSS in `render_app_page()` correctly targets `#acm2-root`:
```css
#acm2-root {
    min-height: calc(100vh - 32px);
    background: #0f172a;
}
```

This CSS is never applied because the element `#acm2-root` doesn't exist. The developer who wrote this CSS expected the div to have id `acm2-root`, but the HTML renders id `root`. This is evidence of an incomplete refactoring.

---

## Historical Context and Vestigial Code

### The Evolution of the Architecture

The ACM2 system has undergone multiple architectural changes:

#### Phase 1: WordPress Proxy Architecture (Early Design)
- React app called WordPress REST API
- WordPress proxied requests to FastAPI backend
- Configuration passed via `wp_localize_script`

#### Phase 2: Direct Backend Access (Current Design)
- React app calls FastAPI backend directly
- API key passed in `X-ACM2-API-Key` header
- WordPress only serves static assets

The variable naming confusion appears to stem from this transition. The original design may have used `acm2Data` as the global variable name, but when rewriting `class-react-app.php`, someone changed it to `acm2Config` without updating the React code.

### Vestigial Code Analysis

**Comment in class-react-app.php:**
```php
// Browser calls backend API directly with API key in header
// Get the user's ACM2 API key for all auth
```

This comment indicates awareness of the direct-access architecture, but the implementation still follows some patterns from the proxy architecture.

**Comment in main.py:**
```python
# Per-user auth is now handled per-route via Depends(get_current_user)
# from .middleware.auth import ApiKeyMiddleware, RateLimitMiddleware
```

The commented-out import shows remnants of an older authentication approach.

### Trailing Slash Issue (Recently Fixed)

A related issue was discovered and fixed during this investigation:

**Problem**: FastAPI's default `redirect_slashes=True` caused 307 redirects when URLs had trailing slashes. During a 307 redirect, browsers do NOT resend custom headers like `X-ACM2-API-Key`.

**Solution**: Added `TrailingSlashMiddleware` and set `redirect_slashes=False`:

```python
class TrailingSlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.scope["path"]
        if path != "/" and path.endswith("/"):
            request.scope["path"] = path.rstrip("/")
        return await call_next(request)

app = FastAPI(
    # ...
    redirect_slashes=False,
)
app.add_middleware(TrailingSlashMiddleware)
```

This fix was applied to prevent authentication headers from being lost during redirects.

---

## Related Issues Discovered During Investigation

### Issue 1: Vite Build Output Configuration

**Previously Identified and Fixed**

The React app's Vite configuration was outputting files with non-standard names that didn't match what the PHP loader expected.

**Old vite.config.js (problematic):**
```javascript
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../assets/react-build',
    rollupOptions: {
      output: {
        entryFileNames: 'acm2-app.js',
        assetFileNames: 'acm2-app[extname]',
      }
    }
  }
})
```

**New vite.config.js (fixed):**
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../assets/react-build',
  }
})
```

The fix allows Vite to use its default naming convention (`index-[hash].js`, `index-[hash].css`) which the PHP loader correctly discovers via glob patterns.

### Issue 2: API URL Configuration

The backend URL was initially configured as an IP address:
```php
define('ACM2_BACKEND_URL', 'https://54.71.183.56');
```

This was changed to use the proper domain:
```php
define('ACM2_BACKEND_URL', 'https://api.apicostx.com');
```

This ensures Cloudflare SSL certificates work correctly.

### Issue 3: Cache Busting

Extensive cache-busting code exists throughout the codebase, indicating a history of caching-related bugs:

**PHP (class-react-app.php):**
```php
// CACHE BUSTER: Use current timestamp to GUARANTEE no caching
$cache_bust = time();

wp_enqueue_style(
    'acm2-react-app',
    $build_url . $css_file,
    [],
    filemtime($css_files[0]) . '.' . $cache_bust
);
```

**FastAPI (main.py):**
```python
class NoCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware to disable ALL caching on API responses.

    CRITICAL: Caching has caused 3 years of "works once, never again" bugs.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        return response
```

---

## Root Cause Analysis

### Primary Root Cause: Incomplete Code Synchronization

The bugs stem from a failure to maintain consistency between the PHP "host" code and the React "guest" code. Specifically:

1. **No Single Source of Truth**: The DOM element ID and global variable name are defined in two separate places with no mechanism to ensure they match.

2. **Development vs Production Mismatch**: The React app works in development (using its own `index.html` with correct IDs) but fails in production (WordPress rendering different IDs).

3. **Silent Failures**: The React code uses defensive patterns (`if (root)`, optional chaining `?.`) that prevent crashes but mask the actual errors.

### Contributing Factors

1. **Architectural Transition**: The system underwent a transition from proxy-based to direct-access architecture, leaving inconsistent artifacts.

2. **Two-Node Deployment**: Having the frontend and backend on separate servers makes end-to-end testing more difficult.

3. **No Integration Tests**: There appear to be no automated tests that verify the WordPress-to-React integration.

4. **Caching Paranoia**: Excessive cache-busting code throughout suggests a history of being burned by caching issues, which may have distracted from fundamental configuration bugs.

---

## Recommended Fixes

### Fix #1: Correct the Global Variable Name in PHP

**File**: `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php`

**Change**:
```php
// BEFORE (line ~90):
wp_localize_script('acm2-react-app', 'acm2Config', [

// AFTER:
wp_localize_script('acm2-react-app', 'acm2Data', [
```

### Fix #2: Correct the DOM Element ID in PHP

**File**: `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php`

**Change**:
```php
// BEFORE (line ~110):
<div id="root"></div>

// AFTER:
<div id="acm2-root"></div>
```

### Complete Fixed Code for render_app_page()

```php
public static function render_app_page() {
    ?>
    <style>
        #wpbody-content { padding: 0 !important; }
        #wpfooter { display: none; }
        .wrap { margin: 0 !important; padding: 0 !important; max-width: none !important; }
        #acm2-root {
            min-height: calc(100vh - 32px);
            background: #0f172a;
        }
    </style>
    <div class="wrap">
        <div id="acm2-root"></div>  <!-- FIXED: was "root" -->
    </div>
    <?php
}
```

### Alternative Fix: Update React to Match PHP

If modifying PHP is not desirable, the React code could be updated:

**main.jsx**:
```javascript
const root = document.getElementById('root');  // Match PHP's "root"
```

**api.js**:
```javascript
const API_BASE = window.acm2Config.apiUrl.replace(/\/$/, '');  // Match PHP's "acm2Config"
```

However, this is **not recommended** because:
1. It requires rebuilding and redeploying the React bundle
2. The PHP code already shows intent to use `acm2-root` (see CSS styles)
3. `acm2Data` is more descriptive than `acm2Config` for runtime data

---

## Verification Steps

After applying the fixes:

### Step 1: Verify PHP Changes

SSH to frontend server and confirm the changes:

```bash
grep -n "acm2Data" /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php
grep -n "acm2-root" /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php
```

Expected output should show `acm2Data` in the `wp_localize_script` call and `acm2-root` in the div.

### Step 2: Restart Apache

```bash
sudo /opt/bitnami/ctlscript.sh restart apache
```

### Step 3: Clear Browser Cache

1. Open Chrome DevTools (F12)
2. Right-click the Refresh button
3. Select "Empty Cache and Hard Reload"

### Step 4: Navigate to ACM2 App Page

1. Go to WordPress Admin → ACM2 → App
2. Open Chrome DevTools Console (F12 → Console tab)
3. Verify no JavaScript errors
4. Check that `window.acm2Data` is defined: `console.log(window.acm2Data)`
5. Check that the root element exists: `console.log(document.getElementById('acm2-root'))`

### Step 5: Verify React Rendering

The page should now show the React application instead of a blank page. The "Your Runs" heading or "Loading runs..." message should appear.

---

## Appendices

### Appendix A: Full Source Code Listings

#### A.1: class-react-app.php (Current - Buggy)

```php
<?php
/**
 * React App Integration Class
 *
 * Loads the React frontend in WordPress admin pages.
 */

class ACM2_React_App {

    public static function init() {
        add_action('admin_menu', [__CLASS__, 'add_admin_pages']);
        add_action('admin_enqueue_scripts', [__CLASS__, 'enqueue_react_app']);
    }

    public static function add_admin_pages() {
        add_submenu_page(
            'acm2-settings',
            'ACM2 App',
            'App',
            'manage_options',
            'acm2-app',
            [__CLASS__, 'render_app_page']
        );
    }

    public static function enqueue_react_app($hook) {
        if (strpos($hook, 'acm2-app') === false) {
            return;
        }

        $build_dir = ACM2_PLUGIN_DIR . 'assets/react-build/assets/';
        $build_url = ACM2_PLUGIN_URL . 'assets/react-build/assets/';

        $js_files = glob($build_dir . 'index-*.js');
        $css_files = glob($build_dir . 'index-*.css');

        if (empty($js_files) || empty($css_files)) {
            return;
        }

        $js_file = basename($js_files[0]);
        $css_file = basename($css_files[0]);

        $cache_bust = time();

        wp_enqueue_style(
            'acm2-react-app',
            $build_url . $css_file,
            [],
            filemtime($css_files[0]) . '.' . $cache_bust
        );

        wp_enqueue_script(
            'acm2-react-app',
            $build_url . $js_file,
            [],
            filemtime($js_files[0]) . '.' . $cache_bust,
            true
        );

        add_filter('script_loader_tag', function($tag, $handle) {
            if ($handle === 'acm2-react-app') {
                return str_replace(' src', ' type="module" src', $tag);
            }
            return $tag;
        }, 10, 2);

        $acm2_api_key = function_exists('acm2_get_user_api_key') ? acm2_get_user_api_key() : '';
        $backend_url = defined('ACM2_BACKEND_URL') ? ACM2_BACKEND_URL : 'http://127.0.0.1:8000';

        // BUG: Uses 'acm2Config' but React expects 'acm2Data'
        wp_localize_script('acm2-react-app', 'acm2Config', [
            'apiUrl' => $backend_url . '/api/v1',
            'nonce' => wp_create_nonce('wp_rest'),
            'currentUser' => wp_get_current_user()->user_login,
            'apiKey' => $acm2_api_key,
        ]);
    }

    public static function render_app_page() {
        ?>
        <style>
            #wpbody-content { padding: 0 !important; }
            #wpfooter { display: none; }
            .wrap { margin: 0 !important; padding: 0 !important; max-width: none !important; }
            #acm2-root {
                min-height: calc(100vh - 32px);
                background: #0f172a;
            }
        </style>
        <div class="wrap">
            <!-- BUG: Uses 'root' but React expects 'acm2-root' -->
            <div id="root"></div>
        </div>
        <?php
    }
}
```

#### A.2: main.jsx (Current)

```javascript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

// Expects 'acm2-root' but PHP provides 'root'
const root = document.getElementById('acm2-root');
if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
```

#### A.3: api.js (Current)

```javascript
/**
 * API Client for ACM2
 *
 * This client calls WordPress REST API endpoints which proxy to ACM2 backend.
 * The WordPress proxy handles authentication and API key management.
 */

// Expects 'acm2Data' but PHP provides 'acm2Config'
const API_BASE = window.acm2Data.apiUrl.replace(/\/$/, '');

class ACM2Client {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-WP-Nonce': window.acm2Data?.nonce || '',
        ...options.headers,
      },
      credentials: 'same-origin',
    });

    if (!response.ok) {
      let errorText = '';
      try {
        errorText = await response.text();
      } catch (e) {
        // ignore
      }

      let message = '';
      try {
        const parsed = errorText ? JSON.parse(errorText) : null;
        message = parsed?.message || parsed?.detail || '';
      } catch (e) {
        // ignore
      }

      if (!message) {
        message = errorText ? errorText.slice(0, 200) : `HTTP ${response.status}`;
      }

      throw new Error(message);
    }

    return response.json();
  }

  async getRuns() {
    return this.request('/runs');
  }

  async getRun(id) {
    return this.request(`/runs/${id}`);
  }

  async createRun(data) {
    return this.request('/runs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getProviderKeys() {
    return this.request('/provider-keys/');
  }

  async saveProviderKey(provider, apiKey) {
    return this.request('/provider-keys/', {
      method: 'POST',
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
  }

  async deleteProviderKey(provider) {
    return this.request(`/provider-keys/${provider}`, {
      method: 'DELETE',
    });
  }
}

export const api = new ACM2Client();
```

### Appendix B: Directory Structure

```
Frontend Server (16.145.206.59)
/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/
├── acm2-integration.php          # Main plugin entry
├── admin/
│   ├── class-react-app.php       # React loader (BUGGY)
│   ├── class-settings-page.php   # Settings UI
│   └── class-provider-keys-page.php
├── assets/
│   ├── provider-keys.css
│   ├── provider-keys.js
│   └── react-build/
│       ├── index.html
│       └── assets/
│           ├── index-BSfwxMAP.js
│           └── index-B-3FEFOe.css
├── includes/
│   └── class-user-sync.php
└── react-app/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── node_modules/
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── styles.css
        ├── components/
        │   └── RunsList.jsx
        └── services/
            └── api.js

Backend Server (54.71.183.56)
C:\devlop\acm2\acm2\app\
├── main.py                    # FastAPI entry
├── api/
│   ├── router.py
│   └── endpoints/
│       ├── health.py
│       ├── provider_keys.py
│       ├── runs.py
│       └── ...
├── auth/
│   ├── middleware.py
│   └── user_registry.py
├── middleware/
│   └── ...
└── config.py
```

### Appendix C: Diagnostic Commands

**Check what React expects vs what PHP provides:**

```bash
# On frontend server
ssh bitnami@16.145.206.59

# Check what global variable PHP sets
grep -n "wp_localize_script" /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php

# Check what div id PHP renders
grep -n "<div id=" /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php

# Check what React expects
grep -n "window.acm2" /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/react-app/src/services/api.js
grep -n "getElementById" /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/react-app/src/main.jsx
```

**Check build output:**
```bash
ls -la /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/assets/react-build/assets/
```

**Check Apache logs:**
```bash
sudo tail -50 /opt/bitnami/apache/logs/error_log
```

**Check WordPress debug log:**
```bash
tail -100 /opt/bitnami/wordpress/wp-content/debug.log
```

---

## Conclusion

The ACM2 React application fails to load due to two simple but critical configuration mismatches between the PHP code that renders the page and the React code that attempts to mount. These bugs are:

1. **Global Variable Mismatch**: PHP uses `acm2Config`, React expects `acm2Data`
2. **DOM Element ID Mismatch**: PHP renders `id="root"`, React expects `id="acm2-root"`

Both fixes require only single-line changes in the PHP file `class-react-app.php`. After applying the fixes and restarting Apache, the React application should load correctly.

---

*Report generated: February 4, 2025*
*Investigation conducted using: SSH access, file system analysis, source code review*
*Backend: FastAPI 2.0.0 on Windows Server*
*Frontend: WordPress 6.x on Bitnami LAMP Stack*

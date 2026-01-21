# Presets Not Loading - Error Report

**Date:** January 16, 2026  
**Error Message:** "Failed to load presets: ApiError: Not Found"  
**Status:** RESOLVED (Jan 20, 2026) - Per-user DB schema drift fixed

---

## Summary

When a user logs into WordPress and navigates to the ACM2 app page, the frontend failed to load presets due to API failures. This prevented users from using the application.

**Update (Jan 20, 2026):** Root cause expanded to include per-user DB schema drift (legacy `runs` table missing `preset_id`), which caused `GET /api/v1/presets` to 500. Fixes now rebuild invalid per-user DBs, auto-seed when `user_meta` is missing, and batch content copy with a per-user seed lock.

---

## Architecture Overview

The system has three main components:

1. **FastAPI Backend** - Runs on `http://127.0.0.1:8000`, serves `/api/v1/*` endpoints
2. **WordPress** - Runs on `http://localhost/wordpress` (Apache port 80)
3. **React Frontend** - Built with Vite, embedded in WordPress admin pages

The WordPress plugin (`acm2-integration`) includes:
- An API proxy class that forwards requests from `/wp-json/acm2/v1/*` to the FastAPI backend
- A React app loader that injects configuration including `apiUrl`

---

## Root Cause Analysis

### What We Determined

The React frontend's API client (`ui/src/api/client.ts`) determines its API base URL like this:

```
- If running on dev ports 5173/5174: Use http://127.0.0.1:8002/api/v1
- Otherwise (production): Use /api/v1
```

When embedded in WordPress (port 80), the relative URL `/api/v1` resolves to `http://localhost/api/v1`. Apache has no route for this path and returns **404 Not Found**.

The WordPress plugin provides a configuration object `window.acm2Config.apiUrl` set to `/wordpress/wp-json/acm2/v1`, which routes through the WordPress REST API proxy to FastAPI. However, the React app was not reading this configuration.

### Evidence

1. **Server logs showed no preset requests** - The FastAPI backend never received a request for `/api/v1/presets`, confirming the request never reached the backend.

2. **Direct Apache request returned 404:**
   ```
   GET http://localhost/api/v1/presets → 404 Not Found (Apache)
   ```

3. **Direct FastAPI request works:**
   ```
   GET http://127.0.0.1:8000/api/v1/presets/ → Requires valid API key, but route exists
   ```

4. **Per-user database is correctly populated:**
   - `data/user_3.db` contains 1 preset ("Default Preset") and 5 content items
   - Seeding completed successfully

---

## Attempted Solutions

### Solution 1: Update API Client to Read WordPress Config

**What we changed:**

Modified `ui/src/api/client.ts` to check for `window.acm2Config.apiUrl` before falling back to the hardcoded paths:

```typescript
const wpConfig = (window as any).acm2Config?.apiUrl
export const API_BASE_URL = wpConfig || (isDev ? 'http://127.0.0.1:8002/api/v1' : '/api/v1')
```

**Result:** FAILED - Same error persists after rebuild.

---

## Why The Fix Didn't Work - Hypotheses

### Hypothesis 1: Build Not Deployed

The Vite build outputs to:
```
xampp/htdocs/wordpress/wp-content/plugins/acm2-integration/assets/react-build/
```

The build completed successfully and created new files (`index-DiAxIlJ1.js`). However, the browser may be caching the old JavaScript bundle.

**To verify:** Hard refresh (Ctrl+F5) or clear browser cache.

### Hypothesis 2: WordPress Config Not Being Injected

The WordPress plugin uses `wp_localize_script()` to inject the config:
```php
wp_localize_script('acm2-react-app', 'acm2Config', [
    'apiUrl' => '/wordpress/wp-json/acm2/v1',
    ...
]);
```

This creates a `<script>` tag with `var acm2Config = {...}` BEFORE the React app loads. If the script order is wrong or the localization fails, `window.acm2Config` would be undefined.

**To verify:** Open browser DevTools console and type `window.acm2Config` to see if it exists.

### Hypothesis 3: React App Not Using WordPress Bundle

There may be two different React builds:
1. The one we just modified and built (`c:\dev\godzilla\ui`)
2. A separate build inside the WordPress plugin folder

The WordPress plugin has its own `react-app` folder with source files. If WordPress is serving a different build than the one we modified, our fix wouldn't apply.

**To verify:** Check if there's a separate build process for `wp-content/plugins/acm2-integration/react-app/`.

### Hypothesis 4: Script Loading Order

The React app script may load before `acm2Config` is defined. The WordPress `wp_localize_script` should inject the config before the script, but if the script has `type="module"` and defers execution differently, the timing could be wrong.

**To verify:** Check the rendered HTML source to see the script order.

---

## What We Know Works

1. **FastAPI backend is running** - Health checks return 200 OK
2. **User creation works** - POST /api/v1/users returns 201 Created
3. **Per-user database seeding works** - user_3.db has correct data
4. **Provider keys endpoint works** - Returns 200 OK after our earlier fix
5. **WordPress proxy class exists** - Code looks correct, routes to 127.0.0.1:8000

---

## Next Steps to Debug

1. **Check browser cache** - Hard refresh or open in incognito mode

2. **Verify acm2Config exists** - In browser console:
   ```javascript
   console.log(window.acm2Config)
   ```

3. **Check network requests** - In DevTools Network tab, filter by "presets" and see:
   - What URL is being called?
   - What response is returned?

4. **Check rendered HTML** - View page source and look for:
   - `acm2Config` variable definition
   - Which JS bundle is loaded

5. **Check WordPress script loading** - The `class-react-app.php` adds `type="module"` via filter - verify this works correctly with `wp_localize_script`

6. **Test the proxy directly** - While logged into WordPress, try:
   ```
   GET http://localhost/wordpress/wp-json/acm2/v1/presets
   ```
   If this works, the proxy is fine and the issue is purely frontend routing.

---

## Files Involved

| File | Purpose | Status |
|------|---------|--------|
| `ui/src/api/client.ts` | Frontend API client | Modified to read wpConfig |
| `wp-content/plugins/acm2-integration/includes/class-api-proxy.php` | WordPress → FastAPI proxy | Unchanged, appears correct |
| `wp-content/plugins/acm2-integration/admin/class-react-app.php` | Loads React app in WP | Unchanged, injects acm2Config |
| `acm2/app/api/routes/presets.py` | Backend presets endpoint | Unchanged |
| `acm2/data/user_3.db` | User's database | Correctly seeded |

---

## Conclusion

The root cause is confirmed: the React app calls `/api/v1/presets` which Apache cannot serve. The fix to read `window.acm2Config.apiUrl` was implemented but the error persists. Further debugging is needed to determine why the fix isn't taking effect - likely browser caching, script loading order, or the WordPress config not being injected properly.

# Frontend Response to Backend Changes

## Overview

Thanks for the detailed summary. The new architecture makes sense. Here are my answers to your questions, based on my analysis of the WordPress plugin code.

---

## Answers to Your Questions

### 1. API Key Storage

**Where:** WordPress MySQL database, table `wp_acm2_api_keys`

**How:** 
- When backend returns the API key during user creation, WordPress stores it **encrypted** using AES-256-CBC
- Encryption key is derived from WordPress's `AUTH_KEY` (in wp-config.php)
- Key is decrypted server-side (PHP) when the React app page loads
- Decrypted key is passed to React via `wp_localize_script()` as a JavaScript variable

**Not stored in:** localStorage, sessionStorage, cookies, or any client-side persistent storage

---

### 2. API Key Format Handling

**Current parsing:** The frontend checks if a key starts with `acm2_` to detect legacy plaintext keys (vs encrypted keys in database).

**Will new format break anything?** NO. The new format `acm2_u{id}_...` still starts with `acm2_` so existing logic will work.

**Relevant code:**
```php
// class-key-encryption.php
if (strpos($encrypted_key, 'acm2_') === 0) {
    return $encrypted_key;  // It's plaintext, return as-is
}
```

This is just for backwards compatibility with old unencrypted keys. The new format passes this check fine.

---

### 3. User Creation Flow

**Current flow:**

1. WordPress user registers (or already exists)
2. WordPress plugin hook `user_register` fires
3. Plugin calls `POST /api/v1/users` **server-to-server** (PHP, not browser)
4. Plugin sends `X-ACM2-Plugin-Secret` header
5. Backend returns API key
6. Plugin encrypts and stores the key in MySQL

**Does frontend ever call `/api/v1/users` directly?** NO. Only WordPress PHP code calls it. The React app never creates users.

**Relevant file:** `includes/class-user-sync.php`

---

### 4. Authentication Headers

**Header used:** `X-ACM2-API-Key`

This matches what you expect. ✅

**Relevant code (React):**
```javascript
// api.js
if (API_KEY) {
    headers['X-ACM2-API-Key'] = API_KEY;
}
```

---

### 5. User ID Usage

**Does frontend extract user_id from API key?** NO.

The frontend treats the API key as an opaque string. It never parses it.

If user info is needed, it would call `/api/v1/users/me`.

**Note:** With your new format, we COULD extract the user_id from the key if needed, but currently we don't.

---

### 6. Error Handling

**Current behavior for 401:**
- React app displays the error message from the response
- No automatic redirect to login
- No token refresh attempt

**Relevant code:**
```javascript
// api.js
if (!response.ok) {
    // ... parse error ...
    throw new Error(message);
}
```

The component catches this and shows it to the user.

**Improvement needed?** Possibly. We could redirect to WordPress login on 401.

---

### 7. Multiple API Keys

**Supported?** NO.

Current implementation assumes one key per user:
- One row per user in `wp_acm2_api_keys` table (unique constraint on `wp_user_id`)
- If backend sends a new key, it overwrites the old one

---

### 8. WordPress Integration

**How API key gets to React:**

1. User loads WordPress admin page (ACM2 App)
2. PHP runs `wp_localize_script()`:
   ```php
   wp_localize_script('acm2-react-app', 'acm2Config', [
       'apiUrl' => $backend_url . '/api/v1',
       'apiKey' => acm2_get_user_api_key($current_user_id),  // Decrypted
   ]);
   ```
3. This creates a JavaScript global variable `window.acm2Config`
4. React reads `window.acm2Config.apiKey`

**No callback URL. No redirect. Key is embedded in the page HTML.**

---

### 9. Current Endpoints Used

Based on the React app code:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/runs` | GET | List user's runs |
| `/runs/{id}` | GET | Get single run |
| `/runs` | POST | Create new run |
| `/provider-keys/` | GET | List configured providers |
| `/provider-keys/` | POST | Save a provider key |
| `/provider-keys/{provider}` | DELETE | Delete a provider key |

**Not currently called by React:**
- `/users` (only WordPress PHP calls this)
- `/users/me` (not currently used, but could be)

---

### 10. State Management for User Data

**Client-side user data:**
- `window.acm2Config.currentUser` - WordPress username (for display)
- `window.acm2Config.apiKey` - API key (for requests)

**No Redux/Zustand.** Simple React component state for runs, etc.

**Session tracking:** Relies entirely on WordPress session. If WordPress session expires, user gets redirected to WordPress login (before React even loads).

**Caching:** None currently. Fresh API calls each time.

---

## Questions for Backend Team

### 1. Plugin Secret Location

You mentioned `.env` has `ACM2_PLUGIN_SECRET`. 

**Question:** Should WordPress read this from:
- A) `wp-config.php` define (I paste it there manually)
- B) WordPress options table (entered via admin UI)
- C) An `.env` file on the WordPress server

Currently I implemented option A. Is that acceptable?

### 2. Existing Users Migration

We have existing WordPress users who were synced to the backend with the OLD key format (`acm2_{random}`).

**Question:** Will these old keys still work? Or do we need to:
- A) Regenerate keys for all existing users
- B) Run a migration on the backend
- C) Something else

### 3. User ID Mismatch

Your new format embeds `user_id` from the backend. WordPress has its own `wordpress_user_id`.

**Question:** When creating a user, does the backend use the `wordpress_user_id` we send as the `user_id`? Or does it generate its own?

Example:
- WordPress user ID: 42
- We send: `{ "wordpress_user_id": 42 }`
- Backend creates user with ID: ???
- API key format: `acm2_u???_...`

If they match (both 42), that's clean. If they're different, we need to track the mapping.

### 4. Health Check Endpoint

Does the backend have a health check endpoint that doesn't require authentication?

Currently the WordPress admin settings page calls `/api/v1/health` to check connectivity. Does this still exist?

### 5. CORS

The React app runs in the browser and calls the backend directly (not proxied through WordPress).

**Question:** Is CORS configured to allow requests from our WordPress domain?

---

## Summary

**Good news:** The frontend is already aligned with most of your architecture:
- ✅ Uses `X-ACM2-API-Key` header
- ✅ Uses `X-ACM2-Plugin-Secret` for user creation
- ✅ User creation is server-to-server only
- ✅ API key stored server-side (encrypted)
- ✅ New key format won't break anything

**Potential issues:**
- ⚠️ Existing users with old format keys
- ⚠️ User ID mapping (WordPress ID vs Backend ID)

---

## Next Steps

Once you answer my questions, I can:
1. Update the key format detection if needed
2. Add user ID extraction from key (if useful)
3. Handle migration of existing users
4. Test the full flow end-to-end

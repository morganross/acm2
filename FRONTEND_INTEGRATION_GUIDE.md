# ACM2 Frontend Integration Guide

> **Purpose**: This document is for developers (or AI assistants) working on the WordPress/frontend side of ACM2 who need to integrate with the backend authentication system.

---

## What is ACM2?

ACM2 is a multi-user AI research platform with two main components:

| Component | Stack | Location | Purpose |
|-----------|-------|----------|---------|
| **Frontend** | WordPress + React | Bitnami (Linux VM) | User management, UI, subscription handling |
| **Backend** | FastAPI + Python | Windows machine | AI processing, document analysis, research runs |

Users log into WordPress, then the React app (embedded in WordPress) communicates directly with the backend API.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER'S BROWSER                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  WordPress Page                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │  React App (embedded)                                        │    │   │
│  │  │  - Sends X-ACM2-API-Key header on all backend requests      │    │   │
│  │  │  - Gets API key from wp_localize_script() on page load      │    │   │
│  │  └──────────────────────────┬──────────────────────────────────┘    │   │
│  └─────────────────────────────┼───────────────────────────────────────┘   │
└────────────────────────────────┼───────────────────────────────────────────┘
                                 │
                                 │ HTTPS (direct, not proxied)
                                 │ Header: X-ACM2-API-Key: acm2_xxx...
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI on Windows)                                               │
│                                                                             │
│  data/master.db (SQLite) ─── users, api_keys tables                        │
│  data/user_1.db (SQLite) ─── presets, runs, documents (user 1)             │
│  data/user_2.db (SQLite) ─── presets, runs, documents (user 2)             │
│  ...                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Two Types of Keys

| Key Type | Format | Purpose | Who Uses It |
|----------|--------|---------|-------------|
| **Plugin Secret** | `sk_plugin_Kx7mP9qR...` | Authorizes WordPress to create users on backend | WordPress plugin only |
| **User API Key** | `acm2_Kx7mP9qR2wN5...` | Authorizes React app to call backend APIs | React app (per user) |

---

## Authentication Flow

### 1. User Creation (WordPress → Backend)

When a WordPress user first activates ACM2:

```
WordPress Plugin                              Backend
      │                                           │
      │  POST /api/v1/users                       │
      │  Headers:                                 │
      │    X-ACM2-Plugin-Secret: sk_plugin_xxx    │
      │  Body:                                    │
      │    { "username": "bob",                   │
      │      "email": "bob@example.com",          │
      │      "wordpress_user_id": 42 }            │
      │──────────────────────────────────────────►│
      │                                           │
      │◄──────────────────────────────────────────│
      │  Response:                                │
      │    { "user_id": 6,                        │
      │      "api_key": "acm2_Kx7mP9qR..." }      │
      │                                           │
      │  WordPress encrypts & stores the key      │
      │  in wp_usermeta                           │
```

### 2. API Calls (React → Backend)

On every request from the React app:

```
React App                                     Backend
      │                                           │
      │  GET /api/v1/runs                         │
      │  Headers:                                 │
      │    X-ACM2-API-Key: acm2_Kx7mP9qR...       │
      │──────────────────────────────────────────►│
      │                                           │
      │  Backend validates key, opens user's DB   │
      │                                           │
      │◄──────────────────────────────────────────│
      │  Response: [{ run data... }]              │
```

---

## Required Frontend Changes

### 1. Plugin Activation: Generate Plugin Secret

```php
/**
 * Generate plugin secret on activation.
 * This secret must be copied to the backend .env file.
 */
function acm2_activate() {
    if (!get_option('acm2_plugin_secret')) {
        $secret = 'sk_plugin_' . bin2hex(random_bytes(32));
        update_option('acm2_plugin_secret', $secret);
    }
}
register_activation_hook(__FILE__, 'acm2_activate');
```

### 2. Admin Settings: Display Secret for Copying

```php
/**
 * Display the plugin secret in admin settings.
 * Admin must copy this to backend .env as ACM2_PLUGIN_SECRET=xxx
 */
function acm2_render_settings_page() {
    $secret = get_option('acm2_plugin_secret');
    ?>
    <div class="wrap">
        <h1>ACM2 Settings</h1>
        
        <div class="notice notice-info">
            <p><strong>Backend Configuration Required</strong></p>
            <p>Add this line to your backend <code>.env</code> file:</p>
            <pre style="background: #f0f0f0; padding: 10px; display: inline-block;">
ACM2_PLUGIN_SECRET=<?php echo esc_html($secret); ?></pre>
        </div>
        
        <!-- rest of settings... -->
    </div>
    <?php
}
```

### 3. User Creation: Include Plugin Secret Header

```php
/**
 * Create a user on the backend when they activate ACM2.
 */
function acm2_create_backend_user($wp_user_id) {
    $user = get_userdata($wp_user_id);
    $backend_url = get_option('acm2_backend_url');
    $plugin_secret = get_option('acm2_plugin_secret');
    
    $response = wp_remote_post($backend_url . '/api/v1/users', [
        'timeout' => 30,
        'headers' => [
            'Content-Type' => 'application/json',
            'X-ACM2-Plugin-Secret' => $plugin_secret,  // REQUIRED
        ],
        'body' => json_encode([
            'username' => $user->user_login,
            'email' => $user->user_email,
            'wordpress_user_id' => $wp_user_id,
        ]),
    ]);
    
    if (is_wp_error($response)) {
        error_log('ACM2: Failed to create backend user: ' . $response->get_error_message());
        return false;
    }
    
    $status = wp_remote_retrieve_response_code($response);
    $body = json_decode(wp_remote_retrieve_body($response), true);
    
    if ($status === 201 && isset($body['api_key'])) {
        // Encrypt and store the API key
        $encrypted = ACM2_Key_Encryption::encrypt($body['api_key']);
        update_user_meta($wp_user_id, 'acm2_api_key_enc', $encrypted);
        update_user_meta($wp_user_id, 'acm2_user_id', $body['user_id']);
        return true;
    }
    
    error_log('ACM2: Backend returned status ' . $status . ': ' . print_r($body, true));
    return false;
}
```

### 4. Key Encryption Class

```php
/**
 * Encrypts/decrypts API keys using WordPress AUTH_KEY.
 * Keys are stored encrypted in wp_usermeta, decrypted only when needed.
 */
class ACM2_Key_Encryption {
    
    /**
     * Encrypt an API key for storage.
     * Uses AES-256-CBC with AUTH_KEY from wp-config.php.
     */
    public static function encrypt($raw_key) {
        $key = hash('sha256', AUTH_KEY, true);  // 32-byte key
        $iv = random_bytes(16);                  // Random IV for each encryption
        $encrypted = openssl_encrypt($raw_key, 'aes-256-cbc', $key, 0, $iv);
        return base64_encode($iv . $encrypted);  // IV prepended for decryption
    }
    
    /**
     * Decrypt an API key for use.
     */
    public static function decrypt($encrypted_key) {
        if (empty($encrypted_key)) {
            return null;
        }
        $key = hash('sha256', AUTH_KEY, true);
        $data = base64_decode($encrypted_key);
        $iv = substr($data, 0, 16);
        $encrypted = substr($data, 16);
        return openssl_decrypt($encrypted, 'aes-256-cbc', $key, 0, $iv);
    }
}
```

### 5. Key Retrieval for React

```php
/**
 * Get decrypted API key for a user.
 */
function acm2_get_user_api_key($wp_user_id) {
    $encrypted = get_user_meta($wp_user_id, 'acm2_api_key_enc', true);
    return ACM2_Key_Encryption::decrypt($encrypted);
}

/**
 * Pass configuration to React app via wp_localize_script.
 */
function acm2_enqueue_react_app() {
    $user_id = get_current_user_id();
    
    wp_enqueue_script('acm2-react', /* script URL */);
    
    wp_localize_script('acm2-react', 'acm2Config', [
        'backendUrl' => get_option('acm2_backend_url'),
        'apiKey' => acm2_get_user_api_key($user_id),  // Decrypted for React
        'userId' => get_user_meta($user_id, 'acm2_user_id', true),
    ]);
}
add_action('wp_enqueue_scripts', 'acm2_enqueue_react_app');
```

---

## React Side (No Changes Needed)

React already receives the API key via `window.acm2Config.apiKey` and includes it in requests:

```javascript
// This should already exist in your React app
const response = await fetch(`${acm2Config.backendUrl}/api/v1/runs`, {
    headers: {
        'X-ACM2-API-Key': acm2Config.apiKey,
        'Content-Type': 'application/json',
    },
});
```

---

## Exploring the Codebase

### Backend (FastAPI/Python)

| File | Purpose |
|------|---------|
| `acm2/app/db/master.py` | Backend.master SQLite database manager (users, api_keys) |
| `acm2/app/auth/middleware.py` | Authentication middleware (validates X-ACM2-API-Key) |
| `acm2/app/auth/api_keys.py` | Key generation and validation (bcrypt) |
| `acm2/app/api/routes/users.py` | POST /api/v1/users endpoint |
| `acm2/app/config.py` | Settings including ACM2_PLUGIN_SECRET |
| `acm2/BACKEND_MASTER_DB_PLAN.md` | Detailed architecture documentation |

### Frontend (WordPress/React)

To explore the WordPress plugin, look for:
- Main plugin file (usually `acm2.php` or similar)
- Admin settings page
- User creation hooks
- Script enqueuing for React

---

## Testing the Integration

### 1. Generate and sync plugin secret

```bash
# On WordPress: Activate plugin, copy secret from admin page
# On Backend: Add to .env file
ACM2_PLUGIN_SECRET=sk_plugin_xxx...
```

### 2. Test user creation

```bash
curl -X POST https://your-backend/api/v1/users \
  -H "Content-Type: application/json" \
  -H "X-ACM2-Plugin-Secret: sk_plugin_xxx..." \
  -d '{"username": "testuser", "email": "test@example.com", "wordpress_user_id": 1}'
```

Expected response:
```json
{
  "user_id": 1,
  "username": "testuser", 
  "email": "test@example.com",
  "api_key": "acm2_Kx7mP9qR2wN5vB8cD3fG...",
  "message": "User created successfully"
}
```

### 3. Test API authentication

```bash
curl https://your-backend/api/v1/users/me \
  -H "X-ACM2-API-Key: acm2_Kx7mP9qR2wN5vB8cD3fG..."
```

---

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 401 on user creation | Missing/wrong plugin secret | Check X-ACM2-Plugin-Secret header matches .env |
| 500 on user creation | Plugin secret not configured | Add ACM2_PLUGIN_SECRET to backend .env |
| 401 on API calls | Invalid user key | Re-create user or check encryption/decryption |
| Key decryption fails | AUTH_KEY changed | Keys encrypted with old AUTH_KEY can't be recovered |

---

## Questions?

Read `BACKEND_MASTER_DB_PLAN.md` for the full architecture documentation including database schemas, authentication flow diagrams, and implementation details.

# ACM2 Production Architecture

## Overview

**Core Principle:** Users bring their own LLM provider API keys. ACM2 provides the orchestration platform.

**Why WordPress?** Building a user system from scratch (registration, login, password reset, email verification, 2FA, payment processing, subscriptions) would take **months of development**. WordPress provides all of this **out of the box** - it's actually the **simplest** way to handle users.

The application uses **API key authentication**:
- Each user gets an **ACM2 API key** (identifies the user/account)
- Each user stores their own **LLM provider keys** (OpenAI, Google, Anthropic, etc.)
- Users can access ACM2 via:
  - **WordPress website** (embeds React UI) - Main interface for most users
  - **Direct API calls** (Python SDK, curl, custom apps) - For developers

**Key Difference from Traditional SaaS:**
- We DON'T charge per LLM API call
- We DON'T use our LLM credits
- Users pay LLM providers directly
- We charge for the platform/orchestration

---

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                    USER'S LLM PROVIDER KEYS                        │
│                     (stored per ACM2 account)                      │
│                                                                    │
│  OpenAI:     sk-proj-...                                          │
│  Google:     AIzaSy...                                            │
│  Anthropic:  sk-ant-...                                           │
│  [User pays OpenAI/Google directly, not us]                       │
└────────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────────┐
│                        ACM2 API KEY                                │
│                    (identifies user account)                       │
│                                                                    │
│  acm2_abc123xyz456...                                             │
│  [User pays us for platform access, not LLM usage]               │
└────────────────────────────────────────────────────────────────────┘
                              ↓
                 ┌────────────┴─────────────┐
                 │                          │
        ┌────────▼────────┐      ┌─────────▼──────────┐
        │  WordPress Site │      │  Direct API Access │
        │                 │      │                    │
        │  Embeds React   │      │  Python SDK / curl │
        │  UI with user's │      │  Custom apps       │
        │  ACM2 API key   │      │                    │
        └─────────────────┘      └────────────────────┘
                 │                          │
                 └────────────┬─────────────┘
                              ↓
                    ┌──────────────────┐
                    │  ACM2 FastAPI    │
                    │  Backend         │
                    │                  │
                    │  1. Validate key │
                    │  2. Get user's   │
                    │     LLM keys     │
                    │  3. Orchestrate  │
                    └──────────────────┘
```

---

## Components

### WordPress Website (Primary User Interface)

**Purpose:** Handle everything users need (the simple way)

**WordPress provides for FREE:**
- ✅ User registration & login
- ✅ Password reset & email verification
- ✅ Session management (secure cookies)
- ✅ Payment processing (WooCommerce/Easy Digital Downloads)
- ✅ Subscription management
- ✅ Email notifications
- ✅ 2FA plugins available
- ✅ GDPR compliance plugins
- ✅ Marketing pages & blog
- ✅ SEO optimization
- ✅ Community forums (bbPress)

**What YOU build (simple plugin):**
- Store user's ACM2 API key in user meta
- Proxy API requests to ACM2 backend
- Embed React UI in WordPress page
- ~500 lines of PHP code

**WordPress handles:**
- Location: `yoursite.com`
- Everything user-facing except the ACM2 application itself

### React Frontend (Embedded in WordPress)

**Purpose:** The actual ACM2 application UI

- Served by: WordPress (built React app copied to plugin folder)
- Auth: WordPress session cookie (transparent to React)
- API calls: Go through WordPress proxy endpoints
- Location: `yoursite.com/dashboard` (WordPress page with `[acm2_app]` shortcode)

**Why embedded?**
- User never leaves WordPress domain
- No CORS issues
- WordPress menu/header/footer stay visible
- Single sign-on experience

### FastAPI Backend (Uvicorn - API Only)

**Purpose:** The actual ACM2 orchestration engine

- Handles: All application logic (multi-LLM orchestration)
- Auth: API keys only (validated against master.db)
- Uses: User's stored LLM provider keys for API calls
- Location: `localhost:8199` (internal only, proxied through Apache/Nginx)
- Does NOT serve static files (WordPress does that)

**Why separate?**
- Python for complex orchestration logic
- Async/await for concurrent LLM calls
- FastAPI's automatic API docs
- Can be scaled independently

---

## Authentication & Execution Flow

### Single Authentication Method: API Key

**Setup Phase:**
```
1. User signs up → receives ACM2 API key (acm2_abc123...)
2. User navigates to ACM2 Settings page
3. User enters their LLM provider keys:
   - OpenAI API Key: sk-proj-...
   - Google API Key: AIzaSy...
   - Anthropic API Key: sk-ant-...
4. Keys are encrypted and stored in user's database
```

**Execution Phase:**
```
┌─────────────┐
│  User/Site  │  Makes request with ACM2 API key
└──────┬──────┘
       │  POST /api/v1/runs
       │  X-ACM2-API-Key: acm2_abc123
       │  { "prompt": "...", "models": ["gpt-4", "claude-3"] }
       ↓
┌──────────────────────────────────────────────────────┐
│  ACM2 API Backend                                    │
│                                                      │
│  Step 1: Validate API Key                           │
│    → Query: SELECT user_id FROM api_keys            │
│              WHERE key_hash = hash('acm2_abc123')   │
│    → Result: user_id = 42                           │
│                                                      │
│  Step 2: Get User's Provider Keys                   │
│    → Connect to user_42.db                          │
│    → Query: SELECT provider, api_key_encrypted      │
│              FROM provider_keys WHERE user_id = 42  │
│    → Decrypt keys:                                  │
│       openai_key = "sk-proj-..."                    │
│       anthropic_key = "sk-ant-..."                  │
│                                                      │
│  Step 3: Execute Multi-LLM Orchestration            │
│    → Call OpenAI using user's sk-proj-...           │
│    → Call Anthropic using user's sk-ant-...         │
│    → Aggregate, compare, evaluate results           │
│                                                      │
│  Step 4: Return Results                             │
│    → JSON response with comparison data             │
└──────────────────────────────────────────────────────┘
       │
       │  Response: { "results": [...], "cost": "$0.42" }
       ↓
┌─────────────┐
│  User/Site  │  Receives results
└─────────────┘
```

**Two Access Paths:**

**Option A: Via WordPress Website (Secure Proxy Pattern)**
```
1. Setup:
   - User's ACM2 API key stored securely in WordPress database
   - Key NEVER exposed to browser/frontend

2. Request Flow:
   Browser → WordPress Backend → ACM2 API
   
   a) User's browser makes request to WordPress endpoint
      POST https://yoursite.com/wp-json/acm2/v1/runs
      Cookie: wordpress_logged_in_xyz (WordPress session)
      Body: { "prompt": "...", "models": [...] }
   
   b) WordPress validates session → identifies user
      if (!is_user_logged_in()) return 401;
      $user_id = get_current_user_id();
   
   c) WordPress retrieves user's ACM2 API key from database
      $acm2_key = get_user_meta($user_id, 'acm2_api_key', true);
   
   d) WordPress proxies request to ACM2 API
      POST https://acm2.com/api/v1/runs
      X-ACM2-API-Key: {$acm2_key}  ← FROM WORDPRESS DB, NOT BROWSER
      Body: { "prompt": "...", "models": [...] }
   
   e) ACM2 API processes request (using user's provider keys)
   
   f) WordPress returns results to browser
      Response: { "results": [...] }

3. Security Benefits:
   - ✅ ACM2 API key NEVER exposed to browser
   - ✅ WordPress session validates user identity
   - ✅ User can't steal/see their own ACM2 key
   - ✅ Key can be rotated server-side without user knowing
```

**Option B: Direct API Access**
```
1. User stores ACM2 API key in their code
2. User makes direct API calls:
   curl -H "X-ACM2-API-Key: acm2_abc123" \
        https://acm2.com/api/v1/runs
3. ACM2 looks up provider keys and executes
4. Results returned as JSON
```

**Payment Flow:**
```
User pays TWO entities:
├─ LLM Providers (OpenAI, Google, etc.)
│  └─ Direct charges for API usage
│  └─ User's credit card on file with them
│
└─ ACM2 (us)
   └─ Platform subscription/usage fee
   └─ Via WordPress/Stripe checkout
```

---

## Database Architecture

### Per-User Database Isolation
```
/data/
  master.db           ← User accounts, ACM2 API keys, billing
  user_123.db         ← Alice's runs, documents, settings, LLM keys
  user_456.db         ← Bob's runs, documents, settings, LLM keys
  user_789.db         ← Carol's runs, documents, settings, LLM keys
```

### Benefits
- **True isolation**: No risk of data leaking between users
- **Easy backups**: Export one user's data by copying their file
- **Easy deletion**: Delete user = delete their file
- **Performance**: Each database stays small
- **Compliance**: Easier for GDPR, data residency requirements
- **Security**: Each user's LLM keys isolated in their own database

### Master Database Schema (`master.db`)
```sql
-- User accounts
users (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP,
  database_file TEXT,  -- e.g., "user_123.db"
  subscription_status TEXT,  -- active, cancelled, etc.
  wordpress_user_id INTEGER  -- optional link to WordPress
)

-- ACM2 API keys (for authentication)
api_keys (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  key_hash TEXT UNIQUE NOT NULL,  -- hashed acm2_abc123...
  key_prefix TEXT,  -- First 8 chars for display: "acm2_abc"
  name TEXT,  -- User-friendly name: "WordPress Site"
  created_at TIMESTAMP,
  last_used_at TIMESTAMP,
  expires_at TIMESTAMP,
  revoked_at TIMESTAMP
)

-- Usage tracking for billing
usage_logs (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  timestamp TIMESTAMP,
  endpoint TEXT,  -- /api/v1/runs
  run_id TEXT,
  provider_costs JSON  -- {"openai": 0.42, "anthropic": 0.15}
)
```

### Per-User Database Schema (`user_123.db`)
```sql
-- LLM Provider API keys (encrypted at rest)
provider_keys (
  id INTEGER PRIMARY KEY,
  provider TEXT NOT NULL,  -- 'openai', 'google', 'anthropic'
  api_key_encrypted BLOB NOT NULL,  -- encrypted with master key
  api_key_prefix TEXT,  -- First 7 chars for display: "sk-proj"
  label TEXT,  -- User label: "My OpenAI Key"
  created_at TIMESTAMP,
  last_used_at TIMESTAMP,
  is_active BOOLEAN DEFAULT 1
)

-- Application data
runs (...)
documents (...)
presets (...)
evaluation_criteria (...)
-- etc. (existing ACM2 tables)
```

**Security Notes:**
- ACM2 API keys are hashed (bcrypt/argon2) - we can't see them
- Provider keys are encrypted (AES-256) - we can decrypt for use, but not exposed to user browsing
- Master encryption key stored in environment variable, not in database
- Each user's LLM keys isolated in their own database file

---

## 🔑 Key Architectural Difference

### Traditional SaaS Model (ChatGPT, Claude, etc.)
```
User → Platform (charges per token) → LLM Provider (platform's keys)

Cost Flow:
User pays Platform ($20/month + usage)
Platform pays OpenAI (with their corporate keys)
```

**Limitations:**
- ❌ Expensive: Platform marks up LLM costs
- ❌ Rate limits: Shared across all users
- ❌ No control: Can't use your own credits
- ❌ Vendor lock: Can't take your keys elsewhere

### ACM2 Model (Our Architecture)
```
User → ACM2 (platform fee) ─┐
                            ↓ (uses user's keys)
                        LLM Providers (user's keys)

Cost Flow:
User pays ACM2 (platform subscription)
User pays OpenAI directly (with their own keys)
User pays Google directly (with their own keys)
```

**Benefits:**
- ✅ Transparent: User sees exact LLM costs
- ✅ Own rate limits: User's own API quotas
- ✅ Flexibility: Can use credits, enterprise pricing
- ✅ Portable: User owns their keys
- ✅ Privacy: We never see the prompts (keys used client-side)

**Example Cost Comparison:**
```
Traditional SaaS:
- Platform: $50/month
- Usage: 1M tokens = $60 (marked up from $40)
- Total: $110/month

ACM2 Model:
- ACM2: $20/month (platform fee)
- OpenAI: $40 (direct billing, your own account)
- Total: $60/month (save $50!)
```

---

## Server Architecture

### Development
```
Uvicorn (single process, --reload) → FastAPI → SQLite
```

### Production
```
Uvicorn (multiple workers) → FastAPI → SQLite per user
```

### Production with Scale
```
Load Balancer → Multiple Uvicorn instances → Shared storage for SQLite files
```

### Optional: Add Nginx
Only needed if you want:
- SSL termination (or use Cloudflare instead)
- Static file serving (or use CDN)
- Rate limiting at edge
- Multiple apps on one server

---

## Hosting Setup

### Option 1: Subdomain Split
```
yoursite.com          →  WordPress (Apache)
app.yoursite.com      →  React frontend (Uvicorn or CDN)
api.yoursite.com      →  FastAPI (Uvicorn)
```

### Option 2: Path-Based (Apache Proxy)
```
yoursite.com/*        →  WordPress
yoursite.com/app/*    →  Proxy to Uvicorn (frontend)
yoursite.com/api/*    →  Proxy to Uvicorn (API)
```

---

## Security Architecture

### WordPress Proxy Implementation (Secure Pattern)

**WordPress Plugin Code (PHP):**
```php
// Register WordPress REST API endpoint
add_action('rest_api_init', function() {
    register_rest_route('acm2/v1', '/runs', [
        'methods' => 'POST',
        'callback' => 'acm2_proxy_to_api',
        'permission_callback' => 'is_user_logged_in'  // Require WP login
    ]);
});

function acm2_proxy_to_api($request) {
    // 1. Validate WordPress session
    $user_id = get_current_user_id();
    if (!$user_id) {
        return new WP_Error('unauthorized', 'Not logged in', ['status' => 401]);
    }
    
    // 2. Get user's ACM2 API key from database (never exposed to browser)
    $acm2_api_key = get_user_meta($user_id, 'acm2_api_key', true);
    if (empty($acm2_api_key)) {
        return new WP_Error('no_api_key', 'ACM2 API key not configured', ['status' => 400]);
    }
    
    // 3. Proxy request to ACM2 API
    $response = wp_remote_post('https://acm2.com/api/v1/runs', [
        'headers' => [
            'X-ACM2-API-Key' => $acm2_api_key,  // ← FROM DB, NOT BROWSER
            'Content-Type' => 'application/json'
        ],
        'body' => json_encode($request->get_json_params()),
        'timeout' => 60
    ]);
    
    // 4. Return response to browser
    if (is_wp_error($response)) {
        return new WP_Error('api_error', $response->get_error_message(), ['status' => 502]);
    }
    
    $body = wp_remote_retrieve_body($response);
    $status = wp_remote_retrieve_response_code($response);
    
    return new WP_REST_Response(json_decode($body), $status);
}
```

**React Frontend Code (JavaScript):**
```javascript
// React makes requests to WORDPRESS, not directly to ACM2
async function createRun(prompt, models) {
    const response = await fetch('/wp-json/acm2/v1/runs', {
        method: 'POST',
        credentials: 'include',  // Send WordPress session cookie
        headers: {
            'Content-Type': 'application/json'
            // NO API KEY HERE! WordPress adds it server-side
        },
        body: JSON.stringify({ prompt, models })
    });
    
    return response.json();
}
```

**Security Flow:**
```
┌──────────────────────────────────────────────────────────────┐
│  Browser (React Frontend)                                   │
│                                                              │
│  ❌ No ACM2 API key in JavaScript                           │
│  ❌ No API key in localStorage/sessionStorage                │
│  ❌ No API key in HTML data attributes                       │
│  ✅ Only has WordPress session cookie                       │
└──────────────────────────────────────────────────────────────┘
                        ↓
          POST /wp-json/acm2/v1/runs
          Cookie: wordpress_logged_in_xyz
                        ↓
┌──────────────────────────────────────────────────────────────┐
│  WordPress Backend (PHP)                                     │
│                                                              │
│  1. Validates WordPress session cookie                       │
│  2. Gets user_id from session                               │
│  3. Queries database for user's ACM2 key                    │
│  4. Makes request to ACM2 API with key                      │
└──────────────────────────────────────────────────────────────┘
                        ↓
          POST https://acm2.com/api/v1/runs
          X-ACM2-API-Key: acm2_abc123 (from WordPress DB)
                        ↓
┌──────────────────────────────────────────────────────────────┐
│  ACM2 API (FastAPI)                                          │
│                                                              │
│  1. Validates acm2_abc123 → user_id = 42                    │
│  2. Gets user's provider keys from user_42.db               │
│  3. Executes multi-LLM workflow                             │
│  4. Returns results                                          │
└──────────────────────────────────────────────────────────────┘
```

### Security Best Practices

**1. API Key Storage:**
```sql
-- WordPress database (wp_usermeta table)
INSERT INTO wp_usermeta (user_id, meta_key, meta_value)
VALUES (42, 'acm2_api_key', 'acm2_abc123xyz');

-- Key is:
✅ Stored in WordPress database (server-side only)
✅ Never sent to browser
✅ Only accessible by WordPress PHP backend
❌ Never in JavaScript/HTML/cookies
```

**2. WordPress Session Security:**
```php
// WordPress automatically handles:
// - HTTP-only cookies (JavaScript can't access)
// - Secure flag (HTTPS only)
// - SameSite=Lax (CSRF protection)
// - Session timeout (default: 2 weeks, or 2 days for "remember me")

// Example WordPress auth cookie:
wordpress_logged_in_xyz = user|1704672000|token|hmac
// ↑ HttpOnly, Secure, not accessible from JavaScript
```

**3. Rate Limiting:**
```php
// Implement rate limiting in WordPress proxy
function acm2_proxy_to_api($request) {
    $user_id = get_current_user_id();
    
    // Check rate limit
    $rate_limit_key = "acm2_rate_limit_{$user_id}";
    $requests = get_transient($rate_limit_key) ?: 0;
    
    if ($requests >= 100) {  // 100 requests per hour
        return new WP_Error('rate_limit', 'Too many requests', ['status' => 429]);
    }
    
    set_transient($rate_limit_key, $requests + 1, HOUR_IN_SECONDS);
    
    // ... continue with proxy
}
```

**4. CORS Configuration:**
```php
// Only needed if React app on different domain
add_action('rest_api_init', function() {
    remove_filter('rest_pre_serve_request', 'rest_send_cors_headers');
    add_filter('rest_pre_serve_request', function($value) {
        // Only allow requests from your WordPress site
        $origin = get_http_origin();
        if ($origin === 'https://yoursite.com') {
            header('Access-Control-Allow-Origin: https://yoursite.com');
            header('Access-Control-Allow-Credentials: true');
        }
        return $value;
    });
});
```

### Attack Prevention

**Attack #1: Stealing API key from browser**
```
❌ Attacker opens DevTools → No API key found
✅ Key stored in WordPress DB, never sent to browser
```

**Attack #2: CSRF (Cross-Site Request Forgery)**
```
❌ Attacker tries to make request from evil.com
✅ WordPress nonce validation required
✅ SameSite cookie prevents cross-origin requests
```

**Attack #3: Session hijacking**
```
❌ Attacker steals WordPress session cookie
✅ HTTPS prevents cookie sniffing
✅ HTTP-only prevents XSS theft
✅ Short session timeout limits exposure
```

**Attack #4: Impersonating another user**
```
❌ Attacker tries to use someone else's ACM2 key
✅ WordPress validates session before retrieving key
✅ Each user can only access their own key
```

**Attack #5: API key enumeration**
```
❌ Attacker tries to guess API keys
✅ Keys are long random strings (acm2_base62_random_32chars)
✅ Rate limiting prevents brute force
✅ Failed attempts logged
```

### Alternative: Short-Lived Tokens (Advanced)

For even better security, WordPress can issue short-lived tokens:

```php
// WordPress generates temporary token (expires in 5 minutes)
function acm2_get_temp_token($request) {
    $user_id = get_current_user_id();
    if (!$user_id) return new WP_Error('unauthorized', 'Not logged in', ['status' => 401]);
    
    // Generate short-lived token
    $token = bin2hex(random_bytes(32));
    $expires = time() + 300;  // 5 minutes
    
    // Store mapping: token → user's ACM2 key
    set_transient("acm2_token_{$token}", [
        'user_id' => $user_id,
        'acm2_key' => get_user_meta($user_id, 'acm2_api_key', true)
    ], 300);
    
    return ['token' => $token, 'expires_in' => 300];
}

// React uses temporary token for direct API calls
const { token } = await fetch('/wp-json/acm2/v1/token').then(r => r.json());

fetch('https://acm2.com/api/v1/runs', {
    headers: { 'X-ACM2-Temp-Token': token }
});

// ACM2 API validates temp token with WordPress
// (more complex, but allows direct API calls without proxy)
```

**Recommendation:** Start with WordPress proxy (simpler, secure). Add temp tokens later if needed for performance.

---

## Security Considerations

### Session Security
- Sessions stored server-side (WordPress)
- Cookie is HTTP-only, Secure, SameSite
- Session expires after inactivity

### API Key Security
- Keys stored hashed in ACM2 master database (bcrypt/argon2)
- WordPress stores keys in plaintext (but server-side only, never exposed)
- Keys can be revoked
- Rate limiting per key
- Keys never logged

### Database Security
- Each user's database is a separate file
- User can only access their own database
- API validates user before connecting to their database

---

## Implementation Roadmap

### Phase 1: Core Multi-User Support (Week 1-2)

**Goal:** Enable multiple users with isolated databases

**Tasks:**
1. **Master Database Setup**
   - Create master.db schema (users, api_keys, usage_logs)
   - Implement user registration endpoint
   - Implement API key generation and validation

2. **Per-User Database Isolation**
   - Implement database router (connects to user_X.db based on API key)
   - Migrate existing single database to per-user model
   - Add database creation on user signup

3. **API Key Authentication**
   ```python
   # Implement middleware
   @app.middleware("http")
   async def auth_middleware(request: Request, call_next):
       api_key = request.headers.get("X-ACM2-API-Key")
       if not api_key:
           return JSONResponse({"error": "API key required"}, status_code=401)
       
       user = await validate_api_key(api_key)
       if not user:
           return JSONResponse({"error": "Invalid API key"}, status_code=401)
       
       request.state.user = user
       request.state.db_path = f"user_{user.id}.db"
       return await call_next(request)
   ```

4. **Testing**
   - Create test users
   - Verify database isolation
   - Test API key validation

**Deliverable:** Multiple users can use ACM2 with their own API keys and isolated data

---

### Phase 2: Provider Key Management (Week 3)

**Goal:** Users can store and manage their LLM provider keys

**Tasks:**
1. **Provider Keys Table**
   ```sql
   CREATE TABLE provider_keys (
       id INTEGER PRIMARY KEY,
       user_id INTEGER,
       provider TEXT,  -- 'openai', 'google', 'anthropic'
       api_key_encrypted BLOB,
       api_key_prefix TEXT,
       label TEXT,
       created_at TIMESTAMP,
       last_used_at TIMESTAMP,
       is_active BOOLEAN DEFAULT 1
   );
   ```

2. **Encryption Implementation**
   - Install cryptography library: `pip install cryptography`
   - Generate master encryption key (store in env var)
   - Implement encrypt/decrypt functions using Fernet (AES-256)

3. **Settings API Endpoints**
   ```python
   POST   /api/v1/settings/provider-keys  # Add key
   GET    /api/v1/settings/provider-keys  # List keys (masked)
   DELETE /api/v1/settings/provider-keys/{id}  # Remove key
   PUT    /api/v1/settings/provider-keys/{id}  # Update label
   ```

4. **Update Adapters**
   - Modify FPF/GPTR adapters to use user's keys instead of global keys
   - Fetch keys from user's database before making LLM calls
   - Handle missing keys gracefully

5. **Settings UI**
   - Create Settings page in React
   - Provider key management interface
   - Test connection button for each provider

**Deliverable:** Users can add their own OpenAI, Google, Anthropic keys

---

### Phase 3: WordPress Integration (Week 4)

**Goal:** WordPress website can embed ACM2 securely

**Tasks:**
1. **WordPress Plugin Development**
   - Create ACM2 WordPress plugin
   - User settings page (view/regenerate ACM2 API key)
   - Store ACM2 API key in user meta

2. **WordPress Proxy Endpoints**
   ```php
   // Proxy all ACM2 API calls through WordPress
   register_rest_route('acm2/v1', '/(?P<endpoint>.*)', [
       'methods' => ['GET', 'POST', 'PUT', 'DELETE'],
       'callback' => 'acm2_proxy_handler',
       'permission_callback' => 'is_user_logged_in'
   ]);
   ```

3. **React Build for WordPress**
   - Configure Vite to build for WordPress embedding
   - Remove API key from frontend (use WordPress proxy)
   - Update all API calls to go through WordPress

4. **WordPress Shortcode**
   ```php
   // [acm2_app] - Embeds full application
   add_shortcode('acm2_app', 'acm2_render_app');
   ```

5. **Testing**
   - Test WordPress login → ACM2 access
   - Verify API key never exposed to browser
   - Test rate limiting

**Deliverable:** WordPress users can access ACM2 through WordPress without seeing API keys

---

### Phase 4: Billing & Usage Tracking (Week 5-6)

**Goal:** Track usage for billing purposes

**Tasks:**
1. **Usage Logging**
   ```python
   # Log every API call
   async def log_usage(user_id, endpoint, run_id, provider_costs):
       await db.execute("""
           INSERT INTO usage_logs (user_id, endpoint, run_id, provider_costs, timestamp)
           VALUES (?, ?, ?, ?, ?)
       """, [user_id, endpoint, run_id, json.dumps(provider_costs), datetime.now()])
   ```

2. **Usage Dashboard**
   - Show user's ACM2 platform usage
   - Show estimated LLM provider costs (based on their API calls)
   - Monthly breakdown
   - Export to CSV

3. **Subscription Management**
   - Integrate Stripe/PayPal for payments
   - Subscription tiers (if applicable)
   - Usage limits per tier

4. **WordPress Payment Integration**
   - Link WordPress user to Stripe customer
   - Handle subscription webhooks
   - Disable ACM2 access for unpaid accounts

**Deliverable:** Usage tracking and billing system in place

---

### Phase 5: Python SDK (Week 7)

**Goal:** Developers can use ACM2 via Python SDK

**Tasks:**
1. **SDK Package Structure**
   ```
   acm2-sdk/
   ├── acm2/
   │   ├── __init__.py
   │   ├── client.py
   │   ├── resources/
   │   │   ├── runs.py
   │   │   ├── documents.py
   │   │   └── evaluation.py
   │   └── exceptions.py
   ├── setup.py
   └── README.md
   ```

2. **Client Implementation**
   ```python
   import acm2
   
   client = acm2.Client(api_key="acm2_abc123")
   
   # Create run
   run = client.runs.create(
       prompt="Compare these models",
       models=["gpt-4", "claude-3"]
   )
   
   # Wait for completion
   run = client.runs.retrieve(run.id)
   ```

3. **Publish to PyPI**
   - Package for distribution
   - Publish: `pip install acm2`

**Deliverable:** Developers can use ACM2 from Python scripts

---

### Phase 6: Production Deployment (Week 8)

**Goal:** Deploy to production with proper infrastructure

**Tasks:**
1. **Server Setup**
   - Provision VPS (DigitalOcean, AWS, etc.)
   - Install dependencies
   - Setup SSL certificates (Let's Encrypt)

2. **Database Backups**
   - Automated daily backups of all user databases
   - S3/Backblaze storage
   - Restoration testing

3. **Monitoring**
   - Setup logging (CloudWatch, Datadog, or similar)
   - Error tracking (Sentry)
   - Uptime monitoring
   - Alert on API failures

4. **Performance Optimization**
   - Enable database connection pooling
   - Add Redis for caching
   - CDN for static files

5. **Security Hardening**
   - Rate limiting (per user, per IP)
   - DDoS protection (Cloudflare)
   - Security headers
   - Regular security updates

**Deliverable:** Production-ready deployment

---

### Phase 7: Advanced Features (Week 9+)

**Optional enhancements:**

1. **Team/Organization Support**
   - Multiple users per organization
   - Shared runs and presets
   - Role-based access control

2. **Webhooks**
   - Notify user when run completes
   - POST to user's endpoint with results

3. **API Rate Limiting**
   - Configurable limits per subscription tier
   - Quota management

4. **Advanced Security**
   - 2FA for API key generation
   - Audit logs
   - IP whitelisting

5. **Additional Integrations**
   - Slack notifications
   - Discord bot
   - Chrome extension

---

## Current Implementation Status

### ✅ Already Implemented
- Multi-LLM orchestration (FPF, GPTR)
- Single-doc and pairwise evaluation
- Run execution pipeline
- React frontend
- FastAPI backend
- SQLite database
- Timeline events
- Cost tracking structure (ready for per-user keys)
- Deviation calculations (with decimal precision)

### 🚧 In Progress
- None currently

### 📋 TODO (Following Roadmap Above)
- Phase 1: Multi-user support (master DB, API keys)
- Phase 2: Provider key management
- Phase 3: WordPress integration
- Phase 4: Billing system
- Phase 5: Python SDK
- Phase 6: Production deployment
- Phase 7: Advanced features

---

## API Auth Implementation

FastAPI authentication (Phase 1):

```python
from fastapi import Depends, HTTPException, Request
from typing import Optional
import bcrypt

async def get_current_user(request: Request):
    # Get API key from header
    api_key = request.headers.get("X-ACM2-API-Key")
    if not api_key:
        raise HTTPException(401, "API key required")
    
    # Validate API key
    user = await validate_api_key(api_key)
    if not user:
        raise HTTPException(401, "Invalid API key")
    
    # Attach to request
    request.state.user = user
    request.state.db_path = f"data/user_{user.id}.db"
    
    return user

async def validate_api_key(api_key: str) -> Optional[User]:
    # Hash the key
    key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt())
    
    # Look up in master database
    async with aiosqlite.connect("data/master.db") as db:
        cursor = await db.execute(
            "SELECT user_id FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
            [key_hash]
        )
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        # Update last_used_at
        await db.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
            [datetime.now(), key_hash]
        )
        await db.commit()
        
        # Get user
        cursor = await db.execute(
            "SELECT id, email, database_file FROM users WHERE id = ?",
            [row[0]]
        )
        user_row = await cursor.fetchone()
        
        return User(id=user_row[0], email=user_row[1], database_file=user_row[2])

# Use in routes
@router.get("/runs")
async def get_runs(user: User = Depends(get_current_user)):
    # Access user's database
    async with aiosqlite.connect(f"data/{user.database_file}") as db:
        cursor = await db.execute("SELECT * FROM runs WHERE user_id = ?", [user.id])
        rows = await cursor.fetchall()
        return {"runs": rows}
```

---

## Migration Path

### Current State
- Single database, no auth
- Uvicorn serving everything

### Phase 1: Add User Isolation
- Implement per-user database files
- Add user context to all queries

### Phase 2: Add WordPress Integration
- Set up JWT/session handoff from WordPress
- Add session validation middleware

### Phase 3: Add API Keys
- API key generation in WordPress dashboard
- API key validation in FastAPI

### Phase 4: Production Deployment
- Uvicorn with multiple workers
- Proper domain/subdomain setup
- SSL via Cloudflare or Let's Encrypt

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Web Server | Uvicorn (ASGI) |
| API Framework | FastAPI |
| Frontend | React + TypeScript + Vite |
| Database | SQLite (per-user files) |
| Auth (Web) | WordPress Sessions |
| Auth (API) | API Keys |
| CMS/Users | WordPress |
| Payments | WordPress plugin (WooCommerce, etc.) |

---

## Why This Architecture?

| Benefit | Reason |
|---------|--------|
| **Security** | No API keys exposed in browser |
| **Simplicity** | WordPress handles login, password reset, etc. |
| **Flexibility** | Power users can script against your API |
| **Separation** | API is a standalone product, frontend is just one client |
| **Isolation** | Per-user databases for true data separation |
| **Scalability** | Can scale horizontally with load balancer |

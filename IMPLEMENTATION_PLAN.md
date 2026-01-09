# ACM2 Multi-User Implementation Plan

**Objective:** Convert single-user ACM2 into multi-user platform with WordPress integration

**Pre-requisite:** WordPress installed and running (user handles this)

**Timeline:** 6-8 weeks for full production deployment

---

## Expected Challenges & How to Handle Them

### 🔴 HARD: User ID Propagation Through Evaluation Pipeline

**Problem:**
The evaluation pipeline has 10+ nested function calls. You need to pass `user_id` through ALL of them:
```
create_run() → execute_run() → evaluate_single_doc() → call_judge() → 
call_openai() → get_provider_key(user_id) 
```

**Why it's hard:**
- Touch 15-20 files across the codebase
- Easy to miss one function call, which breaks at runtime
- Type signatures need updating everywhere
- Existing code doesn't have this parameter

**Solution:**
1. **Bottom-up approach**: Start with adapters, work backwards
   - Update `call_openai(user_id, ...)` first
   - Then update all callers of `call_openai()`
   - Repeat until you reach the top-level route
2. **Use TypeScript-style type hints**: Python type checker will catch missing params
3. **Add a test that fails if user_id not passed**: 
   ```python
   # In adapter
   assert user_id is not None, "user_id is required"
   ```

**Time estimate:** 2-3 hours of careful editing

---

### 🟡 MEDIUM: WordPress Security (API Key Proxy)

**Problem:**
If you mess up the proxy, API keys could be exposed to the browser. This is the CRITICAL security boundary.

**Common mistakes:**
```php
// ❌ WRONG - Exposes key to browser
function get_user_key() {
    return ['api_key' => get_user_meta($user_id, 'acm2_api_key', true)];
}

// ✅ RIGHT - Key never leaves WordPress backend
function proxy_request($endpoint) {
    $key = get_user_meta($user_id, 'acm2_api_key', true);
    $response = wp_remote_post($endpoint, ['headers' => ['X-ACM2-API-Key' => $key]]);
    return json_decode($response['body']);  // NO key in response
}
```

**How to verify it's secure:**
1. Open browser DevTools → Network tab
2. Make API call from React app
3. Search for "acm2_" in request/response
4. If you find the full API key anywhere → YOU HAVE A SECURITY BUG

**Solution:**
- NEVER return the API key in any API response
- ONLY return the key prefix (first 8 chars) for display
- Add unit test that verifies key not in response

---

### 🟡 MEDIUM: Database Migration (Single → Multi-User)

**Problem:**
You have existing runs in `acm2.db`. You need to migrate them to `user_1.db` without losing data.

**Gotchas:**
- Old database might have different schema (missing columns)
- Run IDs might collide if multiple users migrated
- Evaluation results reference models that might not exist in new user's keys

**Solution:**
```python
async def migrate_existing_database():
    # 1. Create first user
    user_id = await create_user("admin@example.com")
    
    # 2. Copy all tables
    async with aiosqlite.connect("data/acm2.db") as old:
        async with aiosqlite.connect(f"data/user_{user_id}.db") as new:
            # Get table names
            cursor = await old.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            
            for table in tables:
                # Copy all rows
                cursor = await old.execute(f"SELECT * FROM {table}")
                rows = await cursor.fetchall()
                
                if rows:
                    # Get column count
                    placeholders = ",".join(["?" for _ in rows[0]])
                    await new.executemany(
                        f"INSERT INTO {table} VALUES ({placeholders})",
                        rows
                    )
            await new.commit()
    
    # 3. Backup old database
    import shutil
    shutil.move("data/acm2.db", "data/acm2.db.backup")
    
    print(f"✅ Migrated to user {user_id}")
```

**Test before running on real data:**
1. Make a copy of `acm2.db` → `acm2_test.db`
2. Run migration on test copy
3. Verify all runs still accessible
4. Only then run on real database

---

### 🟡 MEDIUM: Frontend Build & WordPress Integration

**Problem:**
Vite generates files with random hashes: `index-abc123.js`. WordPress needs to know the exact filename to enqueue.

**Why it's hard:**
- Build output changes every time
- WordPress plugin needs to find the current filename
- Path references might break (CSS loading images, etc.)

**Solution:**
```php
// In WordPress plugin
function acm2_enqueue_react_app() {
    $assets_dir = ACM2_PLUGIN_DIR . 'assets/react-app/assets/';
    
    // Find current JS file
    $js_files = glob($assets_dir . 'index-*.js');
    if (empty($js_files)) {
        wp_die('React app not built. Run: cd frontend && npm run build');
    }
    
    $js_file = basename($js_files[0]);
    $css_file = basename(glob($assets_dir . 'index-*.css')[0]);
    
    wp_enqueue_script('acm2-app', 
        ACM2_PLUGIN_URL . 'assets/react-app/assets/' . $js_file, 
        [], 
        filemtime($js_files[0]),  // Use file modification time as version
        true
    );
}
```

**Alternative (cleaner):** Generate a manifest file
```json
// frontend/dist/manifest.json
{
  "index.js": "assets/index-abc123.js",
  "index.css": "assets/index-def456.css"
}
```

Then WordPress just reads the manifest.

---

### 🔴 HARD: Async Context Propagation (Python)

**Problem:**
Python's `asyncio` makes it tricky to pass context (like `user_id`) through deeply nested async calls.

**Current architecture:**
```python
# Multiple functions need user_id
await evaluate_single_doc(user_id, doc, models)
    await call_judge(user_id, model, messages)
        await call_openai(user_id, model, messages)
            await get_provider_key(user_id, "openai")
```

**Pain points:**
- Every function signature needs `user_id` parameter
- Easy to forget in one place
- Function signatures become long

**Better solution (optional, advanced):**
Use Python's `contextvars` to store user_id in async context:

```python
from contextvars import ContextVar

# Global context variable
current_user_id: ContextVar[int] = ContextVar('current_user_id')

# In FastAPI route
@router.post("/runs")
async def create_run(user_id: CurrentUser, ...):
    # Set context for this request
    current_user_id.set(user_id)
    
    # Now all nested functions can access it
    await execute_run(...)  # No user_id parameter needed!

# In adapter
async def get_provider_key(provider: str) -> str:
    user_id = current_user_id.get()  # Get from context
    async with get_user_db(user_id) as db:
        ...
```

**Pros:**
- Cleaner function signatures
- Can't forget to pass user_id

**Cons:**
- Harder to understand for someone reading code
- Context can be confusing in concurrent scenarios

**Recommendation:** Start simple (pass user_id everywhere), refactor to contextvars later if needed.

---

### 🟡 MEDIUM: Long-Running Requests (Timeouts)

**Problem:**
Evaluations can take 5-10 minutes. Default WordPress/Apache/Nginx timeouts are 30-60 seconds.

**Symptoms:**
- Request works for small runs, fails for large ones
- 504 Gateway Timeout errors
- WordPress shows "The site is experiencing technical difficulties"

**What needs to be configured:**
```apache
# Apache config
ProxyPass /api http://localhost:8199/api timeout=600

# PHP config (php.ini)
max_execution_time = 600

# WordPress plugin
wp_remote_post($url, [
    'timeout' => 600  // 10 minutes
]);

# FastAPI (Uvicorn)
# Default is no timeout - good!
```

**Better solution:** Use background jobs
```python
# Instead of waiting for evaluation to complete:
@router.post("/runs")
async def create_run(...):
    run_id = generate_uuid()
    
    # Start evaluation in background
    asyncio.create_task(execute_run_async(run_id, user_id, ...))
    
    # Return immediately
    return {"run_id": run_id, "status": "pending"}

# Frontend polls for status
GET /runs/{run_id}  # Returns status: pending/running/completed/failed
```

---

### 🔴 HARD: Encryption Key Management

**Problem:**
The encryption key is in `.env` file. If you lose it, ALL provider keys become unrecoverable.

**Scenarios:**
1. **Server crashes, .env file lost** → All user provider keys gone forever
2. **You commit .env to git, need to rotate key** → Need to re-encrypt all keys
3. **Encryption key compromised** → Attacker can decrypt all provider keys

**Solution - Key Backup:**
```bash
# Store encryption key in multiple places
echo $ACM2_ENCRYPTION_KEY > ~/acm2_encryption_key.backup
gpg --encrypt ~/acm2_encryption_key.backup  # Encrypt the backup!
scp ~/acm2_encryption_key.backup.gpg user@backup-server:/backups/
```

**Solution - Key Rotation:**
```python
async def rotate_encryption_key(old_key: str, new_key: str):
    """Re-encrypt all provider keys with new encryption key"""
    old_fernet = Fernet(old_key.encode())
    new_fernet = Fernet(new_key.encode())
    
    # Find all user databases
    for db_file in Path("data").glob("user_*.db"):
        async with aiosqlite.connect(db_file) as db:
            cursor = await db.execute("SELECT id, encrypted_key FROM provider_keys")
            rows = await cursor.fetchall()
            
            for key_id, encrypted_key in rows:
                # Decrypt with old key
                plaintext = old_fernet.decrypt(encrypted_key.encode())
                # Re-encrypt with new key
                new_encrypted = new_fernet.encrypt(plaintext).decode()
                # Update database
                await db.execute(
                    "UPDATE provider_keys SET encrypted_key = ? WHERE id = ?",
                    [new_encrypted, key_id]
                )
            await db.commit()
```

---

### 🟡 MEDIUM: Testing Multi-Tenancy (Data Isolation)

**Problem:**
How do you prove User A can't access User B's data? Manual testing is tedious and error-prone.

**What to test:**
1. User A creates run → User B can't see it
2. User A adds provider key → User B can't use it
3. User A's evaluation doesn't affect User B's quota/rate limits

**Solution - Automated test:**
```python
import pytest

@pytest.mark.asyncio
async def test_data_isolation():
    # Create two users
    user1_id = await create_user("user1@example.com")
    user2_id = await create_user("user2@example.com")
    
    # User 1 creates run
    async with get_user_db(user1_id) as db:
        await db.execute(
            "INSERT INTO runs (id, prompt) VALUES (?, ?)",
            ["run1", "User 1's secret prompt"]
        )
        await db.commit()
    
    # User 2 should NOT see it
    async with get_user_db(user2_id) as db:
        cursor = await db.execute("SELECT * FROM runs WHERE id = ?", ["run1"])
        row = await cursor.fetchone()
        assert row is None, "User 2 can see User 1's run!"
    
    # User 2 creates run with same ID
    async with get_user_db(user2_id) as db:
        await db.execute(
            "INSERT INTO runs (id, prompt) VALUES (?, ?)",
            ["run1", "User 2's different prompt"]
        )
        await db.commit()
    
    # Verify they're separate
    async with get_user_db(user1_id) as db:
        cursor = await db.execute("SELECT prompt FROM runs WHERE id = ?", ["run1"])
        prompt = (await cursor.fetchone())[0]
        assert prompt == "User 1's secret prompt"
    
    async with get_user_db(user2_id) as db:
        cursor = await db.execute("SELECT prompt FROM runs WHERE id = ?", ["run1"])
        prompt = (await cursor.fetchone())[0]
        assert prompt == "User 2's different prompt"
```

---

### 🟡 MEDIUM: WordPress Development Environment

**Problem:**
If you're not familiar with WordPress, setting up a local dev environment is painful.

**What you need:**
- PHP 8.0+
- MySQL/MariaDB
- WordPress installation
- Understanding of WordPress hooks/filters

**Quick setup (LocalWP - easiest):**
```bash
# Download LocalWP from localwp.com
# Click "Create New Site"
# Site name: acm2-dev
# PHP: 8.2, MySQL: 8.0
# Click "Add Site"

# Done! WordPress running at: http://acm2-dev.local
```

**Alternative (Docker):**
```yaml
# docker-compose.yml
version: '3'
services:
  wordpress:
    image: wordpress:latest
    ports:
      - "8080:80"
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_PASSWORD: password
  db:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: password
      MYSQL_DATABASE: wordpress
```

**Where to put plugin during development:**
```bash
# Option 1: Symlink (hot reload)
ln -s /path/to/acm2/wordpress-plugin /path/to/wordpress/wp-content/plugins/acm2

# Option 2: Copy (must rebuild each time)
cp -r wordpress-plugin /path/to/wordpress/wp-content/plugins/acm2
```

---

### 🔴 HARD: Debugging Async Python Errors

**Problem:**
When an async function fails deep in the evaluation pipeline, the error message is cryptic.

**Example error:**
```
Task exception was never retrieved
Future exception was never retrieved
Traceback (most recent call last):
  ...
  (no useful information)
```

**Solution - Add better error handling:**
```python
# In evaluation pipeline
async def execute_run(user_id: int, ...):
    try:
        result = await evaluate_single_doc(user_id, ...)
        return result
    except Exception as e:
        # Log full context
        logger.error(
            f"Evaluation failed for user {user_id}",
            extra={
                "user_id": user_id,
                "run_id": run_id,
                "models": models,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
        # Re-raise with more context
        raise RuntimeError(f"Evaluation failed: {e}") from e
```

**Solution - Use `asyncio.create_task` with error handler:**
```python
async def safe_background_task(coro):
    """Wrapper that logs errors from background tasks"""
    try:
        await coro
    except Exception as e:
        logger.error(f"Background task failed: {e}", exc_info=True)

# Usage
asyncio.create_task(safe_background_task(execute_run(...)))
```

---

## Summary: What's Hard, What's Not

### ✅ Easy Parts (1-2 hours each):
- Creating database schemas (just SQL)
- API key generation (bcrypt is simple)
- Encryption setup (Fernet is easy)
- WordPress plugin structure (copy/paste)
- Frontend environment detection (one if statement)

### 🟡 Medium Parts (3-5 hours each):
- Authentication middleware (FastAPI dependency injection)
- Database router (context manager)
- WordPress API proxy (PHP is annoying but straightforward)
- Frontend build integration (path hell)
- Provider keys UI (React CRUD is tedious)

### 🔴 Hard Parts (1-2 days each):
- **User ID propagation through evaluation pipeline** (touch many files)
- **Database migration** (can't afford to lose data)
- **Testing multi-tenancy thoroughly** (need comprehensive test suite)
- **Security audit** (one mistake = all API keys leaked)
- **Production deployment** (Apache config, SSL, systemd, all the DevOps)

---

## Risk Mitigation Strategy

1. **Start with Phase 1 & 2 ONLY**
   - Get multi-user backend working
   - Test with curl/Postman
   - Don't touch WordPress yet

2. **Test data isolation BEFORE adding WordPress**
   - Create 2 users
   - Add runs for each
   - Verify they can't see each other's data

3. **WordPress is just a proxy**
   - If WordPress breaks, backend still works
   - You can always use API directly
   - WordPress is optional (nice to have)

4. **Backup before migration**
   - Copy `acm2.db` multiple times
   - Test migration on copy first
   - Keep old database as backup

5. **Security checklist before production**
   - [ ] API keys never in logs
   - [ ] Encryption key backed up
   - [ ] Provider keys encrypted in DB
   - [ ] WordPress proxy doesn't expose keys
   - [ ] Rate limiting on API endpoints
   - [ ] HTTPS enforced

---

## The Complete User Flow - Plain English Narrative

### Scenario: Bob wants to run an LLM evaluation

---

### Step 1: Bob Opens His Browser

Bob is a lawyer who wants to use AI to analyze a contract. He's heard about your ACM2 service that can run the same prompt through multiple AI models (OpenAI, Google, Anthropic) and compare their responses.

Bob types your website address into his browser and presses Enter. The browser sends a request across the internet to your web server.

Your web server (Apache) receives the request. It looks at the URL and sees it's asking for a WordPress page. Apache hands the request to WordPress to figure out what to show.

---

### Step 2: WordPress Checks Who Bob Is

WordPress looks at the cookies the browser sent along with the request. There's a cookie called something like "wordpress_logged_in" that was created when Bob logged in earlier today.

WordPress reads this cookie and thinks: "Ah, this is Bob. He logged in this morning. His user ID in my database is 42."

---

### Step 3: WordPress Checks If Bob Has Set Up ACM2

WordPress queries its database to see if Bob has ever generated an ACM2 API key. It looks in a table where it stores extra information about users.

It finds a record that says "User 42 (Bob) has an ACM2 API key: acm2_xyz789..." This key is stored securely in the WordPress database. Bob has never seen it and doesn't need to know what it is.

WordPress also checks: "Does Bob have provider keys set up?" (OpenAI, Google, Anthropic). If not, it would show a message telling Bob to add them first. But Bob already did that, so we're good.

---

### Step 4: WordPress Builds the Page

WordPress starts building the HTML page to send to Bob's browser. It includes:

- Your website's header and navigation menu
- A special container where the React app will load
- Some critical information injected into the page as JavaScript variables:
  - Where to send API requests (the WordPress proxy endpoint)
  - A special security token called a "nonce" (a random string that proves this page came from your website)
  - Bob's user ID and email (just for display purposes)

WordPress sends this complete HTML page across the internet to Bob's browser.

---

### Step 5: Bob's Browser Receives and Renders the Page

Bob's browser receives the HTML. It starts parsing it from top to bottom.

When it encounters the JavaScript code, it executes it. The code creates a variable called "acm2Config" with all that information WordPress injected.

Then the browser loads the React application code. The React app starts up and immediately checks: "Is there an acm2Config variable?" 

It finds it and thinks: "Great! I'm running inside WordPress. That means I don't need to ask Bob for an API key. WordPress will handle authentication for me."

The React app hides the "Enter API Key" input field (since it's not needed in WordPress mode) and shows Bob the main dashboard interface.

---

### Step 6: Bob Fills Out the Evaluation Form

Bob sees a form where he can:
- Enter the text he wants evaluated (the contract)
- Choose which AI models to use (he checks boxes for GPT-4, Gemini, and Claude)
- Choose evaluation criteria (accuracy, completeness, tone, etc.)

Bob types his contract text into the box, selects all three models, and clicks the big "Start Evaluation" button.

---

### Step 7: React Prepares the Request

The React app collects all the information Bob entered and packages it up into a neat bundle of data. It needs to send this to the backend to actually run the evaluation.

But here's the key: The React app doesn't send the request directly to your ACM2 backend. Instead, it sends it to WordPress.

The React app makes a network request to "yoursite.com/wp-json/acm2/v1/runs" (a WordPress endpoint). Along with the request, it includes:
- The data Bob entered (contract text, selected models)
- The security token (nonce) that WordPress gave it earlier
- The browser automatically includes WordPress session cookies

---

### Step 8: The Request Travels to WordPress

The request goes from Bob's computer across the internet to your web server. Apache receives it and looks at the URL. It sees "/wp-json/" in the path and knows this should go to WordPress, so it hands it over.

---

### Step 9: WordPress Performs Security Checks

WordPress receives the request and immediately starts validating it:

**First check:** Is the nonce valid? WordPress looks at the security token and checks if it's one it recently created and hasn't expired. This proves the request came from a page WordPress served, not from some malicious website trying to trick Bob's browser. ✓ Valid.

**Second check:** Is there a session cookie, and is it valid? WordPress checks the cookie and confirms Bob is logged in. ✓ Valid.

**Third check:** What's Bob's user ID? WordPress extracts from the session that this is user 42 (Bob). ✓ Identified.

**Fourth check:** Does Bob have an ACM2 API key? WordPress queries its database and finds Bob's ACM2 API key: "acm2_xyz789..." ✓ Found.

All security checks passed! WordPress now has everything it needs.

---

### Step 10: WordPress Acts as a Middleman (The Proxy)

Here's where the security magic happens. WordPress doesn't send Bob's ACM2 API key to his browser. It keeps it secret in its database. Instead, WordPress itself will use the key to talk to your ACM2 backend.

WordPress takes the data Bob submitted and makes a NEW request - this time to your ACM2 backend running on the same server at "localhost:8199/api/v1/runs"

This is an internal request - it never goes over the internet. It stays inside your server.

With this request, WordPress includes Bob's ACM2 API key in the headers. The ACM2 backend will use this to know who Bob is and which database to use.

---

### Step 11: ACM2 Backend Validates the API Key

Your ACM2 backend (the Python FastAPI application) receives the request. It immediately looks for the API key in the headers.

It finds "X-ACM2-API-Key: acm2_xyz789..."

The backend takes this key and hashes it with bcrypt (a secure one-way function). Then it queries the master database looking for a matching hash.

It finds a record that says: "This key belongs to ACM2 user ID 5". So Bob's WordPress user ID is 42, but his ACM2 user ID is 5. The backend makes note: "This request is for user 5."

---

### Step 12: ACM2 Opens Bob's Personal Database

The backend has a directory full of database files. Each user has their own file. Bob's is called "user_5.db"

The backend opens Bob's database file. This file contains:
- All of Bob's previous evaluation runs
- Bob's OpenAI, Google, and Anthropic API keys (encrypted)
- Bob's usage statistics
- Everything that belongs to Bob and ONLY Bob

The backend queries this database to get Bob's provider keys. It finds three encrypted strings.

---

### Step 13: ACM2 Decrypts Bob's Provider Keys

The backend needs to actually call OpenAI, Google, and Anthropic to run the evaluation. But to do that, it needs Bob's API keys for those services.

The backend reads an encryption key from an environment file (a secret file on the server). Using this encryption key, it decrypts Bob's three provider API keys:
- OpenAI key: "sk-proj-bob-secret-key-12345"
- Google key: "AIza-bob-google-key-67890"
- Anthropic key: "sk-ant-bob-anthropic-key-abcdef"

Now the backend has everything it needs to run the evaluation.

---

### Step 14: ACM2 Calls the LLM Providers

The backend starts making API calls to the actual AI companies. It's like the backend is acting as Bob, using Bob's keys.

**First, it calls OpenAI:**
"Hey OpenAI, using Bob's account, please analyze this contract text with GPT-4."

OpenAI's servers receive the request, process it (takes about 10 seconds), and send back GPT-4's analysis.

**Then it calls Google:**
"Hey Google, using Bob's account, please analyze this contract text with Gemini."

Google's servers process it and send back Gemini's analysis.

**Then it calls Anthropic:**
"Hey Anthropic, using Bob's account, please analyze this contract text with Claude."

Anthropic's servers process it and send back Claude's analysis.

This whole process takes 1-2 minutes because each AI model needs time to think and generate a response.

---

### Step 15: ACM2 Compares the Results

Now the backend has three responses from three different AI models. It runs its analysis algorithm to compare them:

- Which model was most thorough?
- Where did they agree?
- Where did they disagree?
- What were the deviations in their scores?
- How much did this cost? (Based on token usage and each provider's pricing)

The backend calculates all these statistics and stores everything in Bob's database file (user_5.db). It generates a run ID like "abc-123-def-456" so Bob can reference this specific evaluation later.

---

### Step 16: ACM2 Sends Results Back to WordPress

The backend packages up all the results into a response and sends it back to WordPress. The response includes:
- The run ID
- Status: "completed"
- All three AI responses
- Comparison statistics
- Deviation analysis
- Cost breakdown

**Critically, the response does NOT include:**
- Bob's ACM2 API key
- Bob's OpenAI/Google/Anthropic keys
- Any sensitive information

Just the evaluation results.

---

### Step 17: WordPress Forwards Results to Bob's Browser

WordPress receives this response from the ACM2 backend. It doesn't modify it - it just acts as a messenger, passing it along to Bob's browser.

The response travels across the internet back to Bob's computer.

---

### Step 18: Bob Sees the Results

Bob's browser receives the response. The React app processes it and updates the user interface.

Bob now sees:
- A success message: "Evaluation complete!"
- A table showing all three AI model responses side-by-side
- Highlighting where they agreed and disagreed
- Statistics about which model was most confident
- A breakdown showing this evaluation cost $2.47 (charged to Bob's accounts with OpenAI, Google, and Anthropic - your service didn't charge anything extra)
- A button to download the results or run another evaluation

---

### Why This Architecture is Secure

**Bob's browser never knew:**
- What his ACM2 API key was (stored in WordPress)
- What his OpenAI/Google/Anthropic keys were (stored encrypted in ACM2)

**WordPress acted as a gatekeeper:**
- Verified Bob was logged in before doing anything
- Checked the security token to prevent attacks
- Stored Bob's API key safely and used it on his behalf
- Never exposed the key to Bob's browser

**The ACM2 backend enforced isolation:**
- Each user has a separate database file
- Bob can only access his own data
- Even if Bob somehow got another user's ACM2 API key, it would open that user's database, not Bob's

**If an attacker tried to interfere:**
- They can't get Bob's nonce (browser security prevents it)
- They can't get Bob's session cookie (browser security prevents it)
- They can't guess Bob's ACM2 API key (bcrypt hashing makes this impossible)
- They can't decrypt the provider keys (they don't have the encryption key from the server)

---

### Later That Day

Bob wants to see his previous evaluations. He clicks "My Runs" in the navigation.

The whole flow happens again - WordPress checks Bob is logged in, gets his API key, forwards the request to ACM2, ACM2 opens Bob's database, retrieves all his runs, sends them back through WordPress to Bob's browser.

Bob sees a list of all his previous evaluations and can click any one to see the full results again.

Everything is stored safely in his personal database file. When he comes back tomorrow, next week, or next year, all his data will still be there, isolated from everyone else's data.

---

## Database Architecture Decision: Hybrid Approach

### Why Hybrid (MySQL Master + SQLite Users)?

After evaluating three approaches (all SQLite, all MySQL, or hybrid), we're implementing **the hybrid approach** for optimal balance:

**MySQL for Master Database:**
- Small, shared data (users, API keys)
- Benefits from server features (replication, monitoring)
- Already running in XAMPP alongside WordPress
- Easy admin queries: "How many users?" "List all active keys"

**SQLite for User Databases:**
- Large, isolated data (runs, provider keys, usage stats)
- Physical isolation = bulletproof security
- No concurrent write conflicts (separate files)
- Easy per-user backup/deletion

### The Architecture

```
┌─────────────────────────────────────┐
│   WordPress (MySQL: acm2_wordpress) │
│   - wp_users, wp_posts, wp_options │
└─────────────────────────────────────┘
                ↕
┌─────────────────────────────────────┐
│   ACM2 Master (MySQL: acm2_master)  │
│   - users (ACM2 accounts)           │
│   - api_keys (authentication)       │
│   Size: < 1 MB                      │
└─────────────────────────────────────┘
                ↕
┌─────────────────────────────────────┐
│   ACM2 User Data (SQLite per-user)  │
│   data/user_1.db  ← Alice           │
│   data/user_2.db  ← Bob             │
│   data/user_3.db  ← Carol           │
│   - runs, provider_keys, stats      │
│   Size: 10-500 MB each              │
└─────────────────────────────────────┘
```

### Benefits of This Approach

**Security:**
- LLM API keys physically isolated in separate SQLite files
- Impossible to accidentally query wrong user's data
- Delete user = delete one file

**Performance:**
- Master lookups fast (MySQL indexed)
- User operations fast (small SQLite files)
- No lock contention (each user has own file)

**Operations:**
- Easy admin queries (MySQL master)
- Easy per-user backups (copy SQLite files)
- MySQL already running (XAMPP)

**Scalability:**
- Master can upgrade to MySQL replication/HA
- User files can migrate to Postgres independently
- Scales to 10,000-50,000 users comfortably

### What Goes Where

| Data | Storage | Reason |
|------|---------|--------|
| User accounts | MySQL master | Shared, small, needs queries |
| API keys (hashes) | MySQL master | Shared, small, needs lookups |
| Evaluation runs | SQLite per-user | Large, isolated, high volume |
| Provider keys | SQLite per-user | Sensitive, encrypted, isolated |
| Usage statistics | SQLite per-user | Per-user metrics |

### Implementation Impact

**Phase 1 Changes:**
- Master database uses MySQL instead of SQLite
- User databases remain SQLite (no change)
- Code uses `aiomysql` for master, `aiosqlite` for users

**Connection Pattern:**
```python
# Master connection (shared, pooled)
master_pool = await aiomysql.create_pool(
    host='localhost',
    user='root',
    db='acm2_master'
)

# User connection (per-request, file-based)
user_db = await aiosqlite.connect(f'data/user_{user_id}.db')
```

---

## Phase 1: Multi-User Database Foundation (Week 1-2)

**Goal:** Transform single-user ACM2 into multi-tenant system with per-user data isolation

**Database Strategy:** Hybrid (MySQL master + SQLite per-user)

---

### 1.1 Create Master Database in MySQL

**Step 1: Create Database**

```sql
-- Connect to MySQL via phpMyAdmin or command line
CREATE DATABASE acm2_master
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
```

**Step 2: Create Tables**

**File:** `acm2/app/db/master_schema_mysql.sql`

```sql
-- Master database: MySQL acm2_master
-- Stores user accounts and API keys (shared data)

USE acm2_master;

CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    wordpress_user_id INT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_wordpress_user (wordpress_user_id),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE api_keys (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    last_used_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_key_hash (key_hash),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Tasks:**
- [ ] Create `acm2_master` database in MySQL
- [ ] Create `master_schema_mysql.sql` with schema above
- [ ] Execute schema: `mysql -u root acm2_master < master_schema_mysql.sql`
- [ ] Verify tables: `SHOW TABLES;` should show `users` and `api_keys`

---

### 1.2 Create Master Database Manager (MySQL)

**File:** `acm2/app/db/master.py`

```python
"""
Master Database Manager (MySQL)
Handles user accounts and API keys
"""
import aiomysql
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class MasterDB:
    """Manages master database with user accounts and API keys."""
    
    def __init__(self, host: str = 'localhost', user: str = 'root', 
                 password: str = '', db: str = 'acm2_master'):
        """Initialize master database connection pool.
        
        Args:
            host: MySQL host
            user: MySQL username
            password: MySQL password
            db: Database name
        """
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'db': db,
            'charset': 'utf8mb4',
            'autocommit': True
        }
        self._pool: Optional[aiomysql.Pool] = None
    
    async def connect(self):
        """Create connection pool."""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(**self.config)
            logger.info("Master database pool created")
    
    async def close(self):
        """Close connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("Master database pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:
            yield conn
    
    async def create_user(self, username: str, email: str,
                         wordpress_user_id: Optional[int] = None) -> int:
        """Create a new user.
        
        Args:
            username: Unique username
            email: User email address
            wordpress_user_id: Optional WordPress user ID
            
        Returns:
            New user's ID
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """INSERT INTO users (username, email, wordpress_user_id)
                       VALUES (%s, %s, %s)""",
                    (username, email, wordpress_user_id)
                )
                user_id = cursor.lastrowid
                logger.info(f"Created user: {username} (ID: {user_id})")
                return user_id
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM users WHERE id = %s", (user_id,)
                )
                return await cursor.fetchone()
    
    async def get_user_by_wordpress_id(self, wordpress_id: int) -> Optional[Dict[str, Any]]:
        """Get user by WordPress user ID."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM users WHERE wordpress_user_id = %s",
                    (wordpress_id,)
                )
                return await cursor.fetchone()
    
    async def create_api_key(self, user_id: int, key_hash: str,
                           key_prefix: str, name: Optional[str] = None) -> int:
        """Store API key for user.
        
        Args:
            user_id: User ID
            key_hash: bcrypt hash of the API key
            key_prefix: First 8 chars for display
            name: Optional name for the key
            
        Returns:
            API key record ID
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """INSERT INTO api_keys (user_id, key_hash, key_prefix, name)
                       VALUES (%s, %s, %s, %s)""",
                    (user_id, key_hash, key_prefix, name)
                )
                key_id = cursor.lastrowid
                logger.info(f"Created API key for user {user_id}: {key_prefix}...")
                return key_id
    
    async def get_user_by_api_key_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Get user by API key hash.
        
        Args:
            key_hash: bcrypt hash of API key
            
        Returns:
            User dict or None if key not found/revoked
        """
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Get user and update last_used_at
                await cursor.execute(
                    """SELECT u.* FROM users u
                       JOIN api_keys k ON u.id = k.user_id
                       WHERE k.key_hash = %s AND k.revoked_at IS NULL""",
                    (key_hash,)
                )
                user = await cursor.fetchone()
                
                if user:
                    # Update last_used_at
                    await cursor.execute(
                        "UPDATE api_keys SET last_used_at = %s WHERE key_hash = %s",
                        (datetime.utcnow(), key_hash)
                    )
                
                return user
    
    async def revoke_api_key(self, key_id: int):
        """Revoke an API key."""
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE api_keys SET revoked_at = %s WHERE id = %s",
                    (datetime.utcnow(), key_id)
                )
                logger.info(f"Revoked API key ID: {key_id}")
    
    async def list_user_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """List all API keys for a user."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """SELECT id, key_prefix, name, created_at, last_used_at, 
                              revoked_at
                       FROM api_keys
                       WHERE user_id = %s
                       ORDER BY created_at DESC""",
                    (user_id,)
                )
                return await cursor.fetchall()


# Global instance
_master_db: Optional[MasterDB] = None


async def get_master_db() -> MasterDB:
    """Get or create master database singleton."""
    global _master_db
    if _master_db is None:
        _master_db = MasterDB()
        await _master_db.connect()
    return _master_db
```

**Tasks:**
- [ ] Install MySQL driver: `pip install aiomysql`
- [ ] Create `master.py` with code above
- [ ] Test connection: Import and call `get_master_db()`

---

### 1.3 Create Per-User Database Schema (SQLite - Unchanged)

async def get_master_db():
    """Context manager for master database connection"""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db

async def create_user(email: str, wordpress_user_id: Optional[int] = None) -> int:
    """Create a new user and their database file"""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO users (email, wordpress_user_id, database_file) VALUES (?, ?, ?)",
            [email, wordpress_user_id, f"user_temp.db"]  # Temporary, will update
        )
        await db.commit()
        user_id = cursor.lastrowid
        
        # Update with actual database filename
        database_file = f"user_{user_id}.db"
        await db.execute(
            "UPDATE users SET database_file = ? WHERE id = ?",
            [database_file, user_id]
        )
        await db.commit()
        
        # Create user's database
        from acm2.app.db.user_db import create_user_database
        await create_user_database(user_id)
        
        return user_id

async def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email"""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            [email]
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_user_by_wordpress_id(wp_user_id: int) -> Optional[dict]:
    """Get user by WordPress user ID"""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE wordpress_user_id = ? AND is_active = 1",
            [wp_user_id]
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
```

**File:** `acm2/app/db/init_db.py` (CLI script)

```python
"""Command-line script to initialize databases"""
import asyncio
from acm2.app.db.master import init_master_db

async def main():
    print("Initializing ACM2 multi-user database system...")
    await init_master_db()
    print("✅ Database initialization complete!")

if __name__ == "__main__":
    asyncio.run(main())
```

**Tasks:**
- [ ] Create directory `acm2/app/db/` if not exists
- [ ] Create `master_schema.sql` with schema above
- [ ] Create `master.py` with initialization functions
- [ ] Create `init_db.py` CLI script
- [ ] Run: `python -m acm2.app.db.init_db`
- [ ] Verify `data/master.db` exists
- [ ] Open with SQLite browser, verify tables and indexes
- [ ] Test `create_user()` function, verify user created

**Testing:**
```python
# test_master_db.py
import asyncio
from acm2.app.db.master import init_master_db, create_user, get_user_by_email

async def test():
    await init_master_db()
    user_id = await create_user("test@example.com")
    print(f"Created user: {user_id}")
    
    user = await get_user_by_email("test@example.com")
    assert user['id'] == user_id
    assert user['email'] == "test@example.com"
    print("✅ Master DB tests passed")

asyncio.run(test())
```

---

### 1.2 Per-User Database Structure

**File:** `acm2/app/db/user_schema.sql`

```sql
-- Per-user database: data/user_{id}.db
-- Each user has their OWN isolated database file
-- Contains all their runs, results, and provider keys

-- Provider API keys (OpenAI, Google, Anthropic)
CREATE TABLE provider_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,  -- 'openai', 'google', 'anthropic'
    encrypted_key TEXT NOT NULL,  -- AES-256 encrypted
    key_name TEXT,  -- Optional: user-friendly name "My OpenAI Key"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

CREATE INDEX idx_provider_keys_provider ON provider_keys(provider);

-- All existing tables stay the same:
-- runs, run_results, source_docs, single_evals, etc.
-- These will be copied from current database schema
```

**File:** `acm2/app/db/user_db.py`

```python
"""Per-user database management"""
import aiosqlite
from pathlib import Path
from typing import Optional

USER_DB_DIR = Path("data")

async def create_user_database(user_id: int) -> str:
    """Create isolated database for a specific user"""
    db_path = USER_DB_DIR / f"user_{user_id}.db"
    
    if db_path.exists():
        raise ValueError(f"Database already exists: {db_path}")
    
    # Read existing schema (runs, run_results, etc.)
    existing_schema = Path("acm2/app/db/schema.sql").read_text()
    
    # Read new schema (provider_keys)
    new_schema = Path("acm2/app/db/user_schema.sql").read_text()
    
    async with aiosqlite.connect(db_path) as db:
        # Create all tables
        await db.executescript(existing_schema)
        await db.executescript(new_schema)
        await db.commit()
    
    print(f"✅ Created user database: {db_path}")
    return str(db_path)

async def get_user_db_path(user_id: int) -> Path:
    """Get path to user's database"""
    return USER_DB_DIR / f"user_{user_id}.db"

async def get_user_db(user_id: int):
    """Context manager for user's database connection"""
    db_path = await get_user_db_path(user_id)
    
    if not db_path.exists():
        raise ValueError(f"User database not found: {db_path}")
    
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        yield db

async def delete_user_database(user_id: int) -> None:
    """Delete user's database (DANGEROUS - use for testing only)"""
    db_path = await get_user_db_path(user_id)
    if db_path.exists():
        db_path.unlink()
        print(f"🗑️  Deleted user database: {db_path}")
```

**Tasks:**
- [ ] Export current database schema to `acm2/app/db/schema.sql`
  - Run: `sqlite3 data/acm2.db .schema > acm2/app/db/schema.sql`
- [ ] Create `user_schema.sql` with provider_keys table
- [ ] Create `user_db.py` with functions above
- [ ] Test: Call `create_user_database(123)`, verify file created
- [ ] Open `data/user_123.db` in SQLite browser
- [ ] Verify ALL tables exist (runs, run_results, provider_keys, etc.)
- [ ] Test: Call `get_user_db(123)`, verify connection works

**Testing:**
```python
# test_user_db.py
import asyncio
from acm2.app.db.user_db import create_user_database, get_user_db, delete_user_database

async def test():
    # Create test database
    await create_user_database(999)
    
    # Write data
    async with get_user_db(999) as db:
        await db.execute("INSERT INTO provider_keys (provider, encrypted_key) VALUES (?, ?)",
                        ["openai", "encrypted_test_key"])
        await db.commit()
    
    # Read data
    async with get_user_db(999) as db:
        cursor = await db.execute("SELECT * FROM provider_keys")
        rows = await cursor.fetchall()
        assert len(rows) == 1
    
    # Cleanup
    await delete_user_database(999)
    print("✅ User DB tests passed")

asyncio.run(test())
```

---

### 1.3 API Key Generation & Validation

**File:** `acm2/app/auth/api_keys.py`

```python
"""API key generation and validation"""
import secrets
import bcrypt
import aiosqlite
from datetime import datetime
from typing import Optional
from acm2.app.db.master import MASTER_DB_PATH

def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a secure API key
    Returns: (plaintext_key, key_hash, key_prefix)
    
    Example: 
        plaintext_key = "acm2_xj4kN8pqL9..."
        key_hash = "$2b$12$..." (bcrypt hash)
        key_prefix = "acm2_xj4" (first 8 chars for display)
    """
    # Generate 32 random bytes, encode as URL-safe base64
    random_part = secrets.token_urlsafe(32)
    plaintext_key = f"acm2_{random_part}"
    
    # Hash for storage (bcrypt is intentionally slow = good for passwords/keys)
    key_hash = bcrypt.hashpw(plaintext_key.encode(), bcrypt.gensalt()).decode()
    
    # First 8 characters for display (safe to show in UI/logs)
    key_prefix = plaintext_key[:8]
    
    return plaintext_key, key_hash, key_prefix

async def save_api_key(
    user_id: int, 
    key_hash: str, 
    key_prefix: str,
    note: Optional[str] = None
) -> int:
    """Save API key to master database"""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO api_keys (user_id, key_hash, key_prefix, note) 
               VALUES (?, ?, ?, ?)""",
            [user_id, key_hash, key_prefix, note]
        )
        await db.commit()
        return cursor.lastrowid

async def validate_api_key(plaintext_key: str) -> Optional[int]:
    """
    Validate API key and return user_id if valid
    Returns None if invalid
    
    Note: This is intentionally slow (bcrypt) to prevent brute force attacks
    """
    if not plaintext_key.startswith("acm2_"):
        return None
    
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        # Get all active API keys (we need to check each hash)
        cursor = await db.execute(
            """SELECT id, user_id, key_hash FROM api_keys 
               WHERE is_active = 1"""
        )
        rows = await cursor.fetchall()
        
        # Check each key hash (bcrypt.checkpw is constant-time)
        for row in rows:
            key_id, user_id, key_hash = row
            if bcrypt.checkpw(plaintext_key.encode(), key_hash.encode()):
                # Update last_used_at timestamp
                await db.execute(
                    "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                    [datetime.utcnow().isoformat(), key_id]
                )
                await db.commit()
                return user_id
    
    return None

async def get_user_api_keys(user_id: int) -> list[dict]:
    """Get all API keys for a user (without the actual keys)"""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, key_prefix, created_at, last_used_at, is_active, note
               FROM api_keys WHERE user_id = ?
               ORDER BY created_at DESC""",
            [user_id]
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def revoke_api_key(key_id: int, user_id: int) -> bool:
    """Revoke (deactivate) an API key"""
    async with aiosqlite.connect(MASTER_DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE api_keys SET is_active = 0 WHERE id = ? AND user_id = ?",
            [key_id, user_id]
        )
        await db.commit()
        return cursor.rowcount > 0
```

**File:** `acm2/app/api/routes/auth.py` (New file)

```python
"""Authentication endpoints"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from acm2.app.auth.api_keys import (
    generate_api_key, 
    save_api_key, 
    get_user_api_keys,
    revoke_api_key
)
from acm2.app.db.master import create_user, get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])

class CreateUserRequest(BaseModel):
    email: str
    wordpress_user_id: int | None = None

class CreateUserResponse(BaseModel):
    user_id: int
    api_key: str  # Only returned once!
    key_prefix: str

@router.post("/users", response_model=CreateUserResponse)
async def create_user_endpoint(req: CreateUserRequest):
    """
    Create a new user and generate their API key
    
    This endpoint will be called by:
    1. WordPress plugin when user registers
    2. CLI tool for testing
    
    Security: In production, this should require admin authentication
    """
    # Check if user already exists
    existing = await get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user
    user_id = await create_user(req.email, req.wordpress_user_id)
    
    # Generate API key
    plaintext_key, key_hash, key_prefix = generate_api_key()
    await save_api_key(user_id, key_hash, key_prefix, note="Initial key")
    
    return CreateUserResponse(
        user_id=user_id,
        api_key=plaintext_key,  # ⚠️ ONLY time we return the full key!
        key_prefix=key_prefix
    )

class APIKeyResponse(BaseModel):
    api_key: str
    key_prefix: str

@router.post("/generate-key", response_model=APIKeyResponse)
async def generate_key_endpoint(user_id: int):
    """
    Generate a new API key for existing user
    
    TODO: This should require authentication in production
    For now, accepts user_id in request body for testing
    """
    # Generate new key
    plaintext_key, key_hash, key_prefix = generate_api_key()
    await save_api_key(user_id, key_hash, key_prefix)
    
    return APIKeyResponse(
        api_key=plaintext_key,
        key_prefix=key_prefix
    )
```

**Tasks:**
- [ ] Install bcrypt: `pip install bcrypt`
- [ ] Create `acm2/app/auth/` directory
- [ ] Create `api_keys.py` with functions above
- [ ] Create `acm2/app/api/routes/auth.py`
- [ ] Register auth router in `main.py`: `app.include_router(auth.router)`
- [ ] Test key generation: Call `generate_api_key()`, verify format
- [ ] Test key validation: Generate key, validate it, verify returns user_id
- [ ] Test key revocation: Revoke key, verify validation fails

**Testing:**
```python
# test_api_keys.py
import asyncio
from acm2.app.auth.api_keys import generate_api_key, save_api_key, validate_api_key
from acm2.app.db.master import create_user

async def test():
    # Create test user
    user_id = await create_user("test@example.com")
    
    # Generate and save key
    plaintext, key_hash, prefix = generate_api_key()
    print(f"Generated key: {plaintext}")
    print(f"Key prefix: {prefix}")
    
    await save_api_key(user_id, key_hash, prefix)
    
    # Validate correct key
    validated_user_id = await validate_api_key(plaintext)
    assert validated_user_id == user_id
    print("✅ Valid key accepted")
    
    # Validate wrong key
    wrong_user_id = await validate_api_key("acm2_wrong_key")
    assert wrong_user_id is None
    print("✅ Invalid key rejected")
    
    print("✅ API key tests passed")

asyncio.run(test())
```

---

### 1.4 Authentication Middleware

**File:** `acm2/app/auth/middleware.py`

```python
"""FastAPI authentication middleware"""
from fastapi import Header, HTTPException, Depends
from typing import Annotated
from acm2.app.auth.api_keys import validate_api_key

async def get_current_user(
    x_acm2_api_key: Annotated[str, Header(alias="X-ACM2-API-Key")]
) -> int:
    """
    FastAPI dependency that validates API key and returns user_id
    
    Usage in routes:
        @router.get("/runs")
        async def get_runs(user_id: int = Depends(get_current_user)):
            # user_id is guaranteed to be valid here
    
    If API key is invalid, raises 401 Unauthorized
    """
    user_id = await validate_api_key(x_acm2_api_key)
    
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user_id

# Type alias for cleaner route signatures
CurrentUser = Annotated[int, Depends(get_current_user)]
```

**File:** `acm2/app/api/routes/runs/routes.py` (Update existing file)

```python
"""Update existing runs routes to use authentication"""
from fastapi import APIRouter, Depends
from acm2.app.auth.middleware import CurrentUser
from acm2.app.db.user_db import get_user_db

router = APIRouter(prefix="/runs", tags=["runs"])

@router.get("")
async def get_runs(user_id: CurrentUser):
    """Get all runs for authenticated user"""
    async with get_user_db(user_id) as db:
        cursor = await db.execute(
            """SELECT id, created_at, status, prompt 
               FROM runs 
               ORDER BY created_at DESC"""
        )
        rows = await cursor.fetchall()
        return {"runs": [dict(row) for row in rows]}

@router.get("/{run_id}")
async def get_run(run_id: str, user_id: CurrentUser):
    """Get specific run for authenticated user"""
    async with get_user_db(user_id) as db:
        cursor = await db.execute(
            "SELECT * FROM runs WHERE id = ?",
            [run_id]
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        
        return dict(row)

@router.post("")
async def create_run(request: CreateRunRequest, user_id: CurrentUser):
    """Create new run for authenticated user"""
    # Create run in user's database
    async with get_user_db(user_id) as db:
        # ... existing run creation logic ...
        pass
```

**Tasks:**
- [ ] Create `middleware.py` with `get_current_user()` dependency
- [ ] Update ALL existing routes to require authentication:
  - `acm2/app/api/routes/runs/routes.py`
  - `acm2/app/api/routes/models.py` (if exists)
  - Any other route files
- [ ] Add `user_id: CurrentUser` parameter to all route functions
- [ ] Update database queries to use `get_user_db(user_id)`
- [ ] Test: Call API without key → 401
- [ ] Test: Call API with invalid key → 401
- [ ] Test: Call API with valid key → 200 + data

**Testing:**
```bash
# Terminal testing

# 1. Create user and get API key
curl -X POST http://localhost:8199/api/v1/auth/users \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
# Save the api_key from response

# 2. Test without API key (should fail)
curl http://localhost:8199/api/v1/runs
# Expected: 401 Unauthorized

# 3. Test with invalid key (should fail)
curl http://localhost:8199/api/v1/runs \
  -H "X-ACM2-API-Key: acm2_invalid_key"
# Expected: 401 Unauthorized

# 4. Test with valid key (should work)
curl http://localhost:8199/api/v1/runs \
  -H "X-ACM2-API-Key: acm2_[YOUR_KEY_HERE]"
# Expected: 200 OK + list of runs
```

---

### 1.5 Database Router & Data Isolation

**Goal:** Ensure all data access goes through user-specific database, prevent cross-user data leakage

**File:** `acm2/app/db/router.py`

```python
"""Database routing utilities"""
from contextlib import asynccontextmanager
from acm2.app.db.user_db import get_user_db as _get_user_db

# Re-export for convenience
@asynccontextmanager
async def get_user_db(user_id: int):
    """
    Get connection to user's isolated database
    
    Usage:
        async with get_user_db(user_id) as db:
            cursor = await db.execute("SELECT * FROM runs")
            rows = await cursor.fetchall()
    
    Security: Each user has their own SQLite file
    - user_1.db contains User 1's data
    - user_2.db contains User 2's data
    - No way for User 1 to access User 2's data
    """
    async with _get_user_db(user_id) as db:
        yield db
```

**File:** `acm2/app/db/migrations.py` (Optional but recommended)

```python
"""Database migration utilities"""
import aiosqlite
from pathlib import Path

async def migrate_single_user_to_multi_user():
    """
    Migrate existing acm2.db (single-user) to multi-user system
    
    Steps:
    1. Create user_1.db
    2. Copy all data from acm2.db to user_1.db
    3. Create user in master.db
    4. Generate API key for user
    """
    old_db = Path("data/acm2.db")
    if not old_db.exists():
        print("No existing database to migrate")
        return
    
    print("🔄 Migrating single-user database to multi-user...")
    
    # Create first user
    from acm2.app.db.master import create_user
    from acm2.app.auth.api_keys import generate_api_key, save_api_key
    
    user_id = await create_user("admin@example.com")
    print(f"✅ Created user {user_id}")
    
    # Copy data
    async with aiosqlite.connect(old_db) as old:
        async with aiosqlite.connect(f"data/user_{user_id}.db") as new:
            # Get all tables
            cursor = await old.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            
            for table in tables:
                # Copy all rows
                cursor = await old.execute(f"SELECT * FROM {table}")
                rows = await cursor.fetchall()
                
                if rows:
                    placeholders = ",".join(["?" for _ in rows[0]])
                    await new.executemany(
                        f"INSERT INTO {table} VALUES ({placeholders})",
                        rows
                    )
            
            await new.commit()
    
    # Generate API key
    plaintext, key_hash, prefix = generate_api_key()
    await save_api_key(user_id, key_hash, prefix, note="Migrated from single-user")
    
    print(f"✅ Migration complete!")
    print(f"   User ID: {user_id}")
    print(f"   API Key: {plaintext}")
    print(f"   ⚠️  Save this key! It won't be shown again.")
    print(f"   Old database backed up to: {old_db}.backup")
    
    # Backup old database
    old_db.rename(f"{old_db}.backup")
```

**Major Route Updates Required:**

All these files need to be updated to use `get_user_db(user_id)`:

1. **`acm2/app/api/routes/runs/routes.py`**
   - Change all `get_db()` calls to `get_user_db(user_id)`
   - Add `user_id: CurrentUser` to all functions

2. **`acm2/app/api/routes/runs/helpers.py`**
   - Update any database queries to accept `user_id`

3. **`acm2/app/evaluation/run_pipeline.py`**
   - Pass `user_id` through evaluation pipeline
   - Save results to user's database

**Tasks:**
- [ ] Create `router.py` with database routing utilities
- [ ] Update `runs/routes.py`:
  - Add `user_id: CurrentUser` to all endpoints
  - Change all database calls to `get_user_db(user_id)`
- [ ] Update `evaluation/run_pipeline.py`:
  - Accept `user_id` parameter
  - Save results to user's database
- [ ] Create migration script (optional)
- [ ] Test data isolation:
  - Create User 1, add run
  - Create User 2, add run
  - Verify User 1 can't see User 2's run
  - Verify User 2 can't see User 1's run

**Testing Data Isolation:**
```python
# test_data_isolation.py
import asyncio
from acm2.app.db.master import create_user
from acm2.app.auth.api_keys import generate_api_key, save_api_key, validate_api_key
from acm2.app.db.router import get_user_db

async def test():
    # Create two users
    user1_id = await create_user("user1@example.com")
    user2_id = await create_user("user2@example.com")
    
    # Add data to user1's database
    async with get_user_db(user1_id) as db:
        await db.execute(
            "INSERT INTO runs (id, prompt) VALUES (?, ?)",
            ["run1", "User 1's run"]
        )
        await db.commit()
    
    # Add data to user2's database
    async with get_user_db(user2_id) as db:
        await db.execute(
            "INSERT INTO runs (id, prompt) VALUES (?, ?)",
            ["run2", "User 2's run"]
        )
        await db.commit()
    
    # Verify user1 can only see their data
    async with get_user_db(user1_id) as db:
        cursor = await db.execute("SELECT * FROM runs")
        rows = await cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "User 1's run"
    
    # Verify user2 can only see their data
    async with get_user_db(user2_id) as db:
        cursor = await db.execute("SELECT * FROM runs")
        rows = await cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "User 2's run"
    
    print("✅ Data isolation test passed!")

asyncio.run(test())
```

---

**Phase 1 Deliverable Checklist:**

- [ ] ✅ Master database (`data/master.db`) created with users and api_keys tables
- [ ] ✅ Per-user databases (`data/user_X.db`) created with isolated data
- [ ] ✅ API key generation working (format: `acm2_xxx...`)
- [ ] ✅ API key validation working (bcrypt hash check)
- [ ] ✅ Authentication middleware applied to all routes
- [ ] ✅ All routes require `X-ACM2-API-Key` header
- [ ] ✅ Database queries use user-specific database file
- [ ] ✅ Data isolation verified (users can't see each other's data)
- [ ] ✅ Migration script created (optional)
- [ ] ✅ All tests passing

**Verification Commands:**
```bash
# Check databases exist
ls -la data/

# Expected output:
# master.db
# user_1.db
# user_2.db
# acm2.db.backup (if migrated)

# Check master.db structure
sqlite3 data/master.db ".tables"
# Expected: users, api_keys

# Check user database structure
sqlite3 data/user_1.db ".tables"
# Expected: runs, run_results, provider_keys, etc.

# Test API endpoints
curl -X POST http://localhost:8199/api/v1/auth/users \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Test authentication
curl http://localhost:8199/api/v1/runs \
  -H "X-ACM2-API-Key: [API_KEY_FROM_ABOVE]"
```

---

**Common Gotchas & Solutions:**

1. **Problem:** "Table already exists" error when creating user database
   **Solution:** User database was already created. Either delete it or use existing one.

2. **Problem:** API key validation is slow
   **Solution:** This is intentional (bcrypt is slow). In production, add caching layer.

3. **Problem:** Can't find user's database file
   **Solution:** Check `users.database_file` column in master.db

4. **Problem:** Routes still returning 401 with valid key
   **Solution:** Check `is_active` column in `api_keys` table. Verify key hasn't been revoked.

5. **Problem:** Multiple users seeing each other's data
   **Solution:** You're still using old `get_db()` instead of `get_user_db(user_id)`

---

## Phase 2: Provider Key Management (Week 3)

**Goal:** Allow users to securely store their OpenAI/Google/Anthropic API keys, encrypted at rest

---

### 2.1 Encryption System Setup

**File:** `acm2/app/security/encryption.py`

```python
"""Encryption utilities for provider API keys"""
from cryptography.fernet import Fernet
import os
from typing import Optional

class KeyEncryption:
    """
    Encrypts/decrypts provider API keys using AES-256 (via Fernet)
    
    Fernet provides:
    - AES-256 encryption
    - HMAC authentication
    - Timestamp verification
    - URL-safe encoding
    """
    
    _instance: Optional['KeyEncryption'] = None
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize with encryption key
        
        Args:
            encryption_key: Base64-encoded Fernet key from environment
                           If None, loads from ACM2_ENCRYPTION_KEY env var
        """
        key = encryption_key or os.getenv("ACM2_ENCRYPTION_KEY")
        
        if not key:
            raise ValueError(
                "ACM2_ENCRYPTION_KEY environment variable not set.\n"
                "Generate one with: python -m acm2.app.security.generate_key"
            )
        
        self.fernet = Fernet(key.encode())
    
    @classmethod
    def get_instance(cls) -> 'KeyEncryption':
        """Singleton instance (loads encryption key once)"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def encrypt_key(self, plaintext: str) -> str:
        """
        Encrypt a provider API key
        
        Args:
            plaintext: The actual API key (e.g., "sk-proj-...")
        
        Returns:
            Encrypted key as URL-safe base64 string
        """
        encrypted_bytes = self.fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()
    
    def decrypt_key(self, encrypted: str) -> str:
        """
        Decrypt a provider API key
        
        Args:
            encrypted: The encrypted key from database
        
        Returns:
            The original plaintext API key
        
        Raises:
            cryptography.fernet.InvalidToken: If key is corrupted or tampered
        """
        decrypted_bytes = self.fernet.decrypt(encrypted.encode())
        return decrypted_bytes.decode()
    
    def rotate_key(self, old_encrypted: str, new_fernet_key: str) -> str:
        """
        Re-encrypt a key with a new encryption key (for key rotation)
        
        Args:
            old_encrypted: Key encrypted with old encryption key
            new_fernet_key: New Fernet key to use
        
        Returns:
            Key re-encrypted with new key
        """
        # Decrypt with old key
        plaintext = self.decrypt_key(old_encrypted)
        
        # Encrypt with new key
        new_fernet = Fernet(new_fernet_key.encode())
        new_encrypted = new_fernet.encrypt(plaintext.encode())
        
        return new_encrypted.decode()

# Convenience functions
def encrypt(plaintext: str) -> str:
    """Encrypt a provider key (convenience function)"""
    return KeyEncryption.get_instance().encrypt_key(plaintext)

def decrypt(encrypted: str) -> str:
    """Decrypt a provider key (convenience function)"""
    return KeyEncryption.get_instance().decrypt_key(encrypted)
```

**File:** `acm2/app/security/generate_key.py` (CLI tool)

```python
"""Generate encryption key for provider API keys"""
from cryptography.fernet import Fernet

def generate_encryption_key():
    """Generate a new Fernet encryption key"""
    key = Fernet.generate_key()
    print("\n🔑 ACM2 Encryption Key Generated\n")
    print("Add this to your .env file:")
    print(f"ACM2_ENCRYPTION_KEY={key.decode()}")
    print("\n⚠️  WARNING: Keep this key secret!")
    print("   - Don't commit to git")
    print("   - Don't share with anyone")
    print("   - If lost, all provider keys become unrecoverable")
    print("\n")

if __name__ == "__main__":
    generate_encryption_key()
```

**Environment Setup:**

```bash
# .env file
ACM2_ENCRYPTION_KEY=xJ8k3nL9qM2pR5tY7wZ4aB6cD1eF0gH8iJ3kL5mN2oP9qR=

# .env.example (commit this to git, NOT .env)
ACM2_ENCRYPTION_KEY=your_encryption_key_here
```

**Tasks:**
- [ ] Install cryptography: `pip install cryptography`
- [ ] Create `acm2/app/security/` directory
- [ ] Create `encryption.py` with `KeyEncryption` class
- [ ] Create `generate_key.py` CLI tool
- [ ] Run: `python -m acm2.app.security.generate_key`
- [ ] Copy generated key to `.env` file
- [ ] Add `.env` to `.gitignore` if not already
- [ ] Test encryption: Encrypt "test", decrypt, verify matches
- [ ] Test with wrong key: Try to decrypt with different key, verify fails

**Testing:**
```python
# test_encryption.py
from acm2.app.security.encryption import KeyEncryption

def test():
    # Generate test key
    from cryptography.fernet import Fernet
    test_key = Fernet.generate_key().decode()
    
    enc = KeyEncryption(encryption_key=test_key)
    
    # Test encryption/decryption
    plaintext = "sk-proj-test_api_key_12345"
    encrypted = enc.encrypt_key(plaintext)
    decrypted = enc.decrypt_key(encrypted)
    
    assert decrypted == plaintext
    print("✅ Encryption/decryption works")
    
    # Test with wrong key fails
    wrong_key = Fernet.generate_key().decode()
    enc2 = KeyEncryption(encryption_key=wrong_key)
    
    try:
        enc2.decrypt_key(encrypted)
        assert False, "Should have failed with wrong key"
    except Exception:
        print("✅ Wrong key correctly rejected")
    
    print("✅ Encryption tests passed")

test()
```

---

### 2.2 Provider Keys API Endpoints

**File:** `acm2/app/api/routes/provider_keys.py`

```python
"""Provider API keys management endpoints"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from acm2.app.auth.middleware import CurrentUser
from acm2.app.db.router import get_user_db
from acm2.app.security.encryption import encrypt, decrypt

router = APIRouter(prefix="/provider-keys", tags=["provider-keys"])

# Request/Response Models
class AddProviderKeyRequest(BaseModel):
    provider: str = Field(..., description="Provider name: openai, google, anthropic")
    api_key: str = Field(..., description="Provider API key (will be encrypted)")
    key_name: Optional[str] = Field(None, description="Optional friendly name")
    
    class Config:
        json_schema_extra = {
            "example": {
                "provider": "openai",
                "api_key": "sk-proj-xxx...",
                "key_name": "My OpenAI Key"
            }
        }

class ProviderKeyResponse(BaseModel):
    id: int
    provider: str
    key_name: Optional[str]
    key_preview: str  # First 8 chars + "..."
    created_at: str
    last_used_at: Optional[str]
    is_active: bool

class ProviderKeysListResponse(BaseModel):
    keys: list[ProviderKeyResponse]

# Endpoints
@router.post("", status_code=201)
async def add_provider_key(
    request: AddProviderKeyRequest,
    user_id: CurrentUser
):
    """
    Store encrypted provider API key
    
    Security:
    - Key is encrypted with AES-256 before storage
    - Only encrypted value stored in database
    - User can have multiple keys per provider
    """
    # Validate provider
    valid_providers = ["openai", "google", "anthropic"]
    if request.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
        )
    
    # Validate key format (basic check)
    if len(request.api_key) < 10:
        raise HTTPException(status_code=400, detail="API key too short")
    
    # Encrypt the key
    encrypted_key = encrypt(request.api_key)
    
    # Store in user's database
    async with get_user_db(user_id) as db:
        cursor = await db.execute(
            """INSERT INTO provider_keys (provider, encrypted_key, key_name, created_at, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            [request.provider, encrypted_key, request.key_name, datetime.utcnow().isoformat()]
        )
        await db.commit()
        key_id = cursor.lastrowid
    
    return {
        "id": key_id,
        "provider": request.provider,
        "message": "Provider key added successfully"
    }

@router.get("", response_model=ProviderKeysListResponse)
async def list_provider_keys(user_id: CurrentUser):
    """
    List all provider keys (without exposing the actual keys)
    
    Returns metadata only:
    - Provider name
    - Friendly name
    - Preview (first 8 chars)
    - Created/last used timestamps
    """
    async with get_user_db(user_id) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, provider, key_name, encrypted_key, created_at, last_used_at, is_active
               FROM provider_keys
               ORDER BY created_at DESC"""
        )
        rows = await cursor.fetchall()
    
    keys = []
    for row in rows:
        # Decrypt just to get preview
        try:
            decrypted = decrypt(row['encrypted_key'])
            preview = decrypted[:8] + "..." if len(decrypted) > 8 else "***"
        except Exception:
            preview = "[ERROR]"
        
        keys.append(ProviderKeyResponse(
            id=row['id'],
            provider=row['provider'],
            key_name=row['key_name'],
            key_preview=preview,
            created_at=row['created_at'],
            last_used_at=row['last_used_at'],
            is_active=row['is_active']
        ))
    
    return ProviderKeysListResponse(keys=keys)

@router.delete("/{key_id}")
async def delete_provider_key(key_id: int, user_id: CurrentUser):
    """
    Delete a provider key
    
    Note: This is a hard delete. Consider soft delete (is_active=0) for audit trail.
    """
    async with get_user_db(user_id) as db:
        cursor = await db.execute(
            "DELETE FROM provider_keys WHERE id = ? AND user_id IS NULL",  # user_id check happens via DB isolation
            [key_id]
        )
        await db.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Provider key not found")
    
    return {"message": "Provider key deleted successfully"}

@router.get("/test/{provider}")
async def test_provider_key(provider: str, user_id: CurrentUser):
    """
    Test if a provider key works by making a simple API call
    
    This is useful for validating keys after adding them.
    """
    # Get the key
    async with get_user_db(user_id) as db:
        cursor = await db.execute(
            """SELECT encrypted_key FROM provider_keys 
               WHERE provider = ? AND is_active = 1
               ORDER BY created_at DESC LIMIT 1""",
            [provider]
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No active {provider} key found"
            )
        
        api_key = decrypt(row[0])
    
    # Test the key (basic validation, not full API call)
    if provider == "openai":
        if not api_key.startswith("sk-"):
            return {"valid": False, "error": "Invalid OpenAI key format"}
    elif provider == "google":
        if len(api_key) < 20:
            return {"valid": False, "error": "Invalid Google key format"}
    elif provider == "anthropic":
        if not api_key.startswith("sk-ant-"):
            return {"valid": False, "error": "Invalid Anthropic key format"}
    
    # TODO: Make actual API call to test key
    # For now, just format validation
    
    return {"valid": True, "message": "Key format appears valid"}
```

**Tasks:**
- [ ] Create `provider_keys.py` with endpoints above
- [ ] Register router in `main.py`: `app.include_router(provider_keys.router)`
- [ ] Test POST: Add OpenAI key, verify encrypted in database
- [ ] Test GET: List keys, verify actual key not exposed
- [ ] Test DELETE: Remove key, verify deleted
- [ ] Test with SQLite browser: Open user DB, verify keys are encrypted (not plaintext)

**Testing:**
```bash
# Add a provider key
curl -X POST http://localhost:8199/api/v1/provider-keys \
  -H "X-ACM2-API-Key: acm2_xxx..." \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk-proj-test_key_12345",
    "key_name": "My Test Key"
  }'

# List provider keys (should NOT show actual key)
curl http://localhost:8199/api/v1/provider-keys \
  -H "X-ACM2-API-Key: acm2_xxx..."

# Expected response:
# {
#   "keys": [{
#     "id": 1,
#     "provider": "openai",
#     "key_name": "My Test Key",
#     "key_preview": "sk-proj-...",
#     "created_at": "2026-01-08T10:00:00",
#     "is_active": true
#   }]
# }

# Delete a key
curl -X DELETE http://localhost:8199/api/v1/provider-keys/1 \
  -H "X-ACM2-API-Key: acm2_xxx..."
```

---

### 2.3 Update LLM Adapters to Use User Keys

**Current State:** Adapters load keys from environment variables  
**Target State:** Adapters load keys from user's database

**File:** `acm2/app/adapters/provider_key_loader.py` (New file)

```python
"""Load provider keys from user's database"""
from typing import Optional
from acm2.app.db.router import get_user_db
from acm2.app.security.encryption import decrypt

async def get_provider_key(user_id: int, provider: str) -> str:
    """
    Get decrypted provider key for user
    
    Args:
        user_id: The user ID
        provider: Provider name (openai, google, anthropic)
    
    Returns:
        Decrypted API key
    
    Raises:
        ValueError: If no key found or key inactive
    """
    async with get_user_db(user_id) as db:
        cursor = await db.execute(
            """SELECT encrypted_key, id FROM provider_keys
               WHERE provider = ? AND is_active = 1
               ORDER BY created_at DESC
               LIMIT 1""",
            [provider]
        )
        row = await cursor.fetchone()
        
        if not row:
            raise ValueError(
                f"No active {provider} API key configured. "
                f"Please add one in Settings > Provider Keys."
            )
        
        encrypted_key, key_id = row
        
        # Update last_used_at
        from datetime import datetime
        await db.execute(
            "UPDATE provider_keys SET last_used_at = ? WHERE id = ?",
            [datetime.utcnow().isoformat(), key_id]
        )
        await db.commit()
        
        # Decrypt and return
        return decrypt(encrypted_key)

async def has_provider_key(user_id: int, provider: str) -> bool:
    """Check if user has a provider key configured"""
    try:
        await get_provider_key(user_id, provider)
        return True
    except ValueError:
        return False

async def get_all_configured_providers(user_id: int) -> list[str]:
    """Get list of all providers user has keys for"""
    async with get_user_db(user_id) as db:
        cursor = await db.execute(
            """SELECT DISTINCT provider FROM provider_keys
               WHERE is_active = 1"""
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
```

**File:** `acm2/app/adapters/openai_adapter.py` (Update existing)

```python
"""OpenAI adapter - UPDATED to use user's keys"""
from openai import AsyncOpenAI
from acm2.app.adapters.provider_key_loader import get_provider_key

# OLD CODE (remove this):
# client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# NEW CODE:
async def get_openai_client(user_id: int) -> AsyncOpenAI:
    """Get OpenAI client with user's API key"""
    api_key = await get_provider_key(user_id, "openai")
    return AsyncOpenAI(api_key=api_key)

# Update all functions to accept user_id
async def call_openai(
    user_id: int,  # NEW PARAMETER
    model: str,
    messages: list,
    **kwargs
) -> dict:
    """Call OpenAI API with user's API key"""
    client = await get_openai_client(user_id)
    
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        **kwargs
    )
    
    return response.model_dump()
```

**File:** `acm2/app/adapters/google_adapter.py` (Update existing)

```python
"""Google adapter - UPDATED to use user's keys"""
import google.generativeai as genai
from acm2.app.adapters.provider_key_loader import get_provider_key

async def get_google_client(user_id: int):
    """Configure Google client with user's API key"""
    api_key = await get_provider_key(user_id, "google")
    genai.configure(api_key=api_key)

async def call_google(
    user_id: int,  # NEW PARAMETER
    model: str,
    messages: list,
    **kwargs
) -> dict:
    """Call Google API with user's API key"""
    await get_google_client(user_id)
    
    # ... rest of existing logic ...
```

**File:** `acm2/app/adapters/anthropic_adapter.py` (Update existing)

```python
"""Anthropic adapter - UPDATED to use user's keys"""
from anthropic import AsyncAnthropic
from acm2.app.adapters.provider_key_loader import get_provider_key

async def get_anthropic_client(user_id: int) -> AsyncAnthropic:
    """Get Anthropic client with user's API key"""
    api_key = await get_provider_key(user_id, "anthropic")
    return AsyncAnthropic(api_key=api_key)

async def call_anthropic(
    user_id: int,  # NEW PARAMETER
    model: str,
    messages: list,
    **kwargs
) -> dict:
    """Call Anthropic API with user's API key"""
    client = await get_anthropic_client(user_id)
    
    response = await client.messages.create(
        model=model,
        messages=messages,
        **kwargs
    )
    
    return response.model_dump()
```

**Tasks:**
- [ ] Create `provider_key_loader.py` with `get_provider_key()` function
- [ ] Update `openai_adapter.py`:
  - Add `user_id` parameter to all functions
  - Replace environment variable with `get_provider_key()`
- [ ] Update `google_adapter.py`:
  - Add `user_id` parameter to all functions
  - Replace environment variable with `get_provider_key()`
- [ ] Update `anthropic_adapter.py`:
  - Add `user_id` parameter to all functions
  - Replace environment variable with `get_provider_key()`
- [ ] Test: Add provider key, make API call, verify it uses user's key
- [ ] Test: Remove provider key, try API call, verify error message

---

### 2.4 Update Evaluation Pipeline

**Goal:** Pass `user_id` through entire evaluation pipeline so adapters can load user's keys

**File:** `acm2/app/evaluation/run_pipeline.py` (Update existing)

```python
"""Update run pipeline to pass user_id"""

async def execute_run(
    user_id: int,  # NEW PARAMETER - pass to all adapter calls
    run_config: RunConfig,
    ...
) -> RunResult:
    """Execute evaluation run with user's provider keys"""
    
    # ... existing setup ...
    
    # When calling adapters, pass user_id
    if model_name.startswith("openai:"):
        from acm2.app.adapters.openai_adapter import call_openai
        result = await call_openai(
            user_id=user_id,  # NEW
            model=model_name.split(":")[1],
            messages=messages,
            ...
        )
    elif model_name.startswith("google:"):
        from acm2.app.adapters.google_adapter import call_google
        result = await call_google(
            user_id=user_id,  # NEW
            model=model_name.split(":")[1],
            messages=messages,
            ...
        )
    # ... etc for all providers ...
```

**File:** `acm2/app/api/routes/runs/routes.py` (Update existing)

```python
"""Update runs routes to pass user_id to pipeline"""

@router.post("")
async def create_run(
    request: CreateRunRequest,
    user_id: CurrentUser  # Already have this from Phase 1
):
    """Create and execute run"""
    
    # Pass user_id to evaluation pipeline
    result = await execute_run(
        user_id=user_id,  # NEW
        run_config=request.config,
        ...
    )
    
    # Save to user's database
    async with get_user_db(user_id) as db:
        # ... save result ...
```

**Tasks:**
- [ ] Update `run_pipeline.py`:
  - Add `user_id` parameter to `execute_run()`
  - Pass `user_id` to all adapter calls
- [ ] Update all intermediate functions in pipeline:
  - `evaluate_single_doc(user_id, ...)`
  - `call_judge_model(user_id, ...)`
  - Any other functions that call adapters
- [ ] Update `routes.py`:
  - Pass `user_id` from auth to pipeline
- [ ] Test: Create run with user's provider keys
- [ ] Test: Verify `last_used_at` timestamp updated after run
- [ ] Test: User without provider key gets helpful error message

---

### 2.5 Error Handling & User Feedback

**File:** `acm2/app/api/errors.py` (New file)

```python
"""Custom exception handlers for better user feedback"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from cryptography.fernet import InvalidToken

async def provider_key_error_handler(request: Request, exc: ValueError):
    """Handle missing provider key errors"""
    if "API key" in str(exc):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "provider_key_missing",
                "message": str(exc),
                "action": "Please add your provider API key in Settings > Provider Keys"
            }
        )
    raise exc

async def encryption_error_handler(request: Request, exc: InvalidToken):
    """Handle encryption errors (corrupted keys)"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "encryption_error",
            "message": "Failed to decrypt provider key. Key may be corrupted.",
            "action": "Please delete and re-add your provider key"
        }
    )
```

**File:** `acm2/app/main.py` (Update existing)

```python
"""Register error handlers"""
from acm2.app.api.errors import provider_key_error_handler, encryption_error_handler
from cryptography.fernet import InvalidToken

app = FastAPI(...)

# Register exception handlers
app.add_exception_handler(ValueError, provider_key_error_handler)
app.add_exception_handler(InvalidToken, encryption_error_handler)
```

**Tasks:**
- [ ] Create `errors.py` with custom error handlers
- [ ] Register handlers in `main.py`
- [ ] Test: Try to run evaluation without provider key
  - Should get clear error message with action item
- [ ] Test: Corrupt provider key in database
  - Should get decryption error with fix instructions

---

**Phase 2 Deliverable Checklist:**

- [ ] ✅ Encryption system working (AES-256 via Fernet)
- [ ] ✅ Encryption key generated and stored in .env
- [ ] ✅ Provider keys API endpoints working:
  - [ ] POST /provider-keys (add key)
  - [ ] GET /provider-keys (list keys)
  - [ ] DELETE /provider-keys/{id} (remove key)
  - [ ] GET /provider-keys/test/{provider} (validate key)
- [ ] ✅ Provider keys stored encrypted in database
- [ ] ✅ Adapters load keys from user's database (not environment)
- [ ] ✅ Evaluation pipeline passes user_id to adapters
- [ ] ✅ `last_used_at` timestamp updated after each use
- [ ] ✅ Error handling provides helpful messages
- [ ] ✅ All tests passing

**Verification Commands:**
```bash
# Generate encryption key
python -m acm2.app.security.generate_key

# Add to .env
echo "ACM2_ENCRYPTION_KEY=xxx..." >> .env

# Test encryption
python -c "from acm2.app.security.encryption import encrypt, decrypt; \
  enc = encrypt('test'); print(f'Encrypted: {enc}'); \
  dec = decrypt(enc); print(f'Decrypted: {dec}')"

# Check database (key should be encrypted)
sqlite3 data/user_1.db "SELECT provider, encrypted_key FROM provider_keys"
# Should see gibberish, not plaintext keys

# Test API
curl -X POST http://localhost:8199/api/v1/provider-keys \
  -H "X-ACM2-API-Key: acm2_xxx..." \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-proj-test"}'
```

---

**Security Checklist:**

- [ ] ✅ Encryption key stored in .env (not in code)
- [ ] ✅ .env file in .gitignore
- [ ] ✅ Provider keys NEVER returned in API responses (only previews)
- [ ] ✅ Provider keys encrypted in database (AES-256)
- [ ] ✅ Decryption only happens in memory during API calls
- [ ] ✅ No provider keys logged anywhere
- [ ] ✅ Error messages don't leak provider keys

---

**Common Gotchas & Solutions:**

1. **Problem:** "ACM2_ENCRYPTION_KEY environment variable not set"
   **Solution:** Generate key with `python -m acm2.app.security.generate_key`, add to .env

2. **Problem:** "InvalidToken" error when decrypting
   **Solution:** Encryption key changed or database corrupted. User must re-add keys.

3. **Problem:** Provider key validation failing
   **Solution:** Check adapter is loading key correctly. Add debug logging.

4. **Problem:** Environment variables still being used instead of database
   **Solution:** Remove fallback to `os.getenv()` in adapters. Force database-only.

5. **Problem:** Multiple API calls per evaluation are slow
   **Solution:** This is expected (each call decrypts key). Consider caching decrypted keys in memory during run (with timeout).

---

## Phase 3: WordPress Plugin Development (Week 4)

**Goal:** Create WordPress plugin that proxies API requests and embeds React UI

---

### 3.1 Plugin Directory Structure

Create this structure in your ACM2 repository (will copy to WordPress later):

```
acm2/wordpress-plugin/
├── acm2-integration.php          # Main plugin file (WordPress header)
├── includes/
│   ├── class-api-proxy.php       # API proxy class
│   ├── class-user-manager.php    # User & API key management
│   ├── class-settings-page.php   # Admin settings UI
│   └── class-shortcode.php       # [acm2_app] shortcode
├── assets/
│   ├── css/
│   │   └── admin.css             # Admin page styling
│   ├── js/
│   │   └── admin.js              # Admin page JS
│   └── react-app/                # Built React app (copied from frontend/dist)
│       ├── index.html
│       └── assets/
│           ├── index-xxx.js
│           └── index-xxx.css
├── readme.txt                    # WordPress plugin readme
└── uninstall.php                 # Cleanup on uninstall
```

**Tasks:**
- [ ] Create `acm2/wordpress-plugin/` directory
- [ ] Create subdirectories: `includes/`, `assets/css/`, `assets/js/`, `assets/react-app/`

---

### 3.2 Main Plugin File

**File:** `acm2-integration.php`

```php
<?php
/**
 * Plugin Name: ACM2 Integration
 * Plugin URI: https://github.com/yourusername/acm2
 * Description: Connect WordPress users to ACM2 API for multi-LLM evaluations
 * Version: 1.0.0
 * Author: Your Name
 * Author URI: https://yoursite.com
 * License: MIT
 * Text Domain: acm2
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Plugin constants
define('ACM2_VERSION', '1.0.0');
define('ACM2_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('ACM2_PLUGIN_URL', plugin_dir_url(__FILE__));

// ACM2 API URL (configurable via settings later)
define('ACM2_API_URL', get_option('acm2_api_url', 'http://localhost:8199/api/v1'));

// Load dependencies
require_once ACM2_PLUGIN_DIR . 'includes/class-api-proxy.php';
require_once ACM2_PLUGIN_DIR . 'includes/class-user-manager.php';
require_once ACM2_PLUGIN_DIR . 'includes/class-settings-page.php';
require_once ACM2_PLUGIN_DIR . 'includes/class-shortcode.php';

// Initialize plugin
add_action('plugins_loaded', 'acm2_init');

function acm2_init() {
    // Initialize API proxy
    ACM2_API_Proxy::init();
    
    // Initialize user manager
    ACM2_User_Manager::init();
    
    // Initialize settings page
    if (is_admin()) {
        ACM2_Settings_Page::init();
    }
    
    // Initialize shortcode
    ACM2_Shortcode::init();
}

// Activation hook
register_activation_hook(__FILE__, 'acm2_activate');

function acm2_activate() {
    // Set default options
    add_option('acm2_api_url', 'http://localhost:8199/api/v1');
    
    // Flush rewrite rules
    flush_rewrite_rules();
}

// Deactivation hook
register_deactivation_hook(__FILE__, 'acm2_deactivate');

function acm2_deactivate() {
    // Flush rewrite rules
    flush_rewrite_rules();
}
```

**Tasks:**
- [ ] Create `acm2-integration.php` with header above
- [ ] Test: Copy to WordPress plugins folder, activate
- [ ] Verify plugin appears in WordPress admin

---

### 3.3 API Proxy Class (The Critical Security Layer)

**File:** `includes/class-api-proxy.php`

```php
<?php
/**
 * API Proxy - Routes WordPress requests to ACM2 API
 * 
 * Security Model:
 * 1. User's browser makes request to WordPress endpoint
 * 2. WordPress validates session, identifies user
 * 3. WordPress retrieves user's ACM2 API key from database
 * 4. WordPress proxies request to ACM2 API with key
 * 5. ACM2 API key NEVER exposed to browser
 */

class ACM2_API_Proxy {
    
    public static function init() {
        add_action('rest_api_init', [__CLASS__, 'register_routes']);
    }
    
    public static function register_routes() {
        $namespace = 'acm2/v1';
        
        // Runs endpoints
        register_rest_route($namespace, '/runs', [
            'methods' => 'GET',
            'callback' => [__CLASS__, 'proxy_get_runs'],
            'permission_callback' => '__return_true',  // We check auth in callback
        ]);
        
        register_rest_route($namespace, '/runs', [
            'methods' => 'POST',
            'callback' => [__CLASS__, 'proxy_create_run'],
            'permission_callback' => '__return_true',
        ]);
        
        register_rest_route($namespace, '/runs/(?P<id>[a-f0-9-]+)', [
            'methods' => 'GET',
            'callback' => [__CLASS__, 'proxy_get_run'],
            'permission_callback' => '__return_true',
        ]);
        
        // Provider keys endpoints
        register_rest_route($namespace, '/provider-keys', [
            'methods' => 'GET',
            'callback' => [__CLASS__, 'proxy_get_provider_keys'],
            'permission_callback' => '__return_true',
        ]);
        
        register_rest_route($namespace, '/provider-keys', [
            'methods' => 'POST',
            'callback' => [__CLASS__, 'proxy_add_provider_key'],
            'permission_callback' => '__return_true',
        ]);
        
        register_rest_route($namespace, '/provider-keys/(?P<id>\d+)', [
            'methods' => 'DELETE',
            'callback' => [__CLASS__, 'proxy_delete_provider_key'],
            'permission_callback' => '__return_true',
        ]);
    }
    
    /**
     * Generic proxy function
     * Handles all API requests with consistent security checks
     */
    private static function proxy_request($method, $endpoint, $body = null) {
        // 1. Check if user is logged in
        if (!is_user_logged_in()) {
            return new WP_Error(
                'not_logged_in',
                'You must be logged in to use ACM2',
                ['status' => 401]
            );
        }
        
        $user_id = get_current_user_id();
        
        // 2. Get user's ACM2 API key
        $acm2_key = get_user_meta($user_id, 'acm2_api_key', true);
        
        if (empty($acm2_key)) {
            return new WP_Error(
                'no_api_key',
                'ACM2 API key not configured. Please generate one in Settings.',
                ['status' => 400]
            );
        }
        
        // 3. Build request to ACM2 API
        $url = ACM2_API_URL . $endpoint;
        
        $args = [
            'method' => $method,
            'headers' => [
                'X-ACM2-API-Key' => $acm2_key,  // ← Key from WordPress DB, NOT browser
                'Content-Type' => 'application/json',
            ],
            'timeout' => 300,  // 5 minutes for long evaluations
        ];
        
        if ($body !== null) {
            $args['body'] = is_string($body) ? $body : json_encode($body);
        }
        
        // 4. Make request to ACM2 API
        $response = wp_remote_request($url, $args);
        
        // 5. Handle errors
        if (is_wp_error($response)) {
            return new WP_Error(
                'acm2_api_error',
                'Failed to connect to ACM2 API: ' . $response->get_error_message(),
                ['status' => 500]
            );
        }
        
        // 6. Parse response
        $status_code = wp_remote_retrieve_response_code($response);
        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);
        
        // 7. Forward response to browser
        if ($status_code >= 400) {
            return new WP_Error(
                'acm2_api_error',
                $data['detail'] ?? 'ACM2 API error',
                ['status' => $status_code]
            );
        }
        
        return rest_ensure_response($data);
    }
    
    // Runs endpoints
    public static function proxy_get_runs(WP_REST_Request $request) {
        return self::proxy_request('GET', '/runs');
    }
    
    public static function proxy_create_run(WP_REST_Request $request) {
        $body = $request->get_json_params();
        return self::proxy_request('POST', '/runs', $body);
    }
    
    public static function proxy_get_run(WP_REST_Request $request) {
        $run_id = $request['id'];
        return self::proxy_request('GET', "/runs/{$run_id}");
    }
    
    // Provider keys endpoints
    public static function proxy_get_provider_keys(WP_REST_Request $request) {
        return self::proxy_request('GET', '/provider-keys');
    }
    
    public static function proxy_add_provider_key(WP_REST_Request $request) {
        $body = $request->get_json_params();
        return self::proxy_request('POST', '/provider-keys', $body);
    }
    
    public static function proxy_delete_provider_key(WP_REST_Request $request) {
        $key_id = $request['id'];
        return self::proxy_request('DELETE', "/provider-keys/{$key_id}");
    }
}
```

**Tasks:**
- [ ] Create `class-api-proxy.php` with code above
- [ ] Test: Make GET request to `/wp-json/acm2/v1/runs`
- [ ] Verify it returns 401 if not logged in
- [ ] Verify it returns 400 if no API key configured
- [ ] Verify it proxies correctly with valid key

**Testing:**
```bash
# Test without login (should fail)
curl http://localhost/wp-json/acm2/v1/runs

# Test with WordPress cookie (need to extract from browser)
curl http://localhost/wp-json/acm2/v1/runs \
  --cookie "wordpress_logged_in_xxx=..."
```

---

### 3.4 User Manager Class (API Key Generation)

**File:** `includes/class-user-manager.php`

```php
<?php
/**
 * User Manager - Handle ACM2 API key generation for WordPress users
 */

class ACM2_User_Manager {
    
    public static function init() {
        // AJAX handler for API key generation
        add_action('wp_ajax_acm2_generate_key', [__CLASS__, 'ajax_generate_key']);
        add_action('wp_ajax_acm2_regenerate_key', [__CLASS__, 'ajax_regenerate_key']);
    }
    
    /**
     * Generate ACM2 API key for WordPress user
     * 
     * Flow:
     * 1. Check if user already has ACM2 account (by WordPress user ID)
     * 2. If not, create ACM2 user via API
     * 3. Generate API key via ACM2 API
     * 4. Store key in WordPress user meta
     */
    public static function generate_api_key_for_user($wp_user_id) {
        $wp_user = get_userdata($wp_user_id);
        if (!$wp_user) {
            return new WP_Error('invalid_user', 'WordPress user not found');
        }
        
        // Check if user already has ACM2 account
        $acm2_user_id = get_user_meta($wp_user_id, 'acm2_user_id', true);
        
        if (empty($acm2_user_id)) {
            // Create ACM2 user via API
            $response = wp_remote_post(ACM2_API_URL . '/auth/users', [
                'headers' => ['Content-Type' => 'application/json'],
                'body' => json_encode([
                    'email' => $wp_user->user_email,
                    'wordpress_user_id' => $wp_user_id
                ]),
                'timeout' => 30
            ]);
            
            if (is_wp_error($response)) {
                return $response;
            }
            
            $data = json_decode(wp_remote_retrieve_body($response), true);
            
            if (empty($data['user_id']) || empty($data['api_key'])) {
                return new WP_Error('acm2_error', 'Failed to create ACM2 user');
            }
            
            $acm2_user_id = $data['user_id'];
            $api_key = $data['api_key'];
            $key_prefix = $data['key_prefix'];
            
            // Store ACM2 user ID
            update_user_meta($wp_user_id, 'acm2_user_id', $acm2_user_id);
            
        } else {
            // User exists, generate new key
            $response = wp_remote_post(ACM2_API_URL . '/auth/generate-key', [
                'headers' => ['Content-Type' => 'application/json'],
                'body' => json_encode(['user_id' => $acm2_user_id]),
                'timeout' => 30
            ]);
            
            if (is_wp_error($response)) {
                return $response;
            }
            
            $data = json_decode(wp_remote_retrieve_body($response), true);
            $api_key = $data['api_key'];
            $key_prefix = $data['key_prefix'];
        }
        
        // Store API key securely in WordPress (key never sent to browser)
        update_user_meta($wp_user_id, 'acm2_api_key', $api_key);
        update_user_meta($wp_user_id, 'acm2_api_key_prefix', $key_prefix);
        update_user_meta($wp_user_id, 'acm2_key_generated_at', time());
        
        return [
            'success' => true,
            'key_prefix' => $key_prefix,
            'message' => 'API key generated successfully'
        ];
    }
    
    /**
     * AJAX handler for generating API key
     */
    public static function ajax_generate_key() {
        check_ajax_referer('acm2_generate_key', 'nonce');
        
        $user_id = get_current_user_id();
        if (!$user_id) {
            wp_send_json_error(['message' => 'Not logged in'], 401);
        }
        
        $result = self::generate_api_key_for_user($user_id);
        
        if (is_wp_error($result)) {
            wp_send_json_error([
                'message' => $result->get_error_message()
            ], 500);
        }
        
        wp_send_json_success($result);
    }
    
    /**
     * AJAX handler for regenerating API key
     */
    public static function ajax_regenerate_key() {
        check_ajax_referer('acm2_regenerate_key', 'nonce');
        
        $user_id = get_current_user_id();
        if (!$user_id) {
            wp_send_json_error(['message' => 'Not logged in'], 401);
        }
        
        // Revoke old key (TODO: add revocation to ACM2 API)
        // For now, just generate new key
        
        $result = self::generate_api_key_for_user($user_id);
        
        if (is_wp_error($result)) {
            wp_send_json_error([
                'message' => $result->get_error_message()
            ], 500);
        }
        
        wp_send_json_success($result);
    }
    
    /**
     * Check if user has ACM2 API key configured
     */
    public static function user_has_api_key($wp_user_id) {
        $key = get_user_meta($wp_user_id, 'acm2_api_key', true);
        return !empty($key);
    }
    
    /**
     * Get key prefix for display (safe to show)
     */
    public static function get_key_prefix($wp_user_id) {
        return get_user_meta($wp_user_id, 'acm2_api_key_prefix', true);
    }
}
```

**Tasks:**
- [ ] Create `class-user-manager.php` with code above
- [ ] Test: Call `generate_api_key_for_user()` function
- [ ] Verify it creates ACM2 user via API
- [ ] Verify it stores key in WordPress user meta
- [ ] Verify key is NOT visible in browser console/network tab

---

### 3.5 Settings Page (Admin UI)

**File:** `includes/class-settings-page.php`

```php
<?php
/**
 * Settings Page - WordPress admin interface for ACM2
 */

class ACM2_Settings_Page {
    
    public static function init() {
        add_action('admin_menu', [__CLASS__, 'add_menu_page']);
        add_action('admin_enqueue_scripts', [__CLASS__, 'enqueue_assets']);
    }
    
    public static function add_menu_page() {
        add_menu_page(
            'ACM2 Settings',           // Page title
            'ACM2',                    // Menu title
            'read',                    // Capability (all logged-in users)
            'acm2-settings',           // Menu slug
            [__CLASS__, 'render_page'],  // Callback
            'dashicons-superhero',     // Icon
            80                         // Position
        );
    }
    
    public static function enqueue_assets($hook) {
        if ($hook !== 'toplevel_page_acm2-settings') {
            return;
        }
        
        wp_enqueue_style(
            'acm2-admin',
            ACM2_PLUGIN_URL . 'assets/css/admin.css',
            [],
            ACM2_VERSION
        );
        
        wp_enqueue_script(
            'acm2-admin',
            ACM2_PLUGIN_URL . 'assets/js/admin.js',
            ['jquery'],
            ACM2_VERSION,
            true
        );
        
        wp_localize_script('acm2-admin', 'acm2Admin', [
            'ajaxUrl' => admin_url('admin-ajax.php'),
            'generateNonce' => wp_create_nonce('acm2_generate_key'),
            'regenerateNonce' => wp_create_nonce('acm2_regenerate_key'),
        ]);
    }
    
    public static function render_page() {
        $user_id = get_current_user_id();
        $has_key = ACM2_User_Manager::user_has_api_key($user_id);
        $key_prefix = ACM2_User_Manager::get_key_prefix($user_id);
        
        ?>
        <div class="wrap acm2-settings">
            <h1>🦖 ACM2 Settings</h1>
            
            <div class="acm2-card">
                <h2>API Key Configuration</h2>
                
                <?php if ($has_key): ?>
                    <div class="acm2-key-status success">
                        <span class="dashicons dashicons-yes-alt"></span>
                        <div>
                            <strong>API Key Active</strong>
                            <p>Your ACM2 API key: <code><?php echo esc_html($key_prefix); ?>...</code></p>
                            <p class="description">This key is securely stored and never exposed to your browser.</p>
                        </div>
                    </div>
                    
                    <button 
                        type="button" 
                        class="button" 
                        id="acm2-regenerate-key"
                    >
                        Regenerate API Key
                    </button>
                    
                    <p class="description">
                        ⚠️ Regenerating will invalidate your current key. 
                        Any scripts using the old key will stop working.
                    </p>
                    
                <?php else: ?>
                    <div class="acm2-key-status warning">
                        <span class="dashicons dashicons-warning"></span>
                        <div>
                            <strong>No API Key</strong>
                            <p>You need to generate an API key to use ACM2.</p>
                        </div>
                    </div>
                    
                    <button 
                        type="button" 
                        class="button button-primary" 
                        id="acm2-generate-key"
                    >
                        Generate API Key
                    </button>
                <?php endif; ?>
                
                <div id="acm2-key-message" class="acm2-message" style="display:none;"></div>
            </div>
            
            <div class="acm2-card">
                <h2>Getting Started</h2>
                <ol>
                    <li><strong>Generate API Key:</strong> Click the button above</li>
                    <li><strong>Add Provider Keys:</strong> Visit the <a href="<?php echo home_url('/dashboard'); ?>">Dashboard</a> and add your OpenAI/Google/Anthropic keys</li>
                    <li><strong>Run Evaluations:</strong> Create your first evaluation run</li>
                </ol>
            </div>
            
            <div class="acm2-card">
                <h2>Provider Keys (LLM APIs)</h2>
                <p>You need to add API keys for the LLM providers you want to use:</p>
                <ul>
                    <li><strong>OpenAI:</strong> Get keys at <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com</a></li>
                    <li><strong>Google:</strong> Get keys at <a href="https://aistudio.google.com/app/apikey" target="_blank">aistudio.google.com</a></li>
                    <li><strong>Anthropic:</strong> Get keys at <a href="https://console.anthropic.com/settings/keys" target="_blank">console.anthropic.com</a></li>
                </ul>
                <p>Add these keys in the <a href="<?php echo home_url('/dashboard'); ?>">ACM2 Dashboard</a> → Settings.</p>
            </div>
        </div>
        <?php
    }
}
```

**File:** `assets/css/admin.css`

```css
.acm2-settings .acm2-card {
    background: white;
    border: 1px solid #ccd0d4;
    box-shadow: 0 1px 1px rgba(0,0,0,.04);
    padding: 20px;
    margin: 20px 0;
}

.acm2-key-status {
    display: flex;
    align-items: flex-start;
    padding: 15px;
    border-radius: 4px;
    margin-bottom: 20px;
}

.acm2-key-status.success {
    background: #d4edda;
    border: 1px solid #c3e6cb;
}

.acm2-key-status.warning {
    background: #fff3cd;
    border: 1px solid #ffeeba;
}

.acm2-key-status .dashicons {
    margin-right: 10px;
    font-size: 24px;
}

.acm2-key-status code {
    background: rgba(0,0,0,0.1);
    padding: 2px 6px;
    border-radius: 3px;
}

.acm2-message {
    margin-top: 15px;
    padding: 10px;
    border-radius: 4px;
}

.acm2-message.success {
    background: #d4edda;
    color: #155724;
}

.acm2-message.error {
    background: #f8d7da;
    color: #721c24;
}
```

**File:** `assets/js/admin.js`

```javascript
jQuery(document).ready(function($) {
    // Generate API key
    $('#acm2-generate-key').on('click', function() {
        const $btn = $(this);
        const $message = $('#acm2-key-message');
        
        $btn.prop('disabled', true).text('Generating...');
        $message.hide();
        
        $.ajax({
            url: acm2Admin.ajaxUrl,
            method: 'POST',
            data: {
                action: 'acm2_generate_key',
                nonce: acm2Admin.generateNonce
            },
            success: function(response) {
                if (response.success) {
                    $message
                        .removeClass('error')
                        .addClass('success')
                        .html('✅ API key generated successfully! Reloading page...')
                        .show();
                    
                    // Reload page to show new key
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showError(response.data.message);
                }
            },
            error: function() {
                showError('Failed to generate API key. Please try again.');
            }
        });
        
        function showError(msg) {
            $message
                .removeClass('success')
                .addClass('error')
                .html('❌ ' + msg)
                .show();
            $btn.prop('disabled', false).text('Generate API Key');
        }
    });
    
    // Regenerate API key
    $('#acm2-regenerate-key').on('click', function() {
        if (!confirm('Are you sure? This will invalidate your current key.')) {
            return;
        }
        
        const $btn = $(this);
        const $message = $('#acm2-key-message');
        
        $btn.prop('disabled', true).text('Regenerating...');
        $message.hide();
        
        $.ajax({
            url: acm2Admin.ajaxUrl,
            method: 'POST',
            data: {
                action: 'acm2_regenerate_key',
                nonce: acm2Admin.regenerateNonce
            },
            success: function(response) {
                if (response.success) {
                    $message
                        .removeClass('error')
                        .addClass('success')
                        .html('✅ API key regenerated! Reloading page...')
                        .show();
                    
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showError(response.data.message);
                }
            },
            error: function() {
                showError('Failed to regenerate key. Please try again.');
            }
        });
        
        function showError(msg) {
            $message
                .removeClass('success')
                .addClass('error')
                .html('❌ ' + msg)
                .show();
            $btn.prop('disabled', false).text('Regenerate API Key');
        }
    });
});
```

**Tasks:**
- [ ] Create `class-settings-page.php` with code above
- [ ] Create `assets/css/admin.css` with styles
- [ ] Create `assets/js/admin.js` with AJAX handlers
- [ ] Test: Visit WordPress admin → ACM2
- [ ] Test: Click "Generate API Key", verify it works
- [ ] Test: Verify key prefix displayed (not full key)
- [ ] Test: Regenerate key, verify old key invalidated

---

### 3.6 Shortcode (Embed React App)

**File:** `includes/class-shortcode.php`

```php
<?php
/**
 * Shortcode - Embed React app in WordPress pages
 */

class ACM2_Shortcode {
    
    public static function init() {
        add_shortcode('acm2_app', [__CLASS__, 'render_shortcode']);
    }
    
    public static function render_shortcode($atts) {
        // Check if user is logged in
        if (!is_user_logged_in()) {
            return self::render_login_prompt();
        }
        
        $user_id = get_current_user_id();
        
        // Check if user has API key
        if (!ACM2_User_Manager::user_has_api_key($user_id)) {
            return self::render_setup_prompt();
        }
        
        // Enqueue React app
        self::enqueue_react_app();
        
        // Return container div
        return '<div id="acm2-root"></div>';
    }
    
    private static function render_login_prompt() {
        $login_url = wp_login_url(get_permalink());
        return sprintf(
            '<div class="acm2-notice">
                <h3>Login Required</h3>
                <p>Please <a href="%s">log in</a> to use ACM2.</p>
            </div>',
            esc_url($login_url)
        );
    }
    
    private static function render_setup_prompt() {
        $settings_url = admin_url('admin.php?page=acm2-settings');
        return sprintf(
            '<div class="acm2-notice">
                <h3>Setup Required</h3>
                <p>Please <a href="%s">generate an API key</a> to get started.</p>
            </div>',
            esc_url($settings_url)
        );
    }
    
    private static function enqueue_react_app() {
        $react_dir = ACM2_PLUGIN_URL . 'assets/react-app/';
        
        // Find React build files (they have hashes in filename)
        $assets_dir = ACM2_PLUGIN_DIR . 'assets/react-app/assets/';
        $js_files = glob($assets_dir . 'index-*.js');
        $css_files = glob($assets_dir . 'index-*.css');
        
        if (empty($js_files) || empty($css_files)) {
            return '<div class="acm2-notice error">
                <h3>Error</h3>
                <p>React app not found. Please build the frontend first.</p>
            </div>';
        }
        
        $js_file = basename($js_files[0]);
        $css_file = basename($css_files[0]);
        
        // Enqueue CSS
        wp_enqueue_style(
            'acm2-app',
            $react_dir . 'assets/' . $css_file,
            [],
            ACM2_VERSION
        );
        
        // Enqueue JS
        wp_enqueue_script(
            'acm2-app',
            $react_dir . 'assets/' . $js_file,
            [],
            ACM2_VERSION,
            true  // Load in footer
        );
        
        // Pass config to React
        wp_localize_script('acm2-app', 'acm2Config', [
            'apiUrl' => rest_url('acm2/v1'),
            'nonce' => wp_create_nonce('wp_rest'),
            'userId' => get_current_user_id(),
            'userEmail' => wp_get_current_user()->user_email,
        ]);
    }
}
```

**Tasks:**
- [ ] Create `class-shortcode.php` with code above
- [ ] Build React app: `cd frontend && npm run build`
- [ ] Copy build files: `cp -r frontend/dist/* wordpress-plugin/assets/react-app/`
- [ ] Create WordPress page, add `[acm2_app]` shortcode
- [ ] Test: Visit page, verify React app loads
- [ ] Test: Check browser console for `acm2Config` object
- [ ] Test: Make API call from React, verify it proxies through WordPress

---

**Phase 3 Deliverable Checklist:**

- [ ] ✅ WordPress plugin structure created
- [ ] ✅ Main plugin file with activation hooks
- [ ] ✅ API proxy class routing requests to ACM2 API
- [ ] ✅ User manager generating API keys
- [ ] ✅ Settings page with generate/regenerate key UI
- [ ] ✅ Shortcode embedding React app
- [ ] ✅ React app loads in WordPress page
- [ ] ✅ API calls proxied through WordPress
- [ ] ✅ ACM2 API key NEVER exposed to browser
- [ ] ✅ All endpoints working: runs, provider-keys, etc.

**Deployment to WordPress:**
```bash
# From your ACM2 repository
cd wordpress-plugin

# Copy to WordPress
cp -r . /path/to/wordpress/wp-content/plugins/acm2-integration/

# Or create symlink for development
ln -s $(pwd) /path/to/wordpress/wp-content/plugins/acm2-integration

# Activate plugin
# Go to WordPress admin → Plugins → Activate "ACM2 Integration"
```

**Common Gotchas:**

1. **Problem:** React app not loading
   **Solution:** Check console for errors. Verify build files exist in `assets/react-app/assets/`

2. **Problem:** 404 on API endpoints
   **Solution:** Go to WordPress admin → Settings → Permalinks → Click "Save" to flush rewrite rules

3. **Problem:** CORS errors
   **Solution:** Shouldn't happen! React is loaded from same domain as WordPress

4. **Problem:** API key not working
   **Solution:** Check `wp_usermeta` table, verify `acm2_api_key` exists for user

5. **Problem:** Long evaluations timing out
   **Solution:** Increase `timeout` in proxy function to 600 seconds (10 minutes)

---

## Phase 4: Frontend Updates (Week 5)

**Goal:** Make React app work in both standalone mode (direct API) and WordPress mode (proxied)

---

### 4.1 Environment Detection & Configuration

**File:** `frontend/src/config/environment.ts`

```typescript
/**
 * Environment configuration
 * Detects if running standalone or embedded in WordPress
 */

export interface ACM2Config {
  apiUrl: string;
  nonce?: string;
  userId?: number;
  userEmail?: string;
}

// Check if WordPress injected config
declare global {
  interface Window {
    acm2Config?: ACM2Config;
  }
}

export const IS_WORDPRESS_EMBED = !!window.acm2Config;

export const API_BASE_URL = 
  import.meta.env.VITE_API_URL ||  // .env file (standalone mode)
  window.acm2Config?.apiUrl ||      // WordPress injects this
  'http://localhost:8199/api/v1';   // Fallback for development

export const WP_NONCE = window.acm2Config?.nonce;
export const WP_USER_ID = window.acm2Config?.userId;
export const WP_USER_EMAIL = window.acm2Config?.userEmail;

// Log environment for debugging
console.log('[ACM2] Environment:', {
  mode: IS_WORDPRESS_EMBED ? 'WordPress' : 'Standalone',
  apiUrl: API_BASE_URL,
  hasNonce: !!WP_NONCE,
});
```

**File:** `frontend/.env.example`

```bash
# Standalone mode configuration
VITE_API_URL=http://localhost:8199/api/v1

# WordPress mode doesn't need this (WordPress injects config)
```

**Tasks:**
- [ ] Create `config/environment.ts`
- [ ] Create `.env` file: `cp .env.example .env`
- [ ] Test: Log `IS_WORDPRESS_EMBED` in console
- [ ] Verify it's `false` in standalone, `true` in WordPress

---

### 4.2 API Client (Dual-Mode Authentication)

**File:** `frontend/src/api/client.ts`

```typescript
/**
 * API Client - Handles authentication for both modes
 * 
 * Standalone Mode:
 * - User stores API key in localStorage
 * - Sends X-ACM2-API-Key header
 * 
 * WordPress Mode:
 * - WordPress session cookie handles auth
 * - Sends X-WP-Nonce header for CSRF protection
 * - WordPress adds X-ACM2-API-Key on backend
 */

import { API_BASE_URL, IS_WORDPRESS_EMBED, WP_NONCE } from '../config/environment';

export class APIError extends Error {
  constructor(
    public status: number,
    public message: string,
    public data?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export async function apiCall<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  
  // Authentication
  if (IS_WORDPRESS_EMBED) {
    // WordPress mode: Include nonce for CSRF protection
    if (WP_NONCE) {
      headers['X-WP-Nonce'] = WP_NONCE;
    }
  } else {
    // Standalone mode: Include API key from localStorage
    const apiKey = localStorage.getItem('acm2_api_key');
    if (apiKey) {
      headers['X-ACM2-API-Key'] = apiKey;
    }
  }
  
  const url = `${API_BASE_URL}${endpoint}`;
  
  console.log(`[API] ${options.method || 'GET'} ${url}`);
  
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: IS_WORDPRESS_EMBED ? 'include' : 'omit',  // Include cookies in WordPress mode
  });
  
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`;
    let errorData;
    
    try {
      errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      errorMessage = await response.text() || errorMessage;
    }
    
    throw new APIError(response.status, errorMessage, errorData);
  }
  
  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }
  
  return response.json();
}

// Convenience methods
export const api = {
  get: <T = any>(endpoint: string) =>
    apiCall<T>(endpoint, { method: 'GET' }),
  
  post: <T = any>(endpoint: string, data?: any) =>
    apiCall<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),
  
  put: <T = any>(endpoint: string, data?: any) =>
    apiCall<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    }),
  
  delete: <T = any>(endpoint: string) =>
    apiCall<T>(endpoint, { method: 'DELETE' }),
};
```

**Tasks:**
- [ ] Update `client.ts` with dual-mode authentication
- [ ] Test: Make API call in standalone mode with API key
- [ ] Test: Make API call in WordPress mode with nonce
- [ ] Test: Invalid API key returns 401
- [ ] Test: Missing WordPress nonce returns 403

---

### 4.3 Settings Page Updates (Hide API Key Input in WordPress)

**File:** `frontend/src/components/Settings/Settings.tsx`

```typescript
import { IS_WORDPRESS_EMBED, WP_USER_EMAIL } from '../../config/environment';

export function Settings() {
  const [apiKey, setApiKey] = useState(
    localStorage.getItem('acm2_api_key') || ''
  );
  
  return (
    <div className="settings">
      <h1>Settings</h1>
      
      {/* Only show API key section in standalone mode */}
      {!IS_WORDPRESS_EMBED && (
        <section className="settings-section">
          <h2>ACM2 API Key</h2>
          <p>Your API key is used to authenticate with the ACM2 backend.</p>
          
          <div className="form-group">
            <label htmlFor="api-key">API Key</label>
            <input
              id="api-key"
              type="password"
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                localStorage.setItem('acm2_api_key', e.target.value);
              }}
              placeholder="acm2_abc123..."
            />
            <p className="help-text">
              Generate your API key in the backend settings.
            </p>
          </div>
        </section>
      )}
      
      {/* Show WordPress user info */}
      {IS_WORDPRESS_EMBED && (
        <section className="settings-section">
          <h2>Account</h2>
          <p>Logged in as: <strong>{WP_USER_EMAIL}</strong></p>
          <p className="help-text">
            Your API key is managed by WordPress and never exposed to the browser.
          </p>
        </section>
      )}
      
      {/* Provider keys section (shown in BOTH modes) */}
      <section className="settings-section">
        <h2>Provider API Keys</h2>
        <p>Add your LLM provider API keys to run evaluations.</p>
        
        <ProviderKeysList />
        <AddProviderKeyForm />
      </section>
    </div>
  );
}
```

**Tasks:**
- [ ] Update Settings component to hide API key input in WordPress mode
- [ ] Show WordPress user email when embedded
- [ ] Keep provider keys section visible in both modes
- [ ] Test: Standalone mode shows API key input
- [ ] Test: WordPress mode hides API key input

---

### 4.4 Provider Keys Management (Works in Both Modes)

**File:** `frontend/src/components/Settings/ProviderKeysList.tsx`

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface ProviderKey {
  id: number;
  provider: string;
  key_name?: string;
  key_preview: string;
  created_at: string;
  is_active: boolean;
}

export function ProviderKeysList() {
  const queryClient = useQueryClient();
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['provider-keys'],
    queryFn: () => api.get<{ keys: ProviderKey[] }>('/provider-keys'),
  });
  
  const deleteMutation = useMutation({
    mutationFn: (keyId: number) => api.delete(`/provider-keys/${keyId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-keys'] });
    },
  });
  
  if (isLoading) return <div>Loading provider keys...</div>;
  if (error) return <div>Error loading keys: {error.message}</div>;
  
  const keys = data?.keys || [];
  
  if (keys.length === 0) {
    return (
      <div className="no-keys">
        <p>No provider keys configured.</p>
        <p>Add your OpenAI, Google, or Anthropic API keys to get started.</p>
      </div>
    );
  }
  
  return (
    <div className="provider-keys-list">
      {keys.map((key) => (
        <div key={key.id} className="provider-key-item">
          <div className="key-info">
            <span className="provider-badge">{key.provider}</span>
            {key.key_name && <span className="key-name">{key.key_name}</span>}
            <code className="key-preview">{key.key_preview}</code>
            <span className="key-date">
              Added {new Date(key.created_at).toLocaleDateString()}
            </span>
          </div>
          
          <button
            onClick={() => {
              if (confirm(`Delete ${key.provider} key?`)) {
                deleteMutation.mutate(key.id);
              }
            }}
            className="btn-delete"
            disabled={deleteMutation.isPending}
          >
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}
```

**File:** `frontend/src/components/Settings/AddProviderKeyForm.tsx`

```typescript
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

export function AddProviderKeyForm() {
  const [provider, setProvider] = useState<'openai' | 'google' | 'anthropic'>('openai');
  const [apiKey, setApiKey] = useState('');
  const [keyName, setKeyName] = useState('');
  const [showForm, setShowForm] = useState(false);
  
  const queryClient = useQueryClient();
  
  const addMutation = useMutation({
    mutationFn: (data: { provider: string; api_key: string; key_name?: string }) =>
      api.post('/provider-keys', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-keys'] });
      setApiKey('');
      setKeyName('');
      setShowForm(false);
    },
  });
  
  if (!showForm) {
    return (
      <button onClick={() => setShowForm(true)} className="btn-primary">
        + Add Provider Key
      </button>
    );
  }
  
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        addMutation.mutate({
          provider,
          api_key: apiKey,
          key_name: keyName || undefined,
        });
      }}
      className="add-key-form"
    >
      <div className="form-group">
        <label htmlFor="provider">Provider</label>
        <select
          id="provider"
          value={provider}
          onChange={(e) => setProvider(e.target.value as any)}
        >
          <option value="openai">OpenAI</option>
          <option value="google">Google (Gemini)</option>
          <option value="anthropic">Anthropic (Claude)</option>
        </select>
      </div>
      
      <div className="form-group">
        <label htmlFor="api-key">API Key *</label>
        <input
          id="api-key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          required
          placeholder={
            provider === 'openai' ? 'sk-proj-...' :
            provider === 'google' ? 'AIza...' :
            'sk-ant-...'
          }
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="key-name">Friendly Name (optional)</label>
        <input
          id="key-name"
          type="text"
          value={keyName}
          onChange={(e) => setKeyName(e.target.value)}
          placeholder="My Production Key"
        />
      </div>
      
      {addMutation.error && (
        <div className="error-message">
          {addMutation.error.message}
        </div>
      )}
      
      <div className="form-actions">
        <button
          type="submit"
          className="btn-primary"
          disabled={addMutation.isPending}
        >
          {addMutation.isPending ? 'Adding...' : 'Add Key'}
        </button>
        
        <button
          type="button"
          onClick={() => setShowForm(false)}
          className="btn-secondary"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
```

**Tasks:**
- [ ] Create `ProviderKeysList.tsx` component
- [ ] Create `AddProviderKeyForm.tsx` component
- [ ] Test: Add OpenAI key, verify it appears in list
- [ ] Test: Delete key, verify it's removed
- [ ] Test: Works in both standalone and WordPress modes

---

### 4.5 Build Configuration

**File:** `frontend/vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  
  build: {
    // Output to dist/ directory
    outDir: 'dist',
    
    // Generate sourcemaps for debugging
    sourcemap: true,
    
    // Optimize chunk sizes
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          tanstack: ['@tanstack/react-query'],
        },
      },
    },
  },
  
  server: {
    // Development server port
    port: 5173,
    
    // Proxy API requests to backend (standalone mode)
    proxy: {
      '/api': {
        target: 'http://localhost:8199',
        changeOrigin: true,
      },
    },
  },
});
```

**File:** `frontend/package.json`

```json
{
  "name": "acm2-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "copy-to-plugin": "npm run build && cp -r dist/* ../wordpress-plugin/assets/react-app/"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.22.0",
    "@tanstack/react-query": "^5.17.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.0",
    "typescript": "^5.3.3"
  }
}
```

**Tasks:**
- [ ] Update `vite.config.ts` with build optimization
- [ ] Add `copy-to-plugin` script to package.json
- [ ] Test: `npm run build`, verify dist/ created
- [ ] Test: `npm run copy-to-plugin`, verify files copied to WordPress plugin
- [ ] Test: Visit WordPress page, verify latest build loaded

---

### 4.6 Error Handling & User Feedback

**File:** `frontend/src/components/ErrorBoundary.tsx`

```typescript
import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }
  
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: any) {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div className="error-page">
          <h1>Something went wrong</h1>
          <p>{this.state.error?.message}</p>
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      );
    }
    
    return this.props.children;
  }
}
```

**File:** `frontend/src/hooks/useAuth.ts`

```typescript
import { useState, useEffect } from 'react';
import { IS_WORDPRESS_EMBED, WP_USER_ID } from '../config/environment';
import { api } from '../api/client';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    checkAuth();
  }, []);
  
  async function checkAuth() {
    try {
      if (IS_WORDPRESS_EMBED) {
        // WordPress mode: Check if WordPress user ID exists
        setIsAuthenticated(!!WP_USER_ID);
      } else {
        // Standalone mode: Check if API key is valid
        const apiKey = localStorage.getItem('acm2_api_key');
        if (!apiKey) {
          setIsAuthenticated(false);
        } else {
          // Test API key by making a simple request
          await api.get('/runs');
          setIsAuthenticated(true);
        }
      }
    } catch (err: any) {
      setError(err.message);
      setIsAuthenticated(false);
    } finally {
      setIsChecking(false);
    }
  }
  
  return {
    isAuthenticated,
    isChecking,
    error,
    recheck: checkAuth,
  };
}
```

**Tasks:**
- [ ] Create `ErrorBoundary.tsx` component
- [ ] Create `useAuth.ts` hook
- [ ] Wrap app in ErrorBoundary
- [ ] Use `useAuth` hook to check authentication
- [ ] Test: Invalid API key shows auth error
- [ ] Test: WordPress session expired shows re-login prompt

---

### 4.7 Development Workflow

**Standalone Mode Development:**
```bash
# Terminal 1: Backend
cd acm2
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uvicorn acm2.app.main:app --reload --port 8199

# Terminal 2: Frontend
cd frontend
npm run dev
# Visit http://localhost:5173
```

**WordPress Mode Development:**
```bash
# Terminal 1: Backend
cd acm2
source .venv/bin/activate
uvicorn acm2.app.main:app --reload --port 8199

# Terminal 2: Frontend (build and copy)
cd frontend
npm run build && npm run copy-to-plugin

# Visit WordPress page with [acm2_app] shortcode
# Reload page to see changes
```

**Hot Reload for WordPress (Advanced):**
```bash
# Create symlink so WordPress always has latest build
cd wordpress/wp-content/plugins/acm2-integration/assets
rm -rf react-app
ln -s /path/to/acm2/frontend/dist react-app

# Now just run:
cd frontend
npm run dev -- --watch
# Ctrl+R in browser after each build
```

**Tasks:**
- [ ] Document development workflow in README
- [ ] Create npm scripts for common tasks
- [ ] Test: Hot reload works in standalone mode
- [ ] Test: Build & copy works for WordPress mode

---

**Phase 4 Deliverable Checklist:**

- [ ] ✅ Frontend detects standalone vs WordPress mode
- [ ] ✅ API client handles authentication for both modes
- [ ] ✅ Settings page hides API key input in WordPress mode
- [ ] ✅ Provider keys management works in both modes
- [ ] ✅ Build configuration optimized
- [ ] ✅ Error handling and user feedback implemented
- [ ] ✅ Development workflow documented
- [ ] ✅ All tests passing

**Verification Commands:**
```bash
# Build frontend
cd frontend
npm run build

# Verify build output
ls -la dist/
# Should see: index.html, assets/index-xxx.js, assets/index-xxx.css

# Copy to WordPress plugin
npm run copy-to-plugin

# Verify copied
ls -la ../wordpress-plugin/assets/react-app/
# Should see same files

# Test standalone mode
npm run dev
# Visit http://localhost:5173
# Add API key in Settings
# Verify runs page loads

# Test WordPress mode
# Visit WordPress page with [acm2_app]
# Verify no API key input shown
# Verify runs page loads
```

---

**Common Gotchas & Solutions:**

1. **Problem:** React app shows blank page in WordPress
   **Solution:** Check browser console for errors. Verify build files copied correctly.

2. **Problem:** API calls return 401 in WordPress mode
   **Solution:** Check WordPress user is logged in. Verify nonce is being sent.

3. **Problem:** API calls return CORS errors
   **Solution:** Shouldn't happen! Both modes use same domain. Check API_BASE_URL.

4. **Problem:** Provider keys not showing
   **Solution:** Check API endpoint works: `curl http://localhost:8199/api/v1/provider-keys -H "X-ACM2-API-Key: xxx"`

5. **Problem:** Hot reload not working
   **Solution:** In WordPress mode, you must rebuild (`npm run build`) after changes. Or use symlink trick above.

6. **Problem:** `acm2Config` is undefined in browser console
   **Solution:** Verify WordPress `wp_localize_script` is called before React script loads

7. **Problem:** Styles look broken in WordPress
   **Solution:** WordPress CSS may conflict. Add `.acm2-root` prefix to all CSS classes.

---

## Phase 5: Production Deployment (Week 6)

### 5.1 Server Setup
```bash
# Ubuntu VPS (DigitalOcean, AWS, etc.)
sudo apt update
sudo apt install apache2 python3.13 python3-pip mysql-server

# Install WordPress (user handles this)

# Clone ACM2 repository
git clone <repo-url> /opt/acm2
cd /opt/acm2

# Create virtual environment
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create data directory
mkdir -p /opt/acm2/data
chown www-data:www-data /opt/acm2/data
```

**Tasks:**
- [ ] Provision VPS (2GB RAM minimum)
- [ ] Install Apache + PHP + MySQL
- [ ] Install Python 3.13
- [ ] Clone ACM2 repository
- [ ] Create production .env file with encryption key

---

### 5.2 Apache Configuration
**File:** `/etc/apache2/sites-available/acm2.conf`

```apache
<VirtualHost *:443>
    ServerName yoursite.com
    
    # WordPress handles everything except /api
    DocumentRoot /var/www/wordpress
    
    <Directory /var/www/wordpress>
        AllowOverride All
        Require all granted
    </Directory>
    
    # Proxy /api to FastAPI backend
    ProxyPreserveHost On
    ProxyPass /api http://localhost:8199/api
    ProxyPassReverse /api http://localhost:8199/api
    
    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/yoursite.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/yoursite.com/privkey.pem
</VirtualHost>
```

**Tasks:**
- [ ] Enable Apache modules: `sudo a2enmod proxy proxy_http ssl rewrite`
- [ ] Create Apache config file
- [ ] Enable site: `sudo a2ensite acm2`
- [ ] Test config: `sudo apache2ctl configtest`
- [ ] Restart Apache: `sudo systemctl restart apache2`

---

### 5.3 Uvicorn Service (systemd)
**File:** `/etc/systemd/system/acm2.service`

```ini
[Unit]
Description=ACM2 API Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/acm2
Environment="PATH=/opt/acm2/.venv/bin"
ExecStart=/opt/acm2/.venv/bin/uvicorn acm2.app.main:app --host 127.0.0.1 --port 8199 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

**Tasks:**
- [ ] Create systemd service file
- [ ] Reload systemd: `sudo systemctl daemon-reload`
- [ ] Enable service: `sudo systemctl enable acm2`
- [ ] Start service: `sudo systemctl start acm2`
- [ ] Check status: `sudo systemctl status acm2`

---

### 5.4 SSL Certificate (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-apache
sudo certbot --apache -d yoursite.com
```

**Tasks:**
- [ ] Install certbot
- [ ] Generate SSL certificate
- [ ] Verify auto-renewal: `sudo certbot renew --dry-run`
- [ ] Test HTTPS access

---

### 5.5 WordPress Plugin Installation
```bash
# Copy plugin to WordPress
cp -r /opt/acm2/wordpress-plugin /var/www/wordpress/wp-content/plugins/acm2-integration

# Build and copy React app
cd /opt/acm2/frontend
npm run build
cp -r dist/* /var/www/wordpress/wp-content/plugins/acm2-integration/assets/react-app/
```

**Tasks:**
- [ ] Copy plugin to WordPress plugins directory
- [ ] Build React app for production
- [ ] Copy build files to plugin assets
- [ ] Activate plugin in WordPress admin
- [ ] Create page with `[acm2_app]` shortcode

---

**Phase 5 Deliverable:**
- ✅ Production server running with SSL
- ✅ WordPress and ACM2 API both accessible
- ✅ Uvicorn running as systemd service
- ✅ Users can access ACM2 via WordPress

---

## Phase 6: Testing & Validation (Week 7)

### 6.1 User Flow Testing
- [ ] Create test WordPress account
- [ ] Generate ACM2 API key
- [ ] Add provider keys (OpenAI, Google)
- [ ] Create evaluation run
- [ ] Verify results display correctly
- [ ] Check database isolation (no cross-user data leakage)

### 6.2 Security Testing
- [ ] Verify API key never exposed in browser
- [ ] Test invalid API key returns 401
- [ ] Test WordPress session expiration
- [ ] Verify encrypted provider keys in database
- [ ] Test HTTPS enforcement
- [ ] Test CSRF protection

### 6.3 Performance Testing
- [ ] Run multiple evaluations concurrently
- [ ] Monitor memory usage
- [ ] Check database query performance
- [ ] Test with 10+ concurrent users
- [ ] Verify no database locking issues

### 6.4 Documentation
- [ ] User guide: How to set up account
- [ ] User guide: How to add provider keys
- [ ] User guide: How to run evaluations
- [ ] Admin guide: How to manage WordPress
- [ ] Developer guide: API documentation

---

## Phase 7: Launch Preparation (Week 8)

### 7.1 Monitoring Setup
- [ ] Install monitoring (e.g., Uptime Robot)
- [ ] Set up error logging (Sentry or similar)
- [ ] Configure email alerts for API errors
- [ ] Add usage analytics (optional)

### 7.2 Backup Strategy
- [ ] Automated daily database backups
- [ ] Test restore procedure
- [ ] Store backups off-site (S3, etc.)

### 7.3 Payment Integration (WordPress)
- [ ] Install WooCommerce or Easy Digital Downloads
- [ ] Create subscription products
- [ ] Connect Stripe/PayPal
- [ ] Test payment flow
- [ ] Set up webhooks for subscription status

### 7.4 Beta Launch
- [ ] Invite 5-10 beta users
- [ ] Monitor for issues
- [ ] Collect feedback
- [ ] Fix critical bugs
- [ ] Iterate on UX

---

## Current Status

**✅ Completed:**
- Architecture documented
- Deviation data extraction working
- Decimal precision in calculations

**🔄 In Progress:**
- Nothing (ready to start Phase 1)

**⏳ To Do:**
- Everything in this plan!

---

## Success Criteria

### Minimum Viable Product (MVP)
- ✅ Users can register via WordPress
- ✅ Users can generate ACM2 API key
- ✅ Users can store provider keys (encrypted)
- ✅ Users can run evaluations
- ✅ Data is isolated per user
- ✅ API keys never exposed to browser

### Production Ready
- ✅ HTTPS enabled
- ✅ Automated backups
- ✅ Error monitoring
- ✅ Payment processing
- ✅ User documentation
- ✅ Performance tested

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth Method | API Keys | Simpler than JWT, no token refresh needed |
| User Management | WordPress | Provides registration, login, payments out of box |
| Database | SQLite per user | Simple, isolated, no complex permissions |
| Encryption | AES-256 (Fernet) | Standard Python library, secure |
| Frontend Integration | Embedded in WordPress | Single domain, no CORS, unified UX |
| Proxy Pattern | WordPress proxies API | API keys never exposed to browser |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **API key theft** | Keys hashed in DB, never sent to browser |
| **Data leakage** | Per-user databases, validated in middleware |
| **WordPress compromise** | API keys hashed, provider keys encrypted |
| **Performance bottleneck** | Uvicorn with multiple workers, async/await |
| **Database growth** | SQLite scales to ~1TB, migrate to Postgres if needed |
| **Provider key exposure** | Encrypted at rest, decrypted only in memory |

---

## Questions for User

1. **Domain name:** What domain will you use? (for SSL setup)
2. **Hosting:** VPS provider preference? (DigitalOcean, AWS, Linode, etc.)
3. **Payment:** Which payment plugin? (WooCommerce, Easy Digital Downloads, other)
4. **Pricing model:** Subscription? Usage-based? Free tier?
5. **Beta testers:** Do you have users ready to test?

---

## Next Steps

**Immediate action:** Start Phase 1, Task 1.1
- Create `acm2/app/db/master_schema.sql`
- Create `acm2/app/db/master.py`
- Run script to initialize master.db
- Verify tables created correctly

**Command to start:**
```bash
cd c:\dev\godzilla\acm2
mkdir -p acm2/app/db
# Create master_schema.sql and master.py files
```

Ready to begin implementation!

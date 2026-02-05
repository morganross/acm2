# ACM2 User Sync Failure: Root Cause Investigation Report

**Document Version**: 1.0  
**Date**: February 5, 2026  
**Status**: ACTIVE INVESTIGATION  
**Priority**: CRITICAL  
**Failure Count**: 100+ attempts  

---

## EXECUTIVE SUMMARY

This document addresses a persistent, recurring failure in the ACM2 WordPress plugin where new users see "No ACM2 Account" on the Provider Keys page. Despite 100+ attempted fixes, the issue persists. This report acknowledges that **the root cause is likely process-related, not purely technical**, and establishes systematic investigation and validation protocols.

---

# PART 1: PROBLEM DEFINITION

## 1.1 Observed Symptom

When a new WordPress user is created and navigates to the Provider Keys page, they see:

```
Provider API Keys
No ACM2 Account

You don't have an ACM2 API key yet. Please contact your administrator to set up your account.
```

## 1.2 Expected Behavior

When a new WordPress user is created:
1. WordPress fires `user_register` hook
2. Plugin syncs user to ACM2 backend (sends UUID + email)
3. Backend creates user database and API key
4. API key is returned and stored in WordPress
5. User can access Provider Keys page with their key

## 1.3 Failure History

| Date | Fix Attempted | Result | Why It Failed |
|------|---------------|--------|---------------|
| Multiple | Fixed `acm2_get_user_uuid()` parameter | Still broken | Unknown - needs investigation |
| Multiple | Added UUID to sync payload | Still broken | Unknown |
| Multiple | Updated class-user-sync.php | Still broken | Unknown |
| Multiple | Git pull latest code | Still broken | Unknown |
| Multiple | Rebuilt React UI | Still broken | Not the issue |

## 1.4 The Core Acknowledgment

**We have been fixing symptoms without understanding the full flow.**

The agent (Copilot) has limited visibility into:
- Runtime behavior
- Actual HTTP requests being made
- Database state
- Error logs at the moment of failure
- Whether hooks are actually firing
- Whether the backend is actually receiving requests

---

# PART 2: SYSTEMATIC INVESTIGATION PROTOCOL

## 2.1 Investigation Principle

**DO NOT FIX ANYTHING UNTIL THE PROBLEM IS FULLY UNDERSTOOD.**

Every fix attempt without full understanding is a wasted attempt. We must:
1. Trace the COMPLETE flow
2. Identify EXACTLY where it breaks
3. Gather PROOF of the failure point
4. Only THEN implement a fix
5. VERIFY the fix with proof

## 2.2 The Complete User Creation Flow

```
STEP 1: WordPress User Creation
├── WordPress admin creates new user
├── WordPress fires `user_register` hook
└── QUESTION: Is our hook registered? Is it firing?

STEP 2: Hook Handler Execution
├── ACM2_User_Sync::sync_new_user($user_id) should be called
├── QUESTION: Is this function actually being called?
└── QUESTION: What does debug.log show at this moment?

STEP 3: UUID Generation
├── get_or_create_user_uuid($user_id) generates UUID
├── UUID stored in wp_usermeta as 'acm2_user_uuid'
├── QUESTION: Is the UUID actually in the database?
└── QUESTION: Can we query it directly?

STEP 4: Backend API Call
├── WordPress POSTs to backend: /api/v1/users
├── Payload: {uuid: "xxx", email: "xxx"}
├── Headers: X-Plugin-Secret: "xxx"
├── QUESTION: Is the plugin secret set?
├── QUESTION: Is the backend URL correct?
├── QUESTION: Is the request actually being made?
└── QUESTION: What does the backend return?

STEP 5: Backend Processing
├── Backend receives request
├── Backend validates plugin secret
├── Backend creates user_{uuid}.db
├── Backend generates API key
├── Backend returns API key
├── QUESTION: Is the backend receiving anything?
├── QUESTION: What are the backend logs showing?
└── QUESTION: Is the secret matching?

STEP 6: API Key Storage
├── WordPress receives API key from backend
├── Key encrypted and stored in database
├── QUESTION: Is the key actually being saved?
└── QUESTION: Can we query it directly?

STEP 7: Provider Keys Page Load
├── Page loads, calls acm2_get_user_api_key()
├── Key decrypted and returned
├── If no key, shows "No ACM2 Account"
├── QUESTION: What is acm2_get_user_api_key() returning?
└── QUESTION: Is there a key in the database for this user?
```

---

# PART 3: INVESTIGATION COMMANDS

## 3.1 Check If User Sync Hook Is Registered

```bash
ssh user@host "grep -r 'user_register' /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/"
```

**Expected**: Should show `add_action('user_register', ...)`

## 3.2 Check If Hook Is Actually Firing

Add temporary logging:
```php
// In class-user-sync.php, at start of sync_new_user():
error_log('ACM2 SYNC: sync_new_user CALLED for user_id=' . $user_id);
```

Then create a user and check:
```bash
ssh user@host "tail -50 /opt/bitnami/wordpress/wp-content/debug.log | grep ACM2"
```

## 3.3 Check If UUID Is Generated and Stored

```bash
# Get the user ID of the newly created user
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT ID, user_login FROM wp_users ORDER BY ID DESC LIMIT 5;\""

# Check if UUID exists for that user
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT * FROM wp_usermeta WHERE user_id=XX AND meta_key='acm2_user_uuid';\""
```

## 3.4 Check Plugin Secret Configuration

```bash
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT * FROM wp_options WHERE option_name='acm2_plugin_secret';\""
```

**If empty**: The sync will fail with 401 Unauthorized.

## 3.5 Check Backend URL Configuration

```bash
ssh user@host "grep -r 'ACM2_BACKEND_URL' /opt/bitnami/wordpress/"
ssh user@host "grep -r 'backend_url' /opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/"
```

## 3.6 Check If API Key Is Stored

```bash
# Check the acm2_user_keys table
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT * FROM wp_acm2_user_keys;\""

# Or check usermeta
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT * FROM wp_usermeta WHERE meta_key LIKE 'acm2%';\""
```

## 3.7 Check Backend Logs

```bash
ssh user@backend "tail -100 /var/log/acm2/access.log"
ssh user@backend "tail -100 /var/log/acm2/error.log"
# Or wherever the FastAPI logs are
```

## 3.8 Test Backend Connectivity From WordPress Server

```bash
ssh user@frontend "curl -v http://BACKEND_IP:8000/api/v1/health"
ssh user@frontend "curl -v -X POST http://BACKEND_IP:8000/api/v1/users -H 'Content-Type: application/json' -H 'X-Plugin-Secret: TEST' -d '{\"uuid\":\"test-uuid\",\"email\":\"test@test.com\"}'"
```

## 3.9 Check What acm2_get_user_api_key() Returns

Add logging to the function:
```php
function acm2_get_user_api_key($user_id = null) {
    error_log('ACM2: acm2_get_user_api_key called with user_id=' . $user_id);
    // ... existing code ...
    error_log('ACM2: acm2_get_user_api_key returning: ' . ($result ? 'HAS_KEY' : 'NO_KEY'));
    return $result;
}
```

---

# PART 4: POTENTIAL ROOT CAUSES

## 4.1 Category A: Hook Not Firing

**Symptoms**:
- No log entries when user is created
- UUID not in database

**Causes**:
- Plugin not activated
- Hook registered incorrectly
- Init function not being called
- PHP fatal error before hook registration

**Investigation**:
```bash
# Check if plugin is active
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT option_value FROM wp_options WHERE option_name='active_plugins';\""

# Check for PHP errors
ssh user@host "tail -100 /opt/bitnami/wordpress/wp-content/debug.log"
ssh user@host "tail -100 /opt/bitnami/php/var/log/php-fpm.log"
```

## 4.2 Category B: UUID Generated But Sync Fails

**Symptoms**:
- UUID exists in wp_usermeta
- No API key in database
- Backend never receives request

**Causes**:
- Backend URL wrong or unreachable
- Plugin secret not configured
- HTTPS/certificate issues
- Firewall blocking

**Investigation**:
```bash
# Check UUID exists
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT * FROM wp_usermeta WHERE meta_key='acm2_user_uuid';\""

# Test connectivity
ssh user@host "curl -I http://BACKEND:8000/api/v1/"
```

## 4.3 Category C: Backend Rejects Request

**Symptoms**:
- UUID exists
- WordPress debug log shows "401 Unauthorized" or "Invalid plugin secret"
- No API key stored

**Causes**:
- Plugin secret doesn't match backend
- Backend not configured with secret
- Secret generation/storage failure

**Investigation**:
```bash
# Check WordPress secret
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT * FROM wp_options WHERE option_name='acm2_plugin_secret';\""

# Check backend secret (wherever it's configured)
ssh user@backend "cat /path/to/.env | grep PLUGIN_SECRET"
```

## 4.4 Category D: API Key Generated But Not Stored

**Symptoms**:
- Backend logs show successful user creation
- API key generated
- WordPress has no key in database

**Causes**:
- WordPress fails to parse response
- Database write fails
- Encryption fails

**Investigation**:
```bash
# Check for key in WordPress
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT * FROM wp_acm2_user_keys;\""

# Check debug log for storage errors
ssh user@host "grep -i 'error\|fail\|exception' /opt/bitnami/wordpress/wp-content/debug.log | tail -50"
```

## 4.5 Category E: Key Exists But Not Retrieved

**Symptoms**:
- API key IS in database
- Provider Keys page still shows "No ACM2 Account"

**Causes**:
- Wrong user ID being queried
- Decryption failing
- acm2_get_user_api_key() broken

**Investigation**:
```bash
# Verify key exists
ssh user@host "mysql -u USER -pPASS DATABASE -e \"SELECT * FROM wp_acm2_user_keys WHERE wp_user_id=XX;\""

# Check what the retrieval function returns
# Add error_log statements
```

---

# PART 5: THE REAL PROBLEM - PROCESS FAILURES

## 5.1 Why 100+ Fixes Have Failed

### 5.1.1 Symptom-Based Fixing

We have been fixing what appears broken without understanding why it's broken.

**Example**: 
- Saw "No ACM2 Account" error
- Found broken function signature
- Fixed function signature
- Did not verify the entire flow worked

### 5.1.2 Lack of End-to-End Testing

Each fix was verified in isolation:
- ✅ File was modified
- ✅ Syntax is correct
- ❌ Never tested: Create user → See keys

### 5.1.3 No Observability

We have limited ability to see:
- What HTTP requests are made
- What database queries run
- What values are returned
- What errors occur at runtime

### 5.1.4 Context Loss Between Sessions

The AI agent loses context between sessions:
- Previous fixes are forgotten
- Previous debugging is forgotten
- Same investigations repeated
- Same "fixes" applied multiple times

### 5.1.5 Confirmation Bias

We see what we expect:
- "The function now has the parameter" = "It's fixed"
- Never verified it actually runs
- Never verified it returns valid data
- Never verified the downstream components work

## 5.2 The Skill Gap

The AI agent has limitations:

| Capability | Status |
|------------|--------|
| Read files | ✅ Can do |
| Write files | ✅ Can do |
| Run commands | ✅ Can do |
| See command output | ✅ Can do |
| Understand runtime behavior | ❌ Limited |
| Debug live requests | ❌ Cannot |
| Access browser | ❌ Cannot |
| See actual HTTP traffic | ❌ Cannot |
| Query databases easily | ⚠️ Requires setup |
| Maintain context across sessions | ❌ Cannot |

## 5.3 Systems To Work Around Limitations

### 5.3.1 Logging-First Development

Before assuming anything works:
```php
error_log('FUNCTION_NAME: Starting, inputs=' . json_encode($inputs));
// ... code ...
error_log('FUNCTION_NAME: Ending, result=' . json_encode($result));
```

### 5.3.2 Checkpoint-Based Verification

After each operation, immediately verify:
```bash
# After modifying file:
ssh user@host "grep -n 'expected_code' /path/to/file.php"

# After user creation:
ssh user@host "mysql ... -e \"SELECT * FROM wp_usermeta WHERE user_id=XX;\""

# After sync attempt:
ssh user@host "tail -20 /path/to/debug.log | grep ACM2"
```

### 5.3.3 Database State Check Script

Create a script that dumps all relevant state:
```bash
#!/bin/bash
echo "=== ACTIVE PLUGINS ==="
mysql ... -e "SELECT option_value FROM wp_options WHERE option_name='active_plugins';"

echo "=== PLUGIN SECRET ==="
mysql ... -e "SELECT * FROM wp_options WHERE option_name='acm2_plugin_secret';"

echo "=== ALL USERS ==="
mysql ... -e "SELECT ID, user_login, user_email FROM wp_users;"

echo "=== ALL UUIDs ==="
mysql ... -e "SELECT * FROM wp_usermeta WHERE meta_key='acm2_user_uuid';"

echo "=== ALL API KEYS ==="
mysql ... -e "SELECT * FROM wp_acm2_user_keys;"

echo "=== RECENT DEBUG LOG ==="
tail -100 /opt/bitnami/wordpress/wp-content/debug.log | grep ACM2
```

### 5.3.4 Test Endpoint

Create a test endpoint that exercises the full flow:
```php
// Add to plugin: test-sync.php
// Visit: /wp-admin/admin.php?page=acm2-test-sync&user_id=XX
// Shows complete diagnostic of sync state for that user
```

### 5.3.5 Manual Step-By-Step Verification

Before declaring anything "fixed":

```
□ Step 1: Verified hook is registered
  Command: grep -r 'user_register' ...
  Result: _______________

□ Step 2: Created test user
  User ID: _______________
  
□ Step 3: Verified UUID exists
  Command: mysql ... WHERE user_id=XX AND meta_key='acm2_user_uuid'
  Result: _______________

□ Step 4: Checked debug log for sync attempt
  Command: tail ... | grep ACM2
  Result: _______________

□ Step 5: Verified API key stored
  Command: mysql ... FROM wp_acm2_user_keys WHERE wp_user_id=XX
  Result: _______________

□ Step 6: Tested Provider Keys page
  Result: Key displayed / No ACM2 Account (circle one)
```

---

# PART 6: IMMEDIATE INVESTIGATION STEPS

## 6.1 First: Get Database Credentials

```bash
ssh user@host "grep DB_ /opt/bitnami/wordpress/wp-config.php"
```

## 6.2 Second: Get Complete State Dump

```bash
ssh user@host "
MYSQL='/opt/bitnami/mariadb/bin/mysql'
DB_NAME=\$(grep DB_NAME /opt/bitnami/wordpress/wp-config.php | cut -d\\\"'\\\" -f4)
DB_USER=\$(grep DB_USER /opt/bitnami/wordpress/wp-config.php | cut -d\\\"'\\\" -f4)
DB_PASS=\$(grep DB_PASSWORD /opt/bitnami/wordpress/wp-config.php | cut -d\\\"'\\\" -f4)

echo '=== USERS ==='
\$MYSQL -u\$DB_USER -p\$DB_PASS \$DB_NAME -e 'SELECT ID, user_login FROM wp_users ORDER BY ID DESC LIMIT 10;'

echo '=== UUIDS ==='
\$MYSQL -u\$DB_USER -p\$DB_PASS \$DB_NAME -e 'SELECT * FROM wp_usermeta WHERE meta_key=\"acm2_user_uuid\";'

echo '=== PLUGIN SECRET ==='
\$MYSQL -u\$DB_USER -p\$DB_PASS \$DB_NAME -e 'SELECT * FROM wp_options WHERE option_name=\"acm2_plugin_secret\";'

echo '=== API KEYS TABLE ==='
\$MYSQL -u\$DB_USER -p\$DB_PASS \$DB_NAME -e 'SHOW TABLES LIKE \"%acm2%\";'
"
```

## 6.3 Third: Check Recent Debug Log

```bash
ssh user@host "tail -100 /opt/bitnami/wordpress/wp-content/debug.log"
```

## 6.4 Fourth: Check Backend Connectivity

```bash
ssh user@frontend "curl -v http://BACKEND_IP:8000/api/v1/health 2>&1"
```

## 6.5 Fifth: Test Backend User Creation Manually

```bash
ssh user@frontend "curl -X POST http://BACKEND_IP:8000/api/v1/users \
  -H 'Content-Type: application/json' \
  -H 'X-Plugin-Secret: THE_SECRET' \
  -d '{\"uuid\":\"manual-test-uuid\",\"email\":\"test@test.com\"}'"
```

---

# PART 7: HYPOTHESIS TESTING MATRIX

## 7.1 Hypothesis A: Plugin Secret Is Not Set

**Test**:
```bash
ssh user@host "mysql ... -e \"SELECT * FROM wp_options WHERE option_name='acm2_plugin_secret';\""
```

**If TRUE**: 
- Secret is empty/not found
- Fix: Generate and store secret, match with backend

**If FALSE**: 
- Secret exists
- Proceed to next hypothesis

## 7.2 Hypothesis B: Backend URL Is Wrong

**Test**:
```bash
ssh user@host "grep -r 'ACM2_BACKEND_URL\|backend_url' /opt/bitnami/wordpress/"
```

**If TRUE**: 
- URL is wrong or not set
- Fix: Configure correct backend URL

## 7.3 Hypothesis C: Hook Is Not Firing

**Test**:
1. Add logging to sync_new_user()
2. Create user
3. Check debug log

**If TRUE**: 
- No log entry appears
- Fix: Check plugin activation, init function

## 7.4 Hypothesis D: Backend Is Rejecting Requests

**Test**:
```bash
# Check debug log for HTTP response codes
ssh user@host "grep -i 'status\|error\|401\|403\|500' /opt/bitnami/wordpress/wp-content/debug.log | tail -50"
```

**If TRUE**: 
- Backend returns error
- Fix: Debug backend, check secrets match

## 7.5 Hypothesis E: API Key Is Stored But Not Retrieved

**Test**:
```bash
# Get newest user ID
# Check for key directly in database
ssh user@host "mysql ... -e \"SELECT * FROM wp_acm2_user_keys WHERE wp_user_id=XX;\""
```

**If TRUE**: 
- Key exists in DB but page shows "No Account"
- Fix: Debug acm2_get_user_api_key() function

---

# PART 8: DIAGNOSTIC ENHANCEMENT PLAN

## 8.1 Add Comprehensive Logging

Every function should log:
- Entry point with parameters
- Key decision points
- External calls (API, DB)
- Return values
- Errors

## 8.2 Create Health Check Endpoint

```php
// /wp-admin/admin-ajax.php?action=acm2_health_check
function acm2_health_check() {
    $results = [
        'plugin_active' => true,
        'plugin_secret_set' => !empty(get_option('acm2_plugin_secret')),
        'backend_url_set' => defined('ACM2_BACKEND_URL'),
        'backend_reachable' => @file_get_contents(ACM2_BACKEND_URL . '/api/v1/health') !== false,
        'current_user_has_uuid' => !empty(get_user_meta(get_current_user_id(), 'acm2_user_uuid', true)),
        'current_user_has_key' => !empty(acm2_get_user_api_key()),
        'encryption_key_exists' => defined('ACM2_ENCRYPTION_KEY'),
    ];
    wp_send_json($results);
}
add_action('wp_ajax_acm2_health_check', 'acm2_health_check');
```

## 8.3 Create Sync Test Button

In admin, add a button that:
1. Manually triggers sync for current user
2. Shows complete debug output
3. Shows success/failure with details

---

# PART 9: WORKING BACKWARDS FROM THE ERROR

## 9.1 The Error Message Source

The message "No ACM2 Account" comes from:
```php
// class-provider-keys-page.php
$acm2_api_key = acm2_get_user_api_key();
if (!$acm2_api_key) {
    // Show "No ACM2 Account" error
}
```

## 9.2 What Must Be True For Error To Show

```
acm2_get_user_api_key() returns empty/null/false
    ↓
EITHER: Key not in database
    OR: Key retrieval function is broken
    OR: Decryption is failing
```

## 9.3 What Must Be True For Key To Be In Database

```
Key was returned from backend AND stored successfully
    ↓
Backend received valid sync request AND created user AND returned key
    ↓
WordPress sent sync request with valid plugin secret
    ↓
sync_new_user() was called with valid user_id
    ↓
user_register hook fired
    ↓
Plugin is active and hooks are registered
```

## 9.4 Finding The Break Point

Start from the bottom and verify each level:
1. ✓/✗ Plugin active?
2. ✓/✗ Hooks registered?
3. ✓/✗ Hook fires on user creation?
4. ✓/✗ sync_new_user() runs?
5. ✓/✗ UUID generated?
6. ✓/✗ Backend request made?
7. ✓/✗ Backend returns success?
8. ✓/✗ Key stored in WordPress?
9. ✓/✗ Key retrieved successfully?

**THE FIRST ✗ IS THE ROOT CAUSE.**

---

# PART 10: NEXT STEPS

## 10.1 Immediate Actions

1. **Run the diagnostic commands** from Part 6
2. **Identify which hypothesis is true** from Part 7
3. **Fix only that specific issue**
4. **Verify fix end-to-end** with the checklist from 5.3.5

## 10.2 Before Any Fix

Ask these questions:
- What exactly is broken?
- How do I know it's broken? (proof)
- What will fix it? (specific, not general)
- How will I verify it's fixed? (specific test)

## 10.3 After Any Fix

Run this checklist:
- [ ] Created new user
- [ ] User ID is: ____
- [ ] UUID in database: ____
- [ ] Debug log shows: ____
- [ ] API key in database: Yes/No
- [ ] Provider Keys page shows: Key/Error

---

# PART 11: APPENDICES

## A. File Locations

| File | Purpose |
|------|---------|
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/acm2-integration.php` | Main plugin file with helper functions |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/includes/class-user-sync.php` | User sync logic |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-provider-keys-page.php` | Provider Keys page |
| `/opt/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php` | React app loader |
| `/opt/bitnami/wordpress/wp-content/debug.log` | WordPress debug log |
| `/opt/bitnami/wordpress/wp-config.php` | WordPress configuration |

## B. Database Tables

| Table | Purpose |
|-------|---------|
| `wp_users` | WordPress users |
| `wp_usermeta` | User metadata (includes acm2_user_uuid) |
| `wp_options` | Site options (includes acm2_plugin_secret) |
| `wp_acm2_user_keys` | ACM2 API keys (if exists) |

## C. Environment

| Component | Location |
|-----------|----------|
| Frontend Server | 16.145.206.59 |
| Backend Server | 54.71.183.56 |
| PHP Path | /opt/bitnami/php/bin/php |
| MySQL Path | /opt/bitnami/mariadb/bin/mysql |

## D. SSH Access

```bash
ssh -i C:\Users\Administrator\.ssh\id_ed25519 bitnami@16.145.206.59
```

---

# CONCLUSION

The issue "No ACM2 Account" has persisted through 100+ fix attempts because we have been:

1. **Fixing symptoms, not root causes**
2. **Not verifying fixes end-to-end**
3. **Lacking observability into runtime behavior**
4. **Losing context between sessions**

The solution is not another code fix. The solution is:

1. **Investigate completely before fixing**
2. **Use the diagnostic commands in this document**
3. **Identify the EXACT break point**
4. **Fix only that specific issue**
5. **Verify with the complete checklist**

**DO NOT PROCEED WITH ANY FIX UNTIL THE DIAGNOSTICS ARE RUN AND THE EXACT FAILURE POINT IS IDENTIFIED.**

---

*End of Report*

# GitHub App OAuth Implementation Plan for ACM2

## Overview

Replace the current Personal Access Token (PAT) approach with GitHub App OAuth for a seamless user experience. Users will click "Connect with GitHub" and authorize via a popup instead of manually copying/pasting tokens.

---

## Phase 1: Register GitHub App on GitHub.com

### Steps (Manual - One-time setup by developer)

1. Go to GitHub → Settings → Developer Settings → GitHub Apps → **New GitHub App**

2. Fill in the registration form:
   - **GitHub App name**: `ACM2` (must be unique across GitHub)
   - **Homepage URL**: `http://localhost:8002` (or production URL)
   - **Callback URL**: `http://localhost:8002/api/github/oauth/callback`
   - **Expire user authorization tokens**: Keep checked (recommended)
   - **Request user authorization (OAuth) during installation**: Check this
   - **Webhook**: Uncheck "Active" (not needed for our use case)

3. Set Permissions:
   - **Repository permissions**:
     - Contents: **Read and write** (to read/write files)
     - Metadata: **Read-only** (required, auto-selected)

4. Under "Where can this GitHub App be installed?":
   - Select **Any account** (if you want others to use it)
   - Select **Only on this account** (for private use)

5. Click **Create GitHub App**

6. After creation, note down:
   - **App ID**: Shown on the app page
   - **Client ID**: Shown on the app page
   - Click **Generate a new client secret** → Copy and save the **Client Secret**

7. Add these to your environment variables:
   ```
   GITHUB_APP_CLIENT_ID=your_client_id
   GITHUB_APP_CLIENT_SECRET=your_client_secret
   GITHUB_OAUTH_CALLBACK_URL=http://localhost:8002/api/github/oauth/callback
   ```

---

## Phase 2: Backend Implementation

### 2.1 Add Environment Configuration

**File**: `acm2/app/core/config.py`

Add new settings:
```python
GITHUB_APP_CLIENT_ID: str = ""
GITHUB_APP_CLIENT_SECRET: str = ""
GITHUB_OAUTH_CALLBACK_URL: str = "http://localhost:8002/api/github/oauth/callback"
```

### 2.2 Create OAuth Routes

**File**: `acm2/app/api/routes/github_oauth.py` (new file)

Endpoints to implement:

1. **GET `/api/github/oauth/authorize`**
   - Generates a random `state` parameter for CSRF protection
   - Stores state in session/database
   - Returns the GitHub authorization URL:
     ```
     https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={CALLBACK}&state={STATE}&scope=repo
     ```

2. **GET `/api/github/oauth/callback`**
   - Receives `code` and `state` from GitHub
   - Validates `state` matches what we stored
   - Exchanges `code` for access token via POST to:
     ```
     https://github.com/login/oauth/access_token
     ```
   - Fetches user info from GitHub API
   - Stores the access token (encrypted) in database
   - Redirects user back to the app UI with success message

3. **GET `/api/github/oauth/status`**
   - Returns whether the current user has a valid GitHub connection
   - Returns connected GitHub username if connected

4. **POST `/api/github/oauth/disconnect`**
   - Removes the stored GitHub token
   - User can re-authorize later

### 2.3 Update Database Model

**File**: `acm2/app/models/github_connection.py`

Modify or create a model to store OAuth tokens:
```python
class GitHubOAuthToken(Base):
    __tablename__ = "github_oauth_tokens"
    
    id: str  # UUID
    github_user_id: str  # GitHub user ID
    github_username: str  # Display name
    access_token: str  # Encrypted
    refresh_token: str  # Encrypted (optional, for token refresh)
    token_expires_at: datetime  # 8 hours from issuance
    refresh_token_expires_at: datetime  # 6 months from issuance
    created_at: datetime
    updated_at: datetime
```

### 2.4 Token Encryption

**File**: `acm2/app/core/security.py` (new or existing)

Implement encryption for storing tokens:
```python
from cryptography.fernet import Fernet

def encrypt_token(token: str) -> str:
    # Use a secret key from environment
    ...

def decrypt_token(encrypted_token: str) -> str:
    ...
```

### 2.5 Token Refresh Logic

**File**: `acm2/app/services/github_oauth.py` (new file)

```python
async def get_valid_token() -> str:
    """Get a valid access token, refreshing if expired."""
    token = await get_stored_token()
    
    if token.token_expires_at < datetime.utcnow():
        # Token expired, use refresh token
        new_tokens = await refresh_access_token(token.refresh_token)
        await update_stored_tokens(new_tokens)
        return new_tokens.access_token
    
    return token.access_token
```

### 2.6 Update Existing GitHub Routes

**File**: `acm2/app/api/routes/github_connections.py`

Modify existing endpoints to use OAuth tokens instead of PAT:
- Browse repositories → Use OAuth token
- Get file content → Use OAuth token
- Export file → Use OAuth token

---

## Phase 3: Frontend Implementation

### 3.1 Add OAuth API Client

**File**: `acm2/ui/src/api/githubOAuth.ts` (new file)

```typescript
export async function getAuthorizationUrl(): Promise<string> {
  const response = await fetch('/api/github/oauth/authorize');
  const data = await response.json();
  return data.authorization_url;
}

export async function getOAuthStatus(): Promise<{
  connected: boolean;
  username?: string;
}> {
  const response = await fetch('/api/github/oauth/status');
  return response.json();
}

export async function disconnectGitHub(): Promise<void> {
  await fetch('/api/github/oauth/disconnect', { method: 'POST' });
}
```

### 3.2 Create Connect Button Component

**File**: `acm2/ui/src/components/github/GitHubConnectButton.tsx` (new file)

```typescript
export function GitHubConnectButton() {
  const handleConnect = async () => {
    const authUrl = await getAuthorizationUrl();
    // Open in popup or redirect
    window.location.href = authUrl;
  };

  return (
    <Button onClick={handleConnect}>
      <GitHubIcon /> Connect with GitHub
    </Button>
  );
}
```

### 3.3 Update Settings Page

**File**: `acm2/ui/src/pages/Settings.tsx`

Replace the PAT input form with:
1. "Connect with GitHub" button (if not connected)
2. Connected status showing GitHub username (if connected)
3. "Disconnect" button (if connected)

### 3.4 Handle OAuth Callback

**File**: `acm2/ui/src/pages/GitHubCallback.tsx` (new file)

Create a page that:
1. Receives the callback from GitHub
2. Shows a success/error message
3. Redirects to Settings page after a short delay

Add route in router:
```typescript
{ path: '/github/callback', element: <GitHubCallback /> }
```

### 3.5 Update GitHub File Browser

**File**: `acm2/ui/src/components/github/GitHubFileBrowser.tsx`

- Remove connection selection (now using single OAuth connection)
- Check OAuth status before showing browser
- Show "Connect with GitHub" if not connected

---

## Phase 4: Migration & Cleanup

### 4.1 Database Migration

Create Alembic migration to:
1. Add new `github_oauth_tokens` table
2. Optionally keep old `github_connections` table for backwards compatibility

### 4.2 Remove Old PAT Logic

After OAuth is working:
1. Remove PAT input fields from UI
2. Remove PAT-based connection endpoints (or deprecate)
3. Update documentation

---

## Phase 5: Testing

### 5.1 Manual Testing Checklist

- [ ] Click "Connect with GitHub" → redirects to GitHub
- [ ] Authorize on GitHub → redirects back to app
- [ ] Settings shows connected status with username
- [ ] Browse GitHub repositories works
- [ ] Import file from GitHub works
- [ ] Export file to GitHub works
- [ ] Disconnect removes connection
- [ ] Re-connect works after disconnect
- [ ] Token refresh works (wait 8+ hours or manually expire)

### 5.2 Error Handling

Test these scenarios:
- [ ] User denies authorization on GitHub
- [ ] Invalid state parameter (CSRF attack simulation)
- [ ] Expired token refresh
- [ ] Network errors during OAuth flow

---

## Security Considerations

1. **State Parameter**: Always validate to prevent CSRF attacks
2. **Token Storage**: Encrypt tokens at rest in database
3. **HTTPS**: Use HTTPS in production (required by GitHub for OAuth)
4. **Client Secret**: Never expose in frontend code, keep in backend only
5. **Token Scope**: Request minimum necessary permissions
6. **Token Expiry**: Implement proper refresh logic

---

## Environment Variables Summary

```env
# GitHub App OAuth
GITHUB_APP_CLIENT_ID=Iv1.xxxxxxxxxxxx
GITHUB_APP_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_OAUTH_CALLBACK_URL=http://localhost:8002/api/github/oauth/callback

# For production
# GITHUB_OAUTH_CALLBACK_URL=https://yourdomain.com/api/github/oauth/callback
```

---

## API Flow Diagram

```
User clicks "Connect with GitHub"
         │
         ▼
Frontend calls GET /api/github/oauth/authorize
         │
         ▼
Backend generates state, returns GitHub auth URL
         │
         ▼
Frontend redirects to GitHub
         │
         ▼
User authorizes on GitHub
         │
         ▼
GitHub redirects to /api/github/oauth/callback?code=xxx&state=xxx
         │
         ▼
Backend validates state, exchanges code for token
         │
         ▼
Backend stores encrypted token in database
         │
         ▼
Backend redirects to /settings?github=connected
         │
         ▼
Frontend shows success, user can now browse GitHub
```

---

## Estimated Implementation Time

| Phase | Task | Time |
|-------|------|------|
| 1 | Register GitHub App | 15 min |
| 2 | Backend OAuth routes | 2-3 hours |
| 2 | Database model + migration | 30 min |
| 2 | Token encryption | 30 min |
| 2 | Update existing routes | 1 hour |
| 3 | Frontend OAuth flow | 1-2 hours |
| 3 | Update Settings page | 30 min |
| 3 | Update file browser | 30 min |
| 4 | Migration + cleanup | 30 min |
| 5 | Testing | 1 hour |
| **Total** | | **8-10 hours** |

---

## References

- [About GitHub Apps](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/about-creating-github-apps)
- [Registering a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [Generating User Access Tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)
- [Refreshing User Access Tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/refreshing-user-access-tokens)

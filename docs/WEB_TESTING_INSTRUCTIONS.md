C:\xampp\htdocs\wordpress# Web Testing Instructions for LLM Agents

**Purpose**: This is a LIVE document containing instructions for any LLM agent to interact with WordPress and ACM2 for testing. Update this document whenever you discover new solutions, selectors, or error recovery patterns.

**Last Updated**: January 11, 2026

---

## Table of Contents
1. [Quick Reference](#quick-reference)
2. [ACM2 Application](#acm2-application)
3. [WordPress Admin](#wordpress-admin)
4. [Error Recovery Patterns](#error-recovery-patterns)
5. [Known Issues and Solutions](#known-issues-and-solutions)
6. [Testing Workflows](#testing-workflows)

---

## Quick Reference

### URLs
| Application | URL | Notes |
|-------------|-----|-------|
| ACM2 App | `http://localhost:8000` | FastAPI backend + static frontend |
| ACM2 API Docs | `http://localhost:8000/docs` | Swagger UI |
| WordPress | `http://localhost/wp-admin` | Local WordPress (adjust as needed) |

### Default Test Credentials
| Application | Username | Password | Notes |
|-------------|----------|----------|-------|
| ACM2 | `testuser12` | `testuser12` | Test user (user_id=10) |
| ACM2 | `admin` | (check db) | Admin user |
| WordPress | `admin` | (check wp-config) | WordPress admin |

---

## ACM2 Application

### Starting the Server
```
cd C:\dev\godzilla\acm2\acm2
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Page Structure

#### Login Page (`/`)
The app redirects to login if not authenticated.

| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Username input | `input[name="username"]` or `#username` | Try both |
| Password input | `input[name="password"]` or `#password` | Try both |
| Login button | `button[type="submit"]` or `.login-btn` | Try both |
| Error message | `.error-message` or `.alert-danger` | Check after failed login |

#### Main Dashboard (after login)
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Presets list | `.presets-list` or `#presets` | Container for presets |
| Preset item | `.preset-item` or `.preset-card` | Individual preset |
| Add preset button | `.add-preset-btn` or `#add-preset` | Creates new preset |
| Provider keys section | `.provider-keys` or `#provider-keys` | API key management |
| Logout button | `.logout-btn` or `#logout` | Session termination |

#### Settings/Provider Keys
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Provider dropdown | `select[name="provider"]` | OpenAI, Anthropic, etc. |
| API key input | `input[name="api_key"]` or `#api-key` | Encrypted on save |
| Save button | `button[type="submit"]` or `.save-btn` | Submits form |

### API Endpoints (for direct testing)

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/auth/login` | POST | None | Get session/token |
| `/api/presets` | GET | X-ACM2-API-Key | List presets |
| `/api/presets` | POST | X-ACM2-API-Key | Create preset |
| `/api/presets/{id}` | GET | X-ACM2-API-Key | Get single preset |
| `/api/presets/{id}` | PUT | X-ACM2-API-Key | Update preset |
| `/api/presets/{id}` | DELETE | X-ACM2-API-Key | Delete preset |
| `/api/provider-keys` | GET | X-ACM2-API-Key | List provider keys |
| `/api/provider-keys` | POST | X-ACM2-API-Key | Add provider key |

### Authentication Header
```
X-ACM2-API-Key: <api_key_from_acm2_master.api_keys>
```

---

## WordPress Admin

### Login Page (`/wp-admin` or `/wp-login.php`)
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Username input | `#user_login` | WordPress standard |
| Password input | `#user_pass` | WordPress standard |
| Remember me | `#rememberme` | Checkbox |
| Login button | `#wp-submit` | Submit button |
| Error messages | `#login_error` | Shows login failures |

### Admin Dashboard (`/wp-admin/`)
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Admin menu | `#adminmenu` | Left sidebar |
| Settings link | `#menu-settings` | Settings menu |
| Plugins link | `#menu-plugins` | Plugins menu |
| Content area | `#wpbody-content` | Main content |

### Settings Page (`/wp-admin/options-general.php`)
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Site title | `#blogname` | Input field |
| Tagline | `#blogdescription` | Input field |
| Save button | `#submit` | Submit changes |

### ACM2 Plugin Settings (if installed)
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| ACM2 menu | `#toplevel_page_acm2` | Plugin menu item |
| API URL input | `#acm2_api_url` | ACM2 server URL |
| API key input | `#acm2_api_key` | Authentication key |

---

## Error Recovery Patterns

### Element Not Found
**Problem**: `playwright_click` or `playwright_fill` fails with "element not found"

**Solutions** (try in order):
1. **Wait and retry**: Page may still be loading
   ```
   playwright_evaluate: "await new Promise(r => setTimeout(r, 2000))"
   ```
2. **Check HTML structure**: Use `playwright_get_visible_html` to see actual DOM
3. **Try alternative selector**: Many elements have multiple valid selectors
4. **Check for iframe**: Use `playwright_iframe_click` if element is in iframe
5. **Screenshot for debugging**: Use `playwright_screenshot` to see current state

### Login Fails
**Problem**: Login doesn't redirect or shows error

**Solutions**:
1. **Check credentials**: Verify in database
2. **Check console logs**: `playwright_console_logs` for JS errors
3. **Check network**: Server may not be running
4. **Clear cookies**: Navigate away and back, or close browser

### Page Not Loading
**Problem**: Navigation times out or shows error

**Solutions**:
1. **Check server is running**: Look at terminal output
2. **Check port**: Confirm correct port (8000 for ACM2)
3. **Increase timeout**: Add `timeout` parameter to navigate
4. **Check for redirects**: May need to follow redirect chain

### CORS Errors
**Problem**: API calls blocked by CORS

**Solutions**:
1. **Use same origin**: Navigate browser to app first
2. **Check server CORS config**: Backend may need CORS middleware

---

## Known Issues and Solutions

### Issue: Browser Already Open
**Symptom**: Error about existing browser session
**Solution**: Call `playwright_close` before starting new test

### Issue: Screenshot Returns Base64
**Symptom**: Can't see screenshot content
**Solution**: Use `savePng: true` and `downloadsDir` to save to disk

### Issue: Form Submission Doesn't Work
**Symptom**: Click on submit doesn't trigger form
**Solution**: Try `playwright_press_key` with "Enter" instead of click

### Issue: Dropdown Won't Select
**Symptom**: `playwright_select` fails
**Solution**: Check if it's a custom dropdown (not `<select>`), use click instead

### Issue: Page Content Not Updating
**Symptom**: Old content still visible after action
**Solution**: Add wait, or use `playwright_evaluate` to check for changes

---

## Testing Workflows

### Workflow 1: ACM2 Login Test
```
1. playwright_navigate: url="http://localhost:8000"
2. playwright_screenshot: name="login-page"
3. playwright_fill: selector="#username", value="testuser12"
4. playwright_fill: selector="#password", value="testuser12"
5. playwright_click: selector="button[type='submit']"
6. playwright_screenshot: name="after-login"
7. playwright_get_visible_text (verify dashboard content)
```

### Workflow 2: ACM2 API Test
```
1. playwright_post: url="http://localhost:8000/api/auth/login", value='{"username":"testuser12","password":"testuser12"}'
2. (extract token/key from response)
3. playwright_get: url="http://localhost:8000/api/presets" (with auth header)
```

### Workflow 3: WordPress Login Test
```
1. playwright_navigate: url="http://localhost/wp-login.php"
2. playwright_fill: selector="#user_login", value="admin"
3. playwright_fill: selector="#user_pass", value="password"
4. playwright_click: selector="#wp-submit"
5. playwright_screenshot: name="wp-dashboard"
```

### Workflow 4: End-to-End ACM2 Preset Creation
```
1. Login (Workflow 1)
2. playwright_click: selector=".add-preset-btn"
3. playwright_fill: selector="#preset-name", value="Test Preset"
4. playwright_fill: selector="#preset-prompt", value="You are a helpful assistant"
5. playwright_click: selector="button[type='submit']"
6. playwright_screenshot: name="preset-created"
7. Verify preset appears in list
```

---

## Selector Discovery Process

When you encounter a page and don't know the selectors:

1. **Get the HTML**:
   ```
   playwright_get_visible_html: selector="body", cleanHtml=true
   ```

2. **Look for**:
   - `id` attributes (most reliable): `#element-id`
   - `name` attributes: `[name="field"]`
   - Unique classes: `.specific-class`
   - Form elements: `input`, `button`, `select`

3. **Update this document** with discovered selectors!

---

## Debugging Checklist

When something doesn't work:

- [ ] Is the server running? (Check terminal)
- [ ] Did I close the previous browser? (`playwright_close`)
- [ ] Can I see the page? (`playwright_screenshot`)
- [ ] What does the HTML look like? (`playwright_get_visible_html`)
- [ ] Are there console errors? (`playwright_console_logs`)
- [ ] Am I using the right selector? (check alternatives)
- [ ] Is the element in an iframe? (use iframe tools)
- [ ] Did I wait long enough? (add delay)

---

## Notes Section

Add discoveries and learnings here during testing:

### January 11, 2026
- Document created
- ACM2 server runs on port 8000
- testuser12 exists with password testuser12 (user_id=10 in MySQL)
- CRITICAL: Server currently uses shared database, not per-user database (bug to fix)

---

## Remember

1. **Always screenshot** before and after critical actions
2. **Always check console logs** when something fails
3. **Always update this document** when you discover something new
4. **Always close browser** at end of test session
5. **Never assume selectors** - verify with get_visible_html first

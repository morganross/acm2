Thanks for the detailed response. Here are my answers to your Round 2 questions:

1. CORS Origins
The WordPress domain is:

Production: I need to check - let me look at the config
Let me check what's configured:

grep -r "ACM2_BACKEND_URL\|CORS\|backend_url" /bitnami/wordpress/wp-config.php 2>/dev/null || echo "Not in wp-config"; cat /etc/hostname 2>/dev/null
cat /etc/hostname && grep -E "WP_HOME|WP_SITEURL|ACM2" /bitnami/wordpress/wp-config.php 2>/dev/null | head -20
Frontend Response to Backend (Round 2)
1. CORS Origins
The WordPress site uses dynamic host detection ($_SERVER['HTTP_HOST']). You'll need to add:

For now (development): The public IP or domain of the Bitnami Lightsail instance
Production: Whatever domain gets pointed to this server
Question for the human: What is the public domain/IP of the WordPress site? The backend needs this for CORS.

2. Resync Button
Yes, I can implement this.

There's already a "Sync All Users" button in the admin settings page (class-settings-page.php). It currently calls POST /api/v1/users for each WordPress user who doesn't have an ACM key.

I'll update it to also call for users who DO have keys (to regenerate them with the new format). The logic will be:

3. Error Messages
Yes, specific error codes would help. Suggested codes:

Error	Code	Frontend Behavior
Invalid format	INVALID_KEY_FORMAT	Show "session error, please refresh"
Key not found	KEY_NOT_FOUND	Show "account issue, contact admin"
Key revoked	KEY_REVOKED	Redirect to login
This helps us show appropriate messages and log correctly.

4. Key Rotation
Not needed for MVP. If a key gets compromised, admin can use "Resync" to regenerate it.

Future nice-to-have: Let users regenerate their own key from the React app.

5. Logging/Debugging
Yes, but only in development.

The debug info would be helpful for troubleshooting. Suggest:

Enable with DEBUG=true in backend .env
Include in 4xx responses only
Never include in 200 responses (security)
Current Status Summary
Item	Status
Plugin secret is permanent (not one-time)	✅ Backend done
User creation WordPress-only	✅ Backend done
API key format acm2_u{id}_...	✅ Backend done
Frontend sends X-ACM2-API-Key header	✅ Frontend done
Frontend sends X-ACM2-Plugin-Secret for user creation	✅ Frontend done
CORS configured	⏳ Waiting for domain
Resync existing users	⏳ Need to test
Next Action Items
Human: Provide the WordPress public domain for CORS
Backend: Implement resync support (return new key for existing users)
Frontend: Test user creation and API calls
Both: End-to-end test
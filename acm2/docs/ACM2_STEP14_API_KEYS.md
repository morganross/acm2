# ACM 2.0 Step 14: API Key Management

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.

## Summary

ACM 2.0 uses a single API key stored in a `.env` file at `~/.acm2/.env` or `./acm2.env`. The backend reads `ACM2_API_KEY` from this file and validates incoming requests against the `Authorization: Bearer <key>` header. If the key is not set, the API runs unauthenticated (local development mode). There are no scopes, no multiple keys, no database-backed key management, and no revocation endpoints. For a single-user self-hosted tool, this is sufficient.

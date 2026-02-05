# ACM2 Workflow Root‑Cause Analysis Report (User Isolation Failure)

**Date:** 2026‑02‑04  
**Scope:** Workflow and operational root cause analysis for the user‑isolation failure observed when a newly created WordPress user sees another user’s provider keys and the ACM app shows “API key required.”  
**Constraint:** This report is intentionally focused on workflow and operational causality, not syntax or code changes. It contains no remediation proposals.

---

## Executive Summary

The user‑isolation failure is not a single defect in an isolated line of code. It is the emergent outcome of a workflow that splits identity and key ownership across two systems (WordPress and the ACM2 backend), relies on asynchronous synchronization, and treats “system connected” status as equivalent to “user‑ready” status. The operational pipeline does not enforce a single, authoritative checkpoint that confirms (a) WordPress user creation, (b) backend user creation, (c) API key issuance, (d) storage and retrieval of the key in WordPress, and (e) UI propagation of the correct user’s key into the browser session—**as one cohesive, atomic workflow**. Instead, these steps happen in separate subsystems, on separate clocks, and with separate validation semantics.

As a consequence, the system can enter a state where:

- The **WordPress admin UI** shows “API Connected” (system‑level connectivity),
- The **Provider Keys page** is populated (because a valid API key, even if belonging to another user, is present in the request chain), and
- The **ACM app page** shows “API key required” (because the per‑user API key is absent from that specific data path for the current user),

…while no single subsystem asserts that these three states are mutually inconsistent.

The root cause is therefore **workflow fragmentation**, not a syntactic error. The workflow allowed multiple, partially successful steps to appear successful in isolation, with no cross‑step guarantee that the correct key is bound to the correct user throughout the browser session.

---

## Report Relationship to Prior Investigation

This report is a continuation and workflow‑focused reframing of the earlier technical investigation documented at:

**c:\devlop\acm2\INVESTIGATION_REPORT_ACM_APP_NOT_LOADING.md**

That prior report identified technical defects causing the React app to fail to load. The present report does **not** revisit those syntax‑level defects; instead it examines the **workflow conditions** that allowed a user‑isolation failure to surface even after the app was loading correctly.

---

## Observed Symptoms (Field Evidence)

The observed symptoms, in their user‑visible form, are:

1. **Settings page displays “API Connected.”**
2. **Provider Keys page shows an OpenAI key that belongs to another user.**
3. **ACM App page shows “API key required.”**

These three symptoms are inconsistent on their face. They can only occur if:

- The **system‑level backend connectivity test** is not scoped to the current user,
- The **Provider Keys page** is using a valid but **incorrect** API key, and
- The **ACM App** is missing or not receiving the API key that would authenticate the current user.

This is an operational consistency problem rather than a simple runtime failure.

---

## System Topology (Workflow Perspective)

The system is a two‑node architecture with a hard division of responsibility:

- **WordPress Frontend (UI + user management)**
- **FastAPI Backend (per‑user data + API keys)**

Workflow responsibilities are distributed as follows:

1. **WordPress** creates users and stores the per‑user API key in its own database table (`wp_acm2_api_keys`).
2. **Backend** creates a matching per‑user SQLite database and issues API keys (with embedded user_id).
3. **Browser** uses the API key injected into the page to authenticate directly with the backend.

**Critical Workflow Characteristic:** There is **no single transactional boundary** that guarantees all of these steps succeed together. Each step succeeds (or fails) independently, and the system does not assert a mandatory reconciliation before the UI is allowed to proceed.

---

## Identity and Key Flow (Operational Chain)

### Step 1: WordPress User Creation
- WordPress user is created. This is authoritative for UI access.
- The UI permissions (e.g., capability “read” or “manage_options”) determine which pages are visible.

### Step 2: Sync to Backend
- A synchronization event is fired via the WordPress plugin.
- The backend is asked to create or resync the corresponding ACM2 user.

### Step 3: Backend API Key Issuance
- Backend generates an API key with embedded user_id.
- Backend returns this key to WordPress.

### Step 4: WordPress Storage of Key
- WordPress saves the returned key into `wp_acm2_api_keys` for that user.
- A verification step checks whether the key exists after save.

### Step 5: UI Injection
- The API key is injected into the browser context as part of page rendering.
- Separate pages inject the key through separate JavaScript contexts.

### Step 6: Browser→Backend Requests
- Browser uses the injected key to call the backend directly.
- Backend interprets the key, extracts user_id, and selects the per‑user database.

**Critical Observation:** There is no enforced “completion gate” that blocks Steps 5–6 unless Steps 2–4 are proven correct for the **current user**. This allows a correct system‑level connection but incorrect user‑level key usage.

---

## Evidence of Workflow Drift

### 1) Save‑Result Contradiction
The WordPress logs show:

- “Save result: FAILED”
- “Verification ‑ key exists after save: YES”

This is not a code‑syntax issue; it is a **workflow ambiguity** in how success is measured and reported. The workflow treats a failed return value and a successful verification as co‑existing truths without reconciling them. That weakens the reliability of the user‑sync pipeline as an authoritative signal for UI readiness.

### 2) System‑level “API Connected” vs User‑level Readiness
The Settings page indicates “API Connected” as a global connectivity status. This is not equivalent to per‑user provisioning. The workflow does not enforce a separate “User Key Provisioned” status before rendering user‑specific pages.

### 3) Independent Page Pipelines
The Provider Keys page and the ACM App page each acquire the API key through separate front‑end injection contexts. This means each page can be “right” or “wrong” independently, even within the same login session. The workflow does not enforce cross‑page consistency checks.

---

## Root‑Cause Chain (Workflow Perspective)

1. **Fragmented Ownership of Identity**
   - WordPress is authoritative for user identity and session.
   - Backend is authoritative for per‑user data and provider keys.
   - The workflow depends on a synchronization step to bridge the two.

2. **Non‑Atomic Provisioning**
   - User creation, backend creation, key issuance, key storage, and key injection are separate operations.
   - There is no atomic “all‑or‑nothing” checkpoint.

3. **Ambiguous Success Signals**
   - Logs indicate conflicting results for key storage.
   - The system proceeds as though provisioning is successful without a single authoritative pass/fail outcome.

4. **UI Authorization vs Data Authorization Split**
   - UI access is granted based on WordPress capabilities.
   - Data access is granted based on the injected API key.
   - When these diverge, a user can see another user’s data or be blocked despite valid UI access.

5. **Silent Inheritance of Stale or Incorrect Keys**
   - The UI can receive a key that is not tied to the current session’s user.
   - Once a valid key is present, backend calls succeed, even if the key belongs to the wrong user.

6. **Resulting User‑Isolation Failure**
   - Provider keys from the backend are returned for the user_id embedded in the key, not the logged‑in WordPress user.
   - The user sees data that is correct for the key, but incorrect for their identity.

This chain produces **exactly** the observed symptoms while preserving internal consistency inside each subsystem. The failure is therefore systemic and workflow‑level.

---

## Historical Attempts to Fix (Required Section)

The system has already undergone at least one significant remediation cycle, documented in the prior report at **c:\devlop\acm2\INVESTIGATION_REPORT_ACM_APP_NOT_LOADING.md**. That effort focused on frontend load failures that prevented the ACM app from rendering at all. Two critical frontend integration bugs were identified and corrected (as recorded in that report), which restored the React application’s ability to mount and display.

However, restoring the UI surface did not guarantee correct identity‑to‑key binding. This is a workflow reality: a system can be **visually operational** while still operating under incorrect authentication context. The historical fix resolved **render‑time failures**, but did not and could not, by itself, enforce the **cross‑system synchronization integrity** that is required for per‑user key isolation. The persistence of the current issue after the UI was restored is evidence that the root cause lies upstream, within the provisioning and synchronization workflow.

---

## Detailed Workflow Failure Analysis

### A) WordPress Sync as an Asynchronous Bridge
The user‑sync step is designed as a background handshake. It is triggered by WordPress events and relies on remote HTTP calls to the backend. This inherently creates a window where the WordPress user exists but the backend record and key may not be fully established. If the UI is accessible during that window, then the browser can load pages before the key is reliably stored.

### B) Inconsistent Notions of “Current User”
The WordPress notion of “current user” is session‑based and tied to cookie state. The backend notion of “current user” is key‑based and independent of WordPress sessions. The workflow allows these two notions to diverge without reconciling them.

### C) Key Storage as a Side‑Effect, Not a Gate
The key is stored in WordPress as a side‑effect of the sync response. The workflow proceeds even if the save result indicates a failure. This produces a state where system logs declare a failure but the later verification declares success, or vice‑versa, leaving the operational state ambiguous.

### D) Per‑Page Injection Variance
The provider keys UI and the ACM app UI are separate surfaces with separate injection contexts. There is no single shared key‑binding enforcement layer. As a result, the two pages can disagree, and both can appear “correct” from their own limited perspective.

---

## Why This Is a Workflow Problem (Not Syntax)

A syntax bug would typically produce a single, repeatable failure mode (e.g., a consistent error, a non‑rendering UI, or a hard exception). Instead, the observed behavior is **incoherent across pages**, indicating that each subsystem is individually functioning but not aligned at the workflow layer.

The system is **operationally permissive**: it allows a user to proceed into pages even when the identity‑key binding is incomplete, ambiguous, or mismatched. This is a workflow design issue in how the system sequences and validates cross‑component identity state.

---

## Evidence Mapping (Subsystem Consistency)

- **Backend**: correctly returns data for whichever key is presented.
- **WordPress**: correctly identifies the logged‑in user.
- **UI**: correctly renders whatever data it is given.

The mismatch is not in any single component’s function. It is in the system‑level workflow that binds these components together without enforcing end‑to‑end invariants.

---

## Conclusion

The root cause is a **workflow integrity gap**. The system does not enforce a single, authoritative “user‑ready” checkpoint that binds WordPress identity, backend identity, API key issuance, key storage, and UI injection into one atomic outcome. Instead, it allows these steps to succeed or fail independently while still presenting the UI as fully operational.

This creates a state where the UI can show another user’s provider keys while simultaneously claiming that the current user lacks an API key. This is not a syntax error; it is a multi‑stage workflow that lacks a cross‑system consistency barrier.

---

## Appendix A: Relevant Artifacts and Locations

- Prior report (frontend load investigation): **c:\devlop\acm2\INVESTIGATION_REPORT_ACM_APP_NOT_LOADING.md**
- WordPress plugin files (frontend): located under the WordPress plugins directory on the frontend host.
- Backend per‑user databases: located under `acm2/data` on the backend host.

---

## Appendix B: Report Length Note

This report is provided as the initial workflow‑focused analysis. It can be expanded iteratively to meet any required word count while preserving the same non‑remediative stance.

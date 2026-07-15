# Sprint 01 — Identity and Secure API Foundation

**Milestone:** M1 — Identity and Secure API Foundation  
**Sprint Goal:** Establish user authentication with secure token management, server-side refresh token revocation, and encrypted local storage on Android.

---

## 1. Objective

By the end of this sprint, users can:

- Sign up with username, email, password (Argon2id hashed)
- Log in and receive a short-lived JWT access token (5–15 minutes) + long-lived refresh token (7–30 days)
- Use access tokens to call protected endpoints
- Refresh expired access tokens using refresh tokens (with rotation and server-side validation)
- Revoke sessions on logout, password reset, or explicit device removal
- Android: Store tokens securely in Android Keystore via AndroidX Security Crypto, with biometric re-authentication gating (30-second window)
- All infrastructure endpoints (`/health`, `/ready`) remain public (no auth required)

No chat, memory, tasks, or proactive features yet — authentication only.

---

## 2. Scope

### 2.1 In Scope

**Backend — Users & Authentication**
- `User` SQLAlchemy model: `id`, `username`, `email`, `password_hash`, `name`, `phone`, `preferences` (JSON), `created_at`, `updated_at`
- Alembic migration: create `users` table with unique constraints on `username` and `email`
- Password hashing: Argon2id via `argon2-cffi` library
- Endpoints:
  - `POST /auth/signup` — create user, hash password, return access + refresh tokens
  - `POST /auth/login` — verify username/password, return access + refresh tokens
  - `POST /auth/refresh` — validate refresh token, rotate it, return new access token
  - `POST /auth/logout` — revoke refresh token (mark as revoked in DB)
  - `POST /auth/revoke-all` — revoke all refresh tokens for a user (password reset, suspicious activity)
  - `GET /auth/me` — return current user profile (protected endpoint, requires valid access token)
- Middleware: JWT validation on protected endpoints (extracts user from token, attaches to request)
- Error handling: Clear 401 (unauthorized) vs 403 (forbidden) vs 422 (validation) status codes

**Backend — Refresh Token Storage & Revocation**
- `RefreshToken` SQLAlchemy model: `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at`, `created_at`
- Tokens stored as hashes in DB (not plaintext) — hash with SHA256
- Revocation tracked per token (soft delete via `revoked_at` timestamp, not hard delete)
- Session revocation endpoint revokes all tokens for a user at once
- Token rotation: on successful refresh, old token is revoked and new token issued

**Backend — Token Generation & Validation**
- Access token: 10 minutes expiry (configurable)
- Refresh token: 14 days expiry (configurable)
- Tokens include: `user_id`, `token_type` (access/refresh), `iat` (issued at), `exp` (expiration)
- Validation: check expiry, check signature, check revocation status (for refresh tokens)
- Error responses include clear messages ("Token expired", "Token revoked", "Invalid signature")

**Backend — Testing**
- Unit tests for Argon2id hashing (verify hash/verify flow)
- Integration tests for signup/login endpoints (invalid credentials, duplicate username, etc.)
- Integration tests for token refresh (valid refresh, expired token, revoked token, rotation confirmation)
- Integration tests for logout (token revocation confirmed in DB)
- Test fixtures: pre-seeded users with known credentials

**Android — Login Screen & Authentication**
- `LoginScreen.kt` — simple form with username/email field, password field, login button
- On successful login: store access + refresh tokens securely, navigate to main screen (to be built later)
- On error: show error message (invalid credentials, network error, etc.)
- "Remember me" logic: optional, mark refresh token lifetime preference (skip for Sprint 01 if tight on time)

**Android — Token Storage (AndroidX Security Crypto)**
- Dependency: `androidx.security:security-crypto:1.1.0-alpha06` (or latest stable)
- Create `TokenManager.kt`:
  - Use `EncryptedSharedPreferences` to store access + refresh tokens encrypted via Android Keystore
  - Hardware-backed AES key generation (fall back to software if not available)
  - Tokens stored encrypted, decrypted on retrieval
  - Clear tokens on logout
- Create `BiometricManager.kt`:
  - Wrap `BiometricPrompt` to gate token access (optional, but recommended for 30-sec re-auth)
  - Check if biometric is available, fallback to device PIN/pattern if not
  - Re-auth required if last auth >30 seconds ago (track via timestamp in encrypted prefs)

**Android — API Interceptor**
- Create `AuthInterceptor.kt` — OkHttp interceptor that:
  - Attaches access token to every request as `Authorization: Bearer <token>`
  - On 401 response: catch it, attempt refresh using refresh token
  - If refresh succeeds: retry original request with new access token
  - If refresh fails: clear stored tokens, navigate back to login
  - Handle token expiry gracefully (re-login, not silent failure)

**Android — Login Integration**
- Update `MainActivity.kt` or `RaghviNavGraph.kt` to check if user is logged in (token exists) on app startup
- If logged in: navigate to main screen (placeholder for now)
- If not: show `LoginScreen`

**Android — Testing**
- Unit tests for `TokenManager` (encrypt/decrypt, clear)
- Unit tests for `BiometricManager` (re-auth window logic)
- Unit tests for `AuthInterceptor` (token attachment, refresh on 401)
- Instrumented tests for login flow end-to-end (with mock backend)

**CI / GitHub Actions**
- No changes — existing pipeline still runs backend tests, lint, format, Docker build
- New tests are included in pytest runs; CI fails if any test fails

### 2.2 Out of Scope (explicitly deferred)

- Social login (Google, GitHub, etc.) — M2+
- Multi-factor authentication (MFA) — M2+
- Password reset flow (email-based) — M2+
- User profile editing — M2+
- Role-based access control (admin, user roles) — M2+
- Device management (list/revoke devices) — M2+
- Rate limiting on auth endpoints — M2+
- Chat, memory, tasks, or any feature endpoints — M2+

---

## 3. Deliverables

| # | Deliverable | Location |
|---|---|---|
| 1 | Sprint 01 plan (this document) | `docs/05-sprints/sprint-01-auth.md` |
| 2 | User SQLAlchemy model | `backend/app/models/user.py` |
| 3 | RefreshToken model | `backend/app/models/refresh_token.py` |
| 4 | Alembic migration: users + refresh_tokens tables | `backend/alembic/versions/` |
| 5 | Password hashing utilities | `backend/app/security/password.py` |
| 6 | JWT token generation & validation | `backend/app/security/jwt.py` |
| 7 | Auth endpoints (signup/login/refresh/logout/revoke-all) | `backend/app/api/auth.py` |
| 8 | JWT middleware for protected endpoints | `backend/app/middleware/auth.py` |
| 9 | Backend auth tests | `backend/tests/test_auth.py` |
| 10 | Android LoginScreen | `android/app/src/main/java/com/raghvi/assistant/ui/login/LoginScreen.kt` |
| 11 | Android TokenManager | `android/app/src/main/java/com/raghvi/assistant/network/TokenManager.kt` |
| 12 | Android BiometricManager | `android/app/src/main/java/com/raghvi/assistant/network/BiometricManager.kt` |
| 13 | Android AuthInterceptor | `android/app/src/main/java/com/raghvi/assistant/network/AuthInterceptor.kt` |
| 14 | Android login navigation integration | `android/app/src/main/java/com/raghvi/assistant/navigation/RaghviNavGraph.kt` (updated) |
| 15 | Android token/biometric tests | `android/app/src/test/` and `android/app/src/androidTest/` |
| 16 | Updated `libs.versions.toml` (add Argon2id, AndroidX Security Crypto) | `android/gradle/libs.versions.toml` |

---

## 4. Task Breakdown (execution order)

1. Add Argon2id + AndroidX Security Crypto dependencies (`pyproject.toml`, `libs.versions.toml`)
2. Create User model
3. Create RefreshToken model
4. Write Alembic migration for both tables
5. Implement password hashing (Argon2id)
6. Implement JWT token generation & validation
7. Implement auth endpoints (signup, login, refresh, logout, revoke-all)
8. Implement JWT middleware for protected endpoints
9. Write backend auth tests (unit + integration)
10. Update root README with auth endpoint documentation
11. Create Android LoginScreen
12. Implement TokenManager (EncryptedSharedPreferences)
13. Implement BiometricManager
14. Implement AuthInterceptor
15. Integrate login into navigation graph
16. Write Android token/biometric/login tests
17. Verify end-to-end: signup on Android → login → access protected backend endpoint

---

## 5. Acceptance Criteria (Definition of Done for Sprint 01)

- [x] User model with username/email/password_hash/name/phone/preferences exists in DB with unique constraints
- [x] Argon2id hashing works: hash + verify flow passes tests
- [x] Signup endpoint creates user, returns access + refresh tokens
- [x] Login endpoint verifies credentials, returns access + refresh tokens
- [x] Refresh token rotation works: old token revoked, new token issued
- [x] Logout revokes the refresh token (confirmed in DB)
- [x] Access token expires in ~10 minutes; refresh token in ~14 days
- [x] Protected endpoints require valid access token (401 if missing/expired/invalid)
- [x] Refresh with expired/revoked token returns 401, forces re-login
- [x] `/health` and `/ready` remain public (no auth required)
- [x] Android LoginScreen renders correctly
- [x] TokenManager encrypts/decrypts tokens via Android Keystore (not plaintext)
- [x] BiometricManager enforces 30-second re-auth window
- [x] AuthInterceptor attaches access token to requests
- [x] AuthInterceptor handles 401: attempts refresh, retries request, or forces re-login if refresh fails
- [x] Android navigation: unauthenticated users see LoginScreen; authenticated users see main screen placeholder
- [x] All backend auth tests pass (signup, login, refresh, logout, revocation, token expiry)
- [x] All Android token/biometric/login tests pass
- [x] CI pipeline still passes (no regressions in existing tests)
- [x] Root README updated with auth endpoint documentation

---

## 6. Dependencies & Libraries

**Backend (Python):**
- `argon2-cffi>=23.1.0` — Argon2id password hashing
- `PyJWT>=2.8.0` — JWT token creation/validation
- `python-multipart>=0.0.6` — form data parsing for login (likely already present)

**Android (Gradle):**
- `androidx.security:security-crypto:1.1.0-alpha06` (or latest stable) — EncryptedSharedPreferences, Android Keystore
- `androidx.biometric:biometric:1.1.0` — BiometricPrompt API
- (Retrofit + OkHttp already present from Sprint 00)

---

## 7. Risks & Notes

- **Argon2id tuning:** Memory/time parameters affect hashing speed. Default to conservative (slower is safer). Performance test locally before finalizing.
- **Refresh token storage:** Hashing tokens before storage means you can't do plaintext comparison; must hash incoming token before DB lookup. Implement carefully.
- **Token rotation complexity:** Every refresh invalidates the old token. Ensure race conditions don't leave users without valid tokens (e.g., concurrent refresh attempts).
- **Android Keystore availability:** Some very old devices may not support hardware-backed keys. Fallback to software-backed keys is essential.
- **Biometric API fragmentation:** `BiometricPrompt` is the modern way, but availability varies by API level. Gracefully fall back to device PIN/pattern.
- **Token expiry precision:** 10 minutes is aggressive for an access token. If users hit network lag during requests, they may be forced to re-login frequently. Monitor UX feedback.
- **Scope creep:** Do not add password reset, MFA, social login, or device management — these are M2+.

---

## 8. Exit Condition

Sprint 01 is complete when:
- All acceptance criteria are checked off
- All tests pass (backend + Android)
- CI pipeline passes
- You can successfully sign up on Android, log in, and call `GET /auth/me` (a protected endpoint) with the returned access token
- Explicit confirmation that the work is done before moving to M1's next sprint or M2

---

## 9. Post-Sprint Housekeeping

Once Sprint 01 closes:
1. Update the main MVP Delivery Plan (`docs/04-implementations/mvp-delivery-plan.md`) to mark M1 complete
2. Create `docs/05-sprints/sprint-02-chat.md` for the next sprint (basic chat endpoint, Raghvi conversation)
3. Plan M2 — Chat, Memory, Tasks (Sprints 02–04 approximately)
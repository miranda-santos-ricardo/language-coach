# Step 8.4.1g — Pilot SPA OIDC Authentication Lifecycle (increment 1)

## Scope
- Isolated, opt-in pilot frontend shell. Legacy App and its UserSelector are unchanged; **never mount the legacy interface against the protected pilot API**.
- Public OIDC Authorization Code + PKCE S256, random state/nonce, five-minute single-use transaction, token exchange.
- Transaction held in sessionStorage solely to survive authorization redirect. Access token in React component memory only; no persistent refresh token.
- URL callback stripped of authorization code. Errors/expired session deny access. Explicit local logout erases token from memory.
- This is a **pilot authentication shell**, not a complete login-enabled practice application.

## Configuration (frontend/.env.local only; never embed client secrets)
```
VITE_PILOT_OIDC_ENABLED=true
VITE_OIDC_ISSUER=https://your-trusted-idp.example
VITE_OIDC_CLIENT_ID=your-registered-public-spa-client
VITE_OIDC_REDIRECT_URI=https://your-front-end-host.example/
VITE_OIDC_AUTHORIZATION_ENDPOINT=https://your-trusted-idp.example/authorize
VITE_OIDC_TOKEN_ENDPOINT=https://your-trusted-idp.example/token
```
The browser app and IdP must be configured for a **public client**, authorization code + PKCE, permitted redirect URI and token endpoint CORS. The example values above are placeholders, not deployable settings. `openid learner:access` must be supported by the IdP. HTTPS is required except loopback localhost development. No auto discovery of endpoints or untrusted key URLs.

## Explicit limitations / blockers
1. The secured `/users/{id}` and other learner endpoints are NOT wired to this shell in this increment; no pilot usage yet.
2. No browser identity is inferred from `sub`, email or selected user. The backend remains the source of truth for `(issuer,sub)` mapping and authorization.
3. Access tokens are not verified by the frontend; verification remains server-side. The frontend does NOT use an `id_token` as an API bearer.
4. Logout is local only; issued tokens may remain valid at backend until expiry/revocation. A server-side revocation/session management integration is required before claiming effective logout across devices.
5. No silent refresh. Expiration requires a new login. OIDC interactive IdP verification, real CORS and production redirect setup are not yet validated.
6. Do not enable this flag for end users yet. Some IdPs require nonce validation on a decoded ID token; that is left for the server-side/BFF token validation architecture, and is a blocker for final OIDC conformance.
7. React StrictMode callback lifecycle should be checked manually against a real IdP; this shell is experimental and not security certified.

## Acceptance commands
```
cd frontend
npm test -- --run
npm run build
```
Verify local mode remains functional with the flag absent. Pilot mode must show only sign-in shell and no UserSelector or practice features. Never put client secrets in Vite environment vars.

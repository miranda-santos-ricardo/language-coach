# Phase 8 — Step 8.4.1h — TypeScript nullability fix

Changed the authentication effect guard from `if (!isValidSession(tokens)) return;` to `if (!tokens || !isValidSession(tokens)) return;` so TypeScript narrows `tokens` to `AuthTokens` before calling `createPilotApi`. No authorization logic or network behavior changed.

Validation (frontend):

```powershell
npm test -- --run src/test/pilotApi.test.ts
npm test -- --run
npm run build
```

The protected pilot remains opt-in and requires real IdP validation before use.

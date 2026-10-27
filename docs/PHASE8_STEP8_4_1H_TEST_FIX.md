# Step 8.4.1h — Frontend test fix

The `profiles` method validates its `userId` argument synchronously and throws an `Error` before calling the asynchronous API request. The prior test expected a rejected Promise using `.rejects.toThrow`, so the test failed even though the invalid ID was blocked.

The fix changes only `frontend/src/test/pilotApi.test.ts` to assert synchronous throwing via `expect(() => ...).toThrow`. Production code remains unchanged.

Validation in the project's `frontend` directory:

```powershell
npm test -- --run src/test/pilotApi.test.ts
npm test -- --run
npm run build
```

Expected: the invalid-ID test passes and `fetcher` is not invoked. The full suite and build must be run locally before accepting the increment.

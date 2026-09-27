import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest does not expose lifecycle hooks globally by default.
// Register cleanup explicitly so each test starts with a fresh DOM.
afterEach(() => {
  cleanup();
});

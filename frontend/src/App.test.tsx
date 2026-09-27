import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const ricardo = {
  id: "11111111-1111-4111-8111-111111111111",
  display_name: "Ricardo",
  created_at: "2026-09-26T12:00:00Z",
  updated_at: "2026-09-26T12:00:00Z",
};

const frenchProfile = {
  id: "22222222-2222-4222-8222-222222222222",
  user_id: ricardo.id,
  language: { code: "fr", name: "French", is_active: true },
  variant: {
    code: "fr-CA",
    display_name: "French — Canada / Québec",
    country_code: "CA",
    regional_focus: "Québec",
    is_active: true,
  },
  cefr_level: "B2",
  default_production_register: {
    code: "professional",
    display_name: "Professional",
    production_allowed: true,
    comprehension_allowed: true,
    is_active: true,
  },
  comprehension_registers: [
    {
      code: "professional",
      display_name: "Professional",
      production_allowed: true,
      comprehension_allowed: true,
      is_active: true,
    },
    {
      code: "colloquial",
      display_name: "Colloquial",
      production_allowed: true,
      comprehension_allowed: true,
      is_active: true,
    },
  ],
  created_at: "2026-09-26T12:00:00Z",
  updated_at: "2026-09-26T12:00:00Z",
};

const languages = [
  { code: "en", name: "English", is_active: true },
  { code: "fr", name: "French", is_active: true },
];

const registers = [
  {
    code: "colloquial",
    display_name: "Colloquial",
    production_allowed: true,
    comprehension_allowed: true,
    is_active: true,
  },
  {
    code: "professional",
    display_name: "Professional",
    production_allowed: true,
    comprehension_allowed: true,
    is_active: true,
  },
];

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function installFetchMock() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/health")) return jsonResponse({ status: "ok" });
    if (url.endsWith("/users") && method === "GET") return jsonResponse([ricardo]);
    if (url.endsWith("/users") && method === "POST") {
      return jsonResponse(
        { ...ricardo, id: "33333333-3333-4333-8333-333333333333", display_name: "Ana" },
        201,
      );
    }
    if (url.endsWith(`/users/${ricardo.id}/language-profiles`) && method === "GET") {
      return jsonResponse([frenchProfile]);
    }
    if (url.includes("33333333-3333-4333-8333-333333333333/language-profiles")) {
      return jsonResponse([]);
    }
    if (url.endsWith("/languages")) return jsonResponse(languages);
    if (url.endsWith("/languages/fr/variants")) {
      return jsonResponse([frenchProfile.variant]);
    }
    if (url.endsWith("/languages/en/variants")) {
      return jsonResponse([
        {
          code: "en-CA",
          display_name: "English — Canada",
          country_code: "CA",
          regional_focus: null,
          is_active: true,
        },
      ]);
    }
    if (url.endsWith("/communication-registers")) return jsonResponse(registers);
    if (
      url.endsWith(`/users/${ricardo.id}/language-profiles`) &&
      method === "POST"
    ) {
      return jsonResponse(frenchProfile, 201);
    }
    if (url.endsWith(`/language-profiles/${frenchProfile.id}`) && method === "PATCH") {
      return jsonResponse({ ...frenchProfile, cefr_level: "C1" });
    }

    return jsonResponse({ detail: `Unhandled request: ${method} ${url}` }, 500);
  });
}

describe("App", () => {
  beforeEach(() => {
    installFetchMock();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads the backend status and allows selecting a user to see profiles", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("Backend online")).toBeInTheDocument();
    const ricardoButton = await screen.findByRole("button", { name: /Ricardo/i });
    await user.click(ricardoButton);

    expect(await screen.findByText("French — Canada / Québec")).toBeInTheDocument();
    expect(screen.getByText("CEFR B2")).toBeInTheDocument();
    expect(screen.getAllByText("Colloquial").length).toBeGreaterThan(0);
  });

  it("creates a user and selects it", async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("button", { name: /Ricardo/i });
    await user.type(screen.getByLabelText("Add user"), "Ana");
    await user.click(screen.getByRole("button", { name: "+ Add user" }));

    const ana = await screen.findByRole("button", { name: /Ana/i });
    expect(ana).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByText("No language profiles yet")).toBeInTheDocument();
  });

  it("opens the language profile form with data-driven register options", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Ricardo/i }));
    await screen.findByText("French — Canada / Québec");
    await user.click(screen.getByRole("button", { name: "+ Add language" }));

    expect(await screen.findByRole("heading", { name: "Add language profile" })).toBeInTheDocument();
    expect(screen.getByLabelText("Language")).toBeInTheDocument();
    expect(screen.getByLabelText("Default speaking style")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Colloquial" })).toBeInTheDocument();
  });

  it("submits a new language profile using reference-data codes", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Ricardo/i }));
    await screen.findByText("French — Canada / Québec");
    await user.click(screen.getByRole("button", { name: "+ Add language" }));

    await screen.findByRole("heading", { name: "Add language profile" });
    await user.selectOptions(screen.getByLabelText("Language"), "fr");
    await waitFor(() =>
      expect(screen.getByLabelText("Variant")).toHaveValue("fr-CA"),
    );
    await user.selectOptions(screen.getByLabelText("CEFR"), "B2");
    await user.selectOptions(screen.getByLabelText("Default speaking style"), "professional");
    await user.click(screen.getByRole("checkbox", { name: "Colloquial" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/users/${ricardo.id}/language-profiles`),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("edits an existing profile", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Ricardo/i }));
    await screen.findByText("French — Canada / Québec");
    await user.click(screen.getByRole("button", { name: "Edit" }));

    const cefr = await screen.findByLabelText("CEFR");
    await user.selectOptions(cefr, "C1");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByText("CEFR C1")).toBeInTheDocument());
  });
});

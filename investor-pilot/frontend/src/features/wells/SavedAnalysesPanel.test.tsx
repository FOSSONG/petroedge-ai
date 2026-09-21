// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { apiRequest } from "../../api/http";
import { SavedAnalysesPanel } from "./SavedAnalysesPanel";
vi.mock("../../api/http", () => ({ apiRequest: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it("does not display late evidence from the previously selected analysis", async () => {
  let resolveOld!: (value: unknown) => void;
  const pending = new Promise(resolve => { resolveOld = resolve; });
  vi.mocked(apiRequest).mockImplementation(async (url) => {
    if (url === "/analytics/saved") return ["A", "B"].map(id => ({ analysis_id: id, provenance: { well_id: id, source_row: 0, analyzed_at: "now" } })) as never;
    if (url === "/analytics/saved/A/assistant") return pending as never;
    return { analysis_id: String(url).split("/").pop() } as never;
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><SavedAnalysesPanel /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: /A.*row/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Look up saved evidence" }));
  await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/analytics/saved/A/assistant", expect.anything()));
  fireEvent.click(screen.getByRole("button", { name: /B.*row/ }));
  await act(async () => { resolveOld({ answer: "OLD ANSWER", facts: {}, citations: [], limitation: "old" }); await pending; });
  expect(screen.queryByText("OLD ANSWER")).not.toBeInTheDocument();
  client.clear();
});

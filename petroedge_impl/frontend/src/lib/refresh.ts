import type { QueryClient } from "@tanstack/react-query";

export async function refreshPlatform(queryClient: QueryClient, keys: readonly unknown[][] = []) {
  window.dispatchEvent(new CustomEvent("petroedge:refresh", { detail: { at: Date.now() } }));
  if (keys.length) {
    await Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
  } else {
    await queryClient.invalidateQueries();
  }
  await queryClient.refetchQueries({ type: "active" });
}

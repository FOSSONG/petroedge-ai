import {
  lazy,
  type ComponentType,
  type LazyExoticComponent,
} from "react";

type LazyModule<T extends ComponentType<any>> = {
  default: T;
};

const RELOAD_KEY = "petroedge:lazy-reload-attempted";

function isChunkFailure(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);

  return [
    "Failed to fetch dynamically imported module",
    "Importing a module script failed",
    "ChunkLoadError",
    "Loading chunk",
  ].some((candidate) => message.includes(candidate));
}

export function lazyWithRetry<T extends ComponentType<any>>(
  factory: () => Promise<LazyModule<T>>,
): LazyExoticComponent<T> {
  return lazy(async () => {
    try {
      const module = await factory();
      sessionStorage.removeItem(RELOAD_KEY);
      return module;
    } catch (error) {
      if (
        isChunkFailure(error) &&
        sessionStorage.getItem(RELOAD_KEY) !== "true"
      ) {
        sessionStorage.setItem(RELOAD_KEY, "true");
        window.location.reload();

        await new Promise<never>(() => undefined);
      }

      throw error;
    }
  });
}
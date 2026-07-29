export function normaliseCollection<T>(
  response: unknown,
  preferredKeys: string[] = [],
): T[] {
  if (Array.isArray(response)) {
    return response as T[];
  }

  if (
    !response ||
    typeof response !== "object"
  ) {
    return [];
  }

  const record =
    response as Record<string, unknown>;

  const candidateKeys = [
    ...preferredKeys,
    "items",
    "results",
    "data",
    "records",
  ];

  for (const key of candidateKeys) {
    const value = record[key];

    if (Array.isArray(value)) {
      return value as T[];
    }

    if (
      value &&
      typeof value === "object"
    ) {
      const nested =
        normaliseCollection<T>(
          value,
          preferredKeys,
        );

      if (nested.length > 0) {
        return nested;
      }
    }
  }

  return [];
}

export function readString(
  record: Record<string, unknown>,
  keys: string[],
  fallback = "—",
): string {
  for (const key of keys) {
    const value = record[key];

    if (
      typeof value === "string" &&
      value.trim()
    ) {
      return value;
    }

    if (
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      return String(value);
    }
  }

  return fallback;
}

export function readNumber(
  record: Record<string, unknown>,
  keys: string[],
): number | null {
  for (const key of keys) {
    const value = record[key];

    if (
      typeof value === "number" &&
      Number.isFinite(value)
    ) {
      return value;
    }

    if (
      typeof value === "string" &&
      value.trim()
    ) {
      const parsed = Number(value);

      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }

  return null;
}

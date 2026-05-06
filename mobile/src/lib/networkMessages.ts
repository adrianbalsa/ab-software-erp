/** Mensajes de red amigables (paridad con frontend `api-base`). */

const FETCH_FAILURE_HINT =
  "No se pudo conectar con el servidor. Comprueba tu red, bloqueadores o que la API esté disponible.";

export function isLikelyNetworkFetchError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  if (err.name === "AbortError") return false;
  const m = err.message.toLowerCase();
  return (
    m.includes("failed to fetch") ||
    m.includes("networkerror") ||
    m.includes("network request failed") ||
    m.includes("load failed") ||
    (err.name === "TypeError" && (m.includes("fetch") || m === "failed to fetch"))
  );
}

export function userFacingFetchFailureMessage(err: unknown): string {
  if (isLikelyNetworkFetchError(err)) return FETCH_FAILURE_HINT;
  if (err instanceof Error && err.message.trim()) return err.message.trim();
  return FETCH_FAILURE_HINT;
}

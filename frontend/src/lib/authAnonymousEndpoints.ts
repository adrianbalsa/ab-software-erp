/** Rutas donde no debe enviarse Bearer legado (login anónimo / refresh explícito). */
export function isAnonymousAuthEndpoint(input: string): boolean {
  let path = input.trim();
  try {
    path = path.includes("://") ? new URL(path).pathname : path.split("?")[0].split("#")[0];
  } catch {
    path = path.split("?")[0].split("#")[0];
  }
  const norm = path.replace(/\/+$/, "") || "/";
  return norm.endsWith("/auth/login") || norm.endsWith("/auth/refresh");
}

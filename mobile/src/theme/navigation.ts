/** Colores alineados con zinc/slate del shell web (centralizado para `Stack`). */
export function appStackScreenOptions(isDark: boolean) {
  return {
    headerStyle: { backgroundColor: isDark ? "#18181b" : "#f8fafc" },
    headerTintColor: isDark ? "#fafafa" : "#0f172a",
    headerTitleStyle: { fontWeight: "600" as const, color: isDark ? "#fafafa" : "#0f172a" },
  };
}

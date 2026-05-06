import { Redirect, Stack } from "expo-router";

import { useAuth } from "../../src/context/AuthContext";
import { useThemePreference } from "../../src/context/ThemePreferenceContext";
import { appStackScreenOptions } from "../../src/theme/navigation";

export default function AppGroupLayout() {
  const { token, isReady } = useAuth();
  const { resolvedScheme } = useThemePreference();
  const isDark = resolvedScheme === "dark";

  if (!isReady) return null;
  if (!token) return <Redirect href="/(auth)/login" />;

  return (
    <Stack screenOptions={appStackScreenOptions(isDark)}>
      <Stack.Screen name="index" options={{ title: "Portes" }} />
      <Stack.Screen name="pendientes" options={{ title: "Pendientes de Sync" }} />
      <Stack.Screen name="gastos/index" options={{ title: "Gastos" }} />
      <Stack.Screen name="gastos/nuevo" options={{ title: "Nuevo gasto (OCR)" }} />
      <Stack.Screen name="porte/[id]" options={{ title: "Detalle de porte" }} />
      <Stack.Screen name="porte/preview-[id]" options={{ title: "Albarán legal (PDF)" }} />
    </Stack>
  );
}

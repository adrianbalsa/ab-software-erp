import "../global.css";

import "react-native-gesture-handler";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { View } from "react-native";

import { AuthProvider } from "../src/context/AuthContext";
import { ThemePreferenceProvider, useThemePreference } from "../src/context/ThemePreferenceContext";
import { initSyncBackgroundWorker } from "../src/services/sync_service";

function ThemedShell({ children }: { children: React.ReactNode }) {
  const { resolvedScheme } = useThemePreference();
  const isDark = resolvedScheme === "dark";

  return (
    <View className={`flex-1 ${isDark ? "dark" : ""}`} style={{ flex: 1 }}>
      <StatusBar style={isDark ? "light" : "dark"} />
      {children}
    </View>
  );
}

export default function RootLayout() {
  useEffect(() => {
    initSyncBackgroundWorker();
  }, []);

  return (
    <ThemePreferenceProvider>
      <ThemedShell>
        <AuthProvider>
          <Stack screenOptions={{ headerShown: false }} />
        </AuthProvider>
      </ThemedShell>
    </ThemePreferenceProvider>
  );
}

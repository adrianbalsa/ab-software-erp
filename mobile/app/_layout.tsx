import "../global.css";

import "react-native-gesture-handler";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";

import { AuthProvider } from "../src/context/AuthContext";
import { initSyncBackgroundWorker } from "../src/services/sync_service";

export default function RootLayout() {
  useEffect(() => {
    initSyncBackgroundWorker();
  }, []);

  return (
    <AuthProvider>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false }} />
    </AuthProvider>
  );
}

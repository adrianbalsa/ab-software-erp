import { Redirect, Stack } from "expo-router";

import { useAuth } from "../../src/context/AuthContext";

export default function AuthGroupLayout() {
  const { token, isReady } = useAuth();

  if (!isReady) return null;
  if (token) return <Redirect href="/(app)" />;

  return <Stack screenOptions={{ headerShown: false }} />;
}

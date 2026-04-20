import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "../src/context/AuthContext";

export default function Index() {
  const { token, isReady } = useAuth();

  if (!isReady) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (token) {
    return <Redirect href="/(app)" />;
  }

  return <Redirect href="/(auth)/login" />;
}

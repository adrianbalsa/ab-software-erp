import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";

import { ThemeModePicker } from "../../src/components/ThemeModePicker";
import { ConnectionProbe } from "../../src/components/ConnectionProbe";
import { useAuth } from "../../src/context/AuthContext";
import { ApiError } from "../../src/lib/api";

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail === null || detail === undefined) return "Error desconocido";
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export default function LoginScreen() {
  const { signIn } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    setBusy(true);
    try {
      await signIn(username, password);
      router.replace("/(app)");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(formatDetail(e.body));
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError("No se pudo iniciar sesión");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      className="flex-1 bg-slate-50 dark:bg-zinc-950"
    >
      <View className="flex-1 justify-center px-5 py-8">
        <View className="mb-6 flex-row justify-end">
          <ThemeModePicker />
        </View>
        <Text className="text-2xl font-bold text-slate-900 dark:text-zinc-100">AB Logistics</Text>
        <Text className="mt-1 text-sm text-slate-600 dark:text-zinc-400">Acceso operadores</Text>

        <View className="mt-8 gap-3">
          <View>
            <Text className="mb-1 text-xs font-medium uppercase text-slate-500 dark:text-zinc-500">
              Usuario o email
            </Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              value={username}
              onChangeText={setUsername}
              placeholder="usuario@empresa.com"
              placeholderTextColor="#71717a"
              className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-base text-slate-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </View>
          <View>
            <Text className="mb-1 text-xs font-medium uppercase text-slate-500 dark:text-zinc-500">Contraseña</Text>
            <TextInput
              secureTextEntry
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              placeholderTextColor="#71717a"
              className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-base text-slate-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </View>
        </View>

        {error ? (
          <Text className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </Text>
        ) : null}

        <Pressable
          onPress={onSubmit}
          disabled={busy || !username.trim() || !password}
          className="mt-6 items-center rounded-xl bg-indigo-600 py-3.5 active:opacity-90 disabled:opacity-40"
        >
          {busy ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text className="text-base font-semibold text-white">Entrar</Text>
          )}
        </Pressable>

        <View className="mt-10">
          <ConnectionProbe />
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

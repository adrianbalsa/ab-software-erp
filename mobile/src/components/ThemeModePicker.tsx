import { Pressable, Text, View } from "react-native";

import { type ThemePreference, useThemePreference } from "../context/ThemePreferenceContext";

const OPTIONS: { key: ThemePreference; label: string }[] = [
  { key: "light", label: "Claro" },
  { key: "dark", label: "Oscuro" },
  { key: "system", label: "Sistema" },
];

export function ThemeModePicker() {
  const { preference, setPreference } = useThemePreference();

  return (
    <View className="flex-row rounded-lg border border-slate-200 bg-white p-0.5 dark:border-zinc-600 dark:bg-zinc-800">
      {OPTIONS.map(({ key, label }) => {
        const active = preference === key;
        return (
          <Pressable
            key={key}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            onPress={() => void setPreference(key)}
            className={`rounded-md px-2.5 py-1.5 ${active ? "bg-slate-900 dark:bg-slate-100" : ""}`}
          >
            <Text
              className={`text-[11px] font-semibold ${active ? "text-white dark:text-zinc-900" : "text-slate-600 dark:text-zinc-300"}`}
            >
              {label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

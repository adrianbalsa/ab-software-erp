"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

export type ThemeModeLabels = {
  light: string;
  dark: string;
  system: string;
  appearance: string;
};

type Props = {
  labels: ThemeModeLabels;
  className?: string;
};

export function ThemeModeControl({ labels, className }: Props) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  if (!mounted) {
    return (
      <div
        className={cn(
          "inline-flex h-9 rounded-lg border border-zinc-200 bg-white p-0.5 dark:border-zinc-700 dark:bg-zinc-800",
          className,
        )}
        aria-hidden
        style={{ width: 104 }}
      />
    );
  }

  const current = theme ?? "system";

  const btn =
    "inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500";
  const inactive =
    "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-700 dark:hover:text-zinc-100";
  const active =
    "bg-zinc-900 text-white shadow-sm dark:bg-zinc-100 dark:text-zinc-900";

  return (
    <div
      role="group"
      aria-label={labels.appearance}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg border border-zinc-200 bg-white p-0.5 shadow-sm dark:border-zinc-700 dark:bg-zinc-800",
        className,
      )}
    >
      <button
        type="button"
        className={cn(btn, current === "light" ? active : inactive)}
        aria-pressed={current === "light"}
        aria-label={labels.light}
        onClick={() => setTheme("light")}
      >
        <Sun className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        className={cn(btn, current === "dark" ? active : inactive)}
        aria-pressed={current === "dark"}
        aria-label={labels.dark}
        onClick={() => setTheme("dark")}
      >
        <Moon className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        className={cn(btn, current === "system" ? active : inactive)}
        aria-pressed={current === "system"}
        aria-label={labels.system}
        onClick={() => setTheme("system")}
      >
        <Monitor className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}

"use client";

import { useTheme } from "next-themes";
import { Toaster } from "sonner";
import { useEffect, useState } from "react";

export function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const dark = mounted && resolvedTheme === "dark";

  return (
    <Toaster
      position="bottom-right"
      theme={dark ? "dark" : "light"}
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast: dark
            ? "group border border-zinc-800/80 bg-zinc-950/95 text-zinc-100 shadow-2xl backdrop-blur-md"
            : "group border border-zinc-200/90 bg-white/95 text-zinc-900 shadow-lg backdrop-blur-md",
          title: dark ? "text-zinc-100" : "text-zinc-900",
          description: dark ? "text-zinc-400" : "text-zinc-600",
        },
      }}
    />
  );
}

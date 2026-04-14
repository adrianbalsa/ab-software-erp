"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

function joinClasses(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

const badgeVariantClasses: Record<BadgeVariant, string> = {
  default: "border-zinc-700 bg-zinc-800/60 text-zinc-100",
  destructive: "border-red-500/60 bg-red-500/15 text-red-200",
  warning: "border-amber-500/60 bg-amber-500/15 text-amber-200",
  success: "border-emerald-500/60 bg-emerald-500/15 text-emerald-200",
};

type BadgeVariant = "default" | "destructive" | "warning" | "success";

export function Badge({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold whitespace-nowrap",
        badgeVariantClasses[variant],
        joinClasses(className),
      )}
      {...props}
    />
  );
}

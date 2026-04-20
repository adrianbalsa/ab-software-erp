"use client";

import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type Props = {
  icon: LucideIcon;
  title: string;
  description?: string;
  className?: string;
};

/** Estado vacío con icono y texto; `role="status"` para lectores de pantalla. */
export function PortalClienteEmptyState({ icon: Icon, title, description, className }: Props) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-4 py-10 text-center text-zinc-600 dark:text-zinc-400",
        className,
      )}
      role="status"
    >
      <Icon className="h-11 w-11 shrink-0 text-zinc-300 dark:text-zinc-600" aria-hidden />
      <p className="mt-4 max-w-md text-sm font-semibold text-zinc-800 dark:text-zinc-100">{title}</p>
      {description ? <p className="mt-2 max-w-lg text-sm text-zinc-600 dark:text-zinc-400">{description}</p> : null}
    </div>
  );
}

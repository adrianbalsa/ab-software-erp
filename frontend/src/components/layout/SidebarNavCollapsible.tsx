"use client";

import * as Collapsible from "@radix-ui/react-collapsible";
import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { cn } from "@/lib/utils";

const STORAGE_PREFIX = "abl.sidebar.";

export type SidebarSectionStorageKey =
  | "institutional"
  | "operations"
  | "finance"
  | "management"
  | "system";

type Props = {
  sectionId: SidebarSectionStorageKey;
  /** Si la ruta activa pertenece a esta sección, arranca expandida si no hay preferencia guardada. */
  containsActive: boolean;
  title: string;
  subtitle: string;
  /** Separador sutil entre grupos (primera sección suele ser false). */
  withDivider?: boolean;
  children: ReactNode;
};

function readStoredExpanded(sectionId: SidebarSectionStorageKey): boolean | null {
  if (typeof window === "undefined") return null;
  try {
    const v = sessionStorage.getItem(`${STORAGE_PREFIX}${sectionId}`);
    if (v == null) return null;
    if (v === "0") return false;
    return true;
  } catch {
    return null;
  }
}

export function SidebarNavCollapsible({
  sectionId,
  containsActive,
  title,
  subtitle,
  withDivider = true,
  children,
}: Props) {
  const storageKey = `${STORAGE_PREFIX}${sectionId}`;
  const [userExpanded, setUserExpanded] = useState(() => {
    const stored = readStoredExpanded(sectionId);
    if (stored == null) return containsActive;
    return stored;
  });

  function persist(next: boolean) {
    try {
      sessionStorage.setItem(storageKey, next ? "1" : "0");
    } catch {
      /* ignore quota / private mode */
    }
  }

  function onOpenChange(next: boolean) {
    setUserExpanded(next);
    persist(next);
  }

  return (
    <Collapsible.Root open={userExpanded} onOpenChange={onOpenChange}>
      <section className="mt-0">
        <Collapsible.Trigger
          type="button"
          className={cn(
            "flex w-full items-start gap-2 rounded-md px-3 py-2 text-left transition-colors hover:bg-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500/80 dark:hover:bg-zinc-900/50",
            withDivider && "mt-2 border-t border-zinc-200/90 pt-3 dark:border-zinc-800/55",
          )}
        >
          <ChevronDown
            className={cn(
              "mt-0.5 h-4 w-4 shrink-0 text-zinc-500 transition-transform duration-200 dark:text-zinc-500",
              userExpanded ? "rotate-0" : "-rotate-90",
            )}
            aria-hidden
          />
          <span className="min-w-0 flex-1">
            <span className="block text-[10px] font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-500">
              {title}
            </span>
            <span className="mt-0.5 block text-[10px] font-medium leading-snug text-zinc-600 dark:text-zinc-600">
              {subtitle}
            </span>
          </span>
        </Collapsible.Trigger>
        <Collapsible.Content className="overflow-hidden">
          <div className="flex flex-col gap-0.5 pb-0.5 pt-1">{children}</div>
        </Collapsible.Content>
      </section>
    </Collapsible.Root>
  );
}

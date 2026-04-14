import { cn } from "@/lib/utils";

/** Clases compartidas entre AppShell y Sidebar (navegación Búnker / zinc + emerald). */
export function sidebarNavRow(active: boolean) {
  return cn(
    "group flex items-start gap-3 border-l-2 border-l-transparent px-3 py-2.5 text-sm font-medium transition-all duration-200 rounded-r-md",
    active
      ? "border-l-emerald-500 bg-zinc-900 text-zinc-100"
      : "text-zinc-300 hover:bg-zinc-900/60 hover:text-zinc-50",
  );
}

export function sidebarNavIcon(active: boolean) {
  return cn(
    "mt-0.5 h-4 w-4 shrink-0 transition-colors duration-200",
    active ? "text-emerald-500" : "text-zinc-400 group-hover:text-zinc-300",
  );
}

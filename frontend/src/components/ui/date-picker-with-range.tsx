"use client";

import { useEffect, useRef, useState } from "react";
import { CalendarDays } from "lucide-react";

export type DateRangeValue = {
  from: string;
  to: string;
};

function formatRangeLabel(from: string, to: string): string {
  const fmt = new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short", year: "numeric" });
  return `${fmt.format(new Date(`${from}T12:00:00`))} - ${fmt.format(new Date(`${to}T12:00:00`))}`;
}

type DatePickerWithRangeProps = {
  value: DateRangeValue;
  onChange: (next: DateRangeValue) => void;
};

export function DatePickerWithRange({ value, onChange }: DatePickerWithRangeProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DateRangeValue>(value);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (ev: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(ev.target as Node)) {
        onChange(draft);
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open, draft, onChange]);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => {
          setDraft(value);
          setOpen((prev) => !prev);
        }}
        className="flex h-9 w-full items-center gap-2 rounded-md border bg-background px-3 text-sm hover:bg-muted/40"
        aria-expanded={open}
      >
        <CalendarDays className="size-4 text-muted-foreground" />
        <span className="truncate">{formatRangeLabel(value.from, value.to)}</span>
      </button>

      {open ? (
        <div className="absolute right-0 z-50 mt-2 w-full rounded-xl border bg-popover p-4 shadow-xl md:w-[22rem]">
          <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Rango de fechas</p>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">Inicio</span>
              <input
                type="date"
                value={draft.from}
                onChange={(e) => setDraft((prev) => ({ ...prev, from: e.target.value }))}
                className="h-9 w-full rounded-md border bg-background px-2 text-sm"
              />
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">Fin</span>
              <input
                type="date"
                value={draft.to}
                onChange={(e) => setDraft((prev) => ({ ...prev, to: e.target.value }))}
                className="h-9 w-full rounded-md border bg-background px-2 text-sm"
              />
            </label>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setDraft(value);
                setOpen(false);
              }}
              className="rounded-md border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/40"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => {
                onChange(draft);
                setOpen(false);
              }}
              className="rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs text-foreground hover:bg-primary/20"
            >
              Aplicar
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}


"use client";

import * as React from "react";

type SliderProps = {
  value: number[];
  min?: number;
  max?: number;
  step?: number;
  onValueChange?: (value: number[]) => void;
  disabled?: boolean;
  className?: string;
};

function joinClasses(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function Slider({
  value,
  min = -30,
  max = 30,
  step = 1,
  onValueChange,
  disabled = false,
  className,
}: SliderProps) {
  const current = Number.isFinite(value?.[0]) ? value[0] : 0;

  return (
    <input
      type="range"
      value={current}
      min={min}
      max={max}
      step={step}
      disabled={disabled}
      onChange={(e) => onValueChange?.([Number(e.target.value)])}
      className={joinClasses(
        "h-2 w-full cursor-pointer appearance-none rounded-lg bg-zinc-200 accent-[#2563eb] disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
    />
  );
}

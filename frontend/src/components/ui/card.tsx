"use client";

import * as React from "react";

type DivProps = React.HTMLAttributes<HTMLDivElement>;

function joinClasses(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function Card({ className, ...props }: DivProps) {
  return (
    <div
      className={joinClasses(
        "rounded-2xl border border-zinc-200 bg-white text-zinc-900 shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: DivProps) {
  return (
    <div
      className={joinClasses("flex flex-col space-y-1.5 p-6 pb-2", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: DivProps) {
  return (
    <div
      className={joinClasses("text-sm font-semibold leading-none tracking-tight", className)}
      {...props}
    />
  );
}

export function CardDescription({ className, ...props }: DivProps) {
  return <div className={joinClasses("text-xs text-zinc-500", className)} {...props} />;
}

export function CardContent({ className, ...props }: DivProps) {
  return <div className={joinClasses("p-6 pt-2", className)} {...props} />;
}

"use client";

import * as React from "react";

function joinClasses(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function Alert({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="alert"
      className={joinClasses("relative w-full rounded-lg border px-4 py-3 text-sm", className)}
      {...props}
    />
  );
}

export function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={joinClasses("text-sm leading-relaxed", className)} {...props} />;
}

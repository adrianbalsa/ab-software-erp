"use client";

import type { ReactNode } from "react";
import { useRole } from "@/hooks/useRole";
import type { AppRbacRole } from "@/lib/api";

type RoleGuardProps = {
  allowedRoles: AppRbacRole[];
  children: ReactNode;
  /** Si el rol no está permitido, no renderizar nada. */
  fallback?: ReactNode;
};

export function RoleGuard({
  allowedRoles,
  children,
  fallback = null,
}: RoleGuardProps) {
  const { role } = useRole();
  if (!allowedRoles.includes(role)) return <>{fallback}</>;
  return <>{children}</>;
}

"use client";

import React, { type ReactNode } from "react";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

type State = {
  hasError: boolean;
};

export class AppErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(): void {
    // Silence by design in UI; errors are captured by global monitoring.
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="dashboard-bento rounded-xl p-6 text-sm text-zinc-400" role="status" aria-live="polite">
            Este bloque no se pudo cargar. Recarga la página para reintentar.
          </div>
        )
      );
    }
    return this.props.children;
  }
}

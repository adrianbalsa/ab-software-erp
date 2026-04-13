"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const transition = { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] as const };

type Props = {
  children: ReactNode;
  className?: string;
  delay?: number;
};

/** Entrada suave alineada con la landing (fade + slide 10px). */
export function DashboardMotionFadeIn({ children, className, delay = 0 }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...transition, delay }}
      className={cn(className)}
    >
      {children}
    </motion.div>
  );
}

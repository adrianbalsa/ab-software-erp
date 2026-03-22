/**
 * Stress test k6: GET /health/status y GET /finance/dashboard
 *
 * Uso:
 *   API_BASE_URL=http://127.0.0.1:8000 K6_JWT='eyJ...' k6 run stress_test.js
 *
 * /finance/dashboard requiere JWT válido (Authorization: Bearer), igual que el frontend.
 */

import http from "k6/http";
import { check, sleep } from "k6";

const BASE = (__ENV.API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const JWT = (__ENV.K6_JWT || "").trim();

export const options = {
  vus: 50,
  duration: "30s",
  thresholds: {
    /** Ratio de peticiones fallidas (4xx/5xx o error de red). Objetivo: cercano a 0. */
    http_req_failed: ["rate<0.10"],
    /** Percentil 95 de latencia (todas las rutas del escenario). */
    http_req_duration: ["p(95)<5000"],
  },
};

export function setup() {
  if (!JWT) {
    console.warn(
      "[k6] K6_JWT no definido: /finance/dashboard devolverá 401 y subirá http_req_failed. " +
        "Obtén un token (p. ej. POST /auth/login) y exporta K6_JWT.",
    );
  }
}

export default function () {
  const healthRes = http.get(`${BASE}/health/status`, {
    headers: { Accept: "application/json" },
    tags: { name: "GET /health/status" },
    timeout: "10s",
  });
  check(healthRes, {
    "health/status 200": (r) => r.status === 200,
  });

  const financeRes = http.get(`${BASE}/finance/dashboard`, {
    headers: {
      Accept: "application/json",
      ...(JWT ? { Authorization: `Bearer ${JWT}` } : {}),
    },
    tags: { name: "GET /finance/dashboard" },
    timeout: "30s",
  });
  check(financeRes, {
    "finance/dashboard 200": (r) => r.status === 200,
  });

  sleep(0.05);
}

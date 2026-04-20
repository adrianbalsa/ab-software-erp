/**
 * Smoke E2E del portal cargador (bloque 4 roadmap / fase 8).
 *
 * Base URL (primera variable definida gana):
 * - `PLAYWRIGHT_TEST_BASE_URL`
 * - `PLAYWRIGHT_BASE_URL`
 * - por defecto `http://127.0.0.1:3000`
 *
 * Modo A — JWT (sin formulario de login):
 * - `E2E_PORTAL_CLIENTE_JWT`: JWT con claims de **cliente** y sesión portal.
 *   Mis portes → modal riesgo (si aplica) → Facturas.
 *
 * Modo B — credenciales (login real):
 * - `E2E_PORTAL_CLIENT_EMAIL` + `E2E_PORTAL_CLIENT_PASSWORD`
 *   Login → redirect `/portal-cliente/facturas` → riesgo (si aplica) → heading facturas.
 *
 * A11y (bloque 6): con JWT, además de flujos básicos, se validan nombres accesibles de tablas,
 * el botón “Actualizar”, el modal de riesgo (si bloquea), la vista **Sostenibilidad** (CSV,
 * `role="img"` CO₂, tabla de certificados) y un barrido **axe-core** sin violaciones
 * `critical` / `serious`. La pasada manual con VoiceOver (macOS) o NVDA (Windows) sigue siendo
 * la referencia para anuncios, orden de lectura y foco; checklist en `SCRATCHPAD.md` (portal bloque 6).
 *
 * Sin JWT ni pareja email/password los tests se omiten (`test.skip`) para CI/local en verde.
 *
 * Ejemplos:
 *   PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:3000 E2E_PORTAL_CLIENTE_JWT='eyJ...' npx playwright test tests/portal-cliente.spec.ts --project=chromium
 *   PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:3000 E2E_PORTAL_CLIENT_EMAIL=u@x.com E2E_PORTAL_CLIENT_PASSWORD=*** npx playwright test tests/portal-cliente.spec.ts --project=chromium
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const portalJwt = process.env.E2E_PORTAL_CLIENTE_JWT?.trim();
const portalEmail = process.env.E2E_PORTAL_CLIENT_EMAIL?.trim();
const portalPassword = process.env.E2E_PORTAL_CLIENT_PASSWORD;

async function dismissPortalRiskModalIfPresent(page: Page) {
  const dialog = page.getByRole("dialog");
  if (await dialog.isVisible().catch(() => false)) {
    await page.getByRole("checkbox").first().check();
    await page.getByRole("button", { name: /confirmar y continuar|confirm and continue/i }).click();
    await expect(dialog).toBeHidden({ timeout: 25_000 });
  }
}

function expectNoCriticalOrSeriousViolations(
  violations: { id: string; impact?: string | null; nodes?: unknown[] }[],
) {
  const bad = violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(
    bad,
    bad.length
      ? `axe: ${bad.map((v) => `${v.id} (${v.impact}, ${v.nodes?.length ?? 0} nodes)`).join("; ")}`
      : "",
  ).toEqual([]);
}

test.describe("Portal cliente — JWT", () => {
  /** Misma sesión API: si un test acepta el riesgo, el resto ya no verán el modal; el orden importa. */
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ page }) => {
    test.skip(!portalJwt, "Define E2E_PORTAL_CLIENTE_JWT para el flujo con JWT.");
    await page.addInitScript((token: string) => {
      try {
        window.localStorage.setItem("abl_auth_token", token);
      } catch {
        /* ignore */
      }
    }, portalJwt as string);
  });

  test("Modal riesgo — ARIA y foco inicial si bloquea el portal", async ({ page }) => {
    await page.goto("/portal-cliente/mis-portes");
    const dialog = page.getByRole("dialog");
    const dialogVisible = await dialog.isVisible().catch(() => false);
    test.skip(!dialogVisible, "Usuario ya aceptó riesgo o sin bloqueo: no hay modal que validar.");

    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(dialog).toHaveAttribute("aria-labelledby", "portal-risk-dialog-title");

    const checkbox = dialog.getByRole("checkbox").first();
    await expect(checkbox).toBeVisible({ timeout: 20_000 });
    await expect(dialog).toHaveAttribute("aria-describedby", "portal-risk-desc");
    await expect(checkbox).toBeFocused({ timeout: 5000 });

    await checkbox.check();
    await dialog.getByRole("button", { name: /confirmar y continuar|confirm and continue/i }).click();
    await expect(dialog).toBeHidden({ timeout: 25_000 });
  });

  test("Mis portes → aceptar riesgo si aplica → Facturas", async ({ page }) => {
    await page.goto("/portal-cliente/mis-portes");
    await expect(page).toHaveURL(/\/portal-cliente\/mis-portes/);

    await dismissPortalRiskModalIfPresent(page);

    await page.getByRole("link", { name: /facturas|invoices/i }).first().click();
    await expect(page).toHaveURL(/\/portal-cliente\/facturas/);
    await expect(page.getByRole("heading", { level: 1, name: /facturas|invoices/i })).toBeVisible();
  });

  test("Mis portes — tablas con nombre accesible (caption) y botón Actualizar", async ({ page }) => {
    await page.goto("/portal-cliente/mis-portes");
    await dismissPortalRiskModalIfPresent(page);

    await expect(
      page.getByRole("table", {
        name: /Portes activos asignados a su cuenta|Active shipments on your account/i,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("table", {
        name: /Entregas completadas y documentos descargables|Completed deliveries and downloadable documents/i,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: /Actualizar listas de portes activos e historial|Refresh active shipments and history/i,
      }),
    ).toBeVisible();
  });

  test("Sostenibilidad — encabezado, CSV, gráfico CO₂, tabla certificados; axe", async ({ page }) => {
    await page.goto("/portal-cliente/mis-portes");
    await dismissPortalRiskModalIfPresent(page);

    await page.getByRole("link", { name: /Sostenibilidad ESG|ESG sustainability/i }).first().click();
    await expect(page).toHaveURL(/\/portal-cliente\/sostenibilidad/);
    await expect(
      page.getByRole("heading", { level: 1, name: /Sostenibilidad ESG|ESG sustainability/i }),
    ).toBeVisible();

    await expect(
      page.getByRole("button", {
        name: /Descargar histórico ESG en formato CSV|Download YTD ESG history as CSV/i,
      }),
    ).toBeVisible();

    await expect(
      page
        .getByRole("img", {
          name: /Resumen de ahorro de CO₂ acumulado|Accumulated CO₂ savings summary/i,
        })
        .or(page.getByRole("status").filter({ hasText: /Cargando métricas|Loading metrics/i })),
    ).toBeVisible({ timeout: 25_000 });
    await expect(
      page.getByRole("img", {
        name: /Resumen de ahorro de CO₂ acumulado|Accumulated CO₂ savings summary/i,
      }),
    ).toBeVisible({ timeout: 25_000 });

    await expect(
      page.getByRole("table", {
        name: /Portes entregados con certificado ESG descargable|Delivered shipments with downloadable ESG certificate/i,
      }),
    ).toBeVisible();

    const portesCertBody = page.getByRole("status").filter({
      hasText:
        /Cargando portes|Loading shipments|No hay portes entregados todavía|No delivered shipments yet/i,
    });
    const pdfRowBtn = page.getByRole("button", {
      name: /Descargar certificado PDF para el porte|Download PDF certificate for shipment/i,
    });
    await expect(portesCertBody.or(pdfRowBtn).first()).toBeVisible({ timeout: 25_000 });

    const axe = await new AxeBuilder({ page }).analyze();
    expectNoCriticalOrSeriousViolations(axe.violations);
  });

  test("Facturas — listado vacío o tabla con caption; axe sin critical/serious", async ({ page }) => {
    await page.goto("/portal-cliente/mis-portes");
    await dismissPortalRiskModalIfPresent(page);
    await page.getByRole("link", { name: /facturas|invoices/i }).first().click();
    await expect(page).toHaveURL(/\/portal-cliente\/facturas/);
    await expect(page.getByRole("heading", { level: 1, name: /facturas|invoices/i })).toBeVisible();

    const table = page.getByRole("table", {
      name: /Facturas emitidas a su cuenta|Invoices issued to your account/i,
    });
    const emptyStatus = page.getByRole("status").filter({
      hasText: /No hay facturas emitidas|No invoices have been issued yet/i,
    });
    await expect(table.or(emptyStatus).first()).toBeVisible({ timeout: 25_000 });

    const axe = await new AxeBuilder({ page }).analyze();
    expectNoCriticalOrSeriousViolations(axe.violations);
  });

  test("Mis portes — axe sin critical/serious tras desbloquear", async ({ page }) => {
    await page.goto("/portal-cliente/mis-portes");
    await dismissPortalRiskModalIfPresent(page);
    const axe = await new AxeBuilder({ page }).analyze();
    expectNoCriticalOrSeriousViolations(axe.violations);
  });
});

test.describe("Portal cliente — login credenciales", () => {
  test("login → riesgo (si bloquea) → vista facturas", async ({ page }) => {
    test.skip(
      !portalEmail || !portalPassword,
      "Define E2E_PORTAL_CLIENT_EMAIL y E2E_PORTAL_CLIENT_PASSWORD para el flujo con login.",
    );

    test.setTimeout(90_000);

    await page.goto(
      `/login?redirect=${encodeURIComponent("/portal-cliente/facturas")}`,
    );

    await page.locator("#login-username").fill(portalEmail!);
    await page.locator("#login-password").fill(portalPassword!);
    await page.locator('form button[type="submit"]').click();

    await page.waitForLoadState("domcontentloaded");

    const dialog = page.getByRole("dialog");
    const dialogVisible = await dialog.isVisible({ timeout: 12_000 }).catch(() => false);

    if (dialogVisible) {
      const checkbox = dialog.getByRole("checkbox");
      await expect(checkbox).toBeVisible({ timeout: 10_000 });
      await checkbox.check();
      await dialog.getByRole("button", { name: /confirmar y continuar|confirm and continue/i }).click();
      await expect(dialog).toBeHidden({ timeout: 30_000 });
    }

    await expect(page).toHaveURL(/\/portal-cliente\/facturas/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { level: 1, name: /facturas|invoices/i })).toBeVisible({
      timeout: 20_000,
    });

    const axeFacturas = await new AxeBuilder({ page }).analyze();
    expectNoCriticalOrSeriousViolations(axeFacturas.violations);

    await page.getByRole("link", { name: /Sostenibilidad ESG|ESG sustainability/i }).first().click();
    await expect(page).toHaveURL(/\/portal-cliente\/sostenibilidad/);
    await expect(
      page.getByRole("heading", { level: 1, name: /Sostenibilidad ESG|ESG sustainability/i }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("table", {
        name: /Portes entregados con certificado ESG descargable|Delivered shipments with downloadable ESG certificate/i,
      }),
    ).toBeVisible();

    const axeSostenibilidad = await new AxeBuilder({ page }).analyze();
    expectNoCriticalOrSeriousViolations(axeSostenibilidad.violations);
  });
});

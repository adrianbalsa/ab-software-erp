import { expect, test, type Page } from "@playwright/test";

function collectRuntimeErrors(page: Page) {
  const errors: string[] = [];

  page.on("pageerror", (error) => {
    errors.push(error.message);
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });

  return errors;
}

async function isConfigGateVisible(page: Page) {
  return page
    .getByRole("heading", { name: /configuración pendiente/i })
    .isVisible({ timeout: 1000 })
    .catch(() => false);
}

test.describe("Next 16 / React 19 smoke", () => {
  test("renderiza shell de app y ruta con useSearchParams sin errores de runtime", async ({ page }) => {
    const errors = collectRuntimeErrors(page);

    await page.goto("/");
    if (await isConfigGateVisible(page)) {
      await expect(page.getByText(/Falta completar la configuración de Supabase/i)).toBeVisible();
      expect(errors).toEqual([]);
      return;
    }

    await expect(page.getByRole("heading", { name: /AB Logistics OS/i })).toBeVisible();
    await expect(page.getByLabel(/email|correo/i)).toBeVisible();
    await expect(page.getByLabel(/password|contraseña/i)).toBeVisible();

    await page.goto("/pricing?empresa_id=00000000-0000-0000-0000-000000000000");
    await expect(page.getByRole("heading", { level: 1, name: /Planes y cobro/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Contratar Basic/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Contratar Enterprise/i })).toBeVisible();

    expect(errors).toEqual([]);
  });

  test("mantiene rutas legales estáticas servidas por App Router", async ({ page }) => {
    const errors = collectRuntimeErrors(page);

    await page.goto("/aviso-legal");
    if (await isConfigGateVisible(page)) {
      await expect(page.getByText(/Falta completar la configuración de Supabase/i)).toBeVisible();
      expect(errors).toEqual([]);
      return;
    }

    await expect(page.getByRole("heading", { name: /aviso legal/i })).toBeVisible();

    await page.goto("/terminos");
    await expect(page.getByRole("heading", { name: /términos|terminos/i })).toBeVisible();

    expect(errors).toEqual([]);
  });
});

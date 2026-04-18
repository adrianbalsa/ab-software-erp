import { expect, test } from "@playwright/test";

test.describe("Flujo de Emision Fiscal (VeriFactu)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("Debe cargar la lista de facturas", async ({ page }) => {
    await page.goto("/facturas");

    const encabezadoFacturas = page
      .getByRole("heading")
      .filter({ hasText: /facturas/i })
      .first();

    await expect(encabezadoFacturas).toBeVisible();
  });

  test("Debe mostrar controles de VeriFactu para facturas pendientes", async ({ page }) => {
    await page.goto("/facturas");

    // Placeholder: aqui iria la preparacion de datos/mock para asegurar
    // que exista una factura con estado "pending".
    // Ejemplo futuro:
    // 1) Interceptar request de listado con page.route(...)
    // 2) Responder con una factura pending
    // 3) Buscar la fila por identificador y abrir sus acciones

    const botonEnviarAEAT = page.getByRole("button", {
      name: /enviar a aeat/i,
    });
    const botonGenerarHuella = page.getByRole("button", {
      name: /generar huella/i,
    });

    // Base skeleton: valida que al menos uno de los controles clave
    // de cumplimiento VeriFactu esta presente en el DOM.
    await expect(
      botonEnviarAEAT.or(botonGenerarHuella).first(),
    ).toBeVisible();
  });
});

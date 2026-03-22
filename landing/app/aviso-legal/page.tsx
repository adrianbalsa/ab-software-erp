import type { Metadata } from "next";
import { LegalShell } from "../legal/legal-shell";

export const metadata: Metadata = {
  title: "Aviso legal (LSSI) | AB Logistics OS",
  description:
    "Datos identificativos del titular del sitio y limitación de responsabilidad conforme a la Ley 34/2002 (LSSI-CE).",
};

export default function AvisoLegalPage() {
  return (
    <LegalShell title="Aviso legal" lastUpdated="22 de marzo de 2026">
      <p>
        En cumplimiento del artículo 10 de la Ley 34/2002, de 11 de julio, de Servicios de la Sociedad de la Información y
        Comercio Electrónico, se exponen los siguientes datos:
      </p>
      <ul>
        <li>
          <strong>Titular:</strong> Adrián Balsa Guerrero
        </li>
        <li>
          <strong>NIF/CIF:</strong> 35632451T
        </li>
        <li>
          <strong>Domicilio:</strong> A Coruña, Galicia, España
        </li>
        <li>
          <strong>Contacto:</strong>{" "}
          <a href="mailto:hola@ablogistics-os.com" className="text-indigo-600 underline hover:text-indigo-700">
            hola@ablogistics-os.com
          </a>
        </li>
      </ul>

      <h2>Propiedad intelectual</h2>
      <p>
        AB Logistics OS es una plataforma SaaS protegida por las leyes de propiedad intelectual. El código fuente, los
        algoritmos de cálculo de rentabilidad operativa (EBITDA), la estructura de la base de datos y los diseños
        gráficos son propiedad exclusiva de AB Software. Queda expresamente prohibida cualquier ingeniería inversa,
        copia o distribución sin consentimiento previo por escrito.
      </p>

      <h2>Limitación de responsabilidad</h2>
      <p>
        AB Logistics OS proporciona herramientas de cálculo basadas en los datos introducidos por el usuario. El titular
        no se hace responsable de decisiones empresariales derivadas de errores en la introducción de datos por parte del
        cliente o de interrupciones técnicas ajenas a su control. Para el marco contractual completo, consulte los{" "}
        <a href="/legal/terminos" className="text-indigo-600 underline hover:text-indigo-700">
          Términos y Condiciones
        </a>
        .
      </p>
    </LegalShell>
  );
}

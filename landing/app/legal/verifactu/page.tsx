import type { Metadata } from "next";
import { LegalShell } from "../legal-shell";

export const metadata: Metadata = {
  title: "Anexo de Cumplimiento VeriFactu | AB Logistics OS",
  description:
    "Declaración técnica sobre el cumplimiento del sistema de Factura Verificable (AEAT) en AB Logistics OS.",
};

export default function VerifactuPage() {
  return (
    <LegalShell title="Anexo de Cumplimiento VeriFactu (Factura Verificable)" lastUpdated="22 de marzo de 2026">
      <p>
        El presente anexo describe, con carácter <strong>declarativo y técnico</strong>, el enfoque de cumplimiento del
        software AB Logistics OS respecto del sistema de «Factura Verificable» y del registro de facturación de
        conformidad con la Ley 11/2021, de 9 de julio, de medidas de prevención y lucha contra el fraude fiscal, y la
        normativa de desarrollo que resulte aplicable en cada momento, incluidas las disposiciones reglamentarias y
        técnicas publicadas para su implantación (incluidas las referidas al ejercicio 2026 y sucesivas), así como las
        especificaciones técnicas que dicte la Agencia Estatal de Administración Tributaria (AEAT).
      </p>
      <p>
        Este documento complementa los Términos y Condiciones y la documentación del producto. No constituye por sí
        mismo certificación oficial de la AEAT ni sustituye las obligaciones propias del obligado tributario (el Cliente
        o su empresa), que debe asegurar el cumplimiento material de sus deberes de emisión, remisión y conservación
        conforme a la normativa fiscal.
      </p>

      <h2>1. Marco normativo de referencia</h2>
      <p>Sin ánimo exhaustivo, el diseño funcional del módulo fiscal de AB Logistics OS tiene en cuenta, entre otros:</p>
      <ul>
        <li>Ley 11/2021, de medidas de prevención y lucha contra el fraude fiscal.</li>
        <li>El Real Decreto que aprueba el Reglamento general de las acciones y los procedimientos de gestión e
          inspección tributaria y desarrolla la Ley 58/2003 General Tributaria, en la parte que resulte aplicable a la
          facturación y registros.</li>
        <li>
          Los desarrollos reglamentarios y órdenes ministeriales que establezcan requisitos del sistema informático de
          facturación, formatos, firma, remisión de registros y plazos de conservación.
        </li>
        <li>
          Las especificaciones técnicas, esquemas XML, códigos de validación, entornos de prueba y documentación
          publicados por la AEAT para la Factura Verificable y sistemas VERI*FACTU.
        </li>
      </ul>

      <h2>2. Declaración de principios técnicos</h2>
      <p>
        El Proveedor declara que el software AB Logistics OS incorpora, o se actualizará para incorporar, los
        mecanismos necesarios para generar y mantener los <strong>registros de facturación</strong> con las garantías de{" "}
        <strong>integridad, trazabilidad, accesibilidad, legibilidad, conservación e inalterabilidad</strong> exigidas por
        la normativa de factura verificable, incluyendo cuando proceda:
      </p>
      <ul>
        <li>
          <strong>Encadenamiento e integridad.</strong> Uso de mecanismos criptográficos (p. ej. funciones resumen / huella
          digital) que vinculen cada registro con el anterior de forma que cualquier modificación posterior quede
          detectable conforme a las especificaciones vigentes.
        </li>
        <li>
          <strong>Marca temporal y metadatos exigidos.</strong> Registro de los campos obligatorios y metadatos fiscales
          requeridos por la AEAT en la versión normativa aplicable.
        </li>
        <li>
          <strong>Inalterabilidad operativa.</strong> Una vez cumplidos los requisitos legales de alta o cierre de
          registros, el sistema impide la modificación encubierta de los datos sustantivos del registro, salvo las
          rectificaciones o anulaciones expresamente previstas por la normativa (incluidos los supuestos de facturas
          rectificativas o sustitutivas según proceda).
        </li>
        <li>
          <strong>Conservación.</strong> Conservación de los registros durante los plazos legales en formatos que
          permitan su presentación a la Administración tributaria y su legibilidad a lo largo del tiempo, con copias de
          seguridad alineadas con la política de continuidad del servicio.
        </li>
        <li>
          <strong>Remisión o puesta a disposición.</strong> Cuando la normativa exija envío telemático, suministro
          mediante API o sistemas de la AEAT, el Servicio se orientará a cumplir dichos canales técnicos en los plazos y
          formatos exigidos, sujeto a la disponibilidad de entornos de la Administración y a la correcta configuración por
          parte del Cliente (certificados, claves, datos censales, etc.).
        </li>
      </ul>

      <h2>3. Separación de roles y responsabilidad del Cliente</h2>
      <p>
        El cumplimiento efectivo ante la AEAT depende de la exactitud de los datos maestros (NIF-IVA, series, numeración,
        tipos impositivos, destinatarios, etc.) y de la correcta operación por usuarios autorizados. El Cliente es el
        único responsable de:
      </p>
      <ul>
        <li>La veracidad de los datos de facturación introducidos o importados.</li>
        <li>La adecuación de la política de numeración y series a su realidad mercantil y fiscal.</li>
        <li>La gestión de bajas, rectificaciones o sustituciones cuando la normativa lo exija.</li>
        <li>La custodia de evidencias complementarias exigidas por su asesor fiscal.</li>
      </ul>

      <h2>4. Evolución normativa y actualizaciones del producto</h2>
      <p>
        La normativa tecnica-fiscal y los esquemas de la AEAT pueden evolucionar. El Proveedor se compromete a
        <strong> actualizar el Servicio de forma razonable</strong> para adaptarse a cambios legales o técnicos
        obligatorios que afecten al funcionamiento del módulo de Factura Verificable, comunicando al Cliente, cuando sea
        posible, los cambios relevantes y los plazos de transición.
      </p>
      <p>
        No obstante, retrasos en la publicación de especificaciones finales, cambios de última hora en entornos de la
        AEAT o incidencias en sistemas de la Administración pueden afectar temporalmente a ciertas funcionalidades; ello
        se regirá por lo previsto en los Términos y Condiciones (limitación de responsabilidad y SLA).
      </p>

      <h2>5. Auditoría y cooperación</h2>
      <p>
        El Proveedor cooperará con el Cliente, en el marco del contrato de tratamiento de datos y de los límites de
        seguridad, facilitando la información razonablemente necesaria para apoyar auditorías internas o requerimientos de
        consultores fiscales del Cliente relacionados con el uso del módulo de facturación.
      </p>

      <h2>6. Contacto</h2>
      <p>
        Para solicitudes específicas sobre este anexo:{" "}
        <a href="mailto:hola@ablogistics-os.com" className="text-indigo-600 underline hover:text-indigo-700">
          hola@ablogistics-os.com
        </a>
        .
      </p>
    </LegalShell>
  );
}

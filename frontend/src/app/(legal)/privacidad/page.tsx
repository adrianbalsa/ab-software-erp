import type { Metadata } from "next";
import { LegalDocument } from "../_components/LegalDocument";

export const metadata: Metadata = {
  title: "Política de privacidad | AB Logistics OS",
  description: "Política de privacidad de AB Logistics OS conforme al RGPD y la LOPDGDD.",
};

export default function PrivacidadPage() {
  return (
    <LegalDocument
      title="Política de Privacidad"
      subtitle="Última actualización: 22 de abril de 2026. Tratamiento de datos personales conforme al RGPD y a la LOPDGDD."
    >
      <h2>1. Responsable del tratamiento</h2>
      <ul>
        <li>
          <strong>Responsable:</strong> [NOMBRE_EMPRESA]
        </li>
        <li>
          <strong>NIF/CIF:</strong> [NIF]
        </li>
        <li>
          <strong>Domicilio:</strong> [DIRECCIÓN]
        </li>
        <li>
          <strong>Correo de privacidad:</strong> [EMAIL_CONTACTO]
        </li>
      </ul>

      <h2>2. Ámbito y sujetos afectados</h2>
      <p>
        Esta política regula el tratamiento de datos personales realizado en el contexto de los servicios B2B
        de AB Logistics OS. Los datos tratados corresponden principalmente a representantes, personas de
        contacto, personas usuarias autorizadas y, en su caso, transportistas/autónomos cuando el cliente los
        incorpore en sus procesos operativos.
      </p>

      <h2>3. Finalidades y bases jurídicas del tratamiento</h2>
      <p>
        AB Logistics OS trata datos personales de representantes, empleados autorizados y usuarios de
        clientes empresariales para:
      </p>
      <ul>
        <li>
          Alta, gestión y mantenimiento de cuentas corporativas, autenticación y control de accesos.
        </li>
        <li>
          Ejecución de funcionalidades operativas y administrativas (flotas, rutas, expediciones, soporte y
          trazabilidad de actividad).
        </li>
        <li>
          Facturación, cobro, contabilidad y cumplimiento de obligaciones fiscales/mercantiles, incluyendo
          procesos de facturación electrónica y cumplimiento normativo aplicable.
        </li>
        <li>
          Cálculo y generación de indicadores ESG, incluida estimación de huella de carbono sobre la base de
          datos aportados por el cliente.
        </li>
        <li>
          Prevención de fraude, seguridad, monitorización técnica y continuidad del servicio.
        </li>
        <li>
          Gestión de comunicaciones contractuales, técnicas y de soporte con el cliente B2B.
        </li>
      </ul>
      <p>
        <strong>Bases legitimadoras:</strong> ejecución de contrato o medidas precontractuales (art. 6.1.b
        RGPD), cumplimiento de obligaciones legales (art. 6.1.c RGPD), interés legítimo en seguridad y
        prevención de abuso (art. 6.1.f RGPD), y consentimiento cuando proceda (art. 6.1.a RGPD).
      </p>

      <h2>4. Categorías de datos tratados</h2>
      <ul>
        <li>Datos identificativos y de contacto profesional.</li>
        <li>Datos de acceso, autenticación, trazabilidad y logs de actividad.</li>
        <li>Datos de flota, rutas, expediciones y operaciones, cuando incluyan referencias personales.</li>
        <li>Datos de facturación, fiscales, administrativos y de cumplimiento aportados por el cliente.</li>
        <li>Datos financieros y de cobro/pago estrictamente necesarios para la prestación del servicio.</li>
        <li>
          Datos ESG y de emisiones asociados a la actividad logística según parámetros facilitados por el
          cliente.
        </li>
      </ul>
      <p>
        AB Logistics OS no solicita deliberadamente categorías especiales de datos personales, salvo que
        resulte imprescindible por obligación legal y con garantías reforzadas.
      </p>

      <h2>5. Origen de los datos</h2>
      <p>
        Los datos proceden principalmente del propio cliente empresarial, de sus usuarios autorizados y de
        integraciones activadas voluntariamente por el cliente con terceros (entidades financieras, ERP,
        plataformas fiscales o proveedores tecnológicos).
      </p>

      <h2>6. Destinatarios, encargados y subencargados</h2>
      <p>
        Los datos podrán ser comunicados o resultar accesibles por terceros en la medida estrictamente
        necesaria para la prestación de los servicios:
      </p>
      <ul>
        <li>Proveedores de infraestructura cloud, alojamiento y seguridad.</li>
        <li>Pasarelas de pago y proveedores de cobro recurrente (por ejemplo, Stripe o GoCardless).</li>
        <li>Proveedores de servicios API, correo transaccional, monitorización y soporte.</li>
        <li>Entidades financieras o plataformas de banca conectada activadas por el cliente.</li>
        <li>Administraciones públicas y autoridades cuando exista obligación legal.</li>
      </ul>
      <p>
        Con los proveedores que actúan como encargados del tratamiento se suscriben los contratos exigidos
        por el art. 28 RGPD, incorporando garantías de confidencialidad, seguridad y uso limitado.
      </p>

      <h2>7. Transferencias internacionales</h2>
      <p>
        Cuando un proveedor se ubique fuera del Espacio Económico Europeo o implique transferencia
        internacional de datos, [NOMBRE_EMPRESA] aplicará mecanismos válidos conforme al RGPD (decisiones
        de adecuación, cláusulas contractuales tipo u otras garantías equivalentes).
      </p>

      <h2>8. Plazos de conservación</h2>
      <p>
        Los datos se conservarán durante la vigencia de la relación contractual y, finalizada esta, durante
        los plazos exigidos por normativa fiscal, mercantil, contable y de responsabilidad legal. Una vez
        vencidos dichos plazos, se suprimirán o anonimizarán de forma segura.
      </p>

      <h2>9. Derechos de las personas interesadas</h2>
      <p>
        Las personas interesadas pueden ejercer sus derechos de acceso, rectificación, supresión, oposición
        (ARCO), así como limitación del tratamiento y portabilidad, mediante solicitud escrita a
        [EMAIL_CONTACTO], acreditando su identidad y especificando el derecho ejercido.
      </p>
      <p>
        También pueden presentar reclamación ante la Agencia Española de Protección de Datos (AEPD) si
        consideran vulnerados sus derechos.
      </p>

      <h2>10. Seguridad de la información</h2>
      <p>
        [NOMBRE_EMPRESA] aplica medidas técnicas y organizativas adecuadas al riesgo, incluyendo controles
        de acceso, cifrado en tránsito cuando procede, registros de actividad, segmentación de entornos y
        políticas de gestión de incidencias. No obstante, no es posible garantizar seguridad absoluta frente
        a eventos externos imprevisibles o acciones maliciosas de terceros.
      </p>

      <h2>11. Exactitud de datos y responsabilidad del cliente B2B</h2>
      <p>
        El cliente garantiza que los datos facilitados son veraces, adecuados y actualizados, y que dispone
        de base legal suficiente para su cesión o tratamiento en AB Logistics OS. El cliente será
        responsable de cualquier daño o sanción derivada de datos inexactos, incompletos o tratados sin base
        legitimadora.
      </p>

      <h2>12. Rol de las partes y encargo de tratamiento</h2>
      <p>
        Con carácter general, el cliente empresarial actúa como responsable del tratamiento respecto de los
        datos personales incorporados a sus operaciones, y [NOMBRE_EMPRESA] actúa como encargado en la medida
        en que trate datos por cuenta de dicho cliente. Esta relación se regula mediante el correspondiente
        acuerdo de encargo de tratamiento.
      </p>

      <h2>13. Decisiones automatizadas y perfilado</h2>
      <p>
        AB Logistics OS puede aplicar reglas automáticas para cálculos operativos o ESG. Dichos procesos no
        implican, con carácter general, decisiones automatizadas con efectos jurídicos directos sobre
        personas físicas en los términos del art. 22 RGPD.
      </p>

      <h2>14. Cambios en la política de privacidad</h2>
      <p>
        [NOMBRE_EMPRESA] podrá actualizar esta política para adaptarla a cambios normativos, técnicos o de
        producto. La versión vigente será la publicada en esta página.
      </p>
    </LegalDocument>
  );
}

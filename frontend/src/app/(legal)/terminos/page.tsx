import type { Metadata } from "next";
import { LegalDocument } from "../_components/LegalDocument";

export const metadata: Metadata = {
  title: "Términos y Condiciones B2B | AB Logistics OS",
  description: "Condiciones contractuales de prestación del servicio SaaS AB Logistics OS.",
};

export default function TerminosPage() {
  return (
    <LegalDocument
      title="Términos y Condiciones del Servicio (B2B SaaS)"
      subtitle="Última actualización: 22 de abril de 2026. Este documento regula la contratación y uso de AB Logistics OS entre [NOMBRE_EMPRESA] y clientes empresariales."
    >
      <h2>1. Partes y objeto del contrato</h2>
      <p>
        Estos Términos y Condiciones (los &quot;Términos&quot;) regulan la prestación del servicio SaaS AB Logistics OS
        por [NOMBRE_EMPRESA], con NIF [NIF] y domicilio en [DIRECCIÓN], a favor de clientes profesionales o
        empresariales (el &quot;Cliente&quot;).
      </p>
      <p>
        El servicio comprende funcionalidades de gestión de flotas y operaciones logísticas, facturación
        certificada y cumplimiento fiscal (incluyendo integraciones vinculadas a VeriFactu), analítica ESG
        (incluyendo huella de carbono), facturación y conectividad con servicios de terceros.
      </p>

      <h2>2. Naturaleza B2B y aceptación</h2>
      <p>
        El servicio se ofrece exclusivamente a empresas y profesionales en el marco de su actividad
        económica. La contratación, activación o uso de la plataforma implica aceptación íntegra de estos
        Términos y de la documentación contractual complementaria.
      </p>
      <p>
        No se trata de un servicio orientado a consumidores finales ni resulta de aplicación la normativa de
        consumo en los términos legalmente previstos para relaciones B2C.
      </p>

      <h2>3. Licencia de uso</h2>
      <p>
        [NOMBRE_EMPRESA] concede al Cliente una licencia limitada, no exclusiva, no sublicenciable y no
        transferible para usar AB Logistics OS durante la vigencia contractual y según el plan contratado.
      </p>
      <p>La licencia no autoriza:</p>
      <ul>
        <li>Reventa, cesión o explotación comercial del software sin autorización escrita.</li>
        <li>Ingeniería inversa, descompilación o creación de obras derivadas.</li>
        <li>Uso para finalidades ilícitas o contrarias a normativa fiscal, mercantil o de protección de datos.</li>
      </ul>

      <h2>4. Alta, cuentas y seguridad</h2>
      <p>
        El Cliente designará usuarios autorizados, siendo responsable de su gestión interna, roles,
        confidencialidad de credenciales y uso diligente de la plataforma.
      </p>
      <p>
        Toda actividad realizada con credenciales válidas se presumirá efectuada por el Cliente, salvo
        prueba fehaciente en contrario.
      </p>

      <h2>5. Precios, facturación y suscripciones</h2>
      <p>
        AB Logistics OS se comercializa mediante suscripción recurrente conforme al plan contratado y su
        periodicidad de facturación.
      </p>
      <ul>
        <li>
          <strong>Plan Compliance:</strong> 39 EUR/mes (<strong>IVA no incluido</strong>).
        </li>
        <li>
          <strong>Plan Finance:</strong> 149 EUR/mes (<strong>IVA no incluido</strong>).
        </li>
        <li>
          <strong>Plan Enterprise:</strong> 399 EUR/mes (<strong>IVA no incluido</strong>).
        </li>
      </ul>
      <p>
        Los importes anteriores son precios de catálogo y podrán actualizarse por [NOMBRE_EMPRESA], sin
        efecto retroactivo sobre periodos ya facturados, con la antelación legal o contractual exigible.
      </p>
      <ul>
        <li>El IVA y otros tributos aplicables se repercutirán conforme a la normativa vigente.</li>
        <li>El cobro puede gestionarse a través de Stripe, GoCardless u otros proveedores autorizados.</li>
        <li>
          El Cliente autoriza cargos recurrentes según plan contratado y facilitará un método de pago
          válido y actualizado.
        </li>
      </ul>
      <p>
        El impago total o parcial habilita a [NOMBRE_EMPRESA] a suspender funcionalidades, limitar accesos o
        resolver el contrato, sin perjuicio de reclamar cantidades vencidas, intereses y costes de gestión.
      </p>

      <h2>6. Obligaciones del Cliente</h2>
      <p>El Cliente se obliga, entre otros extremos, a:</p>
      <ul>
        <li>Facilitar información veraz, completa, actualizada y legalmente obtenida.</li>
        <li>
          Verificar la exactitud de los datos fiscales y contables remitidos a VeriFactu o a cualquier
          integración administrativa.
        </li>
        <li>
          Revisar, validar y custodiar los documentos fiscales generados por la plataforma antes de su uso
          oficial o remisión a terceros.
        </li>
        <li>
          Cumplir normativa fiscal, mercantil, laboral, sectorial, ambiental y de protección de datos que le
          resulte aplicable.
        </li>
      </ul>
      <p>
        [NOMBRE_EMPRESA] no asume la responsabilidad por errores derivados de datos de entrada incorrectos,
        incompletos o extemporáneos proporcionados por el Cliente.
      </p>

      <h2>7. Integraciones de terceros y límites de responsabilidad</h2>
      <p>
        AB Logistics OS puede depender de servicios externos (APIs fiscales, proveedores cloud, banca
        conectada, pasarelas de pago, identidad digital, e-mail o mensajería). El Cliente acepta que:
      </p>
      <ul>
        <li>La disponibilidad del servicio puede verse afectada por incidencias de dichos terceros.</li>
        <li>
          Cambios técnicos o regulatorios en terceros pueden requerir ajustes, pausas o modificaciones de
          funcionalidades.
        </li>
        <li>
          [NOMBRE_EMPRESA] no garantiza continuidad ininterrumpida de integraciones fuera de su control
          razonable.
        </li>
      </ul>
      <p>
        En la máxima medida legalmente permitida, [NOMBRE_EMPRESA] excluye responsabilidad por daños
        indirectos, lucro cesante, pérdida de ingresos, pérdida de negocio, pérdida de datos no imputable a
        dolo o culpa grave y daños derivados de servicios de terceros.
      </p>
      <p>
        De forma expresa, [NOMBRE_EMPRESA] no será responsable de errores en cálculos, informes o resultados
        relacionados con VeriFactu, fiscalidad o huella de carbono cuando dichos errores deriven, total o
        parcialmente, de datos incompletos, inexactos, desactualizados o incorrectamente parametrizados por el
        Cliente o por terceros bajo su control.
      </p>
      <p>
        El Cliente reconoce su obligación de validar los resultados antes de su uso fiscal, contable,
        regulatorio o comercial frente a terceros o Administraciones.
      </p>

      <h2>8. SLA y soporte</h2>
      <p>
        [NOMBRE_EMPRESA] aplicará esfuerzos razonables para mantener niveles adecuados de disponibilidad y
        soporte técnico conforme al plan contratado y ventanas de mantenimiento comunicadas.
      </p>
      <p>
        Cualquier indicador de nivel de servicio (SLA) tendrá carácter objetivo de calidad y seguimiento,
        pero no implicará penalizaciones automáticas, indemnizaciones automáticas ni créditos de servicio
        salvo pacto expreso y por escrito en contrato específico firmado por ambas partes.
      </p>

      <h2>9. Limitación cuantitativa de responsabilidad</h2>
      <p>
        Salvo disposición imperativa en contrario, la responsabilidad total acumulada de [NOMBRE_EMPRESA] por
        cualquier reclamación relacionada con el servicio quedará limitada al importe efectivamente abonado por
        el Cliente en los doce (12) meses inmediatamente anteriores al hecho causante.
      </p>

      <h2>10. Propiedad intelectual y mejoras</h2>
      <p>
        Todos los derechos de propiedad intelectual e industrial sobre AB Logistics OS corresponden a
        [NOMBRE_EMPRESA] y/o sus licenciantes. El Cliente conserva titularidad sobre sus datos y contenidos.
      </p>
      <p>
        Las sugerencias de mejora remitidas por el Cliente podrán ser utilizadas por [NOMBRE_EMPRESA] para
        evolución del producto sin generar derechos económicos adicionales para el Cliente, salvo pacto
        expreso en contrario.
      </p>

      <h2>11. Protección de datos</h2>
      <p>
        Cuando [NOMBRE_EMPRESA] trate datos personales por cuenta del Cliente, ambas partes se someterán al
        correspondiente acuerdo de encargo de tratamiento (DPA) conforme al art. 28 RGPD. El Cliente actúa,
        con carácter general, como responsable del tratamiento respecto a los datos que introduce.
      </p>

      <h2>12. Confidencialidad</h2>
      <p>
        Cada parte se compromete a mantener confidencial la información técnica, comercial, financiera o de
        negocio de la otra parte, incluso tras la finalización del contrato, durante el plazo legal o
        contractual aplicable.
      </p>

      <h2>13. Duración, renovación y resolución</h2>
      <p>
        La duración será la establecida en el plan o contrato particular. Salvo indicación en contrario, los
        periodos se renovarán automáticamente por periodos equivalentes.
      </p>
      <p>
        Cualquiera de las partes podrá resolver por incumplimiento grave de la otra parte si no se subsana
        en el plazo razonable desde su notificación fehaciente.
      </p>

      <h2>14. Fuerza mayor</h2>
      <p>
        Ninguna parte responderá por incumplimientos debidos a causas de fuerza mayor, caso fortuito, actos
        de autoridad, ciberataques generalizados, caídas de infraestructuras críticas o interrupciones de
        terceros fuera de control razonable.
      </p>

      <h2>15. Modificaciones de los Términos</h2>
      <p>
        [NOMBRE_EMPRESA] podrá actualizar estos Términos por cambios legales, técnicos o de negocio. Las
        modificaciones no retroactivas se comunicarán con antelación razonable cuando sean sustanciales.
      </p>

      <h2>16. Ley aplicable y jurisdicción</h2>
      <p>
        Este contrato se rige por la legislación española. Para la resolución de cualquier controversia, las
        partes, con renuncia expresa a cualquier otro fuero que pudiera corresponderles, se someten a los
        Juzgados y Tribunales de la ciudad del domicilio social de [NOMBRE_EMPRESA].
      </p>

      <h2>17. Contacto legal</h2>
      <p>
        Para consultas legales o contractuales: [EMAIL_CONTACTO].
      </p>
    </LegalDocument>
  );
}

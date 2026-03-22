import type { Metadata } from "next";
import { LegalShell } from "../legal-shell";

export const metadata: Metadata = {
  title: "Términos y Condiciones | AB Logistics OS",
  description:
    "Condiciones generales de contratación y uso de AB Logistics OS: transporte, mapas, SLA y limitación de responsabilidad.",
};

export default function TerminosPage() {
  return (
    <LegalShell title="Términos y Condiciones de Uso y Contratación" lastUpdated="22 de marzo de 2026">
      <p>
        Los presentes Términos y Condiciones (en adelante, las «Condiciones») regulan el acceso y uso de la plataforma
        software como servicio (SaaS) «AB Logistics OS» (en adelante, el «Servicio»), prestado por Adrián Balsa Guerrero
        (en adelante, el «Proveedor»), con NIF 35632451T y domicilio en A Coruña (Galicia), España. El contacto
        contractual y de soporte es{" "}
        <a href="mailto:hola@ablogistics-os.com" className="text-indigo-600 underline hover:text-indigo-700">
          hola@ablogistics-os.com
        </a>
        .
      </p>
      <p>
        La contratación del Servicio implica la aceptación íntegra de estas Condiciones y, en su caso, de condiciones
        particulares o anexos comerciales suscritos por escrito. Si actúa en nombre de una empresa u organismo, declara
        tener facultades suficientes para obligar a dicha entidad.
      </p>

      <h2>1. Objeto y descripción del Servicio</h2>
      <p>
        El Servicio consiste en el acceso remoto, bajo modelo de suscripción o licencia, a un conjunto de funcionalidades
        de gestión empresarial orientadas al sector logístico y de transporte (entre otras: gestión de portes, flota,
        facturación, finanzas, sostenibilidad y cumplimiento fiscal conforme a la normativa aplicable en cada momento).
      </p>
      <p>
        El Proveedor presta una herramienta informática; el Cliente es el único responsable de la actividad empresarial
        que desarrolle, de la contratación de transporte con terceros y del cumplimiento de la normativa sectorial que le
        resulte aplicable (incluida, entre otras, la normativa de ordenación del transporte terrestre y las obligaciones
        laborales, mercantiles, tributarias y de seguridad social).
      </p>

      <h2>2. Transporte de mercancías y relación con terceros</h2>
      <p>
        AB Logistics OS no es transportista, comisionista de transporte ni intermediario obligacional en la cadena
        contractual del transporte salvo que existiera un acuerdo expreso distinto suscrito al margen de estas
        Condiciones.
      </p>
      <ul>
        <li>
          <strong>Independencia operativa.</strong> El Cliente es el único responsable de la organización del transporte,
          la elección de operadores, la formalización de contratos de transporte, la expedición de la documentación
          exigible (incluida, en su caso, documentación CMR u otra) y el cumplimiento de la legislación aplicable a la
          mercancía, pesos, dimensiones, ADR y normativa aduanera.
        </li>
        <li>
          <strong>Uso de datos en la plataforma.</strong> Los datos introducidos en el Servicio (rutas, tiempos,
          costes, documentos, etc.) tienen valor probatorio interno para la gestión del Cliente, sin perjuicio de que la
          validez jurídica frente a terceros dependa de la documentación oficial y de los sistemas de registro que
          correspondan en cada caso.
        </li>
        <li>
          <strong>Siniestros, retrasos y pérdidas.</strong> El Proveedor no responde por daños directos o indirectos
          derivados del transporte de mercancías (pérdida, avería, retraso, multas, penalizaciones contractuales,
          lucro cesante, etc.). Cualquier reclamación de esta naturaleza deberá dirigirse conforme a la relación
          contractual y normativa aplicable entre el Cliente y el transportista o tercero correspondiente.
        </li>
      </ul>

      <h2>3. Servicios de cartografía y Google Maps</h2>
      <p>
        Determinadas funcionalidades del Servicio pueden integrar o mostrar información geográfica basada en servicios
        de terceros, incluyendo, sin carácter limitativo, productos o datos de Google Maps Platform / Google LLC y/o otros
        proveedores de mapas y rutas.
      </p>
      <ul>
        <li>
          <strong>Limitación respecto del Proveedor.</strong> El Cliente reconoce que la disponibilidad, exactitud,
          actualización y continuidad de dichos servicios depende de terceros ajenos al Proveedor. En consecuencia, el
          Proveedor no garantiza que los mapas, geocodificaciones, tiempos estimados, distancias, restricciones de tráfico
          o sugerencias de ruta sean siempre exactos, completos o actualizados.
        </li>
        <li>
          <strong>Exclusión de responsabilidad.</strong> En la máxima medida permitida por la ley, el Proveedor queda
          exonerado de responsabilidad por decisiones operativas o económicas adoptadas con base en datos de mapas o
          rutas, así como por fallos, interrupciones, cambios de API, límites de cuota, errores de geolocalización o
          indisponibilidad temporal de la red o servicios del proveedor de mapas.
        </li>
        <li>
          <strong>Condiciones de terceros.</strong> El uso de determinadas integraciones puede estar sujeto a términos
          adicionales del proveedor de mapas o de otros integradores. El Cliente se compromete a cumplirlos cuando resulte
          obligatorio para el uso del Servicio.
        </li>
      </ul>

      <h2>4. Nivel de servicio y disponibilidad (SLA)</h2>
      <p>
        El Proveedor se compromete a desplegar esfuerzos razonables para mantener el Servicio operativo de forma
        continua, con arquitecturas y prácticas orientadas a la resiliencia, la seguridad y la recuperación ante
        incidentes.
      </p>
      <ul>
        <li>
          <strong>Objetivo orientativo.</strong> Salvo pacto comercial distinto, el objetivo de disponibilidad mensual
          del entorno productivo del Servicio es, a título orientativo, del noventa y ocho coma cinco por ciento (98,5%),
          excluidos los periodos de mantenimiento programado y las causas de exclusión indicadas a continuación.
        </li>
        <li>
          <strong>Mantenimiento.</strong> Podrán realizarse ventanas de mantenimiento programado, preferentemente en
          franjas de baja actividad, con preaviso razonable cuando sea posible. El mantenimiento de emergencia podrá
          ejecutarse sin preaviso cuando sea necesario para preservar la seguridad, integridad o continuidad del Servicio.
        </li>
        <li>
          <strong>Exclusiones.</strong> No computarán como incumplimiento del SLA, entre otros supuestos: (i) causas de
          fuerza mayor o caso fortuito; (ii) indisponibilidad derivada de proveedores de conectividad, DNS, CDN o
          infraestructura cloud; (iii) ataques de denegación de servicio o incidentes de seguridad ajenos al control
          razonable del Proveedor; (iv) suspensiones por impago o incumplimiento contractual del Cliente; (v) fallos
          originados en equipos, redes o software del Cliente; (vi) límites o suspensiones impuestas por terceros
          (incluidos integradores bancarios o administraciones públicas); (vii) uso del Servicio fuera de los parámetros
          documentados o con integraciones no soportadas.
        </li>
        <li>
          <strong>Remedio.</strong> Salvo acuerdo específico, la única compensación por incidencias de disponibilidad
          será la reprogramación o extensión del periodo de servicio o créditos proporcionales conforme a la política
          comercial vigente, sin que ello genere derecho automático a indemnización alguna.
        </li>
      </ul>

      <h2>5. Obligaciones del Cliente</h2>
      <p>El Cliente se obliga a:</p>
      <ul>
        <li>Utilizar el Servicio de conformidad con la ley, las buenas prácticas sectoriales y estas Condiciones.</li>
        <li>
          Mantener la confidencialidad de credenciales de acceso y adoptar medidas organizativas adecuadas (gestión de
          perfiles, MFA cuando esté disponible, revocación de accesos, etc.).
        </li>
        <li>
          Garantizar que los datos que incorpore (incluidos datos de empleados, conductores o terceros) se traten
          lícitamente y con bases jurídicas suficientes, informando y obteniendo consentimientos cuando proceda.
        </li>
        <li>
          No realizar ingeniería inversa, scraping abusivo, pruebas de carga no autorizadas ni intentos de eludir
          controles de seguridad o cuotas del Servicio.
        </li>
      </ul>

      <h2>6. Propiedad intelectual y licencia de uso</h2>
      <p>
        El Proveedor ostenta todos los derechos de propiedad intelectual e industrial sobre el Servicio, su código,
        diseño, documentación y contenidos propios. Se concede al Cliente una licencia no exclusiva, intransferible y
        revocable para usar el Servicio durante la vigencia contractual y según el plan contratado.
      </p>

      <h2>7. Limitación general de responsabilidad</h2>
      <p>
        En la máxima medida permitida por la legislación aplicable, la responsabilidad global del Proveedor frente al
        Cliente por cualquier concepto derivado o relacionado con el Servicio quedará limitada, en conjunto y por
        ejercicio anual, al importe abonado por el Cliente por el Servicio en los doce (12) meses anteriores al
        hecho causante, salvo en caso de dolo o culpa grave demostrable del Proveedor.
      </p>
      <p>
        Quedan excluidos, en cualquier caso, los daños indirectos, lucro cesante, pérdida de oportunidades de negocio,
        daño reputacional o pérdida de datos cuando su origen sea ajeno al incumplimiento grave del Proveedor o cuando
        el Cliente no haya mantenido copias de seguridad razonables fuera del Servicio.
      </p>

      <h2>8. Duración, suspensión y resolución</h2>
      <p>
        La relación contractual se mantendrá por el periodo contratado y sucesivas prórrogas según el plan elegido. El
        Proveedor podrá suspender temporalmente el acceso ante indicios razonables de uso ilícito, riesgo para la
        seguridad, impago o incumplimiento grave, previa comunicación cuando ello sea posible sin perjudicar la
        seguridad del sistema.
      </p>

      <h2>9. Ley aplicable y jurisdicción</h2>
      <p>
        Las presentes Condiciones se rigen por la legislación española. Para la resolución de controversias, las partes se
        someten a los juzgados y tribunales de A Coruña, salvo que la normativa de consumo imponga otro fuero
        imperativo.
      </p>

      <h2>10. Contacto</h2>
      <p>
        Para cualquier consulta sobre estas Condiciones:{" "}
        <a href="mailto:hola@ablogistics-os.com" className="text-indigo-600 underline hover:text-indigo-700">
          hola@ablogistics-os.com
        </a>
        .
      </p>
    </LegalShell>
  );
}

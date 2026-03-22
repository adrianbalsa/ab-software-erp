import type { Metadata } from "next";
import { LegalShell } from "../legal-shell";

export const metadata: Metadata = {
  title: "Política de Privacidad (RGPD) | AB Logistics OS",
  description:
    "Información sobre tratamiento de datos personales, geolocalización, telemetría y servicios bancarios PSD2 en AB Logistics OS.",
};

export default function PrivacidadLegalPage() {
  return (
    <LegalShell title="Política de Privacidad y Protección de Datos" lastUpdated="22 de marzo de 2026">
      <p>
        En AB Logistics OS tratamos los datos personales con transparencia y medidas técnicas y organizativas acordes a
        un entorno B2B y a clientes enterprise. El responsable del tratamiento de los datos recogidos a través del sitio
        web de aterrizaje y, en su caso, de la relación precontractual es Adrián Balsa Guerrero (NIF 35632451T), con
        domicilio en A Coruña (Galicia), España. Contacto:{" "}
        <a href="mailto:hola@ablogistics-os.com" className="text-indigo-600 underline hover:text-indigo-700">
          hola@ablogistics-os.com
        </a>
        .
      </p>
      <p>
        Cuando el Servicio se utiliza por cuenta de una empresa cliente, esta actúa habitualmente como{" "}
        <strong>Responsable del tratamiento</strong> respecto de los datos de su organización, empleados y terceros que
        incorpore a la plataforma; AB Logistics OS actúa como <strong>Encargado del tratamiento</strong> en los términos
        del artículo 28 del Reglamento (UE) 2016/679 («RGPD») y de la Ley Orgánica 3/2018, de 5 de diciembre, de
        Protección de Datos Personales y garantía de los derechos digitales («LOPDGDD»), salvo que para determinadas
        finalidades (p. ej. facturación del Proveedor al Cliente) el Proveedor sea Responsable —lo indicaremos de forma
        específica en cada supuesto.
      </p>

      <h2>1. Datos tratados y finalidades</h2>
      <p>Según las funcionalidades activadas, podrán tratarse, entre otros, las siguientes categorías de datos:</p>
      <ul>
        <li>
          <strong>Datos identificativos y de contacto profesional</strong> del representante o usuarios (nombre,
          apellidos, correo corporativo, teléfono, cargo).
        </li>
        <li>
          <strong>Datos de la cuenta y auditoría de acceso</strong> (identificadores de sesión, dirección IP, marcas de
          tiempo, tipo de dispositivo o navegador cuando se registren con fines de seguridad y trazabilidad).
        </li>
        <li>
          <strong>Datos operativos y de flota</strong>: vehículos, remolques, documentación administrativa (ITV, seguros,
          tacógrafo, etc.), planificación de portes y documentos asociados.
        </li>
        <li>
          <strong>Geolocalización y datos de localización</strong> relativos a rutas, puntos de carga/descarga,
          estimaciones de distancia o tiempos cuando el Cliente o los usuarios autorizados los registren o sincronicen
          con el Servicio. Pueden considerarse datos de carácter personal cuando permitan identificar directa o
          indirectamente a una persona física (por ejemplo, conductor asignado o patrones vinculados a un trabajador).
        </li>
        <li>
          <strong>Datos de conductores y personal</strong> necesarios para la gestión laboral o contractual que el
          Cliente configure (identificación, contacto, nóminas variables, dietas, etc.).
        </li>
        <li>
          <strong>Telemetría y datos técnicos del uso</strong> (logs de aplicación, métricas de rendimiento, errores),
          incluidos los necesarios para mantener la seguridad, prevenir fraude y mejorar la estabilidad del Servicio.
        </li>
        <li>
          <strong>Datos fiscales y de facturación</strong> introducidos por el Cliente para el cumplimiento de
          obligaciones contables y tributarias, incluido el régimen de factura verificable conforme a la normativa
          vigente.
        </li>
        <li>
          <strong>Imágenes y documentos</strong> (tickets, CMR, facturas de gasto) sometidos a procesos de digitalización
          u OCR cuando el Cliente utilice dichas funcionalidades.
        </li>
      </ul>
      <p>Las finalidades principales son:</p>
      <ul>
        <li>Ejecución del contrato de prestación del Servicio SaaS y soporte técnico.</li>
        <li>Cumplimiento de obligaciones legales aplicables al Proveedor y, en su caso, facilitación de evidencias ante
          requerimientos legítimos de autoridades.</li>
        <li>Seguridad de la información, continuidad del servicio y mejora legítima del producto (incluida analítica
          agregada o pseudonimizada cuando sea posible).</li>
        <li>Gestión de la relación comercial (facturación del Proveedor al Cliente, comunicaciones sobre el Servicio).</li>
      </ul>

      <h2>2. Base jurídica</h2>
      <p>Atendemos a las bases siguientes, según el caso:</p>
      <ul>
        <li><strong>Ejecución contractual</strong> (art. 6.1.b RGPD) para operar la plataforma y las funcionalidades
          contratadas.</li>
        <li><strong>Obligación legal</strong> (art. 6.1.c RGPD) en materia mercantil, fiscal, contable o de
          conservación documental.</li>
        <li>
          <strong>Interés legítimo</strong> (art. 6.1.f RGPD) en seguridad, prevención del abuso, mejora del producto y
          gestión de incidencias, equilibrado con los derechos del interesado.
        </li>
        <li>
          <strong>Consentimiento</strong> (art. 6.1.a RGPD) cuando sea requerido para finalidades concretas (p. ej.
          ciertas comunicaciones comerciales no necesarias para el contrato, o cookies no estrictamente necesarias, según
          la Política de Cookies).
        </li>
      </ul>
      <p>
        Respecto de datos de empleados o conductores introducidos por el Cliente, corresponde al Cliente, en su condición
        de Responsable, establecer la base jurídica adecuada (contrato de trabajo, obligación legal, interés legítimo,
        etc.) e informar a los interesados conforme a la normativa laboral y de protección de datos.
      </p>

      <h2>3. Datos especialmente protegidos</h2>
      <p>
        El Servicio no está concebido para el tratamiento sistemático de categorías especiales de datos del artículo 9
        del RGPD (salvo que el Cliente los introduzca por su cuenta de forma accesoria y lícita). Si prevé tratamiento de
        datos de salud, biométricos para identificación única u otros especialmente sensibles, deberá evaluar la base
        jurídica, la minimización y, en su caso, realizar una evaluación de impacto y consultar a su asesor legal y, si
        procede, al Delegado de Protección de Datos.
      </p>

      <h2>4. Servicios bancarios y PSD2 (GoCardless / Nordigen u otros proveedores)</h2>
      <p>
        Las funcionalidades de agregación o sincronización de información financiera pueden integrarse mediante
        proveedores autorizados en el marco de la Directiva (UE) 2015/2366 («PSD2») y su transposición al ordenamiento
        español, tales como entidades de pago o proveedores de servicios de información sobre cuentas (AISP) homologados.
      </p>
      <ul>
        <li>
          <strong>No almacenamiento de credenciales bancarias.</strong> AB Logistics OS{" "}
          <strong>no almacena ni gestiona contraseñas de acceso a la banca en línea ni OTP</strong> del usuario para
          conectar cuentas. La autenticación fuerte y el consentimiento frente a la entidad de pago o banco suelen
          canalizarse a través del proveedor regulado (p. ej. flujos de GoCardless Bank Account Data —antes Nordigen— u
          otros integradores compatibles), conforme a sus propias políticas y a la normativa PSD2.
        </li>
        <li>
          <strong>Datos tratados.</strong> Tras la autorización del usuario, pueden obtenerse metadatos y movimientos
          necesarios para la conciliación o visualización en el Servicio, con arreglo a la finalidad y minimización
          aplicables.
        </li>
        <li>
          <strong>Responsabilidades.</strong> El Cliente debe asegurarse de que los usuarios que conecten cuentas tienen
          facultades para otorgar el consentimiento requerido y de que el uso cumple las políticas del banco y del
          proveedor de agregación.
        </li>
      </ul>

      <h2>5. Encargados y transferencias internacionales</h2>
      <p>
        Podemos recurrir a subencargados para hosting, infraestructura cloud, bases de datos gestionadas, correo
        transaccional, monitorización o soporte, formalizando acuerdos de tratamiento (DPA) y garantías adecuadas (cláusulas
        tipo aprobadas, decisiones de adecuación u otras garantías del capítulo V del RGPD) cuando el tratamiento
        implique acceso desde países terceros.
      </p>

      <h2>6. Plazos de conservación</h2>
      <ul>
        <li>
          <strong>Datos del Servicio del Cliente:</strong> mientras se mantenga la relación contractual y los plazos
          adicionales necesarios para resolver incidencias, reclamaciones o requerimientos legales.
        </li>
        <li>
          <strong>Registros de facturación e información fiscal:</strong> conservación conforme a la Ley 58/2003 General
          Tributaria y normativa de desarrollo (a título orientativo, como mínimo, los plazos legales de prescripción y
          revisión aplicables), sin perjuicio de lo específico en materia de factura verificable.
        </li>
        <li>
          <strong>Logs de seguridad:</strong> periodos proporcionados a la finalidad de detección de incidentes y
          cumplimiento de obligaciones de trazabilidad.
        </li>
      </ul>

      <h2>7. Derechos de las personas interesadas</h2>
      <p>
        Los interesados pueden ejercer los derechos de acceso, rectificación, supresión, limitación, oposición y
        portabilidad cuando proceda, así como retirar el consentimiento en su caso, dirigiendo solicitud a{" "}
        <a href="mailto:hola@ablogistics-os.com" className="text-indigo-600 underline hover:text-indigo-700">
          hola@ablogistics-os.com
        </a>
        , acompañando copia de documento identificativo en los términos legales. Podrá presentar reclamación ante la
        Agencia Española de Protección de Datos (
        <a href="https://www.aepd.es" className="text-indigo-600 underline hover:text-indigo-700" target="_blank" rel="noopener noreferrer">
          www.aepd.es
        </a>
        ).
      </p>
      <p>
        Cuando el Cliente sea Responsable de datos de sus empleados o conductores, las solicitudes de ejercicio de
        derechos sobre dichos datos podrán canalizarse a través del Cliente como canal principal; el Proveedor cooperará
        razonablemente según el artículo 28 del RGPD.
      </p>

      <h2>8. Seguridad</h2>
      <p>
        Aplicamos medidas técnicas y organizativas apropiadas al riesgo, incluyendo cifrado en tránsito, controles de
        acceso por roles, segregación de entornos y copias de seguridad, sin perjuicio de que la seguridad absoluta no
        existe y el Cliente debe mantener buenas prácticas en sus organizaciones.
      </p>

      <h2>9. Actualizaciones</h2>
      <p>
        Esta política puede actualizarse para reflejar cambios normativos o del Servicio. La versión vigente se publicará
        en esta ruta con su fecha de actualización.
      </p>
    </LegalShell>
  );
}

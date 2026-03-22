import type { Metadata } from "next";
import { LegalShell } from "../legal-shell";

export const metadata: Metadata = {
  title: "Política de Cookies | AB Logistics OS",
  description:
    "Información sobre cookies y tecnologías similares utilizadas en AB Logistics OS y el sitio público.",
};

export default function CookiesLegalPage() {
  return (
    <LegalShell title="Política de Cookies" lastUpdated="22 de marzo de 2026">
      <p>
        En cumplimiento de la Ley 34/2002, de 11 de julio, de Servicios de la Sociedad de la Información y de Comercio
        Electrónico (LSSI), del Reglamento (UE) 2016/679 (RGPD), de la Ley Orgánica 3/2018 (LOPDGDD) y de la Directiva
        2002/58/CE (como modificada por la Directiva 2009/136/CE y el marco ePrivacy en trámite de adaptación), le
        informamos sobre el uso de almacenamiento y tecnologías similares en el sitio web público y, en su caso, en el
        acceso al entorno de aplicación (dashboard) de AB Logistics OS.
      </p>

      <h2>1. ¿Qué son las cookies?</h2>
      <p>
        Las cookies son pequeños archivos que se almacenan en su terminal (ordenador, tablet o smartphone) cuando visita
        un sitio web. Las tecnologías similares incluyen almacenamiento local, píxeles de seguimiento o identificadores
        en el navegador. A efectos de esta política, nos referiremos a todas ellas como «cookies».
      </p>

      <h2>2. Tipos de cookies que pueden utilizarse</h2>
      <h3>2.1. Cookies técnicas o estrictamente necesarias</h3>
      <p>
        Permiten la navegación y el uso de funciones esenciales (gestión de sesión, equilibrio de carga, seguridad,
        recordatorio de preferencias de idioma cuando aplique). Están exentas de consentimiento previo cuando cumplen
        los criterios del artículo 22.2 de la LSSI y las orientaciones de la Agencia Española de Protección de Datos.
      </p>
      <ul>
        <li>
          <strong>Cookies de sesión y autenticación:</strong> mantienen la sesión del usuario autenticado en el dashboard
          y protegen el acceso a áreas restringidas.
        </li>
        <li>
          <strong>Cookies de seguridad:</strong> ayudan a mitigar ataques (p. ej. protección CSRF en formularios) y a
          preservar la integridad de la sesión.
        </li>
        <li>
          <strong>Preferencias funcionales:</strong> almacenan elecciones estrictamente necesarias para el funcionamiento
          (p. ej. cookies de consentimiento cuando la herramienta lo requiera para no volver a mostrar el banner de
          forma repetitiva).
        </li>
      </ul>

      <h3>2.2. Cookies de análisis o medición</h3>
      <p>
        Si en el futuro se incorporaran herramientas de analítica que no se consideren estrictamente necesarias, se
        solicitará su consentimiento previo y se informará de la entidad responsable, la duración y la finalidad. En la
        configuración actual orientada a minimización de datos, priorizamos analítica agregada o el uso de métricas propias
        del servidor cuando sea posible.
      </p>

      <h3>2.3. Cookies de terceros vinculadas a pagos o integraciones</h3>
      <p>
        Cuando el Cliente utilice funcionalidades de pago o integraciones externas, el tercero correspondiente puede
        establecer cookies propias sujetas a su política:
      </p>
      <ul>
        <li>
          <strong>Stripe (u otros pasarelas de pago):</strong> cookies técnicas y de seguridad/fraud prevention
          necesarias para completar transacciones de suscripción o cobro conforme a sus estándares PCI-DSS y políticas
          publicadas.
        </li>
        <li>
          <strong>Proveedores de mapas o OCR:</strong> pueden emplear identificadores técnicos o cookies temporales
          asociados a la carga de scripts o al procesamiento de documentos, según el proveedor y la configuración
          implementada en cada versión del Servicio.
        </li>
      </ul>

      <h2>3. Finalidad y base jurídica</h2>
      <ul>
        <li>
          <strong>Cookies necesarias:</strong> interés legítimo y/o ejecución del contrato (uso del Servicio) y
          habilitación segura del sitio.
        </li>
        <li>
          <strong>Cookies no esenciales</strong> (si se activan): consentimiento del usuario, gestionable mediante el
          mecanismo de configuración o banner cuando esté disponible.
        </li>
      </ul>

      <h2>4. Plazo de conservación</h2>
      <p>
        Las cookies de sesión caducan al cerrar el navegador o tras un periodo de inactividad definido por el sistema.
        Otras cookies persistentes tienen una duración limitada según su finalidad (p. ej. mantener preferencias de
        consentimiento durante meses concretos). Puede obtener el detalle actualizado en el panel de preferencias de
        cookies cuando esté implementado en el sitio.
      </p>

      <h2>5. Cómo gestionar o eliminar cookies</h2>
      <p>
        Puede configurar su navegador para rechazar o eliminar cookies. Los enlaces de los principales navegadores suelen
        estar disponibles en sus páginas de ayuda. Tenga en cuenta que bloquear cookies técnicas puede impedir el inicio de
        sesión o el funcionamiento correcto del dashboard.
      </p>

      <h2>6. Actualizaciones</h2>
      <p>
        Esta política se revisará cuando cambien las tecnologías empleadas o la normativa aplicable. La fecha de última
        actualización figura al inicio del documento.
      </p>

      <h2>7. Contacto</h2>
      <p>
        Para cualquier consulta sobre esta política:{" "}
        <a href="mailto:hola@ablogistics-os.com" className="text-indigo-600 underline hover:text-indigo-700">
          hola@ablogistics-os.com
        </a>
        .
      </p>
    </LegalShell>
  );
}

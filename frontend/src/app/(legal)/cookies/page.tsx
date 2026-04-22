import type { Metadata } from "next";
import { LegalDocument } from "../_components/LegalDocument";

export const metadata: Metadata = {
  title: "Política de cookies | AB Logistics OS",
  description: "Información sobre el uso de cookies en AB Logistics OS.",
};

export default function CookiesPage() {
  return (
    <LegalDocument
      title="Política de Cookies"
      subtitle="Última actualización: 22 de abril de 2026. Esta política explica el uso de cookies y tecnologías similares en AB Logistics OS."
    >
      <h2>1. ¿Qué son las cookies?</h2>
      <p>
        Las cookies son archivos o dispositivos que se descargan en el terminal del usuario al acceder a
        una página web o aplicación, y que permiten almacenar y recuperar información sobre la navegación,
        sesión o configuración.
      </p>

      <h2>2. Responsable</h2>
      <p>
        El responsable del sitio y de la gestión de cookies propias es [NOMBRE_EMPRESA], con NIF [NIF] y
        domicilio en [DIRECCIÓN]. Contacto: [EMAIL_CONTACTO].
      </p>

      <h2>3. Tipos de cookies utilizadas</h2>
      <h3>3.1 Cookies técnicas o estrictamente necesarias</h3>
      <p>
        Son imprescindibles para el funcionamiento de AB Logistics OS y no requieren consentimiento previo
        conforme a la normativa aplicable. Incluyen, entre otras:
      </p>
      <ul>
        <li>
          Cookies o tokens de sesión/autenticación para mantener sesión iniciada y validar JWT de acceso.
        </li>
        <li>Cookies de seguridad para prevención de fraude, control de carga y protección de formularios.</li>
        <li>Cookies de balanceo, persistencia de sesión y continuidad de navegación.</li>
        <li>Cookies técnicas de consentimiento para recordar preferencias sobre cookies.</li>
      </ul>
      <p>
        Estas cookies son necesarias para prestar el servicio solicitado por el usuario y/o cliente
        empresarial.
      </p>

      <h3>3.2 Cookies de preferencias</h3>
      <p>
        Permiten recordar opciones del usuario (idioma, visualización o preferencias de interfaz). Se
        utilizan para mejorar la experiencia y pueden requerir consentimiento cuando no sean estrictamente
        necesarias.
      </p>

      <h3>3.3 Cookies analíticas</h3>
      <p>
        Permiten medir el uso de la plataforma (páginas visitadas, rendimiento, eventos de interacción y
        métricas agregadas) para mejorar estabilidad y usabilidad del servicio. Se activan únicamente con
        consentimiento cuando así exija la normativa.
      </p>

      <h2>4. Cookies de terceros</h2>
      <p>
        AB Logistics OS puede utilizar servicios de terceros para analítica, monitorización, seguridad o
        integraciones técnicas. Dichos terceros pueden instalar sus propias cookies bajo sus políticas de
        privacidad y cookies. [NOMBRE_EMPRESA] no controla de manera plena los tratamientos efectuados por
        dichos terceros.
      </p>
      <p>
        La base legitimadora y condiciones de dichas cookies dependerá del proveedor tercero y de la
        configuración activada por el cliente o usuario.
      </p>

      <h2>5. Base jurídica</h2>
      <ul>
        <li>
          <strong>Cookies técnicas:</strong> interés legítimo y necesidad técnica para prestar el servicio
          solicitado.
        </li>
        <li>
          <strong>Cookies analíticas y de preferencias no esenciales:</strong> consentimiento del usuario.
        </li>
      </ul>

      <h2>6. Gestión del consentimiento</h2>
      <p>
        El usuario puede aceptar, rechazar o configurar el uso de cookies no esenciales mediante el panel
        de configuración habilitado por AB Logistics OS. El consentimiento puede retirarse en cualquier
        momento sin afectar a la licitud del tratamiento previo.
      </p>

      <h2>7. Desactivación desde el navegador</h2>
      <p>
        El usuario puede permitir, bloquear o eliminar cookies desde la configuración de su navegador.
        Tenga en cuenta que el bloqueo de cookies técnicas puede impedir el correcto funcionamiento de la
        plataforma, especialmente en procesos de autenticación y seguridad de sesión.
      </p>

      <h2>8. Plazo de conservación</h2>
      <p>
        Las cookies se conservan durante el tiempo mínimo necesario para su finalidad y, en su caso, hasta
        que el usuario las elimine o retire su consentimiento. Los plazos concretos pueden variar según tipo
        de cookie y proveedor.
      </p>

      <h2>9. Actualizaciones de esta política</h2>
      <p>
        [NOMBRE_EMPRESA] podrá actualizar esta Política de Cookies para reflejar cambios normativos,
        técnicos o de proveedores. Se recomienda revisar periódicamente esta página.
      </p>

      <h2>10. Contacto</h2>
      <p>
        Para cualquier consulta sobre cookies o privacidad puede contactar en [EMAIL_CONTACTO].
      </p>
    </LegalDocument>
  );
}

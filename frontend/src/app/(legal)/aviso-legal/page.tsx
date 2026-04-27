import type { Metadata } from "next";
import { LegalDocument } from "../_components/LegalDocument";

export const metadata: Metadata = {
  title: "Aviso legal | AB Logistics OS",
  description: "Información legal y condiciones de uso del sitio web y plataforma AB Logistics OS.",
};

export default function AvisoLegalPage() {
  return (
    <LegalDocument
      title="Aviso Legal"
      subtitle="Última actualización: 22 de abril de 2026. Este aviso regula el acceso y uso del sitio web y plataforma AB Logistics OS conforme a la LSSI-CE y normativa concordante."
    >
      <h2>1. Identificación del titular</h2>
      <p>
        En cumplimiento del artículo 10 de la Ley 34/2002, de 11 de julio, de Servicios de la Sociedad de
        la Información y de Comercio Electrónico (LSSI-CE), se informa de los siguientes datos:
      </p>
      <ul>
        <li>
          <strong>Denominación social:</strong> [NOMBRE_EMPRESA]
        </li>
        <li>
          <strong>NIF/CIF:</strong> [NIF]
        </li>
        <li>
          <strong>Domicilio social:</strong> [DIRECCIÓN]
        </li>
        <li>
          <strong>Correo de contacto:</strong> [EMAIL_CONTACTO]
        </li>
      </ul>
      <p>
        AB Logistics OS es una plataforma tecnológica de uso profesional orientada a la gestión operativa,
        documental y financiera en el sector logístico empresarial.
      </p>

      <h2>2. Objeto y ámbito</h2>
      <p>
        El presente Aviso Legal regula el acceso, navegación y uso del sitio web corporativo, de las áreas
        privadas y de los servicios digitales de AB Logistics OS (en adelante, la &quot;Plataforma&quot;), sin
        perjuicio de las condiciones contractuales específicas aplicables a clientes de pago.
      </p>
      <p>
        El acceso o uso del sitio implica la aceptación plena y sin reservas del presente Aviso Legal. Si la
        persona usuaria no está de acuerdo, deberá abstenerse de utilizar el sitio y/o la Plataforma.
      </p>

      <h2>3. Condiciones de acceso y uso</h2>
      <p>
        La persona usuaria se compromete a utilizar el sitio y la Plataforma de conformidad con la ley, la
        buena fe, el orden público y las presentes condiciones, absteniéndose de causar perjuicio a
        [NOMBRE_EMPRESA] o a terceros.
      </p>
      <p>Queda expresamente prohibido:</p>
      <ul>
        <li>Introducir malware, scripts maliciosos o cualquier software nocivo.</li>
        <li>Realizar ingeniería inversa, descompilación o extracción no autorizada.</li>
        <li>Intentar acceder a áreas restringidas sin autorización.</li>
        <li>Alterar, destruir o suprimir medidas de seguridad o protección técnica.</li>
        <li>Usar credenciales de terceros o compartir accesos de forma no permitida.</li>
        <li>Utilizar la Plataforma para fines ilícitos, fraudulentos o sancionables.</li>
      </ul>

      <h2>4. Propiedad intelectual e industrial</h2>
      <p>
        Todos los contenidos, software, diseños, marcas, nombres comerciales, documentación, estructuras de
        datos, interfaces y elementos gráficos de AB Logistics OS son titularidad de [NOMBRE_EMPRESA] o de
        terceros licenciantes, y se encuentran protegidos por la normativa de propiedad intelectual e
        industrial.
      </p>
      <p>
        No se cede ningún derecho de explotación más allá del uso estrictamente necesario para la navegación
        y, en su caso, para la ejecución de servicios contratados. Cualquier reproducción, distribución,
        comunicación pública, transformación, extracción o reutilización requiere autorización previa y
        escrita.
      </p>

      <h2>5. Enlaces externos y servicios de terceros</h2>
      <p>
        AB Logistics OS puede incorporar enlaces y/o integraciones con servicios de terceros (p. ej.
        infraestructura cloud, pasarelas de pago, banca conectada, servicios de identidad, analítica o APIs
        fiscales). Tales servicios se rigen por sus propios términos, políticas y niveles de servicio.
      </p>
      <p>
        [NOMBRE_EMPRESA] no controla de forma continuada ni asume responsabilidad por la disponibilidad,
        continuidad, seguridad, legalidad, exactitud o funcionamiento de servicios de terceros, incluyendo
        incidencias, interrupciones, retrasos, modificaciones de API o pérdidas de información atribuibles a
        dichos terceros.
      </p>

      <h2>6. Exclusión de garantías</h2>
      <p>
        El sitio y la Plataforma se ofrecen &quot;tal cual&quot; y según disponibilidad, dentro de los límites legales.
        [NOMBRE_EMPRESA] no garantiza:
      </p>
      <ul>
        <li>Disponibilidad ininterrumpida, ausencia total de errores o invulnerabilidad absoluta.</li>
        <li>La compatibilidad universal con todos los navegadores, sistemas o infraestructuras.</li>
        <li>La inexistencia de interrupciones por mantenimiento, fuerza mayor o terceros.</li>
        <li>La adecuación a fines particulares no pactados de forma expresa y por escrito.</li>
      </ul>

      <h2>7. Limitación de responsabilidad</h2>
      <p>
        En la máxima medida permitida por la ley, [NOMBRE_EMPRESA] no será responsable por daños indirectos,
        lucro cesante, pérdida de ingresos, pérdida de oportunidad, daño reputacional o pérdida de datos
        derivados del uso del sitio y/o la Plataforma, especialmente cuando tengan causa en:
      </p>
      <ul>
        <li>Errores u omisiones en la información facilitada por clientes o terceros.</li>
        <li>Uso indebido de credenciales, accesos no autorizados o negligencia del cliente.</li>
        <li>Interrupciones de servicios de terceros (APIs, pasarelas, cloud, telecomunicaciones).</li>
        <li>Actuaciones de autoridades administrativas o cambios normativos sobrevenidos.</li>
        <li>Decisiones empresariales tomadas por el cliente basadas en datos no verificados.</li>
      </ul>
      <p>
        La responsabilidad máxima agregada de [NOMBRE_EMPRESA], salvo disposición imperativa en contrario, no
        excederá de las cantidades efectivamente abonadas por el cliente por el servicio en los doce (12)
        meses anteriores al hecho causante.
      </p>
      <p>
        Lo anterior no limita responsabilidades no excluibles por ley en supuestos de dolo o culpa grave.
      </p>

      <h2>8. Seguridad</h2>
      <p>
        [NOMBRE_EMPRESA] aplica medidas técnicas y organizativas razonables para proteger sistemas e
        información. Sin embargo, ninguna medida de seguridad es absolutamente infalible en entornos de red
        abiertos.
      </p>

      <h2>9. Notificación de incidencias</h2>
      <p>
        Cualquier incidencia técnica o de seguridad podrá comunicarse a [EMAIL_CONTACTO]. [NOMBRE_EMPRESA]
        actuará conforme a sus procedimientos internos y a la normativa aplicable.
      </p>

      <h2>10. Nulidad parcial</h2>
      <p>
        Si alguna cláusula de este Aviso fuese declarada nula o inaplicable, no afectará a la validez del
        resto del documento, que conservará plena eficacia.
      </p>

      <h2>11. Modificaciones</h2>
      <p>
        [NOMBRE_EMPRESA] podrá modificar este Aviso Legal para adaptarlo a novedades legislativas,
        regulatorias, técnicas o de negocio. La versión publicada en cada momento será la vigente desde su
        fecha de publicación.
      </p>

      <h2>12. Derecho aplicable y jurisdicción</h2>
      <p>
        Este Aviso Legal se rige por la legislación española. Para cualquier controversia derivada del acceso
        o uso del sitio, las partes se someten a los Juzgados y Tribunales de [CIUDAD_EMPRESA], salvo norma
        imperativa en contrario.
      </p>
    </LegalDocument>
  );
}

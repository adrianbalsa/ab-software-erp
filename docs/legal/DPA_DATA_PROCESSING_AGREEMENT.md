# DATA PROCESSING AGREEMENT (DPA) — RGPD (ES)

**Versión:** 1.0  
**Fecha:** 25/03/2026  
**Jurisdicción:** España (Ley aplicable: RGPD y normativa española complementaria)

> Este documento está redactado para contratos SaaS B2B y describe compromisos típicos exigibles en el RGPD. Antes de su firma, se recomienda revisión por asesoría legal de las partes para adaptarlo al caso concreto.

## 1. Partes y definiciones (RGPD)
Este Data Processing Agreement (“**DPA**”) se celebra entre:

1. **AB Logistics OS** (“**Encargado del Tratamiento**” o “**Proveedor**”), que presta el servicio SaaS; y
2. El **Cliente** (“**Responsable del Tratamiento**”), que utiliza la Plataforma para sus finalidades propias.

Las partes acuerdan que las definiciones del RGPD serán de aplicación (p. ej., Responsable del Tratamiento, Encargado del Tratamiento, Datos Personales, Subencargado, Violación de la Seguridad de los Datos, etc.).

## 2. Objeto
El objeto del DPA es regular el tratamiento de Datos Personales realizado por el Encargado por cuenta del Responsable, cuando el Responsable utilice la Plataforma para gestionar información operativa y/o de sus conductores, clientes y procesos relacionados.

El presente DPA se incorpora y complementa las condiciones contractuales del servicio SaaS.

## 3. Duración
El tratamiento de Datos Personales tendrá lugar durante la vigencia del contrato SaaS. Al finalizar el contrato, se aplicarán las cláusulas de borrado/retorno establecidas en la Sección 9.

## 4. Categorías de datos y sujetos
En función de la configuración del Cliente y de los módulos contratados, podrán tratarse (categorías no exhaustivas):
- Datos de administración y acceso (usuarios/roles del Cliente).
- Datos operativos de logística (portes, estados, POD/firma cuando proceda).
- Datos de conciliación y facturación vinculados a la actividad del Cliente.
- Datos personales de conductores/partes necesarias para operar y generar documentación.

Los sujetos incluyen (categorías no exhaustivas):
- Conductores.
- Contactos operativos del Cliente.
- Titulares o personal de clientes/receptores vinculados a las operaciones del Cliente.

## 5. Instrucciones documentadas del Responsable
El Encargado tratará los Datos Personales únicamente conforme a:
- las instrucciones documentadas del Responsable; y
- el contrato SaaS y su documentación funcional.

En particular, el Responsable determina:
- la finalidad de tratamiento;
- la naturaleza de los Datos del Cliente que introduce o gestiona;
- el alcance de módulos y funcionalidades que activa.

Salvo instrucción del Responsable o exigencia legal, el Encargado no tratará los Datos Personales para finalidades propias.

## 6. Medidas de seguridad (art. 32 RGPD)
El Encargado aplica medidas técnicas y organizativas adecuadas al riesgo, que incluyen, en términos generales:
- **Control de acceso** y separación de identidades;
- **Aislamiento multi-tenant** mediante mecanismos a nivel de base de datos (RLS) para limitar acceso entre empresas;
- **Cifrado** y protección de secretos en capa app;
- **Rate limiting** y mitigación de abusos para reducir superficie de ataque;
- **Registro de auditoría** y trazabilidad operativa conforme a la arquitectura del sistema;
- **Copias de seguridad** y procedimientos de restauración;
- Hardening de infraestructura (dockerización, proxy inverso, cabeceras de seguridad).

El Encargado revisará y actualizará dichas medidas de forma continuada.

## 7. Confidencialidad (art. 28 y 29 RGPD)
El Encargado se compromete a que las personas autorizadas para tratar los Datos Personales:
- estén sujetas a obligación de confidencialidad;
- reciban formación adecuada;
- traten los Datos Personales solo según lo permitido.

## 8. Subencargados (art. 28.2 RGPD)
El Encargado podrá contratar **Subencargados** para prestar componentes de infraestructura y/o servicios auxiliares necesarios para el funcionamiento del SaaS.

A efectos de este DPA, el Encargado declara que podrán utilizarse, de forma no exhaustiva:
- Proveedores de infraestructura/servicios de base de datos y hosting compatibles con el tratamiento de Datos Personales (p. ej., infraestructura europea y/o entornos compatibles con RGPD).
- Proveedores de mapas y APIs relacionadas (p. ej., Google Cloud) cuando el Cliente active funcionalidades de cartografía/ubicación.
- Servicios de APIs de inteligencia artificial (p. ej., OpenAI) cuando el Cliente active funcionalidades que requieran IA.

El Encargado mantendrá, con sus Subencargados, condiciones contractuales que garanticen, como mínimo, el cumplimiento de las obligaciones del RGPD.

Cuando resulte exigible, el Encargado notificará al Responsable de cambios relevantes en los Subencargados o facilitará información actualizada.

## 9. Borrado/retorno y portabilidad (art. 28 y obligaciones al finalizar)
Al finalizar el contrato SaaS, y tras las solicitudes del Responsable conforme al régimen contractual y legal:
1. el Encargado permitirá **portabilidad/exportación** de los Datos del Cliente en el formato razonable disponible;
2. el Encargado realizará el **borrado** o devolución de los Datos Personales según proceda.

## 9.1. Plazos de borrado
Salvo obligación legal de conservación (incluyendo conservación impuesta por autoridad competente o normativa imperativa), el Encargado procurará que el borrado se realice en un plazo normalmente no superior a **30 días** desde la rescisión o desde la solicitud validada del Responsable, lo que sea posterior.

En relación con copias de seguridad, la eliminación puede quedar sujeta a ciclos de retención técnica, aplicándose medidas de salvaguarda para impedir usos posteriores.

## 10. Notificación de violaciones de seguridad (art. 33 y 34 RGPD)
El Encargado informará al Responsable sobre cualquier Violación de la Seguridad de los Datos Personales de la que tenga conocimiento, sin demora indebida y, en todo caso, dentro de los plazos exigidos por el RGPD, aportando información razonable para la evaluación y notificación a la autoridad de control y, cuando proceda, a los interesados.

## 11. Asistencia al Responsable (art. 28.3 e)
El Encargado prestará asistencia razonable para:
- responder a solicitudes de los interesados;
- realizar evaluaciones de impacto (EIPD/DPIA) si aplica;
- gestionar auditorías o revisiones de seguridad cuando el contrato lo contemple.

La asistencia se proporcionará con medidas razonables y, si hay costes adicionales, conforme a lo acordado contractualmente.

## 12. Auditorías y verificación
El Encargado pondrá a disposición del Responsable la documentación razonable que permita acreditar el cumplimiento de las obligaciones aplicables.

Si el Responsable requiere una auditoría presencial o inspección, las partes acuerdan que se realizará:
- con antelación razonable,
- sin interrumpir indebidamente la operación,
- y bajo confidencialidad.

## 13. Datos del Encargado (subprocesos y trazabilidad)
El Encargado podrá conservar información técnica y registros de operación necesaria para:
- seguridad,
- continuidad operativa,
- cumplimiento de obligaciones de mantenimiento y soporte.

## 14. Responsabilidad y limitación
La responsabilidad del Encargado y su limitación se regirán por el contrato SaaS principal y por la normativa imperativa aplicable.

## 15. Derecho aplicable y jurisdicción
Este DPA se rige por la legislación española y el RGPD. Salvo pacto en contrario, las controversias se someterán a los tribunales competentes conforme al contrato SaaS del que forma parte este DPA.

## 16. Firmas
Por el Encargado (AB Logistics OS): _______________________

Por el Responsable (Cliente): _____________________________

Fecha: ____ / ____ / ______


# POLÍTICA DE PRIVACIDAD (RGPD) — AB Logistics OS

**Versión:** 1.0  
**Última actualización:** 25/03/2026  
**Jurisdicción:** España

## 1. Rol de las Partes (RGPD)
AB Logistics OS actúa como **Encargado del Tratamiento** (“**Encargado**”) de los datos personales tratados en el marco de la prestación del servicio.

El Cliente actúa como **Responsable del Tratamiento** (“**Responsable**”) respecto de los datos personales que introduce, configura y utiliza en la Plataforma.

Esta Política se formula conforme a lo dispuesto en el Reglamento (UE) 2016/679 (“**RGPD**”) y en la normativa española aplicable (incluyendo, en su caso, la Ley Orgánica 3/2018 y normativa complementaria).

## 2. Datos tratados
En el contexto del servicio pueden tratarse, en la medida en que el Cliente los facilite o active, categorías de datos tales como:
- Datos de acceso y administración de usuarios del Cliente.
- Datos operativos y de logística generados por la actividad del Cliente (p. ej., información de portes, flota y estados operativos).
- Datos de facturación y registros vinculados a procesos documentales (incluyendo documentación técnica asociada a la trazabilidad VeriFactu, cuando proceda).
- Datos de conciliación bancaria y movimientos operativos (cuando el Cliente utilice integraciones y módulos correspondientes).
- Datos de contacto y documentación asociada a los usuarios/partes implicadas (conductores, clientes, receptores), en la medida en que el Cliente los gestione.

## 3. Finalidades del tratamiento
AB Logistics OS trata los datos personales únicamente para:
- Proporcionar la Plataforma y sus funcionalidades contratadas.
- Gestionar autenticación, autorización y seguridad (incluyendo aislamiento multi-tenant mediante RLS, control de accesos y prevención de abusos).
- Operar el sistema de auditoría técnica y registros de acceso necesarios para la seguridad y el cumplimiento operativo.
- Realizar copias de seguridad, monitoreo y mantenimiento técnico.
- Atender incidencias y soporte técnico (incluyendo soporte operativo y diagnóstico).

## 4. Instrucciones del Cliente
El tratamiento realizado por AB Logistics OS se efectúa **exclusivamente** conforme a las instrucciones documentadas del Cliente y a las obligaciones que el Cliente deba cumplir como Responsable del Tratamiento.

## 5. Subencargados (Subprocessors)
AB Logistics OS puede emplear subencargados para la provisión de infraestructura y servicios auxiliares, incluyendo de manera **genérica**:
- Infraestructura cloud europea utilizada por el entorno de backend/BD (p. ej., Hetzner o proveedores equivalentes) y servicios de base de datos compatibles con Supabase.
- Proveedores de mapas y geocodificación/estimación de rutas (p. ej., Google Cloud).
- Servicios de APIs de inteligencia artificial y procesamiento de texto (p. ej., OpenAI), cuando el Cliente active funciones que requieran dichos servicios.

Cuando resulte aplicable conforme al RGPD y el contrato entre las partes, la lista completa o las categorías de subencargados se facilitarán al Cliente bajo solicitud y/o mediante el mecanismo previsto contractualmente. Además, se publica un inventario técnico actualizable en **`GET /api/v1/public/compliance`** (campo `subprocessors`, sin autenticación), descrito en `docs/legal/COMPLIANCE_AND_SECURITY_POSTURE.md`.

## 6. Seguridad del tratamiento
AB Logistics OS aplica medidas técnicas y organizativas adecuadas para mitigar riesgos, incluyendo (a modo informativo):
- Aislamiento multi-tenant mediante políticas de seguridad a nivel de base de datos.
- Control de acceso y limitación de velocidad de peticiones (rate limiting) para reducir riesgos de abuso.
- Cifrado y protección de secretos en capa de aplicación conforme a la arquitectura del sistema.
- Gestión de copias de seguridad y almacenamiento de backups.

## 7. Portabilidad y borrado (rescisión del contrato)
Al rescindir la relación contractual, el Cliente podrá solicitar la **portabilidad** de sus datos conforme a la normativa aplicable y a las capacidades técnicas de exportación disponibles.

Asimismo, AB Logistics OS garantiza que, tras la rescisión y sujeto a obligaciones legales imperativas (p. ej., conservación por exigencias reglamentarias o judiciales), los datos serán:
- Eliminados de los sistemas en producción y de los entornos controlados.
- Eliminados de los backups **en los plazos legales aplicables**, así como en los plazos operativos razonables acordados.

En todo caso, el borrado se realizará sin demora indebida, y en un plazo normalmente **no superior a 30 días** desde la rescisión, salvo que la normativa exija un plazo mayor o existan retenciones obligatorias.

## 8. Derechos de los interesados
El ejercicio de los derechos de los interesados (acceso, rectificación, supresión, limitación, oposición y portabilidad) se canaliza a través del Responsable del Tratamiento. AB Logistics OS asistirá al Cliente en la atención de dichos derechos, dentro de sus posibilidades técnicas y con costes que se ajustarán conforme al contrato.

## 9. Transferencias internacionales
Las transferencias internacionales se gestionarán conforme al RGPD, en particular mediante la base jurídica aplicable y mecanismos autorizados (p. ej., decisiones de adecuación o garantías apropiadas), de acuerdo con la ubicación y políticas de los subencargados utilizados.

## 10. Contacto
Para cuestiones de privacidad y solicitudes relacionadas con el tratamiento de datos, el Cliente podrá contactar con AB Logistics OS mediante el canal que se indique contractualmente o a través del contacto corporativo del Encargado.


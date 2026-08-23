# Hito 3: Consulta del contexto desde Telegram

**Fecha:** 23 de agosto de 2026  
**Estado:** Completado  
**Versión:** 0.1.0  

## Objetivo

Permitir que el Agente Orquestador consulte la información almacenada en SQLite y muestre un resumen mediante el comando `/contexto` de Telegram.

El objetivo de este hito es comprobar que el agente puede utilizar el contexto persistente antes de incorporar un modelo de lenguaje o mecanismos de decisión más avanzados.

## Situación inicial

Al comenzar este hito, el sistema ya disponía de:

- Entrada y salida mediante Telegram.
- Normalización con `IncomingMessage` y `OutgoingMessage`.
- Base de datos SQLite.
- Registro de proyectos.
- Gestión de sesiones.
- Persistencia de mensajes.
- Sincronización de documentos Markdown.
- Sincronización del historial Git.

Toda esta información estaba almacenada, pero todavía no existía un servicio unificado para consultarla.

## Servicio de consulta del contexto

Se creó `ContextQueryService`, encargado de recopilar un resumen del contexto del proyecto.

El servicio obtiene:

- Nombre del proyecto.
- Número total de sesiones.
- Número de sesiones activas.
- Número total de mensajes.
- Número de documentos almacenados.
- Número de commits almacenados.
- Documentos modificados recientemente.
- Commits más recientes.

La consulta se realiza directamente sobre la base de datos SQLite.

## Modelos incorporados

Se añadieron modelos específicos para representar el resultado de la consulta:

- `ContextSummary`
- `ContextDocumentSummary`
- `ContextCommitSummary`

Estos modelos separan la información almacenada de la forma concreta en la que se muestra posteriormente.

## Integración con el orquestador

El `Orchestrator` recibe ahora una instancia de `ContextQueryService`.

Cuando recibe un mensaje de tipo comando con el contenido:

```text
/contexto
# Hito 4: Búsqueda de contexto relevante

**Fecha:** 23 de agosto de 2026  
**Estado:** Completado  
**Versión:** 0.1.0  

## Objetivo

Permitir que el Agente Orquestador encuentre información relacionada con una consulta dentro de su almacén SQLite.

La información recuperada procede de:

- Documentos Markdown sincronizados.
- Conversaciones anteriores.
- Mensajes enviados por el usuario.

Este hito prepara el contexto que posteriormente se entregará a un modelo de lenguaje.

## Búsqueda de documentos

Se creó `ContextSearchService`, encargado de buscar documentos relacionados con una consulta.

El proceso realiza las siguientes operaciones:

1. Normaliza la consulta.
2. Convierte el texto a minúsculas.
3. Elimina los acentos para realizar comparaciones.
4. Extrae términos significativos.
5. Descarta palabras comunes.
6. Busca coincidencias en el título, la ruta y el contenido.
7. Calcula una puntuación.
8. Ordena los documentos por relevancia.

## Puntuación de documentos

La puntuación inicial es deliberadamente sencilla y explicable:

- Coincidencia en el título: 5 puntos.
- Coincidencia en la ruta: 3 puntos.
- Coincidencia en el contenido: 1 punto.

Esto permite conocer por qué un documento ha sido seleccionado.

## Modelos de búsqueda documental

Se añadieron los modelos:

- `ContextDocumentMatch`
- `ContextSearchResult`

Cada coincidencia incluye:

- Identificador del documento.
- Ruta relativa.
- Título.
- Puntuación.
- Términos encontrados.
- Extracto del contenido.

## Prueba con documentos reales

Se realizó la consulta:

```text
¿Cómo integramos Telegram?
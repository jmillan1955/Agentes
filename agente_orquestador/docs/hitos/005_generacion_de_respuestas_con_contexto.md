# Hito 5: Generación de respuestas con contexto

**Fecha:** 24 de agosto de 2026  
**Proyecto:** Agente Orquestador  
**Versión:** 0.1.0  
**Estado:** Completado  

## 1. Objetivo

Conectar el Agente Orquestador con un modelo de lenguaje ejecutado localmente mediante Ollama.

El agente debe ser capaz de:

- Recibir una pregunta desde Telegram.
- Recuperar información relevante del contexto SQLite.
- Construir una petición combinando contexto y pregunta.
- Consultar un modelo de lenguaje local.
- Devolver la respuesta mediante Telegram.
- Indicar el modelo utilizado.
- Mostrar el tiempo empleado en generar la respuesta.
- Guardar la pregunta, la respuesta y sus metadatos en SQLite.

## 2. Flujo implementado

El recorrido completo de una pregunta de texto es:

```text
Telegram
→ IncomingMessage
→ Orchestrator
→ ContextBuilder
→ ContextSearchService
→ PromptBuilder
→ ResponseGenerationService
→ OllamaProvider
→ OutgoingMessage
→ Telegram
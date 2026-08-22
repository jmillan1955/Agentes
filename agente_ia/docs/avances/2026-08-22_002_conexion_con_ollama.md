# Avance 002 — Conexión con Ollama

**Fecha:** 22/08/2026
**Hora:** 09:48:19 Hora de verano romance
**Componente:** Conexi?n con Ollama
**Estado:** Completado correctamente

## Objetivo

Crear la primera versi?n funcional del Agente IA, capaz de recibir peticiones desde la consola y responder mediante Qwen3 4B ejecutado localmente con Ollama.

## Archivos creados o modificados

- config.py
- main.py
- app/models.py
- app/orchestrator.py
- providers/base.py
- providers/__init__.py
- providers/ollama_provider.py
- tests/test_orchestrator.py
- requirements.txt
- pytest.ini

## Pruebas realizadas

- Comprobaci?n del acceso a la API de Ollama.
- Consulta directa al modelo qwen3:4b.
- Ejecuci?n interactiva mediante python main.py.
- Generaci?n de una respuesta estructurada en JSON.
- Medici?n del tiempo completo de ejecuci?n.
- Comprobaci?n del comando /salir.

## Resultado

Completado correctamente

## Detalles

El Agente IA recibe peticiones escritas desde la consola, las env?a al endpoint /api/chat de Ollama y devuelve una respuesta estructurada con los campos respuesta y tiempo_ejecuci?n_segundos. El tiempo observado ha sido satisfactorio. Algunas respuestas pueden resultar vagas, por lo que los prompts y par?metros del modelo se ajustar?n en fases posteriores.

## Problemas pendientes

- Mejorar la precisi?n de algunas respuestas.
- Ajustar el prompt de sistema.
- Definir l?mites de longitud seg?n el tipo de petici?n.

## Próximo paso

Crear el registro central de herramientas para que el orquestador pueda decidir entre responder directamente o ejecutar una capacidad especializada.

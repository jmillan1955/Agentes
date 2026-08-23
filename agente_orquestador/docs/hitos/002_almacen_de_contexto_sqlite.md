# Hito 2: Almacén de contexto SQLite

**Fecha:** 23/08/2026  
**Proyecto:** Agente Orquestador  
**Versión:** 0.1.0  
**Estado:** Completado

## 1. Objetivo

Construir un almacén de contexto persistente para el Agente Orquestador utilizando SQLite.

El almacén debe conservar:

- Los proyectos conocidos.
- Las sesiones de trabajo.
- Los mensajes recibidos.
- Las respuestas generadas.
- La última versión de los documentos Markdown.
- Los metadatos del historial de Git.

El contexto debe seguir disponible después de detener o reiniciar el agente.

## 2. Principios de diseño

SQLite actúa como almacén local consultable.

Git continúa siendo la fuente de verdad para:

- Código.
- Documentación publicada.
- Historial completo de modificaciones.
- Recuperación de versiones anteriores.

SQLite no sustituye a Git. Guarda una representación del contexto preparada para que el orquestador pueda consultarla posteriormente.

El archivo SQLite no se publica en GitHub porque puede contener conversaciones y datos propios de cada instalación.

## 3. Ubicación de la base

En Windows:

```text
C:\Python_Proyectos\Agentes\agente_orquestador\data\context.db
```

Ruta relativa configurada:

```dotenv
CONTEXT_DATABASE_PATH=data/context.db
```

En una futura instalación Ubuntu, la misma ruta relativa generará una base propia dentro de la carpeta del proyecto.

## 4. Exclusión de Git

Se creó:

```text
agente_orquestador/data/.gitignore
```

Contenido:

```gitignore
# No publicar el contexto local
*

# Conservar este archivo
!.gitignore
```

Esto excluye:

```text
context.db
context.db-shm
context.db-wal
```

La comprobación se realiza con:

```powershell
git check-ignore -v .\data\context.db
git status --short -- .\data
```

`context.db` no debe aparecer como archivo pendiente de Git.

## 5. Configuración

Variables incorporadas:

```dotenv
CONTEXT_DATABASE_PATH=data/context.db
PROJECT_NAME=Agente Orquestador
GIT_REPOSITORY=https://github.com/jmillan1955/Agentes.git
```

`config.py` convierte la ruta relativa de la base en una ruta absoluta basada en la carpeta de `agente_orquestador`.

La raíz del proyecto se obtiene automáticamente desde la ubicación de `config.py`.

## 6. Componentes creados

```text
app/context/
├── __init__.py
├── database.py
├── schema.py
├── models.py
├── project_repository.py
├── session_repository.py
├── message_repository.py
├── document_repository.py
├── document_synchronizer.py
├── git_commit_repository.py
└── git_commit_synchronizer.py
```

Pruebas:

```text
tests/
├── test_context_database.py
├── test_project_repository.py
├── test_session_repository.py
├── test_message_repository.py
├── test_document_repository.py
├── test_document_synchronizer.py
├── test_git_commit_repository.py
└── test_git_commit_synchronizer.py
```

## 7. Inicialización de SQLite

`ContextDatabase` es responsable de:

- Crear la carpeta de datos cuando sea necesario.
- Abrir la conexión SQLite.
- Activar claves foráneas.
- Configurar un tiempo de espera para bloqueos.
- Activar el modo WAL para bases almacenadas en disco.
- Crear el esquema de forma idempotente.
- Cerrar correctamente la conexión.

Configuraciones aplicadas:

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA journal_mode = WAL;
```

El esquema utiliza:

```sql
PRAGMA user_version;
```

La versión actual del esquema es:

```text
2
```

## 8. Tablas

### projects

Registra los proyectos conocidos.

Campos principales:

```text
id
name
root_path
git_repository
active
created_at
updated_at
```

El primer proyecto almacenado es:

```text
ID: 1
Nombre: Agente Orquestador
Ruta: C:\Python_Proyectos\Agentes\agente_orquestador
Git: https://github.com/jmillan1955/Agentes.git
Activo: True
```

### sessions

Representa una conversación activa.

Campos:

```text
id
project_id
channel
user_id
conversation_id
status
started_at
ended_at
```

Una sesión está asociada a:

```text
Proyecto + canal + usuario + conversación
```

Para una misma combinación solo puede existir una sesión con estado:

```text
active
```

Una sesión cerrada recibe:

```text
status = closed
ended_at = fecha de cierre
```

Después puede crearse una nueva sesión para la misma conversación.

### messages

Almacena entradas y salidas.

Campos:

```text
id
session_id
message_id
correlation_id
direction
channel
content_type
text
metadata_json
created_at
```

Direcciones admitidas:

```text
incoming
outgoing
```

La respuesta se relaciona con la entrada mediante:

```text
IncomingMessage.message_id
→ OutgoingMessage.correlation_id
```

Existe una restricción única para:

```text
channel + message_id
```

Esto evita guardar dos veces una misma actualización de Telegram.

### documents

Conserva la última versión conocida de cada documento.

Campos:

```text
id
project_id
relative_path
title
content
content_hash
file_modified_at
synchronized_at
git_commit_hash
```

La combinación única es:

```text
project_id + relative_path
```

El contenido se compara mediante SHA-256. Si el hash no cambia, el documento no se vuelve a escribir.

### git_commits

Conserva metadatos de los commits.

Campos:

```text
commit_hash
project_id
parent_hash
author_name
authored_at
subject
body
synchronized_at
```

No se guardan parches ni copias completas del código. Git mantiene el historial real.

En commits de fusión, `parent_hash` puede contener varios hashes separados por espacios.

## 9. Repositorio de proyectos

`ProjectRepository` permite:

- Registrar un proyecto.
- Actualizar sus datos.
- Recuperarlo por identificador.
- Recuperarlo por nombre.
- Listar proyectos activos.

La operación `save()` es idempotente por nombre de proyecto.

## 10. Repositorio de sesiones

`SessionRepository` permite:

- Obtener una sesión activa.
- Crear una si no existe.
- Reutilizarla para nuevos mensajes.
- Recuperarla por identificador.
- Listar sesiones activas.
- Cerrar una sesión.

## 11. Repositorio de mensajes

`MessageRepository` recibe directamente:

```text
IncomingMessage
OutgoingMessage
```

Permite:

- Guardar mensajes entrantes.
- Guardar mensajes salientes.
- Evitar duplicados.
- Recuperar un mensaje por identificador.
- Listar cronológicamente los mensajes de una sesión.
- Conservar metadatos como JSON.

## 12. Persistencia del canal Telegram

El canal Telegram continúa sin conocer SQLite.

El flujo implementado es:

```text
TelegramChannel
→ IncomingMessage
→ Orchestrator
→ SessionRepository
→ MessageRepository
→ OutgoingMessage
→ TelegramChannel
```

El orquestador:

1. Obtiene o crea la sesión activa.
2. Guarda el mensaje entrante.
3. Genera la respuesta provisional.
4. Guarda la respuesta.
5. Devuelve el `OutgoingMessage`.

Prueba realizada:

```text
incoming | Este mensaje debe quedar guardado en el contexto.
outgoing | He recibido correctamente tu mensaje:
           Este mensaje debe quedar guardado en el contexto.
```

Los datos continuaron disponibles después de detener el agente.

## 13. Repositorio de documentos

`DocumentRepository` permite:

- Guardar un documento.
- Recuperarlo por ruta.
- Actualizarlo conservando su identificador.
- Evitar la reescritura si el hash no cambia.
- Listar documentos de un proyecto.
- Eliminar documentos que ya no existen.

## 14. Sincronización de documentos

`DocumentSynchronizer` revisa:

```text
agente_orquestador/docs/**/*.md
```

Para cada documento:

1. Calcula su ruta relativa.
2. Lee el contenido como UTF-8.
3. Extrae el primer encabezado `#` como título.
4. Calcula SHA-256.
5. Obtiene la fecha de modificación.
6. Crea o actualiza el registro.
7. Conserva sin cambios los documentos idénticos.
8. Elimina de SQLite documentos borrados del disco.

Resultado comprobado:

```text
Ruta: docs/hitos/001_entrada_salida_telegram.md
Título: Hito 1: Entrada y salida mediante Telegram
Caracteres: 5313
SHA-256: c4837dd28bb7be861d85b0c1a067dcac4b8a92e88df029c9d600c1804dfbca90
```

## 15. Repositorio de commits

`GitCommitRepository` permite:

- Guardar metadatos de commits.
- Actualizar un registro existente.
- Recuperar por hash.
- Listar los commits de un proyecto.
- Ordenar el historial desde el más reciente.

## 16. Sincronización del historial Git

`GitCommitSynchronizer`:

1. Detecta la raíz real mediante:

```bash
git rev-parse --show-toplevel
```

2. Calcula la ruta de `agente_orquestador` dentro del repositorio.

3. Ejecuta `git log` limitado a dicha ruta.

4. Recupera:

```text
hash
padres
autor
fecha
asunto
cuerpo
```

5. Guarda commits nuevos.

6. Evita actualizar commits idénticos.

7. Ignora commits que solo afectan a otros proyectos del repositorio.

Primera sincronización comprobada:

```text
Commits revisados: 13
Commits creados: 13
```

Segunda sincronización:

```text
Commits revisados: 13
Commits creados: 0
Commits actualizados: 0
Commits sin cambios: 13
```

## 17. Secuencia de arranque

El arranque actual sigue este orden:

```text
Cargar configuración
→ abrir context.db
→ aplicar esquema
→ registrar proyecto
→ sincronizar documentos Markdown
→ sincronizar commits Git
→ crear repositorios de sesiones y mensajes
→ crear orquestador
→ iniciar Telegram
```

Ejemplo de registro:

```text
Contexto SQLite conectado
Proyecto registrado
Documentos sincronizados
Commits sincronizados
Iniciando Agente Orquestador
Iniciando canal Telegram
Control de acceso activado
Application started
```

## 18. Consultas de comprobación

### Proyecto registrado

```powershell
python -c "
from config import Settings
from app.context import ContextDatabase, ProjectRepository

s = Settings.load()

with ContextDatabase(s.context_database_path) as db:
    print(
        ProjectRepository(db).get_by_name(
            s.project_name
        )
    )
"
```

### Documentos

```powershell
python -c "
from config import Settings
from app.context import (
    ContextDatabase,
    DocumentRepository,
    ProjectRepository,
)

s = Settings.load()

with ContextDatabase(s.context_database_path) as db:
    project = ProjectRepository(db).get_by_name(
        s.project_name
    )

    for document in DocumentRepository(
        db
    ).list_by_project(project.id):
        print(
            document.relative_path,
            document.title,
            len(document.content),
        )
"
```

### Commits

```powershell
python -c "
from config import Settings
from app.context import (
    ContextDatabase,
    GitCommitRepository,
    ProjectRepository,
)

s = Settings.load()

with ContextDatabase(s.context_database_path) as db:
    project = ProjectRepository(db).get_by_name(
        s.project_name
    )

    commits = GitCommitRepository(
        db
    ).list_by_project(project.id)

    for commit in commits:
        print(
            commit.commit_hash[:7],
            commit.authored_at,
            commit.subject,
        )
"
```

### Conversaciones

```powershell
python -c "
from config import Settings
from app.context import (
    ContextDatabase,
    MessageRepository,
    SessionRepository,
)

s = Settings.load()

with ContextDatabase(s.context_database_path) as db:
    sessions = SessionRepository(
        db
    ).list_active()

    for session in sessions:
        print('Sesión:', session.id)

        for message in MessageRepository(
            db
        ).list_by_session(session.id):
            print(
                message.direction,
                message.text,
            )
"
```

## 19. Pruebas

Ejecución:

```powershell
cd C:\Python_Proyectos\Agentes\agente_orquestador
pytest -v
```

Resultado final:

```text
45 passed
```

Las pruebas cubren:

- Base SQLite.
- Claves foráneas.
- Modo WAL.
- Esquema idempotente.
- Proyectos.
- Sesiones.
- Mensajes.
- Documentos.
- Hashes.
- Actualización y eliminación documental.
- Repositorio de commits.
- Lectura de repositorios Git temporales.
- Filtrado de commits por proyecto.
- Integración del orquestador.
- Adaptación del canal Telegram.

## 20. Commits principales del Hito 2

```text
8ad03ce Crear infraestructura SQLite del orquestador
0682205 Añadir repositorio de proyectos al contexto
2dedd7a Conectar SQLite al arranque del orquestador
ef4d7f6 Añadir gestión de sesiones al contexto
58e5f11 Añadir persistencia de mensajes al contexto
73c738a Persistir conversaciones de Telegram en SQLite
7d9397c Añadir repositorio de documentos al contexto
4e633cb Añadir sincronización de documentos Markdown
80803e0 Sincronizar documentación al iniciar el orquestador
59f68cd Añadir repositorio de commits al contexto
7ef121a Añadir sincronización del historial Git
92d4272 Sincronizar commits al iniciar el orquestador
```

## 21. Limitaciones actuales

SQLite contiene el contexto, pero el orquestador todavía no lo utiliza para elaborar sus respuestas.

Actualmente:

```text
guardar contexto
```

Próximo objetivo:

```text
consultar contexto
→ seleccionar información relevante
→ incorporarla a la petición
→ generar una respuesta contextual
```

Antes de registrar varios proyectos de un mismo monorepositorio se revisará la relación entre `git_commits` y `projects`, porque un mismo commit puede afectar a más de un proyecto.

## 22. Resultado

El Hito 2 queda completado.

El Agente Orquestador dispone de memoria persistente para:

- Proyectos.
- Sesiones.
- Conversaciones.
- Documentos actuales.
- Historial Git.

El contexto se actualiza automáticamente al iniciar el agente y queda disponible para los siguientes hitos.

## 23. Próximo hito

El Hito 3 incorporará la consulta de contexto.

Primera capacidad prevista:

```text
/contexto
```

El comando permitirá consultar desde Telegram:

- Proyecto activo.
- Número de sesiones.
- Número de mensajes.
- Documentos almacenados.
- Commits registrados.
- Últimos avances conocidos.

Después se incorporará el contexto relevante al procesamiento ordinario de las peticiones.
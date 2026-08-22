# Avance 004: Publicación y despliegue del Agente IA en Ubuntu

**Fecha:** 22/08/2026  
**Componente:** Publicación y despliegue  
**Estado:** Completado

## 1. Objetivo

Publicar el proyecto `agente_ia` en GitHub, descargarlo en la máquina Ubuntu y dejarlo funcionando permanentemente como un servicio del sistema.

Telegram queda configurado como canal de entrada predeterminado. El agente admite:

- Mensajes de texto.
- Notas de voz.
- Transcripción local mediante Faster Whisper.
- Consultas a un modelo local servido por Ollama.
- Respuestas formateadas para Telegram.
- Visualización del tiempo de ejecución.

## 2. Arquitectura desplegada

El flujo de producción es el siguiente:

1. El usuario envía un texto o una nota de voz mediante Telegram.
2. El canal Telegram comprueba que el usuario esté autorizado.
3. Si la entrada es una nota de voz, se descarga temporalmente.
4. Faster Whisper transcribe el audio localmente.
5. El canal crea una petición indicando que procede de Telegram.
6. El orquestador recibe la petición.
7. El proveedor de Ollama consulta el modelo configurado.
8. El modelo genera una respuesta estructurada.
9. El canal Telegram extrae y formatea el texto.
10. Telegram muestra la respuesta y su tiempo de ejecución.

## 3. Configuración utilizada

La configuración de producción se guarda en:

```text
/home/jose-millan/Agentes/agente_ia/.env
```

Las variables utilizadas son:

```dotenv
AGENTE_CANAL=telegram
OLLAMA_BASE_URL=http://192.168.1.131:11434
OLLAMA_MODEL=qwen3:4b
TELEGRAM_BOT_TOKEN=token_privado_del_bot
TELEGRAM_ALLOWED_USER_ID=identificador_del_usuario
WHISPER_MODEL=small
```

El archivo `.env` contiene información privada y no debe publicarse en Git.

El repositorio contiene únicamente una plantilla segura:

```text
agente_ia/.env.example
```

En Ubuntu se protegió el archivo real con:

```bash
chmod 600 /home/jose-millan/Agentes/agente_ia/.env
```

## 4. Comprobación de exclusión del archivo `.env`

Antes de publicar se verificó que Git ignoraba correctamente el archivo:

```powershell
git check-ignore -v .\agente_ia\.env
```

El resultado confirmó que la regla global:

```gitignore
.env
```

impedía su incorporación al repositorio.

También se realizó una simulación de los archivos que se añadirían:

```powershell
git add -n -- .\agente_ia
```

Esta comprobación permitió confirmar que `.env` no se encontraba entre los archivos preparados para publicar.

## 5. Comprobación del repositorio en Windows

Desde la raíz del repositorio:

```powershell
cd C:\Python_Proyectos\Agentes
```

Se comprobó la rama activa:

```powershell
git branch --show-current
```

Resultado:

```text
master
```

Se comprobó el repositorio remoto:

```powershell
git remote -v
```

Repositorio utilizado:

```text
https://github.com/jmillan1955/Agentes.git
```

También se revisó el estado general:

```powershell
git status --short
```

Como el repositorio contiene otros proyectos y cambios independientes, se decidió añadir exclusivamente los archivos de `agente_ia`.

No se utilizó:

```powershell
git add .
```

En su lugar, se emplearon rutas concretas para evitar publicar modificaciones pertenecientes a otros proyectos.

## 6. Pruebas realizadas en Windows

Desde la carpeta del proyecto:

```powershell
cd C:\Python_Proyectos\Agentes\agente_ia
```

Se ejecutaron las pruebas:

```powershell
pytest -v
```

Las pruebas verificaron, entre otros aspectos:

- Creación de documentos Markdown.
- Incremento automático de la numeración.
- Normalización del nombre de los componentes.
- Funcionamiento del orquestador.
- Formateo de las respuestas destinadas a Telegram.

También se realizaron pruebas manuales del canal de consola:

```powershell
python main.py --canal consola
```

Para utilizar el canal predeterminado configurado en `.env`:

```powershell
python main.py
```

Al estar configurado Telegram como canal predeterminado, este último comando inicia el bot.

## 7. Primera publicación en GitHub

Una vez comprobado el proyecto, se añadieron exclusivamente sus archivos:

```powershell
cd C:\Python_Proyectos\Agentes
git add -- .\agente_ia
```

Se revisaron los cambios preparados:

```powershell
git status --short -- .\agente_ia
git diff --cached --check
git diff --cached --stat
```

A continuación, se creó el commit inicial:

```powershell
git commit -m "Crear Agente IA con consola Telegram y Ollama"
```

Commit generado:

```text
4c0ae14 Crear Agente IA con consola Telegram y Ollama
```

Se publicó en GitHub:

```powershell
git push origin master
```

## 8. Mejora del formato de Telegram

El proveedor de Ollama devuelve internamente una respuesta estructurada con un contenido similar a:

```json
{
  "respuesta": "Texto generado por el modelo",
  "tiempo_ejecución_segundos": 6.126
}
```

El canal Telegram fue adaptado para:

- Interpretar el JSON interno.
- Mostrar únicamente el contenido de `respuesta`.
- Convertir las secuencias `\n` en saltos de línea reales.
- Ocultar la estructura JSON al usuario.
- Añadir el tiempo de ejecución al final.
- Mantener sin cambios una respuesta que no sea JSON.

El resultado mostrado en Telegram adopta este formato:

```text
Texto generado por el modelo.

⏱ Tiempo de ejecución: 6.126 segundos
```

Después de probar mensajes escritos y notas de voz, se publicó la mejora:

```powershell
cd C:\Python_Proyectos\Agentes

git add -- `
  .\agente_ia\channels\telegram_channel.py `
  .\agente_ia\tests\test_telegram_channel.py

git diff --cached --check
git diff --cached --stat
git commit -m "Mejorar formato de respuestas en Telegram"
git push origin master
```

Commit generado:

```text
2c4bb75 Mejorar formato de respuestas en Telegram
```

Se comprobó con:

```powershell
git log -1 --oneline
```

Resultado:

```text
2c4bb75 (HEAD -> master, origin/master, origin/HEAD) Mejorar formato de respuestas en Telegram
```

## 9. Preparación de Ubuntu

La máquina de producción utiliza:

```text
Ubuntu 24.04
Python 3.12.3
```

El repositorio se encuentra en:

```text
/home/jose-millan/Agentes
```

El entorno virtual compartido se encuentra en:

```text
/home/jose-millan/Agentes/.venv
```

Antes de actualizar el repositorio se comprobaron la rama, el remoto y los cambios locales:

```bash
cd /home/jose-millan/Agentes

git status --short
git branch --show-current
git remote -v
```

La rama activa era:

```text
master
```

El remoto configurado en Ubuntu era:

```text
git@github.com:jmillan1955/Agentes.git
```

El repositorio contenía cambios pertenecientes a otros proyectos. Por esta razón, dichos cambios se conservaron y no se limpiaron ni modificaron.

## 10. Descarga del proyecto en Ubuntu

El proyecto se actualizó desde GitHub mediante un avance rápido:

```bash
cd /home/jose-millan/Agentes
git pull --ff-only origin master
```

La opción `--ff-only` evita que Git cree automáticamente un commit de mezcla durante el despliegue.

Después de la descarga se comprobó el commit instalado:

```bash
git log -1 --oneline
```

Para la primera publicación se obtuvo:

```text
4c0ae14 Crear Agente IA con consola Telegram y Ollama
```

Después de publicar la mejora de Telegram se volvió a actualizar:

```bash
git pull --ff-only origin master
```

El commit instalado pasó a ser:

```text
2c4bb75 Mejorar formato de respuestas en Telegram
```

## 11. Comprobación de Python y del entorno virtual

Se comprobó la versión general de Python:

```bash
python3 --version
```

Resultado:

```text
Python 3.12.3
```

Se comprobó el intérprete del entorno virtual:

```bash
ls -la .venv/bin/python
.venv/bin/python --version
```

Resultado:

```text
Python 3.12.3
```

## 12. Instalación de dependencias

Desde la raíz del repositorio se instalaron las dependencias de `agente_ia`:

```bash
cd /home/jose-millan/Agentes
.venv/bin/python -m pip install -r agente_ia/requirements.txt
```

Las dependencias principales son:

- `httpx`
- `python-dotenv`
- `python-telegram-bot`
- `faster-whisper`
- `pytest`

Se pueden comprobar con:

```bash
.venv/bin/python -m pip show \
  httpx \
  python-dotenv \
  python-telegram-bot \
  faster-whisper
```

## 13. Comprobación de Ollama

Se verificó que Ollama estaba disponible:

```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool
```

Entre los modelos instalados se encontraban:

```text
qwen3:4b
qwen3-vl:4b
qwen2.5-coder:3b
qwen2.5-coder:7b
```

El modelo elegido inicialmente para el agente fue:

```text
qwen3:4b
```

La dirección configurada para acceder a Ollama fue:

```text
http://192.168.1.131:11434
```

## 14. Comprobación de la configuración

Desde la carpeta del proyecto:

```bash
cd /home/jose-millan/Agentes/agente_ia
```

Se verificó la configuración cargada por la aplicación:

```bash
../.venv/bin/python -c "
from config import Settings
s = Settings.cargar()
print('Canal:', s.canal_predeterminado)
print('Ollama:', s.ollama_url)
print('Modelo:', s.ollama_model)
print('Token configurado:', bool(s.telegram_bot_token))
print('Usuario configurado:', s.telegram_allowed_user_id is not None)
print('Whisper:', s.whisper_model)
"
```

Resultado:

```text
Canal: telegram
Ollama: http://192.168.1.131:11434
Modelo: qwen3:4b
Token configurado: True
Usuario configurado: True
Whisper: small
```

Esta comprobación no muestra el token ni el identificador privado; solamente confirma que están configurados.

## 15. Ejecución de pruebas en Ubuntu

Se ejecutaron las pruebas utilizando el entorno virtual de Ubuntu:

```bash
cd /home/jose-millan/Agentes
.venv/bin/python -m pytest -v agente_ia
```

Las pruebas deben completarse antes de iniciar o reiniciar el servicio de producción.

## 16. Prueba manual en Ubuntu

Antes de crear el servicio se realizó una ejecución manual:

```bash
cd /home/jose-millan/Agentes/agente_ia
../.venv/bin/python main.py
```

Se probaron mediante Telegram:

- Una petición escrita.
- Una nota de voz.
- Una respuesta con varios párrafos.
- La presentación del tiempo de ejecución.

La ejecución manual se detuvo con:

```text
Ctrl+C
```

Debe existir una sola instancia del bot de Telegram. Por ello, la ejecución manual debe detenerse antes de arrancar el servicio permanente.

## 17. Creación del servicio systemd

Se creó el archivo:

```text
/etc/systemd/system/agente-ia.service
```

Mediante:

```bash
sudo nano /etc/systemd/system/agente-ia.service
```

Contenido completo:

```ini
[Unit]
Description=Agente IA con Telegram, Whisper y Ollama
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=jose-millan
Group=jose-millan
WorkingDirectory=/home/jose-millan/Agentes/agente_ia
EnvironmentFile=/home/jose-millan/Agentes/agente_ia/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/jose-millan/Agentes/.venv/bin/python /home/jose-millan/Agentes/agente_ia/main.py
Restart=on-failure
RestartSec=10
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

La unidad establece:

- El usuario y grupo que ejecutan el agente.
- La carpeta de trabajo.
- El archivo de configuración.
- El intérprete del entorno virtual.
- El programa principal.
- El reinicio automático cuando el proceso falla.
- Una espera de diez segundos antes del reinicio.
- El inicio después de disponer de conexión de red.

## 18. Activación del servicio

Después de crear la unidad se recargó la configuración de `systemd`:

```bash
sudo systemctl daemon-reload
```

El servicio se habilitó e inició simultáneamente:

```bash
sudo systemctl enable --now agente-ia.service
```

`enable` hace que el agente arranque automáticamente con Ubuntu.

`--now` hace que también se inicie inmediatamente.

## 19. Comprobación del servicio

Se comprobó su estado:

```bash
sudo systemctl status agente-ia.service --no-pager -l
```

También se consultaron los últimos registros:

```bash
sudo journalctl -u agente-ia.service -n 30 --no-pager -l
```

El registro mostró:

```text
Started agente-ia.service - Agente IA con Telegram, Whisper y Ollama.
Iniciando canal Telegram
Control de acceso activado
Application started
```

Se comprobó que el servicio estaba activo:

```bash
systemctl is-active agente-ia.service
```

Resultado:

```text
active
```

Se comprobó que el inicio automático estaba habilitado:

```bash
systemctl is-enabled agente-ia.service
```

Resultado:

```text
enabled
```

## 20. Prueba final en producción

Con el servicio funcionando se realizaron pruebas desde Telegram:

- Envío de mensajes escritos.
- Envío de notas de voz.
- Carga del modelo Whisper.
- Transcripción local del audio.
- Consulta al modelo de Ollama.
- Recepción de la respuesta.
- Presentación limpia del texto.
- Visualización del tiempo de ejecución.
- Mantenimiento del control de acceso.

El resultado fue satisfactorio.

## 21. Administración habitual

### Consultar el estado

```bash
sudo systemctl status agente-ia.service --no-pager -l
```

### Consultar los últimos registros

```bash
sudo journalctl -u agente-ia.service -n 50 --no-pager -l
```

### Seguir los registros en tiempo real

```bash
sudo journalctl -u agente-ia.service -f -l
```

Para dejar de visualizar el registro:

```text
Ctrl+C
```

Esto no detiene el servicio.

### Reiniciar el agente

```bash
sudo systemctl restart agente-ia.service
```

### Detener el agente

```bash
sudo systemctl stop agente-ia.service
```

### Iniciar el agente

```bash
sudo systemctl start agente-ia.service
```

### Desactivar el inicio automático

```bash
sudo systemctl disable agente-ia.service
```

### Volver a activar el inicio automático

```bash
sudo systemctl enable agente-ia.service
```

## 22. Procedimiento para futuras publicaciones

### En Windows

Ejecutar las pruebas:

```powershell
cd C:\Python_Proyectos\Agentes
pytest -v .\agente_ia
```

Revisar únicamente los cambios del agente:

```powershell
git status --short -- .\agente_ia
git diff -- .\agente_ia
```

Añadir exclusivamente los archivos modificados:

```powershell
git add -- <archivos_del_agente_ia>
```

Comprobar el contenido preparado:

```powershell
git diff --cached --check
git diff --cached --stat
```

Crear el commit y publicarlo:

```powershell
git commit -m "Descripción del cambio"
git push origin master
```

### En Ubuntu

Actualizar el repositorio:

```bash
cd /home/jose-millan/Agentes
git pull --ff-only origin master
```

Instalar dependencias si cambió `requirements.txt`:

```bash
.venv/bin/python -m pip install -r agente_ia/requirements.txt
```

Ejecutar las pruebas:

```bash
.venv/bin/python -m pytest -v agente_ia
```

Reiniciar el servicio:

```bash
sudo systemctl restart agente-ia.service
```

Comprobar el estado:

```bash
sudo systemctl status agente-ia.service --no-pager -l
```

Consultar los registros:

```bash
sudo journalctl -u agente-ia.service -n 50 --no-pager -l
```

## 23. Resultado final

El Agente IA queda publicado y funcionando permanentemente en Ubuntu.

Telegram es su canal predeterminado y permite comunicarse con el cerebro mediante texto o audio. Las notas de voz se transcriben localmente y las peticiones se procesan mediante Ollama.

El agente:

- Arranca automáticamente con Ubuntu.
- Funciona sin una terminal abierta.
- Se reinicia si el proceso falla.
- Limita el acceso al usuario autorizado.
- Mantiene separada la configuración privada.
- Presenta las respuestas con un formato adecuado para Telegram.
- Informa del tiempo empleado por el modelo.
- Puede seguir evolucionando mediante nuevos canales, proveedores y herramientas.
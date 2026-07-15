# Publicación del Asistente Cocina

## Objetivo

Publicar una nueva versión del Asistente Cocina desde el equipo de desarrollo Windows hacia la máquina virtual Ubuntu utilizando el Terminal de Home.

La publicación consta de cuatro partes:

1. Publicar el Frontend Angular.
2. Publicar el Backend .NET.
3. Copiar los datos.
4. Verificar el funcionamiento.

---

# Estructura del proyecto

## Desarrollo (Windows)

```
C:\Python_Proyectos\Asistente-cocina
│
├── backend
│   └── AsistenteCocina.Api
│
├── frontend
│   └── asistente-cocina-web
│
├── Data
│
├── agente
│
└── docs
```

## Servidor Ubuntu

```
/home/jose-millan/Asistente-cocina
│
├── backend
│
├── frontend
│
├── Data
│
├── agente
│
└── docs
```

---

# Paso 1. Comprobar el proyecto en desarrollo

Antes de publicar verificar:

- Backend funcionando correctamente.
- Frontend funcionando correctamente.
- Swagger operativo.
- Todas las modificaciones probadas.

---

# Paso 2. Generar el Frontend Angular

Situarse en:

```
frontend/asistente-cocina-web
```

Ejecutar:

```bash
npm install
```

(si fuera necesario)

Después:

```bash
ng build
```

El resultado quedará en:

```
dist/asistente-cocina-web/browser
```

---

# Paso 3. Publicar el Backend

Situarse en:

```
backend/AsistenteCocina.Api
```

Ejecutar:

```bash
dotnet publish -c Release
```

Se generará:

```
bin/Release/net8.0/publish
```

---

# Paso 4. Abrir el Terminal de Home

Conectarse a la máquina Ubuntu.

---

# Paso 5. Detener el backend

Detener el servicio del backend.

(Se documentará el nombre definitivo del servicio cuando quede creado.)

---

# Paso 6. Copiar el Frontend

Copiar el contenido generado por Angular a:

```
/var/www/asistente-cocina/browser
```

---

# Paso 7. Copiar el Backend

Copiar el contenido de:

```
publish
```

a:

```
/home/jose-millan/Asistente-cocina/backend
```

---

# Paso 8. Datos

No sobrescribir la carpeta:

```
Data
```

Salvo que se quiera publicar también nuevos datos.

---

# Paso 9. Reiniciar el backend

Iniciar nuevamente el servicio.

---

# Paso 10. Verificaciones

Comprobar:

## Backend

```
http://localhost:5000/swagger
```

o

```
https://recetas.jmn55.duckdns.org/swagger
```

---

## Frontend

```
https://recetas.jmn55.duckdns.org
```

Comprobar:

- carga de categorías
- listado de recetas
- detalle de receta
- edición
- creación

---

# Paso 11. Verificación final

Realizar una prueba completa:

- Crear una receta.
- Editarla.
- Añadir ingredientes.
- Añadir pasos.
- Guardar.
- Recargar la aplicación.
- Verificar que toda la información permanece correctamente.

---

# Próximas mejoras

Cuando el Agente Cocina esté integrado, el procedimiento incluirá además:

- publicación del agente Python
- creación/actualización del servicio systemd
- reinicio del agente
- comprobación de los endpoints del agente
# Lista de la compra desde Telegram

AgenteIA-local gestiona dos listas almacenadas localmente en Home Assistant:

- **Casa** (`todo.casa`)
- **Casa Jessi** (`todo.casa_jessi`)

Estas operaciones no utilizan ningún modelo de inteligencia artificial y no
consumen tokens. Si no se indica una lista, se utiliza **Casa**.

## Consultar

```text
/lista
/lista casa
/lista jessi
¿Qué falta comprar en Casa?
¿Qué hay en la lista de Casa Jessi?
```

## Añadir productos

```text
/compra casa leche y huevos
/compra jessi pañales, fruta y yogures
Añade leche y huevos a la lista de Casa.
Añade pañales a Casa Jessi.
```

Es posible añadir varios productos separándolos con comas o con `y`.

## Marcar como comprado

```text
Marca leche como comprada en Casa.
Marca pañales como comprados en Casa Jessi.
```

El nombre debe coincidir con el que aparece en la lista. Las mayúsculas y los
acentos no afectan a la búsqueda.

## Borrar

```text
Borra leche de la lista de Casa.
Vacía los productos comprados de Casa Jessi.
```

Antes de borrar un producto o limpiar los ya comprados, el bot muestra botones
para confirmar o cancelar. Cancelar no modifica Home Assistant.

## Notas

- Las cuatro personas autorizadas comparten las mismas dos listas.
- Los cambios aparecen también en el panel **Listas de tareas** de Home Assistant.
- La antigua entidad `todo.lista_de_la_compra` no se utiliza.

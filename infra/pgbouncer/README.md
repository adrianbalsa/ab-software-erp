# PgBouncer (AB Logistics OS)

## `userlist.txt` y credenciales

El formato es **una línea por usuario**:

```text
"nombre_usuario" "contraseña_en_claro"
```

o hash MD5 según la [documentación de PgBouncer](https://www.pgbouncer.org/config.html#authentication-file-format).

**No** se expanden variables de entorno dentro del fichero. En CI/CD o despliegue, genera el fichero desde secretos:

```bash
printf '"%s" "%s"\n' "$POSTGRES_USER" "$POSTGRES_PASSWORD" > userlist.txt
```

El contenido debe coincidir con el usuario/contraseña del servicio Postgres al que PgBouncer hace de proxy (`docker-compose`: mismas variables `POSTGRES_USER` / `POSTGRES_PASSWORD`).

## `pgbouncer.ini`

- `pool_mode = transaction` — adecuado para FastAPI + SQLAlchemy con conexiones cortas por petición.
- El backend en **producción** debe usar `postgresql://...@pgbouncer:6432/...` y evitar sentencias preparadas persistentes entre transacciones (incompatible con este modo de PgBouncer).

### `prepared_statements=false` y SQLAlchemy

En algunos stacks se documenta `?prepared_statements=false` en la URL de conexión. Los drivers **psycopg2/psycopg3** **no** aceptan ese parámetro en la URI (libpq lo rechaza). En este repositorio el equivalente se aplica en `backend/app/db/session.py` con `connect_args={"prepare_threshold": 0}` y `pool_pre_ping=True` en el `create_engine`.

Si defines `DATABASE_URL` con `prepared_statements=false`, `backend/app/core/config.py` lo elimina de la URI antes de crear el motor y el comportamiento sigue siendo el correcto.

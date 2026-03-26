# AB Logistics OS — Restore Checklist (4 comandos)

Objetivo: restaurar un backup “físico” (pg_dump + `dump.rdb`) tras una catástrofe.  
Un backup que no se restaura, no sirve.

Suposiciones:
- Estás en la **carpeta raíz** del repo (`AB_Software/Scanner`).
- Tienes `.env.prod` con `DATABASE_URL` (o con credenciales `POSTGRES_*` equivalentes) y Docker Compose.
- Estás usando **rclone** para traer el backup desde tu storage externo.

Sustituye:
- `<BACKUP_TAR_GZ>` por el nombre real del `.tar.gz` descargado (ej. `ablogistics_backup_20260325_040000.tar.gz`).

## Comandos (exactos)

1. Descargar el archivo desde el storage externo:
```bash
rclone copyto "${RCLONE_REMOTE}:${RCLONE_DEST}/<BACKUP_TAR_GZ>" "./<BACKUP_TAR_GZ>"
```

2. Extraer el contenido en una carpeta de restore:
```bash
mkdir -p ./restore_now && tar -xzf "./<BACKUP_TAR_GZ>" -C ./restore_now
```

3. Restaurar PostgreSQL (ESQUEMA + DATOS) desde `pg_dump.sql`:
```bash
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f ./restore_now/pg_dump.sql
```

4. Restaurar Redis (rate limiting + sesiones) reinyectando `dump.rdb`:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod stop redis && cp ./restore_now/dump.rdb ./data/redis/dump.rdb && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d redis
```


# blacklist-ms

Microservicio Flask que gestiona la lista negra global de emails. Se despliega a mano en AWS Elastic Beanstalk con PostgreSQL en RDS.

## Endpoints

Todos responden JSON. Los de `/blacklists` exigen `Authorization: Bearer <token>`.

| Método | Ruta | Respuestas |
|---|---|---|
| POST | `/blacklists` | `201` agregado · `400` validación · `401` token · `409` ya existe |
| GET | `/blacklists/<email>` | `200` `{"email", "is_blacklisted", "blocked_reason"}` · `401` token |
| GET | `/ping` (sin token) | `200` `{"status": "ok", "version", "instance_id"}` |

Cuerpo del POST:

```json
{
  "email": "cliente@example.com",
  "app_uuid": "0b6f1f0e-2f55-4b9a-9d1c-6a1f0c6c3c11",
  "blocked_reason": "Solicitud del cliente"
}
```

- `email`: obligatorio, se guarda y consulta en minúsculas y sin espacios.
- `app_uuid`: obligatorio, UUID válido.
- `blocked_reason`: opcional, máximo 255 caracteres.
- Internamente se guardan la IP de origen (`request_ip`) y la fecha/hora UTC (`created_at`).

## Variables de entorno

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | `postgresql://usuario:clave@host:5432/blacklistdb` |
| `JWT_SECRET_KEY` | Secreto con que se firma el token (mínimo 32 caracteres). Nunca se sube al repo |
| `PROXY_FIX_X_FOR` | Opcional. Proxies de confianza delante de gunicorn. Por defecto `2` (ALB + nginx de Beanstalk) |

La versión que reporta `/ping` sale **solo** del archivo `VERSION`.

## Desarrollo local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Para correrlo contra PostgreSQL:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/blacklistdb
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
flask --app application init-db
flask --app application generate-token
flask --app application run
```

## Token estático

`flask --app application generate-token` imprime un JWT sin expiración firmado con `JWT_SECRET_KEY`. Debe generarse con **el mismo** `JWT_SECRET_KEY` configurado en Beanstalk. El token va al environment de Postman, no al repo.

## Crear las tablas (una sola vez)

Las tablas **no** se crean al arrancar. Con la RDS privada, se crean desde una instancia del ambiente (`eb ssh` o Session Manager):

```bash
cd /var/app/current
source /var/app/venv/*/bin/activate
export DATABASE_URL="$(sudo /opt/elasticbeanstalk/bin/get-config environment -k DATABASE_URL)"
export JWT_SECRET_KEY="$(sudo /opt/elasticbeanstalk/bin/get-config environment -k JWT_SECRET_KEY)"
flask --app application init-db
```

También sirve para generar el token desde la instancia (`flask --app application generate-token`).

## Despliegue en Elastic Beanstalk

- Plataforma: Python 3.13 (o 3.12) sobre Amazon Linux 2023.
- `.ebextensions/01_python.config` fija `WSGIPath: application:application` y el health check del balanceador en `/ping`.
- Empaquetar **siempre** desde `main` con git (nunca con Finder, que mete `__MACOSX/`):

```bash
git archive -o app.zip HEAD
```

- Para medir las estrategias de despliegue, cambiar **solo** el archivo `VERSION` (v2, v3, ...), hacer commit y volver a empaquetar.

## Estrategias de despliegue (Entrega 1)

Runbook completo en [`docs/estrategias-despliegue.md`](docs/estrategias-despliegue.md). Herramientas:

- `scripts/monitor_deploy.py <url> --target v2 --label rolling`: consulta `/ping` varias veces por segundo durante el despliegue y genera un CSV + resumen en Markdown (versiones mezcladas, errores, instancias iniciales o nuevas).
- `scripts/eb_deploy_times.py --env blacklist-ms-env --region <region> --since <UTC>`: tiempo oficial del despliegue según los eventos de Beanstalk (requiere AWS CLI).

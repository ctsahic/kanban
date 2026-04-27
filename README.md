# kanban-mcp (Required Production Deploy Steps)

This is the minimal process to deploy the production web stack without using a registry.

## 1) Build and export the image (source machine)

Run from this repository root:

```bash
docker build -t kanban-mcp-web:1.0.0 .
docker save -o kanban-mcp-web_1.0.0.tar kanban-mcp-web:1.0.0
```

## 2) Copy tar file to target host

Copy `kanban-mcp-web_1.0.0.tar` to the machine where you will run production.

## 3) Load image and start services (target host)

Run in the directory that contains `docker-compose.prod.yml`:

```bash
docker load -i kanban-mcp-web_1.0.0.tar
KANBAN_WEB_IMAGE=kanban-mcp-web:1.0.0 docker compose -f docker-compose.prod.yml up -d
```

## 4) Verify

```bash
docker compose -f docker-compose.prod.yml ps
```

The web UI is available on port 5000.

## Required notes

- Docker and Docker Compose must be installed on the target host.
- The compose file includes MySQL and persistent volume storage automatically.

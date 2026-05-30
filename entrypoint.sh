#!/bin/bash
set -e

python -m kanban_mcp.startup

exec gunicorn -b 0.0.0.0:${PORT:-5000} --worker-class gthread --threads 4 --preload kanban_mcp.web:app

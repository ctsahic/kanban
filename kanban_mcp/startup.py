#!/usr/bin/env python3
"""Runtime startup checks for the kanban web service."""

import os
import time

from kanban_mcp.db import create_backend
from kanban_mcp.setup import auto_migrate


def _mysql_env_configured() -> bool:
    return all(
        os.environ.get(name)
        for name in (
            'KANBAN_DB_USER',
            'KANBAN_DB_PASSWORD',
            'KANBAN_DB_NAME',
        )
    )


def _wait_for_mysql() -> None:
    from mysql.connector import connect

    host = os.environ.get('KANBAN_DB_HOST', 'localhost')
    port = int(os.environ.get('KANBAN_DB_PORT', '3306'))

    print('Waiting for database...')
    retries = 30
    while retries > 0:
        try:
            connect(
                host=host,
                port=port,
                user=os.environ['KANBAN_DB_USER'],
                password=os.environ['KANBAN_DB_PASSWORD'],
                database=os.environ['KANBAN_DB_NAME'],
            ).close()
            print('Database is ready.')
            return
        except Exception:
            retries -= 1
            if retries <= 0:
                raise RuntimeError('Could not connect to database after 30 attempts.')
            print(f'  Database not ready, retrying in 2s... ({retries} attempts left)')
            time.sleep(2)


def main() -> int:
    if _mysql_env_configured():
        _wait_for_mysql()
    else:
        print('MySQL env vars not set; using the default SQLite backend.')

    print('Running database migrations...')
    backend = create_backend()
    auto_migrate(backend)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
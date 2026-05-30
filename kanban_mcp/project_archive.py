#!/usr/bin/env python3
"""Project archive import/export helpers.

Produces a ZIP archive that contains a JSON manifest/data payload plus all
stored CV attachment blobs from the database.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ARCHIVE_SCHEMA_VERSION = 1
ARCHIVE_MANIFEST_NAME = "manifest.json"
ARCHIVE_DATA_NAME = "project.json"
ARCHIVE_ATTACHMENTS_DIR = "attachments"


def export_project_archive(db, project_id: str) -> bytes:
    """Export a full project archive as ZIP bytes."""
    project = db.get_project_by_id(project_id)
    if not project:
        raise ValueError("Project not found")

    items = _fetch_project_items(db, project_id)
    item_ids = [item["id"] for item in items]

    data = {
        "project": _serialize_row(project),
        "items": [_serialize_row(item) for item in items],
        "tags": _fetch_project_tags(db, project_id),
        "item_tags": _fetch_item_tags(db, item_ids),
        "updates": _fetch_project_updates(db, project_id),
        "update_items": _fetch_update_items(db, project_id),
        "relationships": _fetch_relationships(db, project_id),
        "decisions": _fetch_decisions(db, item_ids),
        "status_history": _fetch_status_history(db, item_ids),
        "item_files": _fetch_item_files(db, item_ids),
        "attachments": [],
    }

    attachments = _fetch_attachments(db, item_ids)
    for attachment in attachments:
        attachment = dict(attachment)
        attachment["archive_path"] = _attachment_archive_path(attachment)
        attachment.pop("file_data", None)
        data["attachments"].append(_serialize_row(attachment))

    manifest = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "project_name": project.get("name"),
        "project_id": project.get("id"),
        "exported_at": datetime.now().isoformat(),
        "counts": {
            "items": len(data["items"]),
            "tags": len(data["tags"]),
            "updates": len(data["updates"]),
            "decisions": len(data["decisions"]),
            "attachments": len(data["attachments"]),
        },
    }

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            ARCHIVE_MANIFEST_NAME,
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        archive.writestr(
            ARCHIVE_DATA_NAME,
            json.dumps(data, ensure_ascii=False, indent=2),
        )
        for attachment in attachments:
            archive_path = _attachment_archive_path(attachment)
            archive.writestr(archive_path, attachment["file_data"])

    return buffer.getvalue()


def import_project_archive(db, archive_bytes: bytes) -> Dict[str, Any]:
    """Import a project archive ZIP and restore its contents."""
    with zipfile.ZipFile(BytesIO(archive_bytes), mode="r") as archive:
        manifest = json.loads(archive.read(ARCHIVE_MANIFEST_NAME).decode("utf-8"))
        data = json.loads(archive.read(ARCHIVE_DATA_NAME).decode("utf-8"))

        if manifest.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
            raise ValueError("Unsupported archive schema version")

        project_data = data.get("project", {})
        project_name = project_data.get("name") or manifest.get("project_name") or "Imported Project"
        project_dir = _allocate_import_directory(project_name)
        project_id = db.ensure_project(project_dir, project_name)

        status_id_map = _build_status_id_map(db)
        tag_id_map = _restore_tags(db, project_id, data.get("tags", []))

        item_id_map = _restore_items(
            db,
            project_id,
            data.get("items", []),
            status_id_map,
        )
        _restore_item_parents(db, item_id_map, data.get("items", []))
        _restore_item_tags(db, item_id_map, tag_id_map, data.get("item_tags", []))
        _restore_updates(db, project_id, item_id_map, data.get("updates", []), data.get("update_items", []))
        _restore_relationships(db, item_id_map, data.get("relationships", []))
        _restore_decisions(db, item_id_map, data.get("decisions", []))
        _restore_status_history(db, item_id_map, status_id_map, data.get("status_history", []))
        _restore_item_files(db, item_id_map, data.get("item_files", []))
        _restore_attachments(db, item_id_map, data.get("attachments", []), archive)

    return {
        "success": True,
        "project_id": project_id,
        "project_name": project_name,
    }


def _fetch_project_items(db, project_id: str) -> List[Dict[str, Any]]:
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(db._sql("""
            SELECT i.*, it.name as type_name, s.name as status_name
            FROM items i
            JOIN item_types it ON i.type_id = it.id
            JOIN statuses s ON i.status_id = s.id
            WHERE i.project_id = %s
            ORDER BY i.id
        """), (project_id,))
        return cursor.fetchall()


def _fetch_project_tags(db, project_id: str) -> List[Dict[str, Any]]:
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(db._sql("""
            SELECT id, project_id, name, color, created_at
            FROM tags
            WHERE project_id = %s
            ORDER BY id
        """), (project_id,))
        return [_serialize_row(row) for row in cursor.fetchall()]


def _fetch_item_tags(db, item_ids: List[int]) -> List[Dict[str, Any]]:
    if not item_ids:
        return []
    placeholders = ",".join([db._backend.placeholder] * len(item_ids))
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(
            db._sql(
                f"""
                SELECT item_id, tag_id, created_at
                FROM item_tags
                WHERE item_id IN ({placeholders})
                ORDER BY item_id, tag_id
                """),
            tuple(item_ids),
        )
        return [_serialize_row(row) for row in cursor.fetchall()]


def _fetch_project_updates(db, project_id: str) -> List[Dict[str, Any]]:
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(db._sql("""
            SELECT id, project_id, content, created_at
            FROM updates
            WHERE project_id = %s
            ORDER BY id
        """), (project_id,))
        return [_serialize_row(row) for row in cursor.fetchall()]


def _fetch_update_items(db, project_id: str) -> List[Dict[str, Any]]:
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(db._sql("""
            SELECT ui.update_id, ui.item_id
            FROM update_items ui
            JOIN updates u ON ui.update_id = u.id
            WHERE u.project_id = %s
            ORDER BY ui.update_id, ui.item_id
        """), (project_id,))
        return [_serialize_row(row) for row in cursor.fetchall()]


def _fetch_relationships(db, project_id: str) -> List[Dict[str, Any]]:
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(db._sql("""
            SELECT r.id, r.source_item_id, r.target_item_id,
                   r.relationship_type, r.created_at
            FROM item_relationships r
            JOIN items s ON r.source_item_id = s.id
            JOIN items t ON r.target_item_id = t.id
            WHERE s.project_id = %s OR t.project_id = %s
            ORDER BY r.id
        """), (project_id, project_id))
        return [_serialize_row(row) for row in cursor.fetchall()]


def _fetch_decisions(db, item_ids: List[int]) -> List[Dict[str, Any]]:
    if not item_ids:
        return []
    placeholders = ",".join([db._backend.placeholder] * len(item_ids))
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(
            db._sql(
                f"""
                SELECT id, item_id, choice, rejected_alternatives,
                       rationale, created_at
                FROM item_decisions
                WHERE item_id IN ({placeholders})
                ORDER BY id
                """),
            tuple(item_ids),
        )
        return [_serialize_row(row) for row in cursor.fetchall()]


def _fetch_status_history(db, item_ids: List[int]) -> List[Dict[str, Any]]:
    if not item_ids:
        return []
    placeholders = ",".join([db._backend.placeholder] * len(item_ids))
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(
            db._sql(
                f"""
                SELECT sh.id, sh.item_id,
                       os.name as old_status_name,
                       ns.name as new_status_name,
                       sh.change_type, sh.changed_at
                FROM status_history sh
                LEFT JOIN statuses os ON sh.old_status_id = os.id
                JOIN statuses ns ON sh.new_status_id = ns.id
                WHERE sh.item_id IN ({placeholders})
                ORDER BY sh.id
                """),
            tuple(item_ids),
        )
        return [_serialize_row(row) for row in cursor.fetchall()]


def _fetch_item_files(db, item_ids: List[int]) -> List[Dict[str, Any]]:
    if not item_ids:
        return []
    placeholders = ",".join([db._backend.placeholder] * len(item_ids))
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(
            db._sql(
                f"""
                SELECT id, item_id, file_path, line_start, line_end, created_at
                FROM item_files
                WHERE item_id IN ({placeholders})
                ORDER BY id
                """),
            tuple(item_ids),
        )
        return [_serialize_row(row) for row in cursor.fetchall()]


def _fetch_attachments(db, item_ids: List[int]) -> List[Dict[str, Any]]:
    if not item_ids:
        return []
    placeholders = ",".join([db._backend.placeholder] * len(item_ids))
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(
            db._sql(
                f"""
                SELECT id, item_id, file_name, mime_type, file_data, created_at
                FROM item_attachments
                WHERE item_id IN ({placeholders})
                ORDER BY id
                """),
            tuple(item_ids),
        )
        return cursor.fetchall()


def _build_status_id_map(db) -> Dict[str, int]:
    with db._db_cursor(dictionary=True) as cursor:
        cursor.execute(db._sql("SELECT id, name FROM statuses"))
        return {row["name"]: row["id"] for row in cursor.fetchall()}


def _restore_tags(db, project_id: str, tags: List[Dict[str, Any]]) -> Dict[int, int]:
    tag_id_map: Dict[int, int] = {}
    for tag in tags:
        new_tag_id = db.ensure_tag(project_id, tag["name"], tag.get("color"))
        tag_id_map[tag["id"]] = new_tag_id
    return tag_id_map


def _restore_items(
    db,
    project_id: str,
    items: List[Dict[str, Any]],
    status_id_map: Dict[str, int],
) -> Dict[int, int]:
    item_id_map: Dict[int, int] = {}
    type_id = db.get_type_id("cv")

    with db._db_cursor(dictionary=True, commit=True) as cursor:
        for item in items:
            status_name = item.get("status_name")
            status_id = status_id_map.get(status_name)
            if status_id is None:
                raise ValueError(f"Unknown status in archive: {status_name}")

            cursor.execute(
                db._sql("""
                    INSERT INTO items
                        (project_id, type_id, status_id,
                         title, description, priority,
                         created_at, updated_at, closed_at,
                         complexity, parent_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                """),
                (
                    project_id,
                    type_id,
                    status_id,
                    item.get("title"),
                    item.get("description"),
                    item.get("priority", 3),
                    _parse_dt(item.get("created_at")),
                    _parse_dt(item.get("updated_at")) or _parse_dt(item.get("created_at")),
                    _parse_dt(item.get("closed_at")),
                    item.get("complexity"),
                ),
            )
            item_id_map[item["id"]] = cursor.lastrowid
    return item_id_map


def _restore_item_parents(db, item_id_map: Dict[int, int], items: List[Dict[str, Any]]) -> None:
    with db._db_cursor(commit=True) as cursor:
        for item in items:
            parent_id = item.get("parent_id")
            if not parent_id:
                continue
            new_parent_id = item_id_map.get(parent_id)
            new_item_id = item_id_map.get(item["id"])
            if new_parent_id and new_item_id:
                cursor.execute(
                    db._sql("UPDATE items SET parent_id = %s WHERE id = %s"),
                    (new_parent_id, new_item_id),
                )


def _restore_item_tags(
    db,
    item_id_map: Dict[int, int],
    tag_id_map: Dict[int, int],
    item_tags: List[Dict[str, Any]],
) -> None:
    with db._db_cursor(commit=True) as cursor:
        for item_tag in item_tags:
            new_item_id = item_id_map.get(item_tag["item_id"])
            new_tag_id = tag_id_map.get(item_tag["tag_id"])
            if new_item_id and new_tag_id:
                cursor.execute(
                    db._sql("INSERT INTO item_tags (item_id, tag_id, created_at) VALUES (%s, %s, %s)"),
                    (new_item_id, new_tag_id, _parse_dt(item_tag.get("created_at"))),
                )


def _restore_updates(
    db,
    project_id: str,
    item_id_map: Dict[int, int],
    updates: List[Dict[str, Any]],
    update_items: List[Dict[str, Any]],
) -> None:
    update_id_map: Dict[int, int] = {}
    with db._db_cursor(dictionary=True, commit=True) as cursor:
        for update in updates:
            cursor.execute(
                db._sql("INSERT INTO updates (project_id, content, created_at) VALUES (%s, %s, %s)"),
                (project_id, update.get("content"), _parse_dt(update.get("created_at"))),
            )
            update_id_map[update["id"]] = cursor.lastrowid

        for update_item in update_items:
            new_update_id = update_id_map.get(update_item["update_id"])
            new_item_id = item_id_map.get(update_item["item_id"])
            if new_update_id and new_item_id:
                cursor.execute(
                    db._sql("INSERT INTO update_items (update_id, item_id) VALUES (%s, %s)"),
                    (new_update_id, new_item_id),
                )


def _restore_relationships(
    db,
    item_id_map: Dict[int, int],
    relationships: List[Dict[str, Any]],
) -> None:
    with db._db_cursor(commit=True) as cursor:
        for rel in relationships:
            source_id = item_id_map.get(rel["source_item_id"])
            target_id = item_id_map.get(rel["target_item_id"])
            if source_id and target_id:
                cursor.execute(
                    db._sql("""
                        INSERT INTO item_relationships
                            (source_item_id, target_item_id, relationship_type, created_at)
                        VALUES (%s, %s, %s, %s)
                    """),
                    (source_id, target_id, rel.get("relationship_type"), _parse_dt(rel.get("created_at"))),
                )


def _restore_decisions(
    db,
    item_id_map: Dict[int, int],
    decisions: List[Dict[str, Any]],
) -> None:
    with db._db_cursor(commit=True) as cursor:
        for decision in decisions:
            new_item_id = item_id_map.get(decision["item_id"])
            if new_item_id:
                cursor.execute(
                    db._sql("""
                        INSERT INTO item_decisions
                            (item_id, choice, rejected_alternatives, rationale, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """),
                    (
                        new_item_id,
                        decision.get("choice"),
                        decision.get("rejected_alternatives"),
                        decision.get("rationale"),
                        _parse_dt(decision.get("created_at")),
                    ),
                )


def _restore_status_history(
    db,
    item_id_map: Dict[int, int],
    status_id_map: Dict[str, int],
    status_history: List[Dict[str, Any]],
) -> None:
    with db._db_cursor(commit=True) as cursor:
        for entry in status_history:
            new_item_id = item_id_map.get(entry["item_id"])
            old_status_name = entry.get("old_status_name")
            new_status_name = entry.get("new_status_name")
            old_status_id = status_id_map.get(old_status_name) if old_status_name else None
            new_status_id = status_id_map.get(new_status_name)
            if new_item_id and new_status_id:
                cursor.execute(
                    db._sql("""
                        INSERT INTO status_history
                            (item_id, old_status_id, new_status_id, change_type, changed_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """),
                    (
                        new_item_id,
                        old_status_id,
                        new_status_id,
                        entry.get("change_type"),
                        _parse_dt(entry.get("changed_at")),
                    ),
                )


def _restore_item_files(
    db,
    item_id_map: Dict[int, int],
    item_files: List[Dict[str, Any]],
) -> None:
    with db._db_cursor(commit=True) as cursor:
        for file_row in item_files:
            new_item_id = item_id_map.get(file_row["item_id"])
            if new_item_id:
                cursor.execute(
                    db._sql("""
                        INSERT INTO item_files
                            (item_id, file_path, line_start, line_end, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """),
                    (
                        new_item_id,
                        file_row.get("file_path"),
                        file_row.get("line_start"),
                        file_row.get("line_end"),
                        _parse_dt(file_row.get("created_at")),
                    ),
                )


def _restore_attachments(
    db,
    item_id_map: Dict[int, int],
    attachments: List[Dict[str, Any]],
    archive: zipfile.ZipFile,
) -> None:
    with db._db_cursor(commit=True) as cursor:
        for attachment in attachments:
            new_item_id = item_id_map.get(attachment["item_id"])
            archive_path = attachment.get("archive_path")
            if not new_item_id or not archive_path:
                continue
            file_data = archive.read(archive_path)
            cursor.execute(
                db._sql("""
                    INSERT INTO item_attachments
                        (item_id, file_name, mime_type, file_data, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """),
                (
                    new_item_id,
                    attachment.get("file_name"),
                    attachment.get("mime_type"),
                    file_data,
                    _parse_dt(attachment.get("created_at")),
                ),
            )


def _attachment_archive_path(attachment: Dict[str, Any]) -> str:
    file_name = Path(attachment.get("file_name", "attachment.bin")).name
    return f"{ARCHIVE_ATTACHMENTS_DIR}/item_{attachment['item_id']}/{attachment['id']}_{file_name}"


def _allocate_import_directory(project_name: str) -> str:
    safe_name = "".join(
        c for c in project_name
        if c.isascii() and (c.isalnum() or c in "-_")
    )[:32] or "project"
    directory = Path(tempfile.gettempdir()) / f"kanban-import-{safe_name}-{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory)


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _serialize_value(value) for key, value in row.items()}


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value
    if isinstance(value, dict):
        return {key: _serialize_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _parse_dt(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value

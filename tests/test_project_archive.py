#!/usr/bin/env python3
"""Tests for full project archive import/export."""

import json
import zipfile
from io import BytesIO

from kanban_mcp.project_archive import (
    export_project_archive,
    import_project_archive,
)


def test_project_archive_roundtrip(db, tmp_path):
    project_path = str(tmp_path / "source-project")
    project_id = db.ensure_project(project_path, "Source Project")

    item_id = db.create_item(
        project_id=project_id,
        type_name="cv",
        title="Alice Candidate",
        description="CV description",
        priority=2,
        status_name="ראיון טלפוני",
    )
    db.add_tag_to_item(item_id, "python")
    db.add_decision(item_id, "עבר סינון", rationale="מתאים לתפקיד")
    db.add_update(project_id, "עדכון ראשון", [item_id])
    db.add_item_attachment(item_id, "cv.txt", b"CV DATA", "text/plain")

    archive_bytes = export_project_archive(db, project_id)
    with zipfile.ZipFile(BytesIO(archive_bytes), "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        project_data = json.loads(archive.read("project.json").decode("utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["counts"]["items"] == 1
    assert manifest["counts"]["attachments"] == 1
    assert project_data["items"][0]["title"] == "Alice Candidate"
    assert project_data["attachments"][0]["file_name"] == "cv.txt"

    result = import_project_archive(db, archive_bytes)
    assert result["success"] is True

    imported_items = db.list_items(project_id=result["project_id"])
    assert len(imported_items) == 1

    imported_item = imported_items[0]
    assert imported_item["title"] == "Alice Candidate"
    assert imported_item["status_name"] == "ראיון טלפוני"

    imported_tags = db.get_item_tags(imported_item["id"])
    assert [tag["name"] for tag in imported_tags] == ["python"]

    imported_decisions = db.get_item_decisions(imported_item["id"])
    assert imported_decisions[0]["choice"] == "עבר סינון"

    imported_updates = db.get_updates(result["project_id"])
    assert imported_updates[0]["content"] == "עדכון ראשון"
    assert imported_updates[0]["item_ids"] == [imported_item["id"]]

    imported_attachments = db.get_item_attachments(imported_item["id"])
    assert len(imported_attachments) == 1
    attachment = db.get_item_attachment(imported_item["id"], imported_attachments[0]["id"])
    assert attachment["file_name"] == "cv.txt"
    assert attachment["file_data"] == b"CV DATA"

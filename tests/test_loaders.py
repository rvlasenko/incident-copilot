import json
from pathlib import Path
from typing import Any

import pytest

from incident_copilot.domain.loaders import (
    DEPENDENCIES_FILE,
    DEPLOYS_FILE,
    LOGS_FILE,
    METRICS_FILE,
    SERVICES_FILE,
    DatasetIntegrityError,
    FixtureLoadError,
    load_dataset,
    load_json_list,
    load_jsonl,
)
from incident_copilot.domain.models import Deploy, DeployStatus, LogEntry
from tests.factories import REPO_FIXTURES_DIR

VALID_DEPLOY: dict[str, Any] = {
    "id": "dep-1",
    "service": "checkout",
    "version": "1.0.0",
    "deployed_at": "2026-09-22T10:00:00Z",
    "author": "alice",
    "status": "succeeded",
    "change_summary": "Initial release",
}

VALID_LOG: dict[str, Any] = {
    "timestamp": "2026-09-22T10:01:00Z",
    "service": "checkout",
    "level": "ERROR",
    "message": "Something failed",
    "version": "1.0.0",
    "trace_id": "t-1",
}

CHECKOUT_SERVICE: dict[str, Any] = {
    "name": "checkout",
    "owner_team": "team-commerce",
    "description": "Checkout",
    "depends_on": [],
}

PSP_DEPENDENCY: dict[str, Any] = {
    "name": "psp-gateway",
    "status": "degraded",
    "since": "2026-09-22T10:00:00Z",
    "description": "Payment service provider",
}


def _write_dataset(
    directory: Path,
    *,
    services: list[dict[str, Any]] | None = None,
    dependencies: list[dict[str, Any]] | None = None,
    deploys: list[dict[str, Any]] | None = None,
) -> None:
    files = {
        SERVICES_FILE: services if services is not None else [CHECKOUT_SERVICE],
        DEPENDENCIES_FILE: dependencies or [],
        DEPLOYS_FILE: deploys or [],
        METRICS_FILE: [],
    }
    for file_name, records in files.items():
        (directory / file_name).write_text(json.dumps(records), encoding="utf-8")
    (directory / LOGS_FILE).write_text("", encoding="utf-8")


def test_json_list_loads_valid_records(tmp_path: Path) -> None:
    path = tmp_path / "deploys.json"
    path.write_text(json.dumps([VALID_DEPLOY]), encoding="utf-8")

    deploys = load_json_list(path, Deploy)

    assert len(deploys) == 1
    assert deploys[0].status is DeployStatus.SUCCEEDED


def test_json_list_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FixtureLoadError, match="cannot read file"):
        load_json_list(tmp_path / "missing.json", Deploy)


def test_json_list_invalid_json_reports_line(tmp_path: Path) -> None:
    path = tmp_path / "deploys.json"
    path.write_text('[\n{"id": "dep-1",\n]', encoding="utf-8")

    with pytest.raises(FixtureLoadError, match="invalid JSON") as exc_info:
        load_json_list(path, Deploy)
    assert exc_info.value.line == 3


def test_json_list_invalid_record_reports_index(tmp_path: Path) -> None:
    path = tmp_path / "deploys.json"
    path.write_text(
        json.dumps([VALID_DEPLOY, {**VALID_DEPLOY, "status": "exploded"}]),
        encoding="utf-8",
    )

    with pytest.raises(FixtureLoadError, match="item 1 is invalid"):
        load_json_list(path, Deploy)


@pytest.mark.parametrize("content", ["42", '{"id": "dep-1"}', "null"])
def test_json_list_top_level_must_be_array(tmp_path: Path, content: str) -> None:
    path = tmp_path / "deploys.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(FixtureLoadError, match="expected a JSON array"):
        load_json_list(path, Deploy)


def test_json_list_non_utf8_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "deploys.json"
    path.write_bytes(b"[\xff]")

    with pytest.raises(FixtureLoadError, match="not valid UTF-8"):
        load_json_list(path, Deploy)


def test_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "logs.jsonl"
    path.write_text(
        f"{json.dumps(VALID_LOG)}\n\n   \n{json.dumps(VALID_LOG)}\n", encoding="utf-8"
    )

    assert len(load_jsonl(path, LogEntry)) == 2


def test_jsonl_bad_line_reports_line_number(tmp_path: Path) -> None:
    path = tmp_path / "logs.jsonl"
    path.write_text(f"{json.dumps(VALID_LOG)}\n\n{{broken\n", encoding="utf-8")

    with pytest.raises(FixtureLoadError) as exc_info:
        load_jsonl(path, LogEntry)
    assert exc_info.value.line == 3


def test_jsonl_non_utf8_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "logs.jsonl"
    path.write_bytes(json.dumps(VALID_LOG).encode() + b"\n\xff\n")

    with pytest.raises(FixtureLoadError, match="not valid UTF-8"):
        load_jsonl(path, LogEntry)


def test_repository_fixtures_load() -> None:
    dataset = load_dataset(REPO_FIXTURES_DIR)

    assert {service.name for service in dataset.services} == {
        "checkout",
        "payments",
        "inventory",
        "auth",
    }


def test_unknown_service_in_deploy_is_reported(tmp_path: Path) -> None:
    _write_dataset(tmp_path, deploys=[{**VALID_DEPLOY, "service": "chekout"}])

    with pytest.raises(
        DatasetIntegrityError,
        match="reference to unknown service 'chekout'",
    ):
        load_dataset(tmp_path)


def test_unknown_dependency_is_reported(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path, services=[{**CHECKOUT_SERVICE, "depends_on": ["psp-gatway"]}]
    )

    with pytest.raises(
        DatasetIntegrityError, match="'checkout' depends on unknown 'psp-gatway'"
    ):
        load_dataset(tmp_path)


def test_all_problems_are_reported_together(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        services=[{**CHECKOUT_SERVICE, "depends_on": ["ghost"]}],
        deploys=[{**VALID_DEPLOY, "service": "phantom"}],
    )

    with pytest.raises(DatasetIntegrityError) as exc_info:
        load_dataset(tmp_path)
    assert len(exc_info.value.problems) == 2


def test_duplicate_service_name_is_reported(tmp_path: Path) -> None:
    _write_dataset(tmp_path, services=[CHECKOUT_SERVICE, CHECKOUT_SERVICE])

    with pytest.raises(
        DatasetIntegrityError, match=f"{SERVICES_FILE}: duplicate name 'checkout'"
    ):
        load_dataset(tmp_path)


def test_duplicate_dependency_name_is_reported(tmp_path: Path) -> None:
    # The copy differs in status: last-wins would silently hide the degradation.
    _write_dataset(
        tmp_path,
        dependencies=[PSP_DEPENDENCY, {**PSP_DEPENDENCY, "status": "operational"}],
    )

    with pytest.raises(
        DatasetIntegrityError,
        match=f"{DEPENDENCIES_FILE}: duplicate name 'psp-gateway'",
    ):
        load_dataset(tmp_path)


def test_service_named_like_dependency_is_reported(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        services=[CHECKOUT_SERVICE, {**CHECKOUT_SERVICE, "name": "psp-gateway"}],
        dependencies=[PSP_DEPENDENCY],
    )

    with pytest.raises(
        DatasetIntegrityError,
        match="'psp-gateway' is both a service and an external dependency",
    ):
        load_dataset(tmp_path)


def test_each_duplicate_is_reported_once(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path, services=[CHECKOUT_SERVICE, CHECKOUT_SERVICE, CHECKOUT_SERVICE]
    )

    with pytest.raises(DatasetIntegrityError) as exc_info:
        load_dataset(tmp_path)
    assert exc_info.value.problems == (f"{SERVICES_FILE}: duplicate name 'checkout'",)

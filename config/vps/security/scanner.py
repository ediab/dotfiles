#!/usr/bin/env python3
"""Sequential, exact-running-image Trivy scan; reports stay private on this host."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
from typing import Any, Callable

from core import MonitorError, atomic_json, deliver_transition, locked, read_private_json

DEFAULT_CONFIG = Path.home() / ".config/vps-security-scan/config.json"
DEFAULT_STATE = Path.home() / ".local/state/vps-security-scan"
GIB = 1024**3
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, capture_output=True, timeout=timeout, check=False)


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _safe_name(value: str) -> str:
    value = value.lstrip("/")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)[:128] or "unnamed"


def _summary_value(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:+/@-]", "_", value)[:128] or "unknown"


def validate_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise MonitorError("scanner configuration must be an object")
    report_dir = config.get("report_dir")
    if not isinstance(report_dir, str) or not Path(report_dir).is_absolute():
        raise MonitorError("report_dir must be an absolute path")
    values = {
        "report_dir": Path(report_dir),
        "min_free_bytes": config.get("min_free_bytes", 10 * GIB),
        "min_containers": config.get("min_containers", 1),
        "max_containers": config.get("max_containers", 40),
        "scan_timeout_seconds": config.get("scan_timeout_seconds", 1200),
        "overall_timeout_seconds": config.get("overall_timeout_seconds", 6600),
        "max_report_bytes": config.get("max_report_bytes", 32 * 1024 * 1024),
        "max_total_report_bytes": config.get("max_total_report_bytes", 512 * 1024 * 1024),
        "max_retained_reports": config.get("max_retained_reports", 30),
        "retention_days": config.get("retention_days", 30),
        "email_transport_root": config.get("email_transport_root", str(Path.home() / "Dev/xbot")),
        "state_dir": Path(config.get("state_dir", str(DEFAULT_STATE))),
        "native_apps_not_scanned": config.get("native_apps_not_scanned", ["tfl", "xbot"]),
    }
    bounds = {
        "min_free_bytes": (GIB, 200 * GIB), "max_containers": (1, 100),
        "min_containers": (1, 50),
        "scan_timeout_seconds": (60, 1800), "max_report_bytes": (1024, 256 * 1024 * 1024),
        "overall_timeout_seconds": (300, 6900),
        "max_total_report_bytes": (16 * 1024 * 1024, 2 * 1024 * 1024 * 1024),
        "max_retained_reports": (2, 100), "retention_days": (2, 180),
    }
    for key, (low, high) in bounds.items():
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise MonitorError(f"invalid scanner setting: {key}")
    if not isinstance(values["email_transport_root"], str):
        raise MonitorError("invalid email transport root")
    native_apps = values["native_apps_not_scanned"]
    if (not isinstance(native_apps, list) or len(native_apps) > 30
            or any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", name)
                   for name in native_apps)):
        raise MonitorError("native application coverage list is invalid")
    if values["min_containers"] > values["max_containers"]:
        raise MonitorError("minimum container count exceeds inventory limit")
    if values["max_total_report_bytes"] < values["max_report_bytes"]:
        raise MonitorError("total report bound must be at least as large as one report")
    return values


def _check_guards(config: dict[str, Any]) -> None:
    _ensure_free(config)
    reports = sorted(config["report_dir"].glob("scan-*.json"), key=lambda p: p.stat().st_mtime)
    latest_valid = None
    for report in reversed(reports):
        try:
            if report.stat().st_size <= config["max_report_bytes"]:
                record = json.loads(report.read_text(encoding="utf-8"))
                if isinstance(record, dict) and record.get("status") in {"clean", "findings"}:
                    latest_valid = report
                    break
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    protected = {latest_valid} if latest_valid is not None else set()
    cutoff = time.time() - config["retention_days"] * 86400
    for report in reports:
        if report not in protected and report.stat().st_mtime < cutoff:
            report.unlink()
    remaining = sorted(config["report_dir"].glob("scan-*.json"), key=lambda p: p.stat().st_mtime)
    while len(remaining) > config["max_retained_reports"] - 1:
        removable = next((report for report in remaining if report not in protected), None)
        if removable is None:
            raise MonitorError("retention cannot preserve the last valid report within count bound")
        remaining.remove(removable)
        removable.unlink()
    total = sum(p.stat().st_size for p in remaining)
    while total + config.get("max_report_bytes", 0) > config["max_total_report_bytes"]:
        removable = next((report for report in remaining if report not in protected), None)
        if removable is None:
            break
        remaining.remove(removable)
        total -= removable.stat().st_size
        removable.unlink()
    if total + config.get("max_report_bytes", 0) > config["max_total_report_bytes"]:
        raise MonitorError("retained reports exceed configured size bound")


def _ensure_free(config: dict[str, Any]) -> None:
    usage = shutil.disk_usage(config["report_dir"].parent)
    if usage.free < config["min_free_bytes"]:
        raise MonitorError("report filesystem is below configured free-space reserve")


def _containers(run: Callable[[list[str], int], subprocess.CompletedProcess[bytes]], limit: int) -> list[dict[str, Any]]:
    listing = run(["/usr/bin/docker", "ps", "--no-trunc", "--quiet"], 20)
    if listing.returncode:
        raise MonitorError("container inventory command failed")
    ids = [line.decode("ascii", "strict").strip() for line in listing.stdout.splitlines() if line.strip()]
    if (len(ids) > limit or len(ids) != len(set(ids))
            or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in ids)):
        raise MonitorError("container inventory exceeded bounds or had invalid identity")
    if not ids:
        return []
    inspected = run(["/usr/bin/docker", "inspect", *ids], 30)
    if inspected.returncode:
        raise MonitorError("container identity inspection failed")
    try:
        values = json.loads(inspected.stdout)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MonitorError("container identity response was invalid") from exc
    if not isinstance(values, list) or len(values) != len(ids):
        raise MonitorError("container identity response shape was invalid")
    returned_container_ids = [row.get("Id") if isinstance(row, dict) else None for row in values]
    if (any(not isinstance(container_id, str) or not re.fullmatch(r"[0-9a-f]{64}", container_id)
            for container_id in returned_container_ids)
            or len(returned_container_ids) != len(set(returned_container_ids))
            or set(returned_container_ids) != set(ids)):
        raise MonitorError("container inspection did not match the requested running IDs")

    raw_image_ids = [row.get("Image") for row in values if isinstance(row, dict)]
    if any(not isinstance(image_id, str) or not IMAGE_ID.fullmatch(image_id) for image_id in raw_image_ids):
        raise MonitorError("container inventory included an invalid immutable image ID")
    image_ids = sorted(set(raw_image_ids))
    inspected_images = run(["/usr/bin/docker", "image", "inspect", *image_ids], 30)
    if inspected_images.returncode:
        raise MonitorError("exact image digest inspection failed")
    try:
        image_rows = json.loads(inspected_images.stdout)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MonitorError("exact image inspection response was invalid") from exc
    if not isinstance(image_rows, list) or len(image_rows) != len(image_ids):
        raise MonitorError("exact image inspection response shape was invalid")
    images_by_id = {}
    for image in image_rows:
        if (not isinstance(image, dict) or not isinstance(image.get("Id"), str)
                or image.get("Id") not in image_ids or image.get("Id") in images_by_id):
            raise MonitorError("exact image inspection returned an unexpected identity")
        digests = image.get("RepoDigests") or []
        if (not isinstance(digests, list)
                or any(not isinstance(digest, str) or not re.search(r"@sha256:[0-9a-f]{64}$", digest)
                       for digest in digests)):
            raise MonitorError("exact image repository digest metadata was invalid")
        images_by_id[image["Id"]] = sorted(set(digests))
    if set(images_by_id) != set(image_ids):
        raise MonitorError("exact image inspection did not cover every running image ID")

    result = []
    for row in values:
        state = row.get("State") if isinstance(row, dict) else None
        if not isinstance(row, dict) or not isinstance(state, dict) or state.get("Running") is not True:
            raise MonitorError("container inventory changed while being captured")
        image_id = row.get("Image")
        container_id = row.get("Id")
        if not isinstance(image_id, str) or not IMAGE_ID.fullmatch(image_id):
            raise MonitorError("running container has no immutable image ID")
        if not isinstance(container_id, str) or not re.fullmatch(r"[0-9a-f]{64}", container_id):
            raise MonitorError("running container has invalid ID")
        config = row.get("Config")
        if not isinstance(config, dict):
            raise MonitorError("container image configuration metadata was invalid")
        config_image = config.get("Image", "")
        name = row.get("Name", "")
        if not isinstance(config_image, str) or not isinstance(name, str):
            raise MonitorError("container labels were invalid")
        name = name.lstrip("/")
        result.append({
            "container_id": container_id,
            "container_name": _safe_name(name),
            "configured_image": config_image[:256],
            "image_id": image_id,
            "repo_digests": images_by_id[image_id],
        })
    return sorted(result, key=lambda x: (x["container_name"], x["container_id"]))


def _findings(report: Any, identity: dict[str, Any]) -> list[dict[str, str]]:
    if (not isinstance(report, dict) or report.get("SchemaVersion") != 2
            or not isinstance(report.get("ArtifactName"), str) or not report["ArtifactName"]
            or report.get("ArtifactType") != "container_image"
            or not isinstance(report.get("Metadata"), dict)
            or report["Metadata"].get("ImageID") != identity["image_id"]
            or not isinstance(report.get("Results"), list)):
        raise MonitorError("Trivy report shape was invalid")
    found = []
    for result in report.get("Results", []):
        if (not isinstance(result, dict) or not isinstance(result.get("Target"), str) or not result["Target"]
                or not isinstance(result.get("Class"), str) or not result["Class"]
                or not isinstance(result.get("Type"), str) or not result["Type"]):
            raise MonitorError("Trivy result entry was invalid")
        vulnerabilities = result.get("Vulnerabilities")
        if vulnerabilities is None:
            vulnerabilities = []
        if not isinstance(vulnerabilities, list):
            raise MonitorError("Trivy vulnerability list was invalid")
        for item in vulnerabilities:
            if not isinstance(item, dict):
                raise MonitorError("Trivy vulnerability entry was invalid")
            required = ("VulnerabilityID", "PkgName", "InstalledVersion", "Severity")
            if any(key not in item or not isinstance(item[key], str) or not item[key] for key in required):
                raise MonitorError("Trivy finding fields were invalid")
            if item["Severity"].upper() not in {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                raise MonitorError("Trivy finding severity was invalid")
            found.append({
                "container": identity["container_name"],
                "image_id": identity["image_id"],
                "target": str(result.get("Target", ""))[:256],
                "vulnerability_id": item.get("VulnerabilityID", ""),
                "package": item.get("PkgName", ""),
                "installed_version": item.get("InstalledVersion", ""),
                "fixed_version": item.get("FixedVersion", ""),
                "severity": item.get("Severity", "UNKNOWN").upper(),
            })
    return sorted(found, key=lambda f: (f["container"], f["target"], f["vulnerability_id"], f["package"]))


def run_scan(config: dict[str, Any], *, run=_run, send_email: Callable[[str], bool] | None = None,
             now: int | None = None, clock: Callable[[], float] | None = None) -> tuple[dict[str, Any], int]:
    """Capture and scan exact Docker image IDs serially. No logs leave this process."""
    clock = time.time if clock is None else clock
    started_at = int(clock()) if now is None else now
    config["report_dir"].mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(config["report_dir"], 0o700)
    lock_path = config["state_dir"] / "scan.lock"
    with locked(lock_path):
        scan_id = datetime.fromtimestamp(started_at, timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        report: dict[str, Any] = {
            "schema_version": 1,
            "scan_id": scan_id,
            "started_at": datetime.fromtimestamp(started_at, timezone.utc).isoformat(),
            "status": "error",
            "images": [],
            "findings": [],
            "errors": [],
            "native_dependency_coverage": {
                "status": "not_scanned",
                "applications": config["native_apps_not_scanned"],
                "note": "Docker image scanning does not cover native applications or host-installed dependencies; review each native app's lockfiles/package manifests separately.",
            },
        }
        try:
            _check_guards(config)
            images = _containers(run, config["max_containers"])
            if len(images) < config["min_containers"]:
                raise MonitorError("running container inventory was below the configured minimum")
            report["images"] = images
            scan_deadline = time.monotonic() + config["overall_timeout_seconds"]
            for identity in images:
                _ensure_free(config)
                remaining_seconds = int(scan_deadline - time.monotonic())
                if remaining_seconds < 1:
                    report["errors"].append({"code": "overall_scan_timeout"})
                    break
                timeout_seconds = min(config["scan_timeout_seconds"], remaining_seconds)
                path = config["state_dir"] / f"trivy-{identity['container_id']}.json"
                if path.exists():
                    path.unlink()
                try:
                    completed = run([
                        "/usr/bin/trivy", "image", "--quiet", "--scanners", "vuln", "--image-src", "docker",
                        "--timeout", f"{timeout_seconds}s", "--format", "json",
                        "--output", str(path), identity["image_id"],
                    ], timeout_seconds)
                    _ensure_free(config)
                    if completed.returncode:
                        report["errors"].append({"container": identity["container_name"], "code": "trivy_exit"})
                        continue
                    info = path.stat()
                    if info.st_size > config["max_report_bytes"]:
                        raise MonitorError("per-image Trivy report exceeded size bound")
                    findings = _findings(json.loads(path.read_text(encoding="utf-8")), identity)
                    report["findings"].extend(findings)
                except subprocess.TimeoutExpired:
                    report["errors"].append({"container": identity["container_name"], "code": "trivy_timeout"})
                except (OSError, UnicodeError, json.JSONDecodeError, MonitorError):
                    report["errors"].append({"container": identity["container_name"], "code": "invalid_trivy_report"})
                finally:
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
            try:
                final_images = _containers(run, config["max_containers"])
                initial_identity = {(item["container_id"], item["image_id"]) for item in images}
                final_identity = {(item["container_id"], item["image_id"]) for item in final_images}
                if initial_identity != final_identity:
                    report["errors"].append({"code": "runtime_inventory_changed"})
            except (MonitorError, OSError, subprocess.TimeoutExpired, UnicodeError):
                report["errors"].append({"code": "runtime_inventory_unverified"})
            report["status"] = "error" if report["errors"] else ("findings" if report["findings"] else "clean")
        except (MonitorError, OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
            # Exception class only: raw command output, paths and secrets are not retained.
            report["errors"].append({"code": type(exc).__name__})
            report["status"] = "error"

        completed_at = int(clock())
        report["completed_at"] = datetime.fromtimestamp(completed_at, timezone.utc).isoformat()
        if len(json.dumps(report, separators=(",", ":")).encode("utf-8")) > config["max_report_bytes"]:
            report["status"] = "error"
            report["findings"] = []
            report["errors"].append({"code": "aggregate_report_too_large"})
        report["identity"] = _digest({"images": report["images"], "findings": report["findings"]})
        report_path = config["report_dir"] / f"scan-{scan_id}.json"
        atomic_json(report_path, report)
        state_path = config["state_dir"] / "notifications.json"
        state: dict[str, Any] = {}
        try:
            state_path.lstat()
        except FileNotFoundError:
            pass
        else:
            loaded = read_private_json(state_path, max_bytes=config["max_report_bytes"])
            if not isinstance(loaded, dict):
                raise MonitorError("scanner notification state has invalid shape")
            state = loaded
        previous_status = state.get("status")
        previous_findings = state.get("findings", [])
        if (previous_status not in {None, "clean", "findings", "error"}
                or not isinstance(previous_findings, list)
                or any(not isinstance(finding, dict) for finding in previous_findings)):
            raise MonitorError("scanner notification state has invalid shape")
        event = None
        summary_lines = []
        if report["status"] == "error":
            event = "scan_error"
            codes = sorted({item.get("code", "unknown") for item in report["errors"]})
            summary_lines.append(f"Daily running-image scan failed; scan_id={scan_id}; errors={','.join(codes)}.")
        elif previous_status == "error":
            event = "recovered"
            summary_lines.append(f"Daily running-image scan recovered; status={report['status']}; findings={len(report['findings'])}; scan_id={scan_id}.")
        elif report["status"] == "findings":
            old = {json.dumps(f, sort_keys=True) for f in previous_findings}
            current = {json.dumps(f, sort_keys=True) for f in report["findings"]}
            added = current - old
            resolved = old - current
            if added or resolved or previous_status != "findings":
                event = "findings_changed"
                summary_lines.append(f"Running-image findings changed; scan_id={scan_id}; total={len(current)}; new_or_changed={len(added)}; resolved={len(resolved)}.")
                for raw in sorted(added)[:30]:
                    finding = json.loads(raw)
                    summary_lines.append("NEW " + " ".join(
                        f"{key}={_summary_value(str(finding[key]))}" for key in (
                            "container", "vulnerability_id", "package", "installed_version", "fixed_version", "severity")))
                if len(added) > 30:
                    summary_lines.append(f"Additional new findings omitted: {len(added) - 30}.")
                for raw in sorted(resolved)[:20]:
                    finding = json.loads(raw)
                    summary_lines.append("RESOLVED " + " ".join(
                        f"{key}={_summary_value(str(finding[key]))}" for key in (
                            "container", "vulnerability_id", "package", "installed_version", "severity")))
                if len(resolved) > 20:
                    summary_lines.append(f"Additional resolved findings omitted: {len(resolved) - 20}.")
        elif previous_status == "findings":
            event = "findings_cleared"
            summary_lines.append(f"Running-image findings cleared; scan_id={scan_id}.")

        if event:
            fingerprint = _digest({"event": event, "status": report["status"], "identity": report["identity"],
                                   "errors": report["errors"] if report["status"] == "error" else []})
            acknowledged = {
                "status": report["status"],
                "findings": report["findings"] if report["status"] != "error" else previous_findings,
                "last_success_at": completed_at if report["status"] != "error" else state.get("last_success_at"),
            }
            if send_email is None:
                sent = deliver_transition(state_path, fingerprint, _email_sender(config), "\n".join(summary_lines), event=event, now=completed_at, extra=acknowledged, state_max_bytes=config["max_report_bytes"])
            else:
                sent = deliver_transition(state_path, fingerprint, send_email, "\n".join(summary_lines), event=event, now=completed_at, extra=acknowledged, state_max_bytes=config["max_report_bytes"])
            if not sent:
                # The same already acknowledged state needs no repeated message.
                pass
        else:
            # Preserve acknowledged state across unchanged scans. Successful run freshness
            # is recorded separately for the stale-job watchdog.
            state["last_success_at"] = completed_at if report["status"] != "error" else state.get("last_success_at")
            state["status"] = report["status"]
            state["findings"] = report["findings"]
            atomic_json(state_path, state)
        run_path = config["state_dir"] / "run.json"
        atomic_json(run_path, {"completed_at": completed_at, "status": report["status"], "scan_id": scan_id,
                               "report": str(report_path)})
        return report, (1 if report["status"] == "error" else 0)


def _email_sender(config: dict[str, Any]) -> Callable[[str], bool]:
    root = Path(config["email_transport_root"])
    if not (root / "summary_config.py").is_file() or not (root / "scrape_timeline.py").is_file():
        raise MonitorError("existing xbot email transport unavailable")
    sys.path.insert(0, str(root))
    try:
        from summary_config import load_environment
        from scrape_timeline import DEFAULT_CURL_EXPIRY_EMAIL, send_alert_email
        load_environment(root)
        recipient = os.getenv("DIGEST_RECIPIENT_EMAIL", "").strip() or DEFAULT_CURL_EXPIRY_EMAIL
        if not recipient:
            raise MonitorError("email recipient is not configured")
        def send(body: str) -> bool:
            try:
                return bool(send_alert_email(recipient, "VPS running-image vulnerability scan", body))
            except Exception as exc:
                raise MonitorError("existing xbot email delivery failed") from exc
        return send
    except MonitorError:
        raise
    except Exception as exc:
        raise MonitorError("existing xbot email transport initialization failed") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    try:
        config = validate_config(read_private_json(args.config))
        report, status = run_scan(config)
        print(f"scan_id={report['scan_id']} status={report['status']} images={len(report['images'])} findings={len(report['findings'])} errors={len(report['errors'])}")
        return status
    except (MonitorError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"scanner could not complete: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

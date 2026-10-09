#!/usr/bin/env python3
"""Hourly disk warning using the VPS's existing xbot email transport."""
import json
import os
from pathlib import Path
import socket
import sys
import time

GIB = 1024**3


def severity(percent, free):
    if percent >= 90 or free < 5 * GIB:
        return 2
    return 1 if percent >= 80 else 0


def notification(level, state, now):
    previous = state.get("level", 0)
    if level != previous:
        return True
    return level > 0 and now - state.get("sent_at", 0) >= 86400


def main():
    # Match df's used/(used+available), which excludes reserved filesystem blocks.
    fs = os.statvfs("/")
    used = (fs.f_blocks - fs.f_bfree) * fs.f_frsize
    free = fs.f_bavail * fs.f_frsize
    percent = used / (used + free) * 100
    level = severity(percent, free)
    now = time.time()
    state_path = Path.home() / ".local/state/vps-disk-alert/state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    print(f"Disk: {percent:.1f}% used, {free / GIB:.1f} GiB available; target: 10 GiB free")
    if not notification(level, state, now):
        return 0

    xbot = Path.home() / "Dev/xbot"
    sys.path.insert(0, str(xbot))
    from summary_config import load_environment
    from scrape_timeline import DEFAULT_CURL_EXPIRY_EMAIL, send_alert_email

    load_environment(xbot)
    recipient = os.getenv("DIGEST_RECIPIENT_EMAIL", "").strip() or DEFAULT_CURL_EXPIRY_EMAIL
    label = {0: "recovered", 1: "warning", 2: "CRITICAL"}[level]
    body = (
        f"Disk {label} on {socket.gethostname()}: {percent:.1f}% used, "
        f"{free / GIB:.1f} GiB available.\n\n"
        "Target: at least 10 GiB available. Warning: 80% used; critical: "
        "90% used or less than 5 GiB available.\n"
        "Inspect df -h /, docker system df, and project/caches usage.\n"
        "No data has been deleted by this alert. Reminders are sent daily.\n"
    )
    if not send_alert_email(recipient, f"VPS disk {label}", body):
        raise RuntimeError("Disk alert delivery failed; state unchanged for retry")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"level": level, "sent_at": now}) + "\n")
    temporary.chmod(0o600)
    temporary.replace(state_path)
    print(f"Sent disk {label} email")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

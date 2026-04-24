#!/usr/bin/env python3

import os
import signal
import subprocess
import sys
import time


AIRPODS_MAC = os.environ.get("AIRPODS_MAC", "1C:0E:C2:CB:FC:6A").upper()
AIRPODS_UNDERSCORE = AIRPODS_MAC.replace(":", "_")
SINK_PREFIXES = (
    f"bluez_output.{AIRPODS_UNDERSCORE}",
    f"bluez_output.{AIRPODS_MAC}",
)
SOURCE_PREFIXES = (
    f"bluez_input.{AIRPODS_MAC}",
    f"bluez_input.{AIRPODS_UNDERSCORE}",
)

running = True


def handle_signal(signum, frame):
    global running
    running = False


def capture(cmd: list[str]) -> str:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    return result.stdout


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def default_name(kind: str) -> str:
    for line in capture(["pactl", "info"]).splitlines():
        if line.startswith(f"Default {kind}:"):
            return line.split(":", 1)[1].strip()
    return ""


def short_list(kind: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in capture(["pactl", "list", "short", kind]).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def first_matching(kind: str, prefixes: tuple[str, ...]) -> tuple[str, str]:
    for node_id, node_name in short_list(kind):
        if any(node_name.startswith(prefix) for prefix in prefixes):
            return node_id, node_name
    return "", ""


def move_all_sink_inputs(target_name: str) -> None:
    for stream_id, _ in short_list("sink-inputs"):
        run(["pactl", "move-sink-input", stream_id, target_name])


def reconcile() -> None:
    sink_id, sink_name = first_matching("sinks", SINK_PREFIXES)
    if sink_name:
        if default_name("Sink") != sink_name:
            run(["pactl", "set-default-sink", sink_name])
        move_all_sink_inputs(sink_name)

    _, source_name = first_matching("sources", SOURCE_PREFIXES)
    if source_name and default_name("Source") != source_name:
        run(["pactl", "set-default-source", source_name])


def main() -> int:
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    reconcile()

    while running:
        proc = subprocess.Popen(
            ["pactl", "subscribe"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None

        for line in proc.stdout:
            if not running:
                break

            lowered = line.lower()
            if "sink" in lowered or "source" in lowered or "server" in lowered or "card" in lowered:
                time.sleep(0.8)
                reconcile()

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        if running:
            time.sleep(1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

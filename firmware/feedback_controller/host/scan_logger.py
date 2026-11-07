#!/usr/bin/env python3
"""Host logger for scanner_controller (MECH5720 2026 event-based structured light).

Sends one command to the Arduino and saves everything it streams back.

Examples
    python scan_logger.py --port COM5 status
    python scan_logger.py --port COM5 goto 1500
    python scan_logger.py --port COM5 --arm sweep 1300 1700 2000 \\
        --nd 0.5 --distance 400 --ambient off --target steps --by Kailas
    python scan_logger.py --port /dev/tty.usbmodem1101 --arm step 1300 1700 9 200 200

Each run is saved to runs/<timestamp>_<command>/:
    raw.log      every line from the board, prefixed with host receive time
    samples.csv  t_us, cmd_us, adc, laser          (all times are the Arduino's micros())
    events.csv   t_us, name, a, b, c
    meta.json    command, conditions, start/end date-time, result, firmware, git commit

and one row per run is appended to runs/run_log.csv: the master log of every
run, with its date and time, conditions and result. Open it in Excel.

The Arduino has no clock, so the date and time come from the laptop; the
Arduino's micros() stays the precise timeline inside each run.

Ctrl+C sends `stop` to the board (laser off, disarmed) before saving.
Requires: pip install pyserial
"""
import argparse
import csv
import datetime as dt
import json
import pathlib
import sys
import time

RUN_COMMANDS = {"sweep", "step"}          # stream data until DONE / ABORTED
END_EVENTS = {"DONE", "ABORTED"}


# ----------------------------------------------------------------------------
# Parsing (no serial needed, so it can be reused on saved raw logs)
# ----------------------------------------------------------------------------
def unwrap_us(values):
    """Undo the 32-bit wrap of Arduino micros() (every ~71.6 minutes)."""
    out, offset, prev = [], 0, None
    for v in values:
        if prev is not None and v < prev - 2**31:
            offset += 2**32
        out.append(v + offset)
        prev = v
    return out


def parse_lines(lines):
    """Split board output into sample rows and event rows.

    Timestamps are unwrapped in arrival order across both streams, so samples
    and events stay on one continuous timeline even across a micros() wrap.
    """
    samples, events = [], []
    offset, prev = 0, None
    for line in lines:
        f = line.strip().split(",")
        if f[0] not in ("S", "E") or len(f) < 3:
            continue
        try:
            t = int(f[1])
        except ValueError:
            continue
        if prev is not None and t < prev - 2**31:
            offset += 2**32
        prev = t
        t += offset
        if f[0] == "S" and len(f) == 5:
            samples.append([t, int(f[2]), int(f[3]), int(f[4])])
        elif f[0] == "E":
            nums = [int(x) for x in f[3:6]]
            events.append([t, f[2]] + nums + [0] * (3 - len(nums)))
    return samples, events


def clock_map(arduino_on_us, davis_on_us, arduino_off_us, davis_off_us):
    """Return f(t_arduino_us) -> t_davis_us from the two laser markers of one sweep.

    The two boards' clocks differ by an offset and run at slightly different
    rates, so map with a straight line through the LASER_ON and LASER_OFF
    markers (both logged by the Arduino, both visible as event bursts).
    """
    scale = (davis_off_us - davis_on_us) / (arduino_off_us - arduino_on_us)
    return lambda t: davis_on_us + (t - arduino_on_us) * scale


def save_run(outdir, raw, meta):
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "raw.log").write_text("".join(f"{h:.6f}\t{l}\n" for h, l in raw))
    samples, events = parse_lines([l for _, l in raw])
    with open(outdir / "samples.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t_us", "cmd_us", "adc", "laser"])
        w.writerows(samples)
    with open(outdir / "events.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t_us", "name", "a", "b", "c"])
        w.writerows(events)
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2))
    return samples, events


def summarise(samples, events):
    names = [e[1] for e in events]
    print(f"  {len(samples)} samples, {len(events)} events")
    ev = {e[1]: e for e in events}
    if "SWEEP_START" in ev and "SWEEP_END" in ev:
        print(f"  sweep duration {(ev['SWEEP_END'][0] - ev['SWEEP_START'][0]) / 1000:.1f} ms")
    ons = [e for e in events if e[1] == "LASER_ON"]
    offs = [e for e in events if e[1] in ("LASER_OFF", "SAFETY_OFF", "LASER_TIMEOUT")]
    if ons:
        print(f"  laser ON markers at t_us = {[e[0] for e in ons][:10]}")
    if offs:
        print(f"  laser OFF markers at t_us = {[e[0] for e in offs][:10]}")
    for bad in ("SAFETY_OFF", "SETTLE_TIMEOUT", "ABORTED", "INTERLOCK_OPEN"):
        if bad in names:
            print(f"  WARNING: {bad} occurred - check raw.log")


# ----------------------------------------------------------------------------
# Master run log
# ----------------------------------------------------------------------------
LOG_FIELDS = ["run_id", "started", "finished", "duration_s", "command", "result",
              "sweep_start_us", "sweep_end_us", "sweep_ms",
              "nd", "distance_mm", "ambient", "target", "by",
              "n_samples", "n_events", "laser_on_us", "laser_off_us",
              "firmware", "git_commit", "folder", "note"]


def git_commit():
    """Short commit hash of the code that took the run, if it lives in a git repo."""
    try:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                           text=True, timeout=2, cwd=pathlib.Path(__file__).resolve().parent)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def run_summary(samples, events):
    ons = [e[0] for e in events if e[1] == "LASER_ON"]
    offs = [e[0] for e in events if e[1] in ("LASER_OFF", "SAFETY_OFF", "LASER_TIMEOUT")]
    return {"n_samples": len(samples), "n_events": len(events),
            "laser_on_us": ons[0] if ons else "", "laser_off_us": offs[-1] if offs else ""}


def append_run_log(log_path, row):
    """Add one row to the master log, writing the header the first time."""
    new = not log_path.exists()
    try:
        with open(log_path, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=LOG_FIELDS, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)
        return True
    except PermissionError:   # Windows: file is open in Excel
        print(f"WARNING: could not write {log_path} (close it in Excel). "
              f"The run itself is saved; its details are in meta.json.")
        return False


# ----------------------------------------------------------------------------
# Serial session
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="e.g. COM5 or /dev/tty.usbmodem1101")
    ap.add_argument("--arm", action="store_true", help="send `arm` first (needed for sweep/step/laser)")
    ap.add_argument("--timeout", type=float, default=120.0, help="give up after this many seconds")
    ap.add_argument("--out", default="runs", help="parent folder for run folders")
    cond = ap.add_argument_group("test conditions (saved with the run and in run_log.csv)")
    cond.add_argument("--nd", default="", help="ND filter on the laser, e.g. 0, 0.5, 1.0")
    cond.add_argument("--distance", default="", help="target distance from the camera, mm")
    cond.add_argument("--ambient", default="", help="room light, e.g. off / on")
    cond.add_argument("--target", default="", help="what was scanned, e.g. flat-board, steps")
    cond.add_argument("--by", default="", help="who ran it")
    cond.add_argument("--note", default="", help="anything unusual about this run")
    ap.add_argument("command", nargs="+", help="command for the board, e.g. sweep 1300 1700 2000")
    args = ap.parse_args()

    import serial  # imported here so the parser can be used without pyserial installed

    cmd = " ".join(args.command).strip().lower()
    verb = cmd.split()[0]
    start = dt.datetime.now().astimezone()          # local date-time with UTC offset
    stamp = start.strftime("%Y%m%d_%H%M%S")
    outdir = pathlib.Path(args.out) / f"{stamp}_{cmd.replace(' ', '_')}"
    conditions = {"nd": args.nd, "distance_mm": args.distance, "ambient": args.ambient,
                  "target": args.target, "by": args.by}
    if verb in RUN_COMMANDS:
        missing = [k for k in ("nd", "distance_mm", "ambient", "target") if not conditions[k]]
        if missing:
            print(f"note: no {', '.join(missing)} given - the run log will have blanks there")

    raw, banner = [], []
    ser = serial.Serial(args.port, 115200, timeout=0.05)
    t_host0 = time.time()

    def readline():
        b = ser.readline()
        if not b:
            return None
        line = b.decode(errors="replace").rstrip("\r\n")
        raw.append((time.time() - t_host0, line))
        return line

    def send(text):
        ser.write((text + "\n").encode())
        raw.append((time.time() - t_host0, f">> {text}"))

    def wait_for(prefixes, seconds):
        t_end = time.time() + seconds
        while time.time() < t_end:
            line = readline()
            if line is None:
                continue
            if line.startswith("#"):
                banner.append(line)
            if line.startswith(prefixes):
                return line
        return None

    # Opening the port resets a classic UNO (its bootloader takes ~2 s), so wait,
    # then drain the banner text before sending anything.
    time.sleep(2.0)
    t_end = time.time() + 1.0
    while time.time() < t_end:
        line = readline()
        if line and line.startswith("#"):
            banner.append(line)

    meta = {"command": cmd, "port": args.port, "armed_by_logger": args.arm,
            "host_start": start.isoformat(timespec="seconds"), "conditions": conditions,
            "note": args.note, "banner": banner}

    try:
        if args.arm:
            send("arm")
            r = wait_for(("OK armed", "ERR"), 3)
            print(f"arm: {r}")
            if not r or r.startswith("ERR"):
                sys.exit(1)

        send(cmd)
        print(f"sent: {cmd}")
        result = None
        t_end = time.time() + args.timeout
        while time.time() < t_end:
            line = readline()
            if line is None:
                continue
            if line.startswith("ERR"):
                result = line
                break
            if verb in RUN_COMMANDS:
                f = line.split(",")
                if f[0] == "E" and len(f) > 2 and f[2] in END_EVENTS:
                    result = f[2]
                    break
            elif line.startswith("OK"):
                result = line
                break
        else:
            result = "TIMEOUT"
            send("stop")
        print(f"result: {result}")
        meta["result"] = result

    except KeyboardInterrupt:
        print("\ninterrupted - sending stop")
        send("stop")
        t_end = time.time() + 1.0
        while time.time() < t_end:
            readline()
        meta["result"] = "INTERRUPTED"
    finally:
        # Local integration: never leave a manual laser or servo session active.
        # Capture explicit off/disarm telemetry before releasing the serial port.
        if verb == "move" and meta.get("result", "").startswith("OK move"):
            # OK move acknowledges pulse slew, not physical arrival.
            time.sleep(0.5)
            send("status")
            wait_for(("OK status", "ERR"), 1)
            send("read 100")
            wait_for(("OK read", "ERR"), 1)
        send("stop")
        stopped = wait_for(("OK stopped", "ERR"), 1)
        send("status")
        final_status = wait_for(("OK status", "ERR"), 1)
        meta["stop_confirmed"] = bool(stopped and final_status and
            "armed=0" in final_status and "laser=0" in final_status)
        ser.close()
        samples, events = save_run(outdir, raw, meta)
        end = dt.datetime.now().astimezone()
        summ = run_summary(samples, events)
        toks = cmd.split()
        sweep = toks[1:4] if verb == "sweep" and len(toks) == 4 else ["", "", ""]
        firmware = next((b.lstrip("# ").strip() for b in banner if "scanner_controller" in b), "")
        meta.update({"host_end": end.isoformat(timespec="seconds"),
                     "duration_s": round((end - start).total_seconds(), 2),
                     "firmware": firmware, "git_commit": git_commit(), **summ})
        (outdir / "meta.json").write_text(json.dumps(meta, indent=2))
        log_path = pathlib.Path(args.out) / "run_log.csv"
        logged = append_run_log(log_path, {
            "run_id": outdir.name, "started": meta["host_start"], "finished": meta["host_end"],
            "duration_s": meta["duration_s"], "command": cmd, "result": meta.get("result", ""),
            "sweep_start_us": sweep[0], "sweep_end_us": sweep[1], "sweep_ms": sweep[2],
            **conditions, **summ, "firmware": firmware, "git_commit": meta["git_commit"],
            "folder": str(outdir), "note": args.note})
        print(f"saved {outdir}")
        if logged:
            print(f"logged in {log_path}")
        summarise(samples, events)


if __name__ == "__main__":
    main()

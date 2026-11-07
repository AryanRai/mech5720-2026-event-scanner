> **Historical upstream notes.** Current measured interpretation and build status are in [docs/BUILD.md](../../docs/BUILD.md). Nominal ADC/PWM-to-degree statements below are not physical calibration; proposed R4/transistor hardware is not proof of the installed R3-type/eBay/D7 arrangement.

# Scanner controller: servo + laser firmware

MECH5720 2026, Event-Based Structured-Light 3D Scanner. Microcontroller part.

The Arduino UNO R4 Minima sweeps the line laser with the servo, records the servo's true angle from its analogue feedback, switches the laser through a transistor behind an interlock, and streams everything with microsecond timestamps over USB.

```
scanner_controller/scanner_controller.ino   Arduino sketch
host/scan_logger.py                         sends a command, saves the run to CSV
dashboard/scanner_dashboard.html            manual control: move the servo, laser on/off, test sweeps
```

## Current rig wiring: UNO clone + DFRobot 270Â° feedback servo (DMS-MG90-A) + MXD1230 line laser

`HAS_FEEDBACK 1` (the default now). About 0.135Â° per Âµs, centre at 1500 Âµs. Diagram: `wiring.png`.

| Wire | Goes to |
|---|---|
| Servo **red** (+) | 5V for bench tests, or an external 5 V supply (see below) |
| Servo **black** (âˆ’) | GND |
| Servo **white** (signal) | **D9** |
| Servo **brown** (feedback, 0â€“3.3 V) | **A0** |
| Laser **red** (+) | **D7** for bench tests, or external +5 V through the transistor switch (see "Wiring for the real rig") |
| Laser **black** (âˆ’) | GND |
| Jumper or enclosure switch | **D2 â†’ GND** |
| 470â€“1000 ÂµF capacitor | across servo + and âˆ’ (long leg to +) |

On the UNO R3 the 0â€“3.3 V feedback covers about 675 of the 1024 ADC counts, so the sketch sums 16 reads and divides by 4: the `adc` column runs about 0â€“2700 (~10 counts per degree).

If the board resets or disconnects when the servo moves, the USB can't supply the servo's current: power the servo from a separate 5 V supply and join its GND to the Arduino GND.

## Bench test wiring: UNO R3 clone + SG90 + KY-008

For testing the code with the parts on hand. `HAS_FEEDBACK` is `0` by default, which suits the SG90.

| Part | Pin | Arduino |
|---|---|---|
| SG90 brown | GND | GND |
| SG90 red | +5 V | 5V |
| SG90 orange | signal | **D9** |
| KY-008 **âˆ’** | GND | GND |
| KY-008 **S** | signal | **D7** |
| KY-008 middle | not needed | leave unconnected; tie to 5V only if the laser won't fire |
| Jumper | interlock | **D2 â†’ GND** (otherwise `arm` is refused) |

The KY-008 is a 5 mW **Class 3R dot** laser. Never look into it or point it at anyone, and watch for reflections. It draws up to about 40 mA straight from D7, which is near the pin's limit: fine for short tests, use the transistor below for the real rig.

On Windows or macOS the clone's CH340 USB chip may need a driver. In the IDE pick **Tools â†’ Board â†’ Arduino Uno**.

## Wiring for the real rig

| From | To | Notes |
|---|---|---|
| Servo signal | **D9** | Check the label on your servo for wire colours |
| Servo feedback (4th wire) | **A0** | 0â€“3.3 V, safe for the 5 V ADC |
| Servo + | Plugpack **+5 V** | Never from the Arduino 5 V pin. Stall current is about 0.8 A |
| Servo âˆ’ | Plugpack **GND** | |
| Plugpack GND | Arduino **GND** | **Common ground is required.** Without it the feedback reading is meaningless |
| D7 â†’ 1 kÎ© â†’ transistor base | | NPN such as 2N2222 or BC337 |
| Transistor base â†’ 10 kÎ© â†’ GND | | Pull-down: keeps the laser **off** while the board resets |
| Emitter â†’ GND, collector â†’ laser âˆ’ | | Low-side switch |
| Laser + â†’ plugpack +5 V | | Module is rated 3â€“12 V. Check its current spec |
| **D2** â†’ interlock switch â†’ GND | | Switch closed = enclosure shut = laser allowed. For bench tests a jumper to GND will do |
| D8 (optional) | scope / DAVIS sync | HIGH during a run. **The R4 outputs 5 V:** check the DAVIS sync input's voltage before connecting |
| 470â€“1000 ÂµF capacitor | across plugpack +5 V / GND near the servo | Stops servo current spikes from browning out the rail |

Do not connect the plugpack +5 V to the Arduino's 5 V pin. The Arduino is powered from the laptop USB only.

## Setup

1. Library Manager â†’ **Servo**. For the UNO R4 also install **Arduino UNO R4 Boards** in Boards Manager; a classic UNO needs nothing extra.
   With a feedback servo (SER0046 on A0), change `#define HAS_FEEDBACK 0` to `1`.
2. Open `scanner_controller.ino`. **Set the limits at the top for your frame first:**
   - `SERVO_MIN_US` / `SERVO_MAX_US`: the furthest the cradle may ever go (about 0.135Â° per Âµs)
   - `LASER_MIN_US` / `LASER_MAX_US`: the range where the beam is guaranteed to hit the beam stop
3. Upload. At power-up the servo moves to 1500 Âµs (`PARK_US`). Keep fingers clear.
4. Host: `pip install pyserial`.

## Commands

Send these from the Serial Monitor (newline ending) or through `scan_logger.py`. They are case-insensitive.

| Command | What it does |
|---|---|
| `arm` / `disarm` | Allow or forbid the laser. Needs the interlock closed |
| `sweep <start_us> <end_us> <ms>` | **Main experiment.** Continuous upward sweep with the laser on |
| `step <start_us> <end_us> <n> <on_ms> <off_ms>` | **Fallback.** Goes to n angles, settles at each, pulses the laser |
| `goto <us>` | Approach from below, settle, report the feedback. Used for angle calibration with planar targets |
| `move <us>` | Manual jog: slew straight to the target, no pre-roll (used by the dashboard nudges) |
| `read [n]` | Mean and standard deviation of n feedback reads. Used to measure ADC noise |
| `laser on` / `laser off` | Manual, for alignment. Switches itself off after 60 s |
| `park`, `status`, `help` | |
| `stop` | Abort anything, laser off, **disarm** |

A typical session:

```
python host/scan_logger.py --port COM5 status
python host/scan_logger.py --port COM5 goto 1500
python host/scan_logger.py --port COM5 --arm sweep 1300 1700 2000 --nd 0.5 --distance 400 --ambient off --target steps --by Kailas
python host/scan_logger.py --port COM5 --arm step 1300 1700 9 200 200
```

Each run is saved to `runs/<YYYYmmdd_HHMMSS>_<command>/` as `raw.log`, `samples.csv`, `events.csv` and `meta.json`.

### Run log

Every run also adds one row to `runs/run_log.csv`, the master log you can open in Excel. It records:

- start and end date-time from the laptop, with time zone (e.g. `2026-11-02T10:14:51+11:00`), and duration
- command, sweep start/end/duration, and result (`DONE`, `ABORTED`, `ERR ...`, `INTERRUPTED`)
- test conditions: `--nd`, `--distance` (mm), `--ambient`, `--target`, `--by`, `--note`
- sample and event counts, the first laser ON and last laser OFF times (Arduino Âµs, for the clock sync)
- firmware version and git commit, and the run's folder

The Arduino has no clock, so the date and time come from the laptop. Inside a run, the Arduino's `micros()` is still the precise timeline. If you forget the conditions on a sweep, the logger warns you but still runs. Close `run_log.csv` in Excel before a run; if it is open, the run is still saved and the logger tells you the row was skipped.

## Dashboard (manual control)

Open `dashboard/scanner_dashboard.html` in **Chrome or Edge** (double-click it, or drag it into the browser). Nothing to install, so you can copy the file to any Windows laptop.

1. Close the Arduino Serial Monitor and anything else using the port, then click **Connect Arduino** and pick the board.
2. Put the DV viewer on the other half of the screen.
3. **Arm**, then **Laser ON** (only inside the laser window, auto-off after 60 s).
4. Nudge with the buttons or arrow keys (10 Âµs, Shift = 50 Âµs; tick **Flip +/- direction** if + moves the line the wrong way) until the line sits where you want it in the DV view. **Mark** the position.
5. Use marks as sweep start/end, run a **test sweep**, then copy the `scan_logger.py` command for the real recorded run. Click **Disconnect** before running the logger.

**STOP** or `Esc` = laser off, disarm, servo released. **Download log** saves everything from the session with date and time. Marks are saved in that browser only.

## Output format

```
S,t_us,cmd_us,adc,laser       feedback sample, 500 Hz during runs
E,t_us,name,a,b,c             event (LASER_ON, SWEEP_START, STEP, DONE, ...)
OK ... / ERR ... / # ...      replies, errors, comments
```

All timestamps come from the Arduino's `micros()`. The host receive time in `raw.log` is for bookkeeping only, because USB adds milliseconds of jitter.

## How a sweep runs, and why

1. **Approach from below.** The servo goes to `start âˆ’ 60 Âµs`, settles, then comes up to `start` and settles again. Every target is reached in the same direction, so gear backlash is always taken up the same way.
2. **Marker 1.** The laser switches **on while the servo is stationary.** The DAVIS sees a sharp burst of ON events, and the Arduino logs the exact `micros()` of the switch.
3. **Sweep.** The command ramps linearly from start to end and changes whenever it moves by 1 Âµs, giving the dense monotonic ramp from the pitch. Feedback is logged at 500 Hz.
4. **Marker 2.** The laser switches **off while stationary** at the end.

### Aligning the Arduino and DAVIS clocks

The two boards' clocks have different zero points and run at slightly different rates. Use both markers:

```python
from scan_logger import clock_map
# Arduino times from events.csv; DAVIS times = the matching ON / OFF event bursts
to_davis = clock_map(a_on_us, d_on_us, a_off_us, d_off_us)
davis_t = to_davis(sample_t_us)        # put every servo sample on the DAVIS timeline
```

This corrects offset and drift with no extra wiring. D8 is there if you'd rather also wire a hardware sync.

## Safety

- The laser is **off at boot**: the pin is driven LOW first, and the 10 kÎ© pull-down covers the reset period.
- It can only be on when **armed + interlock closed + servo inside the laser window**. This is checked continuously.
- If any condition fails during a run, the laser is forced off (`SAFETY_OFF`) and the run is marked `ABORTED`.
- Opening the interlock **disarms**: you must send `arm` again.
- `stop` and Ctrl+C in the logger both kill the laser and disarm.

## Tuning constants

| Constant | Default | Notes |
|---|---|---|
| `SAMPLE_PERIOD_US` | 2000 (500 Hz) | Plenty for a servo. Raise it if the serial link can't keep up |
| `PREROLL_US` | 60 (~8Â°) | Backlash approach distance |
| `SETTLE_TOL_COUNTS` | 20 | 14-bit ADC on a 5 V reference: 0â€“3.3 V spans about 0â€“10,800 counts. If that covers 270Â° linearly, 1Â° â‰ˆ 40 counts. Measure your noise with `read 1000` and set this to about 4Ã— the std |
| `HOLD_MS` | 150 | Stationary hold around each marker |

## Known limitations (worth putting in the report)

- **The servo moves in small steps, not smoothly.** Its dead band is up to 5 Âµs (about 0.7Â°), and the Servo library only updates the pulse every 20 ms. A 1 Âµs command ramp therefore produces small position steps. The feedback log records the true motion, which is why calibration should use **feedback, not command**.
- **The feedback-to-angle mapping is not in the datasheet.** Calibrate it with planar targets, as the pitch says. The firmware reports raw ADC counts on purpose.
- The datasheet quotes about 0.12 s per 60Â° at no load, so very fast sweeps will lag the command. The `cmd_us` vs `adc` columns show by how much.

## Testing done

v1.1 compiles for the UNO R3 (ATmega328P) with the official Arduino AVR core: 43% of flash and 26% of RAM without feedback, 51% and 27% with it. The UNO R4 build is untested.


The sketch was compiled on a PC against a stand-in for the Arduino libraries and run with a simulated servo, laser, interlock and serial port. 33 checks passed: markers bracket the sweep, the ramp is monotonic, 500 Hz sampling, the laser never on outside its window, refusal when unarmed, `stop` aborts and disarms, opening the interlock mid-sweep forces the laser off, step mode, backlash approach, manual-laser timeout, and command parsing. The logger was tested end to end on a virtual serial port.

It has not been run on hardware yet. Test with the laser module unplugged first.

/*
  MECH5720 2026 - Event-Based Structured-Light 3D Scanner
  Servo + laser controller. Runs on an Arduino UNO R3 (or clone) and the UNO R4 Minima.

  - Drives a hobby servo: SG90 (3-wire, no feedback) or DFRobot SER0046 (4-wire, analogue feedback)
  - With a feedback servo, samples analogue feedback on A0 and timestamps every sample (not calibrated angle)
  - Switches the laser (directly or through a transistor), behind a software + hardware interlock
  - Streams everything over USB serial for the host logger (host/scan_logger.py)

  Wiring, commands and output format: see README.md.
*/

#include <Servo.h>

// ===================== Hardware variant =====================
// 0 = plain 3-wire servo such as the SG90: no feedback, angle is taken from the command.
// 1 = servo with an analogue feedback wire on A0, such as the DFRobot SER0046.
#ifndef HAS_FEEDBACK
#define HAS_FEEDBACK 1   // DFRobot 270Â° feedback servo (DMS-MG90-A): brown wire on A0
#endif

// ============================== Pins ==============================
const uint8_t PIN_SERVO     = 9;    // servo signal
const uint8_t PIN_FEEDBACK  = A0;   // servo analogue feedback (0-3.3 V)
const uint8_t PIN_LASER     = 7;    // transistor base/gate: HIGH = laser on
const uint8_t PIN_INTERLOCK = 2;    // switch to GND when the enclosure is closed
const uint8_t PIN_SYNC      = 8;    // optional: HIGH while a sweep/step run is active
const uint8_t PIN_STATUS    = LED_BUILTIN;  // mirrors the laser state

// ===================== Limits - SET FOR YOUR FRAME =====================
// Servo command limits in microseconds. About 0.1 deg per us on an SG90
// (0.135 on the SER0046), so 900-2100 us is roughly 115-160 deg.
// Narrow these to what your cradle can safely reach.
const int SERVO_MIN_US = 900;
const int SERVO_MAX_US = 2100;
// The laser may only be on while the servo command is inside this window,
// i.e. while the beam is guaranteed to land inside the enclosure / on the beam stop.
const int LASER_MIN_US = 1100;
const int LASER_MAX_US = 1900;
const int PARK_US      = 1500;      // where the servo goes at power-up and after `park`

// ============================== Timing ==============================
#if defined(ARDUINO_ARCH_AVR)
const uint32_t SAMPLE_PERIOD_US    = 5000;   // 200 Hz: a classic UNO's 115200-baud serial can't carry more
#else
const uint32_t SAMPLE_PERIOD_US    = 2000;   // 500 Hz on the UNO R4 (native USB)
#endif
#if defined(ARDUINO_ARCH_AVR)
// Classic UNO: 10-bit ADC, and the 0-3.3 V feedback only spans ~675 counts (~2.5 per degree).
// Sum 16 reads and divide by 4: noise dithers the result to ~4x finer steps (0-2700, ~10 per degree).
const uint8_t  ADC_OVERSAMPLE      = 16;
const uint8_t  ADC_DIVIDE          = 4;
const int      SETTLE_TOL_COUNTS   = 12;     // ~1.2 degrees on the UNO R3
#else
const uint8_t  ADC_OVERSAMPLE      = 4;      // analogRead()s averaged per sample
const uint8_t  ADC_DIVIDE          = 4;
const int      SETTLE_TOL_COUNTS   = 20;     // UNO R4, 14-bit (see README)
#endif
const int      PREROLL_US          = 60;     // approach every target from below by ~8 deg (backlash)
const int      SLEW_US_PER_S       = 800;    // speed for non-measurement moves (~108 deg/s)
const uint32_t SETTLE_WINDOW_MS    = 60;     // feedback must stay steady this long, within SETTLE_TOL_COUNTS
const uint32_t SETTLE_TIMEOUT_MS   = 2000;
const uint32_t NOFB_SETTLE_MS      = 400;    // without feedback: just wait this long after a move
const uint32_t HOLD_MS             = 150;    // stationary hold before/after a sweep (sync markers)
const uint32_t MANUAL_LASER_MAX_MS = 60000;  // `laser on` switches itself off after this

// ============================== State ==============================
Servo servo;
int      currentCmd   = PARK_US;
bool     armed        = false;
bool     laserOn      = false;
bool     manualLaser  = false;
uint32_t manualSince  = 0;
bool     busy         = false;   // a sweep/step/goto is running
bool     abortRun     = false;
String   rxLine;

// ============================== Helpers ==============================
int clampCmd(int us) {
  if (us < SERVO_MIN_US) return SERVO_MIN_US;
  if (us > SERVO_MAX_US) return SERVO_MAX_US;
  return us;
}

uint16_t readFeedback() {
#if !HAS_FEEDBACK
  return 0;                                    // no feedback wire: logged as 0
#endif
  uint32_t sum = 0;
  for (uint8_t i = 0; i < ADC_OVERSAMPLE; i++) sum += analogRead(PIN_FEEDBACK);
  return (uint16_t)(sum / ADC_DIVIDE);
}

bool interlockClosed() { return digitalRead(PIN_INTERLOCK) == LOW; }
bool inLaserWindow(int us) { return us >= LASER_MIN_US && us <= LASER_MAX_US; }

// Why the laser is not allowed right now, or nullptr if it is.
const char *laserBlockReason() {
  if (!armed)                      return "not armed (send: arm)";
  if (!interlockClosed())          return "interlock open";
  if (!inLaserWindow(currentCmd))  return "servo outside laser window";
  return nullptr;
}

void logEvent(uint32_t t, const char *name, long a = 0, long b = 0, long c = 0) {
  Serial.print(F("E,")); Serial.print(t);       Serial.print(',');
  Serial.print(name);    Serial.print(',');     Serial.print(a);
  Serial.print(',');     Serial.print(b);       Serial.print(',');
  Serial.println(c);
}

void logSample(uint32_t t, uint16_t adc) {
  Serial.print(F("S,")); Serial.print(t);          Serial.print(',');
  Serial.print(currentCmd); Serial.print(',');     Serial.print(adc);
  Serial.print(',');     Serial.println(laserOn ? 1 : 0);
}

// Physically switch the laser and timestamp the switch as tightly as possible.
void writeLaser(bool on, const char *eventName) {
  if (on == laserOn) return;
  digitalWrite(PIN_LASER, on ? HIGH : LOW);
  uint32_t t = micros();            // marker time: right after the pin changes
  laserOn = on;
  digitalWrite(PIN_STATUS, on ? HIGH : LOW);
  logEvent(t, eventName, currentCmd);
}

// Turn the laser on only if every safety condition holds. Returns false if blocked.
bool laserRequest(bool on) {
  if (!on) { writeLaser(false, "LASER_OFF"); return true; }
  const char *why = laserBlockReason();
  if (why) {
    Serial.print(F("ERR laser blocked: ")); Serial.println(why);
    return false;
  }
  writeLaser(true, "LASER_ON");
  return true;
}

// Called continuously: kills the laser the moment any condition fails.
void safetyCheck() {
  if (laserOn && laserBlockReason()) {
    const char *why = laserBlockReason();
    writeLaser(false, "SAFETY_OFF");
    manualLaser = false;
    if (busy) abortRun = true;                  // a run that lost its laser is invalid
    Serial.print(F("# WARN laser forced off: ")); Serial.println(why);
  }
  if (armed && !interlockClosed()) {            // opening the enclosure disarms
    armed = false;
    logEvent(micros(), "INTERLOCK_OPEN");
  }
  if (manualLaser && laserOn && millis() - manualSince > MANUAL_LASER_MAX_MS) {
    writeLaser(false, "LASER_TIMEOUT");
    manualLaser = false;
  }
}

// Move the servo command. Turns the laser off first if the move leaves the laser window.
void moveCmd(int us) {
  us = clampCmd(us);
  if (laserOn && !inLaserWindow(us)) writeLaser(false, "SAFETY_OFF");
  currentCmd = us;
  if (!servo.attached()) servo.attach(PIN_SERVO, 500, 2400);  // re-attach after `stop`
  servo.writeMicroseconds(us);
}

// Non-blocking line reader for USB serial.
bool readLine(String &out) {
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') { out = rxLine; rxLine = ""; return true; }
    if (rxLine.length() < 80) rxLine += ch;
  }
  return false;
}

// `stop`: laser off, disarm, abort, and stop sending servo pulses so the servo
// goes limp (a continuous-rotation servo would otherwise keep spinning).
// The next move command re-attaches it.
void emergencyStop();

void hardStop() {
  abortRun = true;
  manualLaser = false;
  writeLaser(false, "LASER_OFF");
  armed = false;
  digitalWrite(PIN_SYNC, LOW);
}

void emergencyStop() {
  hardStop();
  servo.detach();
  logEvent(micros(), "SERVO_RELEASED", currentCmd);
}

// Called inside every long-running loop: safety, plus listen for `stop`.
void serviceRun() {
  safetyCheck();
  String line;
  if (readLine(line)) {
    line.trim(); line.toLowerCase();
    if (line == "stop" || line == "s") { emergencyStop(); Serial.println(F("OK stopped, disarmed, servo released")); }
    else Serial.println(F("ERR busy - send stop first"));
  }
}

// Slew to a target at SLEW_US_PER_S in 1 us steps (gentle on the mount).
void slewTo(int target) {
  target = clampCmd(target);
  if (!servo.attached()) moveCmd(currentCmd);   // after `stop`: hold again even if already at the target
  const uint32_t stepPeriod = 1000000UL / SLEW_US_PER_S;
  uint32_t last = micros();
  while (currentCmd != target && !abortRun) {
    serviceRun();
    uint32_t now = micros();
    if (now - last >= stepPeriod) {
      last = now;
      moveCmd(currentCmd + (target > currentCmd ? 1 : -1));
    }
  }
}

// Wait until the feedback stops changing. Returns the mean ADC over the steady window.
// On timeout it still returns the mean so far, but logs SETTLE_TIMEOUT.
long waitSettled() {
#if !HAS_FEEDBACK
  const uint32_t t0 = millis();                // no way to measure: wait a fixed time
  while (!abortRun && millis() - t0 < NOFB_SETTLE_MS) serviceRun();
  return -1;
#endif
  const uint32_t start = millis();
  uint32_t winStart = millis(), sum = 0, n = 0;
  uint16_t lo = 65535, hi = 0;
  while (!abortRun) {
    serviceRun();
    uint16_t v = readFeedback();
    if (v < lo) lo = v;
    if (v > hi) hi = v;
    sum += v; n++;
    if (hi - lo > SETTLE_TOL_COUNTS) {          // still moving: restart the window
      lo = hi = v; sum = v; n = 1; winStart = millis();
    } else if (millis() - winStart >= SETTLE_WINDOW_MS) {
      return (long)(sum / n);
    }
    if (millis() - start > SETTLE_TIMEOUT_MS) {
      logEvent(micros(), "SETTLE_TIMEOUT", currentCmd, hi - lo);
      return n ? (long)(sum / n) : -1;
    }
    delayMicroseconds(500);
  }
  return -1;
}

// Always arrive at a target from below, so gear backlash is taken up the same way every time.
long approach(int target) {
  target = clampCmd(target);
  slewTo(target - PREROLL_US);
  if (abortRun) return -1;
  waitSettled();
  slewTo(target);
  if (abortRun) return -1;
  return waitSettled();
}

// Hold still for `ms` while logging feedback samples.
void holdAndLog(uint32_t ms) {
  const uint32_t t0 = micros();
  uint32_t nextSample = t0;
  while (!abortRun && (micros() - t0) < ms * 1000UL) {
    serviceRun();
    uint32_t now = micros();
    if ((int32_t)(now - nextSample) >= 0) {
      nextSample += SAMPLE_PERIOD_US;
      logSample(now, readFeedback());
    }
  }
}

bool cmdRangeOK(int a, int b) {
  if (a >= b) { Serial.println(F("ERR start must be below end (sweeps run upward only)")); return false; }
  if (a < LASER_MIN_US || b > LASER_MAX_US) {
    Serial.print(F("ERR range must lie inside the laser window "));
    Serial.print(LASER_MIN_US); Serial.print('-'); Serial.println(LASER_MAX_US);
    return false;
  }
  return true;
}

// ============================== Runs ==============================

// Continuous sweep: the primary experiment.
// Laser switches ON at the start and OFF at the end while the servo is stationary,
// giving two sharp event bursts that align the Arduino and DAVIS clocks.
void runSweep(int startUs, int endUs, uint32_t durMs) {
  if (!cmdRangeOK(startUs, endUs)) return;
  if (durMs < 100) { Serial.println(F("ERR duration must be >= 100 ms")); return; }
  const char *why = laserBlockReason();
  if (why && strcmp(why, "servo outside laser window") != 0) {
    Serial.print(F("ERR laser blocked: ")); Serial.println(why); return;
  }

  busy = true; abortRun = false;
  manualLaser = false;
  writeLaser(false, "LASER_OFF");   // ON marker must be a real transition
  Serial.println(F("OK sweep"));
  logEvent(micros(), "SWEEP_PARAMS", startUs, endUs, durMs);

  long fb0 = approach(startUs);
  logEvent(micros(), "SETTLED", currentCmd, fb0);

  digitalWrite(PIN_SYNC, HIGH);
  if (!abortRun && laserRequest(true)) {          // marker 1
    holdAndLog(HOLD_MS);

    const uint32_t t0 = micros();
    const uint32_t durUs = durMs * 1000UL;
    uint32_t nextSample = t0;
    logEvent(t0, "SWEEP_START", startUs, endUs, durMs);

    while (!abortRun) {
      serviceRun();
      const uint32_t now = micros();
      const uint32_t elapsed = now - t0;
      if (elapsed >= durUs) break;
      // Dense monotonic ramp: the command changes whenever it moves by >= 1 us.
      int cmd = startUs + (int)(((int64_t)(endUs - startUs) * elapsed) / durUs);
      if (cmd != currentCmd) moveCmd(cmd);
      if ((int32_t)(now - nextSample) >= 0) {
        nextSample += SAMPLE_PERIOD_US;
        logSample(now, readFeedback());
      }
    }
    if (!abortRun) {
      moveCmd(endUs);
      logEvent(micros(), "SWEEP_END", endUs);
      holdAndLog(HOLD_MS);
    }
  } else {
    abortRun = true;
  }
  writeLaser(false, "LASER_OFF");                 // marker 2
  digitalWrite(PIN_SYNC, LOW);
  logEvent(micros(), abortRun ? "ABORTED" : "DONE");
  busy = false;
}

// Fallback: stop-and-pulse. Go to each calibrated angle, settle, then pulse the laser.
void runStep(int startUs, int endUs, int n, uint32_t onMs, uint32_t offMs) {
  if (!cmdRangeOK(startUs, endUs)) return;
  if (n < 2 || n > 500) { Serial.println(F("ERR n must be 2-500")); return; }
  const char *why = laserBlockReason();
  if (why && strcmp(why, "servo outside laser window") != 0) {
    Serial.print(F("ERR laser blocked: ")); Serial.println(why); return;
  }

  busy = true; abortRun = false;
  manualLaser = false;
  writeLaser(false, "LASER_OFF");   // ON marker must be a real transition
  Serial.println(F("OK step"));
  logEvent(micros(), "STEP_PARAMS", startUs, endUs, n);
  digitalWrite(PIN_SYNC, HIGH);

  for (int k = 0; k < n && !abortRun; k++) {
    int target = startUs + (int)(((long)(endUs - startUs) * k) / (n - 1));
    long fb = approach(target);
    if (abortRun) break;
    logEvent(micros(), "STEP", k, target, fb);
    holdAndLog(offMs);                            // dark, stationary
    if (!laserRequest(true)) { abortRun = true; break; }
    holdAndLog(onMs);                             // lit, stationary: the event burst
    writeLaser(false, "LASER_OFF");
  }

  writeLaser(false, "LASER_OFF");
  digitalWrite(PIN_SYNC, LOW);
  logEvent(micros(), abortRun ? "ABORTED" : "DONE");
  busy = false;
}

// Manual jog for the dashboard: slew straight to the target, no backlash pre-roll,
// so a small step down really moves down. Use `goto` when repeatability matters.
void runMove(int target) {
  busy = true; abortRun = false;
  slewTo(target);
  busy = false;
  Serial.print(F("OK move ")); Serial.println(currentCmd);
}

// Go to an angle and report the settled feedback (for angle calibration).
void runGoto(int target) {
  busy = true; abortRun = false;
  long fb = approach(target);
  logEvent(micros(), "SETTLED", currentCmd, fb);
  Serial.print(F("OK goto ")); Serial.print(currentCmd);
  Serial.print(F(" feedback ")); Serial.println(fb);
  busy = false;
}

// Average many feedback readings and report mean and standard deviation.
void runRead(int n) {
#if !HAS_FEEDBACK
  Serial.println(F("ERR this servo has no feedback wire (HAS_FEEDBACK 0)"));
  return;
#endif
  if (n < 1) n = 256;
  double sum = 0, sum2 = 0;
  for (int i = 0; i < n; i++) {
    double v = analogRead(PIN_FEEDBACK);
    sum += v; sum2 += v * v;
    delayMicroseconds(200);
  }
  double mean = sum / n;
  double var = sum2 / n - mean * mean;
  Serial.print(F("OK read cmd ")); Serial.print(currentCmd);
  Serial.print(F(" mean ")); Serial.print(mean, 1);
  Serial.print(F(" std ")); Serial.print(var > 0 ? sqrt(var) : 0.0, 2);
  Serial.print(F(" n ")); Serial.println(n);
}

// Laser-off diagnostic only. A controller-local deadline also bounds USB loss.
// F timestamps bracket the ADC block; raw_first and sum describe the SAME block.
const uint32_t PROBE_PERIOD_US = 10000;  // 100 Hz, within AVR serial capacity
const uint32_t PROBE_DEADLINE_US = 8000000UL;
uint32_t probeStart, probeNext;

void probeTick() {
  serviceRun();
  if ((uint32_t)(micros() - probeStart) >= PROBE_DEADLINE_US || armed || laserOn)
    abortRun = true;
  if (abortRun) return;
  uint32_t now = micros();
  if ((int32_t)(now - probeNext) < 0) return;
  probeNext = now + PROBE_PERIOD_US;  // skip missed slots, never catch-up bursts
  uint32_t sum = 0;
  uint16_t first = 0;
  for (uint8_t i = 0; i < ADC_OVERSAMPLE; i++) {
    uint16_t v = analogRead(PIN_FEEDBACK);
    if (!i) first = v;
    sum += v;
  }
  uint32_t end = micros();
  Serial.print(F("F,")); Serial.print(now); Serial.print(','); Serial.print(end);
  Serial.print(','); Serial.print(currentCmd);
  Serial.print(','); Serial.print(first);
  Serial.print(','); Serial.print(sum);
  Serial.print(','); Serial.print(ADC_OVERSAMPLE);
  Serial.print(','); Serial.print(ADC_DIVIDE);
  Serial.print(','); Serial.print(servo.attached() ? 1 : 0);
  Serial.print(','); Serial.println(laserOn ? 1 : 0);
}

void probeHold(uint32_t ms) {
  const uint32_t start = micros();
  while (!abortRun && (uint32_t)(micros() - start) < ms * 1000UL) probeTick();
}

void probeSlew(int target) {
  if (!servo.attached()) moveCmd(currentCmd);
  uint32_t last = micros();
  while (!abortRun && currentCmd != target) {
    probeTick();
    if (abortRun) break;
    uint32_t now = micros();
    if ((uint32_t)(now - last) >= 1000000UL / SLEW_US_PER_S) {
      last = now;
      moveCmd(currentCmd + (target > currentCmd ? 1 : -1));
    }
  }
}

void runProbe(int source, int target, uint32_t holdMs) {
  // Reject rather than clamp. Include initial reattach/slew in cleared travel.
  if (!HAS_FEEDBACK || source < 1100 || source > 1900 || target < 1100 || target > 1900 ||
      currentCmd < 1100 || currentCmd > 1900 || holdMs < 100 || holdMs > 3000) {
    Serial.println(F("ERR probe bounds/feedback: 1100-1900 us, 100-3000 ms")); return;
  }
  emergencyStop();
  abortRun = false; busy = true;
  probeStart = probeNext = micros();
  Serial.println(F("OK probe"));
  logEvent(micros(), "PROBE_RELEASED", currentCmd, source, target);
  probeHold(500);
  if (!abortRun) {
    logEvent(micros(), "PROBE_SOURCE_RAMP", source);
    probeSlew(source);
  }
  if (!abortRun) {
    logEvent(micros(), "PROBE_SOURCE_HOLD", currentCmd);
    probeHold(500);
  }
  if (!abortRun) {
    logEvent(micros(), "PROBE_TARGET_RAMP", source, target);
    probeSlew(target);
  }
  if (!abortRun) {
    logEvent(micros(), "PROBE_TARGET_HOLD", currentCmd, holdMs);
    probeHold(holdMs);
  }
  const bool failed = abortRun;
  emergencyStop();  // release independently of browser cleanup, including USB loss
  logEvent(micros(), failed ? "PROBE_ABORTED" : "PROBE_DONE", currentCmd);
  busy = false;
}

void printStatus() {
  Serial.print(F("OK status armed=")); Serial.print(armed);
  Serial.print(F(" interlock=")); Serial.print(interlockClosed() ? F("closed") : F("OPEN"));
  Serial.print(F(" laser=")); Serial.print(laserOn);
  Serial.print(F(" cmd=")); Serial.print(currentCmd);
  Serial.print(F(" feedback=")); Serial.print(readFeedback());
  Serial.print(F(" servo=")); Serial.print(SERVO_MIN_US); Serial.print('-'); Serial.print(SERVO_MAX_US);
  Serial.print(F(" laserwin=")); Serial.print(LASER_MIN_US); Serial.print('-'); Serial.print(LASER_MAX_US);
  Serial.print(F(" probe=1 static=1 observe=1 attached=")); Serial.println(servo.attached() ? 1 : 0);
}

void printHelp() {
  Serial.println(F("# commands:"));
  Serial.println(F("#   arm | disarm                      allow / forbid the laser"));
  Serial.println(F("#   sweep <start_us> <end_us> <ms>    continuous upward sweep, laser on"));
  Serial.println(F("#   step <start_us> <end_us> <n> <on_ms> <off_ms>   stop-and-pulse fallback"));
  Serial.println(F("#   goto <us>                         approach from below, report feedback"));
  Serial.println(F("#   move <us>                         manual jog: go straight there (no pre-roll)"));
  Serial.println(F("#   read [n]                          feedback mean/std over n reads"));
  Serial.println(F("#   probe <source_us> <target_us> <hold_ms>  bounded laser-OFF feedback trace"));
  Serial.println(F("#   static <current_us>  held pose: 3s dark/gate, 1s lit, .5s dark, release"));
  Serial.println(F("#   observe <current_us> same bounded hold; ADC screen advisory; optical review required"));
  Serial.println(F("#   laser on | laser off              manual, for alignment (auto-off 60 s)"));
  Serial.println(F("#   park | status | help"));
  Serial.println(F("#   stop                              laser off, disarm, servo released (limp)"));
}

// ============================== Command parser ==============================
// Fixed command only: no hidden preroll or commanded travel. The feedback gate
// is an electrical screening heuristic, not independently measured shaft settle.
const uint8_t STATIC_N = 50;
uint16_t staticSums[STATIC_N];
uint8_t staticCount, staticIndex;
uint32_t staticStart, staticNext, staticLast, staticLargestGap;

void staticTick() {
  serviceRun();
  if ((uint32_t)(micros()-staticStart) >= 6000000UL || !armed || !interlockClosed()) abortRun=true;
  if (abortRun) return;
  uint32_t now=micros();
  if ((int32_t)(now-staticNext)<0) return;
  staticNext=now+10000UL;
  if (staticLast) {
    uint32_t gap=now-staticLast;
    if (gap>staticLargestGap) staticLargestGap=gap;
  }
  staticLast=now;
  uint32_t sum=0; uint16_t first=0;
  for (uint8_t i=0;i<ADC_OVERSAMPLE;i++) {
    uint16_t v=analogRead(PIN_FEEDBACK); if(!i)first=v; sum+=v;
  }
  uint32_t end=micros();
  staticSums[staticIndex]=sum;
  staticIndex=(staticIndex+1)%STATIC_N;
  if(staticCount<STATIC_N)staticCount++;
  Serial.print(F("F,"));Serial.print(now);Serial.print(',');Serial.print(end);
  Serial.print(',');Serial.print(currentCmd);Serial.print(',');Serial.print(first);
  Serial.print(',');Serial.print(sum);Serial.print(',');Serial.print(ADC_OVERSAMPLE);
  Serial.print(',');Serial.print(ADC_DIVIDE);Serial.print(',');Serial.print(servo.attached()?1:0);
  Serial.print(',');Serial.println(laserOn?1:0);
}

void staticHold(uint32_t ms) {
  const uint32_t begin=micros();
  while(!abortRun && (uint32_t)(micros()-begin)<ms*1000UL)staticTick();
}

bool staticFeedbackReady() {
  if(staticCount!=STATIC_N || staticLargestGap>30000UL)return false;
  // v1.6 exploratory electrical screen: population RMS <=0.5 raw count,
  // max deviation <=3 counts, first/last-half mean difference <=0.5 count.
  // No samples removed. This is not physical shaft/plane calibration.
  uint32_t total=0, firstHalf=0, secondHalf=0;
  for(uint8_t i=0;i<STATIC_N;i++) {
    uint16_t value=staticSums[(staticIndex+i)%STATIC_N];
    total+=value;
    if(i<STATIC_N/2)firstHalf+=value;else secondHalf+=value;
  }
  long drift=(long)firstHalf-(long)secondHalf;
  if(drift>ADC_OVERSAMPLE*(STATIC_N/2)/2 ||
     drift<-(long)ADC_OVERSAMPLE*(STATIC_N/2)/2)return false;
  uint32_t squared=0;
  for(uint8_t i=0;i<STATIC_N;i++) {
    long delta=(long)staticSums[i]*STATIC_N-(long)total;
    if(delta>3L*ADC_OVERSAMPLE*STATIC_N ||
       delta<-3L*ADC_OVERSAMPLE*STATIC_N)return false;
    squared+=(uint32_t)(delta*delta); // bounded by max-deviation guard
  }
  const uint32_t halfCount=ADC_OVERSAMPLE*STATIC_N/2;
  return squared<=halfCount*halfCount*STATIC_N;
}

void runStatic(int target, bool observation=false) {
  if(!HAS_FEEDBACK || target<1100 || target>1900 || target!=currentCmd ||
     !armed || !interlockClosed() || laserOn) {
    Serial.println(F("ERR static requires armed/closed/laser-off, current command, feedback"));return;
  }
  busy=true;abortRun=false;manualLaser=false;
  staticCount=staticIndex=0;staticLast=staticLargestGap=0;
  staticStart=staticNext=micros();
  Serial.println(F("OK static"));
  if(observation)logEvent(micros(),"STATIC_OBSERVE",target);
  moveCmd(target);
  logEvent(micros(),"STATIC_DARK",target,3000);
  staticHold(3000);
  // Observation mode treats ONLY the electrical amplitude/drift screen as
  // advisory. Missing samples, timing gaps and all safety stops still abort.
  if(!abortRun && (staticCount!=STATIC_N || staticLargestGap>30000UL)) {
    logEvent(micros(),"STATIC_SAMPLING_INVALID",target);abortRun=true;
  }
  if(!abortRun && !staticFeedbackReady()) {
    if(observation)logEvent(micros(),"STATIC_SCREEN_WARN",target);
    else {logEvent(micros(),"STATIC_UNSTABLE",target);abortRun=true;}
  }
  if(!abortRun && laserRequest(true)) {
    logEvent(micros(),"STATIC_LIT",target,1000);staticHold(1000);
  } else abortRun=true;
  writeLaser(false,"LASER_OFF");
  if(!abortRun)staticHold(500);
  const bool failed=abortRun;
  emergencyStop();
  logEvent(micros(),failed?"STATIC_ABORTED":"STATIC_DONE",target);
  busy=false;
}

void handleCommand(String line) {
  line.trim(); line.toLowerCase();
  if (line.length() == 0) return;

  // Split into up to 6 whitespace-separated tokens.
  String tok[6]; int nt = 0, i = 0;
  while (i < (int)line.length() && nt < 6) {
    while (i < (int)line.length() && line[i] == ' ') i++;
    int j = i;
    while (j < (int)line.length() && line[j] != ' ') j++;
    if (j > i) tok[nt++] = line.substring(i, j);
    i = j;
  }
  const String &c = tok[0];

  if (c == "help" || c == "?")          printHelp();
  else if (c == "status")               printStatus();
  else if (c == "arm") {
    if (!interlockClosed()) { Serial.println(F("ERR interlock open - close the enclosure")); return; }
    armed = true; Serial.println(F("OK armed"));
  }
  else if (c == "disarm")               { hardStop(); abortRun = false; Serial.println(F("OK disarmed")); }
  else if (c == "stop" || c == "s")     { emergencyStop(); abortRun = false; Serial.println(F("OK stopped, disarmed, servo released")); }
  else if (c == "park")                 { busy = true; abortRun = false; slewTo(PARK_US); busy = false; Serial.println(F("OK park")); }
  else if (c == "goto" && nt == 2)      runGoto(tok[1].toInt());
  else if (c == "move" && nt == 2)      runMove(tok[1].toInt());
  else if (c == "read")                 runRead(nt == 2 ? tok[1].toInt() : 256);
  else if (c == "probe" && nt == 4)     runProbe(tok[1].toInt(), tok[2].toInt(), (uint32_t)tok[3].toInt());
  else if (c == "static" && nt == 2)    runStatic(tok[1].toInt());
  else if (c == "observe" && nt == 2)   runStatic(tok[1].toInt(), true);
  else if (c == "sweep" && nt == 4)     runSweep(tok[1].toInt(), tok[2].toInt(), (uint32_t)tok[3].toInt());
  else if (c == "step" && nt == 6)      runStep(tok[1].toInt(), tok[2].toInt(), tok[3].toInt(),
                                                (uint32_t)tok[4].toInt(), (uint32_t)tok[5].toInt());
  else if (c == "laser" && nt == 2 && tok[1] == "on") {
    if (laserRequest(true)) { manualLaser = true; manualSince = millis(); Serial.println(F("OK laser on")); }
  }
  else if (c == "laser" && nt == 2 && tok[1] == "off") { manualLaser = false; laserRequest(false); Serial.println(F("OK laser off")); }
  else { Serial.print(F("ERR unknown or malformed: ")); Serial.println(line); }
}

// ============================== Setup / loop ==============================
void setup() {
  // Laser OFF before anything else. A 10k pull-down on the transistor input
  // keeps it off while the pin floats during reset.
  pinMode(PIN_LASER, OUTPUT);
  digitalWrite(PIN_LASER, LOW);
  pinMode(PIN_STATUS, OUTPUT);
  digitalWrite(PIN_STATUS, LOW);
  pinMode(PIN_SYNC, OUTPUT);
  digitalWrite(PIN_SYNC, LOW);
  pinMode(PIN_INTERLOCK, INPUT_PULLUP);

#if defined(ARDUINO_ARCH_RENESAS)
  analogReadResolution(14);           // UNO R4: 0-16383. A classic UNO stays at 10 bit (0-1023)
#endif

  servo.attach(PIN_SERVO, 500, 2400); // safe pulse range for SG90 and SER0046
  moveCmd(PARK_US);

  Serial.begin(115200);
  const uint32_t t = millis();
  while (!Serial && millis() - t < 3000) { }

  Serial.println(F("# scanner_controller v1.7 - MECH5720 2026 event-based structured light"));
  Serial.println(HAS_FEEDBACK ? F("# servo feedback: A0") : F("# servo feedback: none (adc column = 0, angle = command)"));
  Serial.println(F("# S,t_us,cmd_us,adc,laser"));
  Serial.println(F("# E,t_us,name,a,b,c"));
  printHelp();
}

void loop() {
  safetyCheck();
  String line;
  if (readLine(line)) handleCommand(line);
}

# Environment inspection

Inspected 30 October 2026 on Windows. The workspace initially contained no project files and was not a Git repository.

- Active base interpreter: `C:\Users\24adi\miniconda3\python.exe`, Python 3.13.14; `dv-processing` was not installed there.
- Project virtual environment: `.venv`, Python 3.13.14; `dv-processing` 2.0.4 installed from pip.
- Official discovery: one DAVIS, serial `60008401`.
- Opened camera name: `DAVIS240C_60008401`; event resolution 240 × 180.
- API reports event, frame and IMU streams available. Frame and IMU delivery have not yet been tested.
- One live non-empty event packet was received (3 events). This is a connectivity check, not a performance measurement.

API reference: https://dv-processing.inivation.com/master/reading_data.html

## Milestone 2 live measurement

A five-second check received 3,962 events in 377 non-empty batches (792.4 events/s), a 240 × 180 uint8 grayscale frame, and 5,010 IMU samples. Frame timestamp 163030 and event/IMU timestamps around 1793337302... have different apparent origins; their synchronisation has not been established. Availability and data delivery were tested, but visual focus and motion response still require human validation.

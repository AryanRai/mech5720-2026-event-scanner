# Local rig work

Read `AGENT_RIG.md` before operating DAVIS, servo or laser, and `AGENT_CAMERA.md` for camera controls. Use `scripts/rig_ctl.py` and the existing single-owner services; never compete for COM13 or the DAVIS USB device. Preserve the working combined dashboard. Never replay uncertain emitting/motion/capture commands, bypass the interlock, or silently reconnect/reset hardware. No physical calibration or synchronization is implied by communication success.

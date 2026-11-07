"""Acquire explicit1626 correction; preserve original1627 records unchanged."""
import json
from pathlib import Path
import subprocess
import sys

out=Path('outputs/static_checks/shoe_repeat_session_20261103_02')
runs=json.loads((out/'runs.json').read_text())
(out/'command_correction.json').write_text(json.dumps(dict(reason='1627 has no frozen plane; correct fitted command is1626. Original1627 retained, excluded from depth evaluation. New independent acquisitions, no uncertain replay.',command_us=1626,repeats=3),indent=2))
try:
    for repeat in [1,2,3]:
        run=f'shoe_repeat_r{repeat}_1626_20261103_02'
        print(json.dumps(dict(start=run)),flush=True)
        result=subprocess.run([sys.executable,'scripts/capture_plane_position.py','--id',run,'--us','1626','--exposure-us','35000','--duration','12'],capture_output=True,text=True)
        (out/(run+'.stdout.txt')).write_text(result.stdout);(out/(run+'.stderr.txt')).write_text(result.stderr)
        runs.append(dict(run_id=run,repeat=repeat,command_us=1626,returncode=result.returncode,corrects_unfitted_command=1627))
        (out/'runs_with_correction.json').write_text(json.dumps(runs,indent=2))
        print(json.dumps(dict(done=run,returncode=result.returncode)),flush=True)
        if result.returncode:raise RuntimeError('Failed; inspect, no replay: '+run)
    result=subprocess.run([sys.executable,'scripts/camera_ctl.py','--request-id','shoe_repeat_session_20261103_02_after_supplement','snapshot','shoe_repeat_session_20261103_02_after_supplement'],capture_output=True,text=True)
    (out/'after_supplement_snapshot.txt').write_text(result.stdout+result.stderr)
finally:
    result=subprocess.run([sys.executable,'scripts/rig_ctl.py','--request-id','shoe_repeat_session_20261103_02_supplement_stop','stop'],capture_output=True,text=True)
    (out/'supplement_final_stop.txt').write_text(result.stdout+result.stderr)

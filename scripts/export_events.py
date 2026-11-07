"""Export a bounded sensor-time event interval from AEDAT4 to compressed NPZ."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dv_processing as dv
import numpy as np

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('recording'); p.add_argument('output'); p.add_argument('--start-us',type=int,required=True); p.add_argument('--end-us',type=int,required=True); a=p.parse_args()
 if a.end_us<=a.start_us: p.error('end must exceed start')
 try:
  r=dv.io.MonoCameraRecording(a.recording); e=r.getEventsTimeRange(a.start_us,a.end_us)
  if e is None: raise ValueError('No events in requested interval')
  path=Path(a.output)
  if path.suffix.lower() != '.npz': raise ValueError('Output must have .npz extension')
  if path.exists(): raise FileExistsError(path)
  arr=e.numpy(); path.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(path,events=arr)
  print(f'Exported {len(arr)} events to {path}; time range requested [{a.start_us}, {a.end_us})'); return 0
 except Exception as exc: print(f'Export error: {type(exc).__name__}: {exc}',file=sys.stderr); return 1
if __name__=='__main__': sys.exit(main())

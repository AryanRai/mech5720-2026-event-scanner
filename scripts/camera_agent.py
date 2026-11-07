"""Single-owner live DAVIS preview and loopback control server."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from event_camera.agent_control import run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial')
    parser.add_argument('--port', type=int, default=8931)
    parser.add_argument('--no-display', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024..65535')
    run(Path(__file__).resolve().parents[1], args.port, args.serial, not args.no_display)

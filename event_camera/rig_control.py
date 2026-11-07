"""Single-flight, durable agent-to-browser actuator mailbox. Never owns serial."""
import copy
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time


def validate(body):
    if not isinstance(body, dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(body.get('id', ''))):
        raise ValueError('Unique ASCII operation id required')
    action = body.get('action')
    fields = {'move': {'us'}, 'read': {'n'}, 'pulse': {'seconds', 'arm'},
              'sweep': {'start_us', 'end_us', 'duration_ms', 'arm'},
              'probe': {'source_us', 'target_us', 'hold_ms'},
              'static': {'us', 'arm'}, 'observe': {'us', 'arm'}, 'stop': set()}
    if action not in fields or set(body) - ({'id', 'action', 'contained'} | fields[action]):
        raise ValueError('Unsupported actuator request')
    if action != 'stop' and body.get('contained') is not True:
        raise ValueError('Explicit contained-environment confirmation required')
    def integer(key, lo, hi):
        value = body.get(key)
        if type(value) is not int or not lo <= value <= hi:
            raise ValueError(f'{key} must be integer {lo}..{hi}')
        return value
    if action in ('move', 'static', 'observe'):
        integer('us', 1100, 1900)
    elif action == 'read':
        integer('n', 1, 1000)
    elif action == 'pulse':
        integer('seconds', 1, 5)
    elif action == 'probe':
        integer('source_us', 1100, 1900)
        integer('target_us', 1100, 1900)
        integer('hold_ms', 100, 3000)
    elif action == 'sweep':
        a, b = integer('start_us', 1100, 1900), integer('end_us', 1100, 1900)
        if a >= b:
            raise ValueError('Sweep must ascend')
        integer('duration_ms', 100, 10000)
    if action in ('pulse', 'sweep', 'static', 'observe') and body.get('arm') is not True:
        raise ValueError('Explicit arm=true required for every emitting operation')
    return copy.deepcopy(body)


class RigControl:
    def __init__(self, root):
        self.lock = threading.RLock()
        self.root = Path(root)
        self.token = secrets.token_urlsafe(32)
        self.client = None
        self.updated = 0
        self.state = {}
        self.active = None
        self.ops = {}
        self.journal = self.root / 'outputs/agent_control/rig_operations.jsonl'
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        if self.journal.exists():
            for line in self.journal.read_text(encoding='utf-8').splitlines():
                op = json.loads(line)
                self.ops[op['id']] = op
            for op in self.ops.values():
                if op['state'] in ('queued', 'claimed'):
                    op.update(state='unknown', error='Server restarted; inspect hardware/logs, never replay')
        runtime = self.root / '.runtime'
        runtime.mkdir(exist_ok=True)
        (runtime / 'rig.json').write_text(json.dumps({'url':'http://127.0.0.1:8933', 'token':self.token}), encoding='utf-8')

    def save(self, op):
        with self.journal.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(op) + '\n')
            fh.flush()
            os.fsync(fh.fileno())

    def status(self):
        with self.lock:
            age = time.monotonic() - self.updated if self.updated else None
            return {'browser_age_s':age, 'fresh':age is not None and age < 3,
                    'controller':copy.deepcopy(self.state), 'active':self.active,
                    'limits':{'move_us':[1100,1900], 'pulse_s':[1,5], 'sweep_ms':[100,10000]},
                    'note':'Command limits are not calibrated beam/angle limits. Browser owns serial.'}

    def submit(self, body):
        body = validate(body)
        with self.lock:
            ident = body['id']
            if ident in self.ops:
                if self.ops[ident]['request'] != body:
                    raise ValueError('ID already used for different request')
                return copy.deepcopy(self.ops[ident])
            if len(self.ops) >= 5000:
                raise ValueError('Journal operation limit reached')
            s = self.status()
            if not s['fresh'] or not self.state.get('connected') or (body['action'] != 'stop' and not self.state.get('agentEnabled')):
                raise ValueError('Enable agent control in a connected, fresh dashboard first')
            if self.active and body['action'] != 'stop':
                raise ValueError('Busy/uncertain operation; inspect it before proceeding')
            if self.state.get('busy') and body['action'] != 'stop':
                raise ValueError('Dashboard busy; commands are not queued behind motion')
            if self.active:  # stop preempts, never replays the earlier command
                old = self.ops[self.active]
                old.update(state='unknown', error='Preempted by explicit stop; inspect returned logs')
                self.save(old)
            op = {'id':ident, 'request':body, 'state':'queued', 'created_utc':time.time()}
            self.ops[ident] = op
            self.active = ident
            self.save(op)
            return copy.deepcopy(op)

    def heartbeat(self, body):
        client = body.get('client')
        if not isinstance(client, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', client):
            raise ValueError('Invalid dashboard client')
        with self.lock:
            if self.client not in (None, client) and time.monotonic() - self.updated < 3:
                raise ValueError('Another dashboard owns the agent mailbox')
            self.client, self.updated = client, time.monotonic()
            self.state = {k: body.get(k) for k in ('connected','busy','agentEnabled','armed','laser','cmd','feedback','interlock','fw')}
            result = body.get('result')
            if result:
                op = self.ops.get(result.get('id'))
                if op and op.get('client') == client and op['state'] in ('claimed', 'unknown'):
                    op.update(state='failed' if result.get('error') else 'done', result=result)
                    self.save(op)
                    if self.active == op['id']:
                        self.active = None
            op = self.ops.get(self.active)
            if op and op['state'] == 'queued':
                op.update(state='claimed', client=client)
                self.save(op)  # persist BEFORE dispatch; never resend uncertain hardware actions
                return {'operation':copy.deepcopy(op)}
            return {'operation':None}

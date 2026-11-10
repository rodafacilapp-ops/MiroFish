#!/usr/bin/env python3
"""Local MiroFish operations. Never starts a simulation or calls an AI API."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get('MIROFISH_RUNTIME_DIR', str(ROOT.parent / '.mirofish-runtime' / ROOT.name))).resolve()
PID = STATE / 'dev.pid'
LOG = STATE / 'dev.log'
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path):
    with HTTP.open('http://127.0.0.1:5001' + path, timeout=10) as response:
        return response.read()


def start():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    for port in (3000, 5001):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                raise SystemExit(f'Port {port} is occupied; inspect status before starting.')
    env = os.environ.copy()
    for name in ('LLM_API_KEY', 'ZEP_API_KEY'):
        if not env.get(name):
            raise SystemExit(f'Missing secure environment binding: {name}')
    base = env.get('LLM_BASE_URL', '').strip()
    if base != 'https://api.openai.com/v1':
        raise SystemExit('Expected LLM_BASE_URL=https://api.openai.com/v1 after trimming.')
    if env.get('ZEP_API_URL'):
        raise SystemExit('ZEP_API_URL is unsupported by this Cloud-only backend.')
    # Do not let local dotenv files override secure Cloud bindings.
    env.update(LLM_BASE_URL=base, PYTHON_DOTENV_DISABLED='1',
               FLASK_DEBUG='false', FLASK_HOST='127.0.0.1', FLASK_PORT='5001',
               VITE_API_BASE_URL='/', BROWSER='none',
               UV_CACHE_DIR=str(STATE / 'uv-cache'),
               UV_PYTHON_INSTALL_DIR=str(STATE / 'python'))
    with LOG.open('ab') as output:
        child = subprocess.Popen(['npm', 'run', 'dev'], cwd=ROOT, env=env,
                                 stdin=subprocess.DEVNULL, stdout=output,
                                 stderr=subprocess.STDOUT, start_new_session=True)
    started = Path(f'/proc/{child.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    PID.write_text(json.dumps({'pid': child.pid, 'start_ticks': started}))
    print(json.dumps({'started_pid': child.pid, 'log': str(LOG)}))


def status():
    result = {}
    for name, url in (('frontend', 'http://127.0.0.1:3000/'),
                      ('backend', 'http://127.0.0.1:5001/health'),
                      ('frontend_api_proxy', 'http://127.0.0.1:3000/api/report/list')):
        try:
            with HTTP.open(url, timeout=10) as response:
                result[name] = {'http_status': response.status}
                if name == 'backend':
                    result[name]['data'] = json.load(response)
        except (OSError, urllib.error.URLError) as error:
            result[name] = {'error': type(error).__name__}
    print(json.dumps(result, indent=2))
    if any(item.get('http_status') != 200 for item in result.values()):
        raise SystemExit(1)


def stop():
    if not PID.exists():
        raise SystemExit('No managed PID file. Inspect processes manually.')
    saved = json.loads(PID.read_text())
    pid = saved['pid'] if isinstance(saved, dict) else int(saved)
    try:
        cmd = Path(f'/proc/{pid}/cmdline').read_bytes()
        started = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
        expected_start = saved.get('start_ticks') if isinstance(saved, dict) else None
        if (cmd.rstrip(b'\x00') != b'npm run dev' or os.getpgid(pid) != pid
                or (expected_start is not None and expected_start != started)):
            raise SystemExit('PID identity changed; refusing to signal it.')
        os.killpg(pid, signal.SIGTERM)
    except FileNotFoundError:
        pass
    PID.unlink(missing_ok=True)
    print('Managed service group stopped.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'status', 'stop', 'reports', 'download'])
    parser.add_argument('report_id', nargs='?')
    args = parser.parse_args()
    if args.action == 'start': start()
    elif args.action == 'status': status()
    elif args.action == 'stop': stop()
    elif args.action == 'reports':
        print(json.dumps(json.loads(get('/api/report/list')), ensure_ascii=False, indent=2))
    else:
        if not args.report_id or not re.fullmatch(r'[A-Za-z0-9_-]+', args.report_id):
            parser.error('download requires a valid report ID')
        content = get('/api/report/' + args.report_id + '/download')
        target = STATE / 'artifacts' / (args.report_id + '.md')
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(content)
        print(str(target))


if __name__ == '__main__':
    main()

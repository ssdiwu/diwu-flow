import json, sys, os, subprocess

d = json.load(sys.stdin)
cwd = d.get('cwd', '.')

tf = os.path.join(cwd, '.diwu/dtask.json')
if not os.path.exists(tf):
    sys.exit(0)

data = json.load(open(tf))
ip = [t for t in data.get('tasks', []) if t['status'] == 'InProgress']

if not ip:
    sys.exit(0)

recording_dir = os.path.join(cwd, '.diwu/recording')
if not os.path.isdir(os.path.dirname(recording_dir)):
    sys.exit(0)

try:
    diff = subprocess.check_output(
        ['git', 'diff', '--stat'], cwd=cwd, stderr=subprocess.DEVNULL
    ).decode().strip()
    cached = subprocess.check_output(
        ['git', 'diff', '--cached', '--stat'], cwd=cwd, stderr=subprocess.DEVNULL
    ).decode().strip()
    stat = '\n'.join(filter(None, [diff, cached]))
except Exception:
    stat = ''

now = subprocess.check_output(['date', '+%Y-%m-%d %H:%M:%S']).decode().strip()
filename = now.replace(' ', '-').replace(':', '')
t = ip[0]
entry = (
    '## [auto-compact] Task#' + str(t['id']) + ' 进度快照 ' + now + '\n\n'
    + '任务：' + t.get('title', '') + '\n'
)
if stat:
    entry += '\n```\n' + stat + '\n```\n'

os.makedirs(recording_dir, exist_ok=True)
session_file = os.path.join(recording_dir, f'session-{filename}.md')
open(session_file, 'w').write(entry)

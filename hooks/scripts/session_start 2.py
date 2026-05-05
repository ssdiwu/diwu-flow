import json, sys, os

d = json.load(sys.stdin)
sid = d.get('session_id', '')
if sid:
    open('/tmp/.claude_main_session', 'w').write(sid)

result = {}
cwd = d.get('cwd', '')
if cwd:
    env_path = os.path.join(cwd, '.claude', 'env')
    if os.path.isfile(env_path):
        env = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
        if env:
            result['env'] = env

if result:
    print(json.dumps(result))

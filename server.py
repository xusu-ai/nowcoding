#!/usr/bin/env python3
"""ShowCode HTTP server - port 3000"""
import http.server, os, sys, json, re, random, threading, time, socket
import urllib.request, urllib.error
socket.setdefaulttimeout(None)  # 永不超时，AI 生成可不间断进行
from urllib.parse import urlparse
from datetime import datetime

PORT = int(os.environ.get('SHOWCODE_PORT', 3000))
DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(DIR, 'projects')
PROJECTS_JSON = os.path.join(PROJECTS_DIR, 'projects.json')
UPSTREAM_LLM = 'http://127.0.0.1:8106'
MODEL_ROUTES = {
    'Macaron-V1-Tall': 'http://127.0.0.1:8106',
}

def _upstream_for(model):
    return MODEL_ROUTES.get(model, UPSTREAM_LLM)

def _llm_call(prompt, temp=0.95, model='Macaron-V1-Tall', max_tokens=8192):
    upstream = _upstream_for(model)
    body = json.dumps({'model': model, 'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temp, 'max_tokens': max_tokens, 'stream': False}).encode('utf-8')
    req = urllib.request.Request(upstream + '/v1/chat/completions', data=body,
        headers={'Content-Type': 'application/json', 'Content-Length': str(len(body))}, method='POST')
    msg = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())['choices'][0]['message']
    return msg.get('content') or msg.get('reasoning_content') or ''

SUGGESTION_FB = {
    'zh': ['做一个霓虹灯登录页面','生成一个瀑布流图片展示页','创建一个贪吃蛇游戏','画一个粒子动画背景'],
    'en': ['Make a neon glow login page','Create a waterfall image gallery','Build a Snake game','Make a particle animation background'],
}
_sug_cache = {'zh': None, 'en': None, 'lock': threading.Lock()}

def _gen_suggestions(lang):
    is_zh = lang.startswith('zh')
    prompt = ('Generate 4 short creative web project ideas for an online code playground (seed={}). '
        'Keep each under 60 chars. Use HTML+CSS+JS. Respond in {}. '
        'Return ONLY a JSON array of 4 strings: ["a","b","c","d"]. No markdown.'
    ).format(random.randint(1, 99999), 'Chinese' if is_zh else 'English')
    try:
        text = _llm_call(prompt, model='Macaron-V1-Tall').strip()
        if text.startswith('```'): text = text.split('\n', 1)[1] if '\n' in text else text.replace('```', '').strip()
        if text.endswith('```'): text = text[:-3].strip()
        s = json.loads(text)
        if isinstance(s, list) and len(s) >= 4: return s[:4]
    except Exception:
        pass
    return SUGGESTION_FB['zh' if is_zh else 'en']

def _refresh_suggestions(lang):
    s = _gen_suggestions(lang)
    with _sug_cache['lock']:
        _sug_cache[lang] = s
    return s

def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', '', s or '').strip()
    return s[:50] or 'untitled'

def load_projects():
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    try:
        with open(PROJECTS_JSON, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception:
        return []

def save_projects(projects):
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    with open(PROJECTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)

def _qs(query):
    return {k: v for k, v in (p.split('=', 1) for p in query.split('&') if '=' in p)}

class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)
    def log_message(self, *a): pass

    def _send_json(self, code, payload, extra=None):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        if extra:
            for k, v in extra.items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _proxy_llm(self, method, upstream_path=None, upstream=None, body=None):
        parsed = urlparse(self.path)
        path = upstream_path or parsed.path
        base = upstream or UPSTREAM_LLM
        target = base + path + ('?' + parsed.query if parsed.query else '')
        if body is None:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length > 0 else None
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ('host', 'connection', 'transfer-encoding', 'content-length')}
        req = urllib.request.Request(target, data=body, headers=headers, method=method)
        sent_headers = False
        try:
            resp = urllib.request.urlopen(req, timeout=600)
            self.send_response(resp.status)
            self.send_header('Transfer-Encoding', 'chunked')
            for k, v in resp.headers.items():
                if k.lower() not in ('transfer-encoding', 'content-length', 'connection'):
                    self.send_header(k, v)
            self.end_headers()
            sent_headers = True
            while True:
                line = resp.readline()
                if not line:
                    self.wfile.write(b'0\r\n\r\n'); self.wfile.flush(); break
                self.wfile.write(format(len(line), 'x').encode() + b'\r\n' + line + b'\r\n')
                self.wfile.flush()
        except urllib.error.HTTPError as e:
            b = e.read()
            if sent_headers:
                self.wfile.write(b'0\r\n\r\n'); self.wfile.flush()
            else:
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)
        except Exception as e:
            if sent_headers:
                try: self.wfile.write(b'0\r\n\r\n'); self.wfile.flush()
                except Exception: pass
            else:
                self._send_json(502, {'error': 'Upstream unavailable: ' + str(e)})

    def do_OPTIONS(self):
        self._send_json(200, {}, {'Allow': 'GET, POST, DELETE, OPTIONS'}) if urlparse(self.path).path.startswith('/api/') else super().do_OPTIONS()

    def do_GET(self):
        p = urlparse(self.path).path
        if p.startswith('/v1/'): self._proxy_llm('GET')
        elif p == '/api/projects': self._send_json(200, load_projects(), {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0', 'Pragma': 'no-cache'})
        elif p == '/api/suggestions': self._send_suggestions()
        else: super().do_GET()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/projects':
            try:
                pid = _qs(parsed.query).get('id', '')
                save_projects([p for p in load_projects() if p.get('id') != pid])
                self._send_json(200, {'ok': True})
            except Exception as e:
                self._send_json(500, {'ok': False, 'error': str(e)})
        else:
            self._send_json(404, {'ok': False, 'error': 'not found'})

    def do_POST(self):
        p = urlparse(self.path).path
        if p.startswith('/v1/'): self._proxy_llm('POST')
        elif p == '/api/chat':
            upstream = None
            try:
                length = int(self.headers.get('Content-Length', 0))
                raw = self.rfile.read(length) if length > 0 else b''
                body_obj = json.loads(raw) if raw else {}
                upstream = _upstream_for(body_obj.get('model', ''))
                self._proxy_llm('POST', '/v1/chat/completions', upstream=upstream, body=raw)
            except Exception:
                self._send_json(400, {'ok': False, 'error': 'bad chat body'})
        elif p == '/api/save': self._save_project()
        else: self._send_json(404, {'ok': False, 'error': 'not found'})

    def _send_suggestions(self):
        q = _qs(urlparse(self.path).query)
        lang = 'zh' if q.get('lang', 'zh').startswith('zh') else 'en'
        if q.get('refresh') == '1':
            s = _refresh_suggestions(lang)
        else:
            with _sug_cache['lock']:
                s = _sug_cache[lang]
            if not s:
                threading.Thread(target=_refresh_suggestions, args=(lang,), daemon=True).start()
                s = SUGGESTION_FB[lang]
        self._send_json(200, s, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0', 'Pragma': 'no-cache'})

    def _save_project(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode('utf-8'))
            html, css, js = (data.get('html') or '').strip(), (data.get('css') or '').strip(), (data.get('js') or '').strip()
            code, title = data.get('code') or '', safe_name(data.get('title') or 'untitled')

            os.makedirs(PROJECTS_DIR, exist_ok=True)
            num = max([int(m.group(1)) for name in os.listdir(PROJECTS_DIR) if name != 'projects.json'
                       and (m := re.match(r'^(\d+)_', name))] + [0]) + 1
            date_str = datetime.now().strftime('%Y-%m-%d')
            base_name = '{:03d}_{}_{}'.format(num, date_str, title)
            folder = os.path.join(PROJECTS_DIR, base_name)
            i = 1
            while os.path.exists(folder):
                folder = os.path.join(PROJECTS_DIR, '{}_{}'.format(base_name, i))
                base_name = os.path.basename(folder); i += 1
            os.makedirs(folder)

            saved = []
            for ext, content in [('html', html), ('css', css), ('js', js)]:
                if content:
                    with open(os.path.join(folder, base_name + '.' + ext), 'w', encoding='utf-8') as f: f.write(content)
                    saved.append(ext)

            projects = load_projects()
            project = {
                'id': data.get('id') or datetime.now().strftime('%y%m%d%H%M%S') + os.urandom(2).hex(),
                'code': code, 'title': title, 'views': int(data.get('views', 0)), 'runs': int(data.get('runs', 0)),
                'createdAt': data.get('createdAt') or int(datetime.now().timestamp() * 1000),
                'folder': base_name, 'saved': saved, 'num': num, 'date': date_str,
            }
            projects.insert(0, project)
            save_projects(projects)
            self._send_json(200, {'ok': True, 'projects': projects, 'project': project})
        except Exception as e:
            self._send_json(500, {'ok': False, 'error': str(e)})

if __name__ == '__main__':
    httpd = http.server.ThreadingHTTPServer((os.environ.get('SHOWCODE_BIND', '127.0.0.1'), PORT), Handler)
    print("ShowCode server running on http://0.0.0.0:{}".format(PORT), flush=True)
    httpd.serve_forever()

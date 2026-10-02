#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xinka 留言板后端（零依赖 stdlib·SQLite 存库·审核后上墙）
- POST /api/submit   提交留言（蜜罐+限速·入库存 pending）
- GET  /api/list     公开墙（只出 approved）
- GET  /health       健康检查
管理（SSH）：python3 admin.py list|approve ID|reject ID|stats
Xinka Guestbook v1.0 · Created by Ren Shiliao (任世燎) 2026
"""
import json
import re
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DB = "/opt/data/xinka_guestbook/guestbook.db"
PORT = 8080
MAX_LEN = 1000
COOLDOWN = 60  # 同 IP 最短间隔秒


def db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS msgs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, contact TEXT, content TEXT,
        ip TEXT, ua TEXT, status TEXT DEFAULT 'pending',
        created REAL, reviewed REAL)""")
    return c


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/health":
            self._json(200, {"ok": True, "service": "xinka-guestbook"})
        elif p == "/api/list":
            c = db()
            rows = c.execute(
                "SELECT id,name,content,created FROM msgs WHERE status='approved' "
                "ORDER BY reviewed DESC LIMIT 50").fetchall()
            c.close()
            self._json(200, {"msgs": [
                {"id": r[0], "name": r[1], "content": r[2],
                 "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(r[3]))}
                for r in rows]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/submit":
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(min(n, 10000)).decode())
        except Exception:
            return self._json(400, {"error": "bad json"})

        # 蜜罐：隐藏字段被填 = 机器人
        if data.get("website"):
            return self._json(200, {"ok": True})  # 假装成功，实际丢弃

        name = str(data.get("name", "")).strip()[:50]
        contact = str(data.get("contact", "")).strip()[:100]
        content = str(data.get("content", "")).strip()
        if not content or len(content) > MAX_LEN:
            return self._json(400, {"error": "内容为空或超长"})
        if not name:
            name = "匿名"

        ip = self.headers.get("X-Real-IP", self.client_address[0])
        c = db()
        # 限速：同 IP 60 秒内一条
        last = c.execute(
            "SELECT MAX(created) FROM msgs WHERE ip=?", (ip,)).fetchone()[0]
        if last and time.time() - last < COOLDOWN:
            c.close()
            return self._json(429, {"error": "请稍后再提交"})
        c.execute(
            "INSERT INTO msgs(name,contact,content,ip,ua,status,created) "
            "VALUES(?,?,?,?,?,'pending',?)",
            (name, contact, content, ip,
             self.headers.get("User-Agent", "")[:120], time.time()))
        c.commit()
        c.close()
        self._json(200, {"ok": True,
                         "note": "留言已收到·审核后上墙"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    print(f"xinka-guestbook listening :{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()

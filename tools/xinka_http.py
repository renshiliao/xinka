#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xinka_http.py — Xinka 信卡 MCP · Streamable HTTP 传输桥（v2·SSE 兼容）

v2 变更（2026-10-03·超小爱兼容）：
  - 协议版本协商：回显客户端请求的 protocolVersion（2025-06-18/2025-03-26 均可）
  - SSE 应答：客户端 Accept 带 text/event-stream 时按 SSE 帧回（event: message）
  - GET /mcp 健康检查与 SSE 长连均支持
无鉴权（只读计算，不落库）· 零依赖（stdlib only）· Created by Ren Shiliao（任世燎）
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from xinka_mcp import handle  # noqa: E402

PORT = 8090
SERVER_INFO = {"name": "xinka", "version": "0.2"}


class MCPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, Authorization, Accept, MCP-Protocol-Version, Mcp-Session-Id")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    def _wants_sse(self):
        return "text/event-stream" in (self.headers.get("Accept") or "")

    def _send_json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, obj):
        data = json.dumps(obj, ensure_ascii=False)
        body = f"event: message\ndata: {data}\n\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        # 健康检查/工具概览；带 SSE 头则按流式回一帧
        info = {
            "service": "xinka-mcp",
            "version": "0.2",
            "transport": "streamable-http",
            "protocolVersions": ["2025-06-18", "2025-03-26", "2024-11-05"],
            "tools": ["xinka_make_card", "xinka_check_card", "xinka_freshness"],
        }
        (self._send_sse if self._wants_sse() else self._send_json)(info)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n) or b"{}"
            req = json.loads(raw)
        except Exception:
            self.send_response(400)
            self._cors()
            self.end_headers()
            return

        # 协议版本协商：回显客户端声明版本
        client_pv = None
        if isinstance(req, dict):
            client_pv = (req.get("params") or {}).get("protocolVersion")
        if not client_pv:
            client_pv = self.headers.get("MCP-Protocol-Version") or "2025-06-18"

        if isinstance(req, list):
            resp = []
            for x in req:
                r = self._dispatch(x, client_pv)
                if r is not None:
                    resp.append(r)
            (self._send_sse if self._wants_sse() else self._send_json)(resp)
        else:
            resp = self._dispatch(req, client_pv)
            if resp is None:
                # notification：202 空体（streamable-http 惯例）
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self._cors()
                self.end_headers()
            else:
                (self._send_sse if self._wants_sse() else self._send_json)(resp)

    def _dispatch(self, req, client_pv):
        if not isinstance(req, dict):
            return None
        if req.get("method") == "initialize":
            rid = req.get("id")
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": client_pv,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            }}
        return handle(req)

    def log_message(self, format, *args):  # noqa: A002
        pass  # 静默


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), MCPHandler).serve_forever()

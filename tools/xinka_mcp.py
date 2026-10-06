#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xinka_mcp.py — Xinka 信卡 MCP 服务器（stdio·零依赖）

任何支持 MCP 的 AI 客户端（Claude Code / Cline / Hermes 等）接上即可用：
  {"command": "python3", "args": ["tools/xinka_mcp.py"]}

暴露三个工具:
  xinka_make_card   — 断言+三源 → 生成信卡 JSON（自动降档 pending）
  xinka_check_card  — 信卡 JSON → 过校验器 R1-R7+R8 独立性
  xinka_freshness   — 扫卡目录 → 过期/临期清单

协议: JSON-RPC 2.0 over stdio (MCP 2024-11-05) · Created by Ren Shiliao（任世燎）
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, "xinka_check.py")

TOOLS = [
    {
        "name": "xinka_make_card",
        "description": "把一条知识断言生成 Xinka 信卡（可信知识最小单元）。六要素自动补全：源/采/信/鲜/位/证。三源独立且≥3 → verified，否则自动降档 pending（孤证不立）。",
        "inputSchema": {
            "type": "object",
            "required": ["claim", "sources", "position"],
            "properties": {
                "claim": {"type": "string", "description": "断言句：不可再拆而保持语义完整的最小命题"},
                "sources": {"type": "array", "items": {"type": "string"}, "description": "真实出处 URL 列表（≥3 独立源才能升 verified，严禁编造 URL）"},
                "position": {"type": "string", "description": "知识树内坐标，小写分隔，如 product/projector/xgimi/market-share"},
                "freshness_years": {"type": "number", "description": "保鲜年限（缺省 2）"},
            },
        },
    },
    {
        "name": "xinka_check_card",
        "description": "校验一张 Xinka 信卡：R1 六要素齐备/R2 时序/R3 置信两档/R4 已验证须≥3源/R5 保鲜/R7 出处坐标 + R8 独立性（防伪互证：三源同域名=转载不算互证）。",
        "inputSchema": {
            "type": "object",
            "required": ["card"],
            "properties": {"card": {"type": "object", "description": "信卡 JSON 对象"}},
        },
    },
    {
        "name": "xinka_freshness",
        "description": "扫描信卡目录的保鲜期：列出已过期（须复核降级）与 60 天内临期条目。",
        "inputSchema": {
            "type": "object",
            "required": ["dir"],
            "properties": {"dir": {"type": "string", "description": "信卡 JSON 所在目录"}},
        },
    },
]


def _domain(url):
    # BUG-7/8 修复：dict 源取 url 字段；removeprefix 替代 lstrip 字符集剥离
    if isinstance(url, dict):
        url = url.get("url", "")
    try:
        return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def make_card(claim, sources, position, freshness_years=2):
    trust = "verified" if len(sources) >= 3 else "pending"
    domains = set(_domain(u) for u in sources if _domain(u))
    warnings = []
    if trust == "verified":
        if len(set(sources)) != len(sources):
            return {"error": "R8 源列表有重复 URL"}
        if len(domains) < 2:
            return {"error": f"R8 三源同域名({','.join(domains)})=疑似转载互抄，不算独立互证——请补独立源或降档 pending"}
    now = datetime.now(timezone.utc)
    collected = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now + timedelta(days=365 * float(freshness_years))).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not re.match(r"^[a-z0-9\-]+(/[a-z0-9\-\.]+)*$", position):
        return {"error": f"R7 位坐标格式非法: {position}（小写+连字符，/ 分层）"}
    card = {
        "xinka_version": "0.1",
        "claim": claim,
        "source_url": sources[0] if sources else "",
        "collected_at": collected,
        "trust_level": trust,
        "freshness_until": fresh,
        "position": position,
        "verification": {
            "method": "three-source cross-check" if trust == "verified" else "single/partial source",
            "sources": sources,
            "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ") if trust == "verified" else None,
        },
    }
    if trust == "pending" and len(sources) < 3:
        warnings.append(f"R4 自动降档 pending：仅 {len(sources)} 源（verified 需 ≥3 独立源）")
    return {"card": card, "warnings": warnings, "trust_level": trust}


def check_card(card):
    import tempfile
    notes = []
    domains = set(_domain(u) for u in card.get("verification", {}).get("sources", []) if _domain(u))
    if card.get("trust_level") == "verified" and len(domains) < 2:
        notes.append("R8 三源同域名=疑似转载互抄，不算独立互证")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False)
        path = f.name
    try:
        r = subprocess.run([sys.executable, CHECKER, path], capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip()
        ok = r.returncode == 0 and not notes
        return {"valid": ok, "checker_output": out, "independence_notes": notes}
    finally:
        os.unlink(path)


def freshness_scan(dir_path):
    if not os.path.isdir(dir_path):
        return {"error": f"目录不存在: {dir_path}"}
    now = datetime.now(timezone.utc)
    soon_before = now + timedelta(days=60)
    expired, soon, bad = [], [], []
    for fn in sorted(os.listdir(dir_path)):
        if not fn.endswith(".json"):
            continue
        try:
            c = json.load(open(os.path.join(dir_path, fn), encoding="utf-8"))
            fu = datetime.fromisoformat(str(c["freshness_until"]).replace("Z", "+00:00"))
        except Exception:
            # BUG-13 修复：坏卡计数不静默（与 pipeline scan 同口径）
            bad.append(fn)
            continue
        row = {"file": fn, "position": c.get("position"), "trust_level": c.get("trust_level"),
               "freshness_until": c.get("freshness_until")}
        if fu < now:
            expired.append(row)
        elif fu < soon_before:
            soon.append(row)
    return {"expired": expired, "expiring_60d": soon}


def handle(req):
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "xinka", "version": "0.1"},
        }}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = req["params"]["name"]
        args = req["params"].get("arguments", {})
        try:
            if name == "xinka_make_card":
                result = make_card(args["claim"], args["sources"], args["position"],
                                   args.get("freshness_years", 2))
            elif name == "xinka_check_card":
                result = check_card(args["card"])
            elif name == "xinka_freshness":
                result = freshness_scan(args["dir"])
            else:
                result = {"error": f"unknown tool: {name}"}
        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"}
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}}
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xinka_query.py — MCP 查询补口（C2·闭源运行时侧 2026-10-06）
补 xinka_mcp 只有制卡/校验/保鲜、缺检索与关联查询的缺口。
用法: python3 xinka_query.py search <关键词> [卡目录]   # 按名/结论搜卡
      python3 xinka_query.py neighbors <卡名> [卡目录]  # 关联链查询（A5 数据源）
      python3 xinka_query.py stats [卡目录]             # 信任状态汇总（D1 数据源）
默认卡目录 = /opt/data/spike_体验包/物理（md 卡）或同级 twin/（JSON 孪生）。
"""
import json
import os
import re
import sys

DEFAULT_MD = "/opt/data/spike_体验包/物理"
DEFAULT_JSON = "/opt/data/spike_体验包/twin"


def load_cards(card_dir):
    cards = []
    if card_dir.endswith("twin") or any(f.endswith(".json") for f in os.listdir(card_dir)):
        for f in sorted(os.listdir(card_dir)):
            if not f.endswith(".json"):
                continue
            c = json.load(open(os.path.join(card_dir, f), encoding="utf-8"))
            c["_file"] = f
            cards.append(c)
    else:
        for f in sorted(os.listdir(card_dir)):
            if not re.match(r"^\d{2}-.+\.md$", f):
                continue
            text = open(os.path.join(card_dir, f), encoding="utf-8").read()
            m = re.search(r"^# 信卡·(.+?)（(.+?)）", text, re.M)
            claim_m = re.search(r"## 结论提炼\s*\n1\.\s*\*\*(.+?)\*\*", text)
            links = re.search(r"## 关联（A5·随卡携带）\n(.+)", text)
            cards.append({
                "claim": claim_m.group(1) if claim_m else (m.group(1) if m else f),
                "position": (re.search(r"position=([a-z0-9\-/\.]+)", text) or [None, ""])[1] if re.search(r"position=([a-z0-9\-/\.]+)", text) else "",
                "_file": f,
                "_links": links.group(1) if links else "",
                "_title": m.group(1) if m else f,
            })
    return cards


def search(kw, card_dir):
    cards = load_cards(card_dir)
    hits = [c for c in cards if kw.lower() in json.dumps(c, ensure_ascii=False).lower()]
    print(f"检索「{kw}」→ {len(hits)}/{len(cards)} 命中")
    for c in hits:
        print(f"  {c['_file']}: {str(c.get('claim', ''))[:60]}")
    return hits


def neighbors(name, card_dir):
    cards = load_cards(card_dir)
    for c in cards:
        if name in c["_file"] or name in str(c.get("_title", "")) or name in str(c.get("claim", "")):
            print(f"主卡: {c['_file']}")
            links = c.get("_links", "")
            if links:
                print(f"关联: {links}")
            else:
                print("关联: （JSON 孪生见 twin/ 对应卡 evidence/position）")
            return
    print(f"未找到: {name}")


def stats(card_dir):
    cards = load_cards(card_dir)
    # 口径修正 2026-10-06：已验证=trust_level 精确匹配（关联≠验证，防虚高）
    ver = sum(1 for c in cards if c.get("trust_level") == "verified")
    pend = sum(1 for c in cards if c.get("trust_level") == "pending")
    print(f"卡总数 {len(cards)} · 已验证 {ver} · 待核验 {pend}")
    if cards and "freshness_until" in cards[0]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        dates = sorted((c["freshness_until"], c.get("_file", "")) for c in cards if c.get("freshness_until"))
        if dates:
            print(f"最近到期: {dates[0][1]} @ {dates[0][0]}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in ("search", "neighbors", "stats"):
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    try:
        if cmd == "search":
            search(args[1], args[2] if len(args) > 2 else DEFAULT_MD)
        elif cmd == "neighbors":
            neighbors(args[1], args[2] if len(args) > 2 else DEFAULT_MD)
        else:
            stats(args[1] if len(args) > 1 else DEFAULT_JSON)
    except BrokenPipeError:
        import os
        os._exit(0)  # 管道下游早关（如 | head）不算错

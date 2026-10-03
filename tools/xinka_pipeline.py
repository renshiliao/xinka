#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xinka_pipeline.py — 信卡自动收录流水线（Xinka 0.1）

用法:
  python3 xinka_pipeline.py run request.json [--out DIR] [--online]
  python3 xinka_pipeline.py scan DIR          # 保鲜期扫描（临期/过期清单）

request.json 结构（单条或列表均可）:
[
  {
    "claim": "断言句（不可再拆而保持语义完整的最小命题）",
    "sources": ["https://...", "https://...", "https://..."],   # ≥3 独立源
    "position": "product/projector/xgimi/market-share",          # 树内坐标
    "trust_level": "verified",        # 缺省: sources≥3 → verified, 否则 pending
    "freshness_years": 2,             # 缺省 2
    "collected_at": "2026-10-03T12:30:00Z"   # 缺省: 当前时刻
  }
]

流水线六步: 补全 → 独立性预检(R8) → 时间理顺 → 生成卡 → 过校验器(R1-R7) → 入库+登记索引
零依赖（stdlib only）· Created by Ren Shiliao（任世燎）
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


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug(pos):
    return re.sub(r"[^a-z0-9\-\.]+", "_", pos.lower())


def domain(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def independence_check(sources, trust_level):
    """R8 独立性预检: 源须互不相同；verified 须 ≥2 个独立域名（防伪互证雏形）"""
    issues = []
    if len(set(sources)) != len(sources):
        issues.append("R8 源列表有重复 URL")
    domains = [domain(u) for u in sources]
    uniq = set(d for d in domains if d)
    if trust_level == "verified":
        if len(sources) < 3:
            issues.append("R8 verified 须 ≥3 源")
        if len(uniq) < 2:
            issues.append(f"R8 三源同域名({','.join(uniq)})=疑似转载互抄，不算独立互证")
    return issues


def online_check(urls):
    """--online: HEAD 探活（4xx/5xx/超时=警示，不作为硬拦——网况会抖）"""
    warns = []
    import urllib.request
    for u in urls:
        try:
            req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "xinka-pipeline/0.1"})
            with urllib.request.urlopen(req, timeout=8) as r:
                if r.status >= 400:
                    warns.append(f"R8 源不可达(HTTP {r.status}): {u}")
        except Exception as e:
            warns.append(f"R8 源探活失败({type(e).__name__}): {u}")
    return warns


def build_card(item, index):
    sources = item.get("sources", [])
    trust = item.get("trust_level") or ("verified" if len(sources) >= 3 else "pending")
    collected = item.get("collected_at") or now_iso()
    years = float(item.get("freshness_years", 2))
    t0 = datetime.strptime(collected, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    fresh = (t0 + timedelta(days=365 * years)).strftime("%Y-%m-%dT%H:%M:%SZ")
    card = {
        "xinka_version": "0.1",
        "claim": item["claim"],
        "source_url": sources[0] if sources else "",
        "collected_at": collected,
        "trust_level": trust,
        "freshness_until": fresh,
        "position": item["position"],
        "verification": {
            "method": "three-source cross-check" if trust == "verified" else "single/partial source",
            "sources": sources,
            "checked_at": now_iso() if trust == "verified" else None,
        },
    }
    return card


def run_check(card_path):
    """过校验器 R1-R7: 返回 (ok, 输出)"""
    r = subprocess.run([sys.executable, CHECKER, card_path],
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def cmd_run(req_path, out_dir, online):
    req = json.load(open(req_path, encoding="utf-8"))
    items = req if isinstance(req, list) else [req]
    os.makedirs(out_dir, exist_ok=True)
    index_path = os.path.join(out_dir, "cards_index.json")
    index = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else []

    report = {"total": len(items), "passed": 0, "failed": 0, "warned": 0, "details": []}
    for i, item in enumerate(items, 1):
        entry = {"claim": item.get("claim", "")[:40], "status": "", "notes": []}
        issues = independence_check(item.get("sources", []), item.get("trust_level") or ("verified" if len(item.get("sources", [])) >= 3 else "pending"))
        warns = online_check(item.get("sources", [])) if online else []
        if issues:
            entry["status"] = "REJECTED(R8)"
            entry["notes"] = issues
            report["failed"] += 1
            report["details"].append(entry)
            print(f"✗ [{i}/{len(items)}] R8 独立性预检拦下: {entry['claim']}…")
            for x in issues:
                print(f"    {x}")
            continue
        card = build_card(item, i)
        fn = os.path.join(out_dir, slug(card["position"]) + ".json")
        json.dump(card, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        ok, out = run_check(fn)
        if ok:
            entry["status"] = "OK"
            report["passed"] += 1
            if warns:
                report["warned"] += 1
                entry["notes"] = warns
            # 入登记索引
            index.append({"position": card["position"], "file": os.path.basename(fn),
                          "trust_level": card["trust_level"], "freshness_until": card["freshness_until"],
                          "collected_at": card["collected_at"], "registered": now_iso()})
            print(f"✓ [{i}/{len(items)}] 信卡合法 → {fn}")
            for w in warns:
                print(f"    ⚠ {w}")
        else:
            entry["status"] = "REJECTED(R1-R7)"
            entry["notes"] = out.splitlines()[:4]
            report["failed"] += 1
            print(f"✗ [{i}/{len(items)}] 校验器拦下: {entry['claim']}…")
            for line in entry["notes"]:
                print(f"    {line}")
        report["details"].append(entry)

    json.dump(index, open(index_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(report, open(os.path.join(out_dir, "pipeline_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n—— 流水线完成: {report['passed']}/{report['total']} 过卡 · "
          f"{report['failed']} 拦下 · {report['warned']} 带警告 · 索引累计 {len(index)} 条")


def cmd_scan(dir_path):
    """保鲜期扫描: 过期=须复核降级 / 临期 60 天=提醒"""
    now = datetime.now(timezone.utc)
    warn_before = now + timedelta(days=60)
    expired, soon = [], []
    for fn in sorted(os.listdir(dir_path)):
        if not fn.endswith(".json") or fn == "cards_index.json":
            continue
        try:
            c = json.load(open(os.path.join(dir_path, fn), encoding="utf-8"))
            fu = datetime.strptime(c["freshness_until"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        row = {"file": fn, "position": c.get("position"), "trust_level": c.get("trust_level"),
               "freshness_until": c.get("freshness_until")}
        if fu < now:
            expired.append(row)
        elif fu < warn_before:
            soon.append(row)
    print(f"保鲜扫描 {dir_path}: 过期 {len(expired)} · 临期60天 {len(soon)}")
    for r in expired:
        print(f"  ✗ 已过期须复核: {r['file']} [{r['trust_level']}] 鲜至 {r['freshness_until']}")
    for r in soon:
        print(f"  ⚠ 临期: {r['file']} [{r['trust_level']}] 鲜至 {r['freshness_until']}")
    return expired, soon


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("run", "scan"):
        print(__doc__)
        sys.exit(1)
    if args[0] == "run":
        req = args[1]
        out = "cards"
        online = "--online" in args
        if "--out" in args:
            out = args[args.index("--out") + 1]
        cmd_run(req, out, online)
    else:
        cmd_scan(args[1])


if __name__ == "__main__":
    main()

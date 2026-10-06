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
sys.path.insert(0, HERE)
try:
    import xinka_evidence as ev
except ImportError:
    ev = None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_rfc3339(v):
    """RFC 3339 -> aware datetime（容忍 Z 与 +08:00 偏移；非法抛 ValueError）"""
    if not isinstance(v, str) or not re.search(r"(Z|[+-]\d{2}:\d{2})$", v.strip()):
        raise ValueError(f"非 RFC 3339 时间（须带时区）: {v!r}")
    dt = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"非 RFC 3339 时间（须带时区）: {v!r}")
    return dt


def slug(pos):
    # BUG-10 修复：保留大小写；'/'→'__'、非法字符→'_'（合法 position 不含 '_'，两级映射无歧义，防 a/b 与 a_b 碰撞）
    s = re.sub(r"[^A-Za-z0-9\-/\.]+", "_", str(pos))
    return s.replace("/", "__").strip("_")


def domain(url):
    # BUG-7 修复：lstrip("www.") 按字符集剥离会剥坏 wiley.com 等——改 removeprefix
    try:
        return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
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


def bind_evidence(item, card):
    """R10 引文绑定 + R9 源分级 + 可达硬拦 + 快照（v0.2 全链）。

    返回 (errors, notes)。errors 非空 = 卡不过。
    """
    errors, notes = [], []
    if ev is None:
        return ["R10 xinka_evidence 模块缺失——无法完成引文绑定"], []
    sources = item.get("sources", [])
    # ① 可达硬拦 + 抓正文（每源只抓一次）
    texts = {}
    for s in sources:
        url = s["url"] if isinstance(s, dict) else s
        try:
            texts[url] = ev.fetch_text(url)
        except Exception as e:
            errors.append(f"R10 源不可达（{type(e).__name__}）——硬拦: {url}")
    if errors:
        return errors, notes
    # ② 引文绑定（quote 可在 item 顶层=主证源，或每源带 quote）
    quotes = item.get("quotes", [])
    if not quotes and item.get("quote"):
        quotes = [{"url": sources[0]["url"] if isinstance(sources[0], dict) else sources[0],
                   "quote": item["quote"]}]
    evidence = []
    for q in quotes:
        url = q["url"]
        if url not in texts:
            errors.append(f"R10 引文源不在 sources 内: {url}")
            continue
        b = ev.bind_quote(url, q["quote"], fetched_text=texts[url])
        if not b["ok"]:
            errors.append(f"R10 引文绑定失败: {b['reason']}（{url}）")
        evidence.append({k: b[k] for k in ("url", "quote", "sha256", "fetched_at")})
    if not evidence:
        errors.append("R10 未提供任何引文（item.quote 或 item.quotes）——v0.2 卡必须引文绑定")
    # ③ R9 源分级（机器核验+归一）
    norm_sources = []
    for s in sources:
        if isinstance(s, dict):
            tier, err = ev.classify_tier(s.get("url", ""), s.get("tier"), s.get("first_party_note", ""))
            if err:
                errors.append(err)
            norm_sources.append({"url": s["url"], "tier": tier})
        else:
            tier, _ = ev.classify_tier(s, None)
            norm_sources.append({"url": s, "tier": tier})
    # ④ 快照存档（尽力而为，失败只记不拦）
    snaps = {}
    for s in norm_sources:
        snap = ev.snapshot(s["url"])
        if snap:
            snaps[s["url"]] = snap
        else:
            notes.append(f"快照存档失败（不影响过卡）: {s['url']}")
    if snaps:
        notes.append(f"archive.org 快照 {len(snaps)}/{len(norm_sources)} 成功")
    card["xinka_version"] = "0.2"
    card["verification"]["sources"] = norm_sources
    card["evidence"] = evidence
    if snaps:
        card["snapshots"] = snaps
    return errors, notes


def build_card(item, index):
    sources = item.get("sources", [])
    src_urls = [s["url"] if isinstance(s, dict) else s for s in sources]
    trust = item.get("trust_level") or ("verified" if len(src_urls) >= 3 else "pending")
    collected = item.get("collected_at") or now_iso()
    # BUG-9 修复：claim 缺失/时间非 RFC3339/年限非数——抛 ValueError 由上层转校验错误，不裸崩
    if "claim" not in item:
        raise ValueError("缺 claim 字段")
    try:
        years = float(item.get("freshness_years", 2))
    except (TypeError, ValueError):
        raise ValueError(f"freshness_years 非法: {item.get('freshness_years')!r}")
    try:
        t0 = parse_rfc3339(collected)
    except ValueError:
        raise ValueError(f"collected_at 非 RFC 3339: {collected!r}")
    fresh = (t0 + timedelta(days=365 * years)).strftime("%Y-%m-%dT%H:%M:%SZ")
    card = {
        "xinka_version": "0.2",
        "claim": item["claim"],
        "source_url": src_urls[0] if src_urls else "",
        "collected_at": collected,
        "trust_level": trust,
        "freshness_until": fresh,
        "position": item["position"],
        "verification": {
            "method": "three-source cross-check" if trust == "verified" else "single/partial source",
            "sources": src_urls,
            "checked_at": now_iso() if trust == "verified" else None,
        },
    }
    return card


def run_check(card_path):
    """过校验器 R1-R7: 返回 (ok, 输出)"""
    r = subprocess.run([sys.executable, CHECKER, card_path],
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def cmd_run(req_path, out_dir):
    # BUG-9 修复：请求文件缺失/坏 JSON——一行报错不裸崩
    try:
        req = json.load(open(req_path, encoding="utf-8"))
    except FileNotFoundError:
        print(f"✗ 请求文件不存在: {req_path}")
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"✗ 请求文件 JSON 解析失败: {e}")
        sys.exit(2)
    items = req if isinstance(req, list) else [req]
    os.makedirs(out_dir, exist_ok=True)
    index_path = os.path.join(out_dir, "cards_index.json")
    index = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else []

    report = {"total": len(items), "passed": 0, "failed": 0, "warned": 0, "details": []}
    for i, item in enumerate(items, 1):
        entry = {"claim": item.get("claim", "")[:40], "status": "", "notes": []}
        src_urls = [s["url"] if isinstance(s, dict) else s for s in item.get("sources", [])]
        issues = independence_check(src_urls, item.get("trust_level") or ("verified" if len(src_urls) >= 3 else "pending"))
        if issues:
            entry["status"] = "REJECTED(R8)"
            entry["notes"] = issues
            report["failed"] += 1
            report["details"].append(entry)
            print(f"✗ [{i}/{len(items)}] R8 独立性预检拦下: {entry['claim']}…")
            for x in issues:
                print(f"    {x}")
            continue
        try:
            card = build_card(item, i)
        except ValueError as e:
            # BUG-9 修复：请求字段非法转校验错误，不裸崩
            entry["status"] = "REJECTED(请求非法)"
            entry["notes"] = [str(e)]
            report["failed"] += 1
            report["details"].append(entry)
            print(f"✗ [{i}/{len(items)}] 请求非法: {entry['claim'] or '(无claim)'}… — {e}")
            continue
        # v0.2 全链：可达硬拦 + 引文绑定 + 源分级 + 快照
        ev_errors, ev_notes = bind_evidence(item, card)
        if ev_errors:
            entry["status"] = "REJECTED(R9/R10)"
            entry["notes"] = ev_errors
            report["failed"] += 1
            report["details"].append(entry)
            print(f"✗ [{i}/{len(items)}] R9/R10 拦下: {entry['claim']}…")
            for x in ev_errors:
                print(f"    {x}")
            continue
        fn = os.path.join(out_dir, slug(card["position"]) + ".json")
        # BUG-10 修复：先校验后写盘；slug 碰撞拒绝（防好卡被坏卡静默覆盖）；坏卡不入库
        if os.path.exists(fn):
            entry["status"] = "REJECTED(slug碰撞)"
            entry["notes"] = [f"目标文件已存在，拒绝覆盖: {os.path.basename(fn)}"]
            report["failed"] += 1
            report["details"].append(entry)
            print(f"✗ [{i}/{len(items)}] slug 碰撞拦下: {entry['claim']}…（{os.path.basename(fn)} 已存在）")
            continue
        tmp_fn = fn + ".tmp"
        json.dump(card, open(tmp_fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        ok, out = run_check(tmp_fn)
        if ok:
            os.replace(tmp_fn, fn)
            entry["status"] = "OK"
            report["passed"] += 1
            entry["notes"] = ev_notes
            index.append({"position": card["position"], "file": os.path.basename(fn),
                          "trust_level": card["trust_level"], "freshness_until": card["freshness_until"],
                          "collected_at": card["collected_at"], "registered": now_iso()})
            print(f"✓ [{i}/{len(items)}] 信卡合法（v0.2·引文绑定）→ {fn}")
            for w in ev_notes:
                print(f"    · {w}")
        else:
            # BUG-10 修复：失败分支删除临时文件——被拦坏卡不留在库
            if os.path.exists(tmp_fn):
                os.remove(tmp_fn)
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
          f"{report['failed']} 拦下 · 索引累计 {len(index)} 条")


def cmd_reverify(dir_path):
    """复检: 重抓源正文→比对 evidence.sha256 指纹——源改稿/消失当场现形"""
    if ev is None:
        print("xinka_evidence 模块缺失")
        return
    total = ok = drifted = vanished = 0
    for fn in sorted(os.listdir(dir_path)):
        if not fn.endswith(".json") or fn == "cards_index.json":
            continue
        card = json.load(open(os.path.join(dir_path, fn), encoding="utf-8"))
        for e in card.get("evidence", []):
            total += 1
            url, digest = e["url"], e["sha256"]
            try:
                text = ev.fetch_text(url)
            except Exception as ex:
                vanished += 1
                print(f"  ✗ 源已失效: {fn} ← {url}（{type(ex).__name__}）")
                continue
            import hashlib
            now_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if now_digest == digest:
                ok += 1
            else:
                drifted += 1
                print(f"  ⚠ 源已改稿（指纹漂移）: {fn} ← {url}")
                q = ev.normalize(e.get("quote", ""))
                if q and q in text:
                    print(f"    （引文仍在正文中——断言未受影响）")
                else:
                    print(f"    ✗✗ 引文已不在正文——断言失据，须复核降级！")
    print(f"\n—— 复检完成: {total} 引文 · 指纹一致 {ok} · 改稿 {drifted} · 失效 {vanished}")


def cmd_scan(dir_path):
    """保鲜期扫描: 过期=须复核降级 / 临期 60 天=提醒"""
    now = datetime.now(timezone.utc)
    warn_before = now + timedelta(days=60)
    expired, soon, bad = [], [], []
    for fn in sorted(os.listdir(dir_path)):
        if not fn.endswith(".json") or fn == "cards_index.json":
            continue
        try:
            c = json.load(open(os.path.join(dir_path, fn), encoding="utf-8"))
            fu = parse_rfc3339(c["freshness_until"])
        except Exception:
            # BUG-13 修复：坏卡/坏时间不静默——计数并警示
            bad.append(fn)
            continue
        row = {"file": fn, "position": c.get("position"), "trust_level": c.get("trust_level"),
               "freshness_until": c.get("freshness_until")}
        if fu < now:
            expired.append(row)
        elif fu < warn_before:
            soon.append(row)
    print(f"保鲜扫描 {dir_path}: 过期 {len(expired)} · 临期60天 {len(soon)}"
          + (f" · 不可解析 {len(bad)}" if bad else ""))
    for b in bad:
        print(f"  ⚠ 不可解析（坏 JSON/坏时间）: {b}")
    for r in expired:
        print(f"  ✗ 已过期须复核: {r['file']} [{r['trust_level']}] 鲜至 {r['freshness_until']}")
    for r in soon:
        print(f"  ⚠ 临期: {r['file']} [{r['trust_level']}] 鲜至 {r['freshness_until']}")
    return expired, soon


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("run", "scan", "reverify"):
        print(__doc__)
        sys.exit(1)
    # BUG-9 修复：缺参数/悬空 --out——报错退出，不 IndexError 裸崩
    def need(idx, what):
        if len(args) <= idx:
            print(f"✗ 缺参数: {what}")
            sys.exit(2)
        return args[idx]
    if args[0] == "run":
        req = need(1, "run 需要请求文件路径")
        out = "cards"
        if "--out" in args:
            i = args.index("--out")
            out = need(i + 1, "--out 需要输出目录")
        cmd_run(req, out)
    elif args[0] == "reverify":
        cmd_reverify(need(1, "reverify 需要卡目录"))
    else:
        cmd_scan(need(1, "scan 需要卡目录"))


if __name__ == "__main__":
    main()

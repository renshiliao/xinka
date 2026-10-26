#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2xinka.py — md 实卡 → xinka JSON 机读孪生卡提取器（C1·闭源运行时侧 2026-10-06·v0.3 2026-10-27）
用法: python3 md2xinka.py <卡目录> <输出目录>
产出: 每张 md 卡一个 .json 孪生（v0.3 结构·过 R1-R12）；源分级元数据随卡输出到 tiers_report.json
v0.3 补收（方法段进机读形制，防再被洗掉）：card_type 卡种（META 组块/标题标记推导）、
能力卡「骨架句」、排障卡「症状词/判死法/修法」三段——字段名与心网 v4 字段表一致，禁改名。
v0.3 信任分型：一手实证+复现判死法 → trust_level=empirical（实证档免三源互证）。
不碰冻结层。A3 引文绑定（R10）需源抓取，另批处理（生成后必重绑；经验卡免绑）。
"""
import json
import os
import re
import sys

# A7 保鲜期按结论类型分层（年）——门类配置
FRESH_YEARS = {
    # 物理定律/公式——半衰极慢
    "01": 5, "02": 5, "03": 5, "04": 5, "05": 5, "06": 5, "07": 5,
    # 定义类（色温/CRI）——定义稳定
    "11": 3, "12": 3,
    # 工程工作法/速算——随口径微调
    "08": 2, "10": 2,
    # 选型区间/分档口诀/报价法/国标值——随市场与改版动
    "09": 1, "13": 1, "14": 1, "15": 1,
    # 教材版本——2024 新版启用期，短保鲜
    "16": 0.5, "17": 0.5, "18": 0.5,
}

# A2 源分级（R9 tier）——按域名贴标签
TIER_RULES = [
    ("baike.baidu.com", "aggregator", "百度百科"),
    ("zhuanlan.zhihu.com", "aggregator", "知乎专栏"),
    ("blog.csdn.net", "aggregator", "CSDN"),
    ("sohu.com", "media", "搜狐"),
    ("jd.com", "media", "京东商品页"),
    ("europtics.com.cn", "media", "欧光"),
]


def tier_of(url):
    for dom, tier, name in TIER_RULES:
        if dom in url:
            return tier, name
    return "unknown", url


# v0.3 卡种：META「组块」→ card_type 枚举（字段名与心网 v4 字段表对齐，禁改名）
BLOCK2TYPE = {"知识": "knowledge", "能力": "ability", "排障": "troubleshoot",
              "台账": "ledger", "心法": "mind"}
TITLE2TYPE = (("能力卡", "ability"), ("排障卡", "troubleshoot"), ("知识卡", "knowledge"),
              ("台账", "ledger"), ("心法卡", "mind"))


def detect_card_type(text, title, subtitle):
    """卡种判定：META 组块 优先 → 标题/小标题标记 兜底 → 默认 knowledge 并提示"""
    m = re.search(r"^组块:\s*(.+)$", text, re.M)
    if m:
        key = m.group(1).strip()
        for k, v in BLOCK2TYPE.items():
            if k in key:
                return v
    head = title + subtitle
    for k, v in TITLE2TYPE:
        if k in head:
            return v
    print(f"⚠ 未识别卡种（组块/标题均无标记），默认 knowledge ——请补 META 组块")
    return "knowledge"


def section_lines(text, name):
    """抽「## name」分节逐行正文（去列表符号），到下一个 ## 或文末——v0.3 方法段抽取"""
    m = re.search(rf"^##\s*{re.escape(name)}[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        return []
    lines = []
    for ln in m.group(1).splitlines():
        ln = re.sub(r"^\s*[-*]\s+|^\s*\d+\.\s+", "", ln).strip()
        if ln:
            lines.append(ln)
    return lines


def parse_card(path):
    text = open(path, encoding="utf-8").read()
    no = os.path.basename(path)[:2]
    out = {"file": os.path.basename(path), "no": no}

    m = re.search(r"^# 信卡·(.+?)（(.+?)）", text, re.M)
    out["title"] = m.group(1).strip() if m else os.path.basename(path)
    out["subtitle"] = m.group(2).strip() if m else ""

    # 六要表
    def row(name):
        mm = re.search(rf"\|\s*\*\*{name}\*\*\s*\|\s*(.+?)\s*\|", text)
        return mm.group(1) if mm else ""

    out["source_row"] = row("来源")
    out["date_row"] = row("日期")
    out["property_row"] = row("属性")

    # 结论提炼第一条 = claim
    cm = re.search(r"## 结论提炼\s*\n1\.\s*\*\*(.+?)\*\*[:：]?\s*(.+)", text)
    if cm:
        out["claim"] = re.sub(r"\s+", " ", (cm.group(1) + "：" + cm.group(2))).strip()
    else:
        out["claim"] = f"{out['title']}——{out['subtitle']}"

    # position（缺口3修复：先卡内 position=，再 META 挂载推导门类，禁硬编码 physics）
    pm = re.search(r"position=([a-z0-9\-/\.]+)", text)
    if pm:
        out["position"] = pm.group(1)
    else:
        mm = re.search(r"^挂:\s*(.+)$", text, re.M)
        seg = (mm.group(1).strip().replace("心网/", "").replace("spike_体验包/", "")
               .replace("物理/", "").replace("index.md", "").replace(".md", "").strip("/")) if mm else ""  # 无挂载字段不崩
        out["position"] = f"{seg or 'misc'}/{no}"
    # 保鲜期：优先读卡内 A7 显式区间（缺口3修复：不再依赖文件名前缀硬表）
    fm = re.search(r"\*\*保鲜期\*\*\s*\|\s*(?:\d+(?:\.\d+)?年：)?\s*([\d-]{10})\s*~\s*([\d-]{10})", text)
    if fm:
        out["collected"] = fm.group(1) + "T12:00:00+08:00"
        out["fresh_until"] = fm.group(2) + "T12:00:00+08:00"

    # URLs（来源行）
    out["urls"] = list(dict.fromkeys(re.findall(r"https?://[^\s、）)]+", out["source_row"])))
    # 置信标记
    out["has_pending"] = "⚠️待核验" in text or "【⚠️】" in text
    out["verified_mark"] = "【已验证】" in text
    # v0.3：卡种 + 方法段（骨架句/症状词/判死法/修法）——防机读层洗掉方法
    out["card_type"] = detect_card_type(text, out["title"], out["subtitle"])
    out["骨架句"] = section_lines(text, "骨架句")
    out["症状词"] = section_lines(text, "症状词")
    out["判死法"] = section_lines(text, "判死法")
    out["修法"] = section_lines(text, "修法")
    out["has_firstparty"] = "[一手]" in text or "一手源" in text
    return out


def make_twin(c, now_iso):
    from datetime import datetime, timedelta, timezone
    collected = c.get("collected", "2026-10-05T12:00:00+08:00")
    fresh = c.get("fresh_until")
    if not fresh:
        years = FRESH_YEARS.get(c["no"], 1)
        t0 = datetime.fromisoformat(collected)
        fresh = (t0 + timedelta(days=round(365 * years))).strftime("%Y-%m-%dT12:00:00+08:00")
    srcs = c["urls"]
    verified = c["verified_mark"] and not c["has_pending"] and len(set(srcs)) >= 3
    # v0.3 信任分型：一手实证+复现判死法/骨架 → empirical（实证档免三源互证）
    empirical = (not verified and c["verified_mark"] and not c["has_pending"]
                 and (c.get("骨架句") or c.get("判死法"))
                 and (c.get("has_firstparty") or not srcs))
    if verified:
        trust, method = "verified", "three-source cross-check"
    elif empirical:
        trust, method = "empirical", "本机一手实证+复现判死法（trust=empirical·实证档免三源互证）"
    else:
        trust, method = "pending", "single/partial source"
    twin = {
        "xinka_version": "0.3",
        "card_type": c["card_type"],
        "claim": c["claim"][:500],
        "source_url": srcs[0] if srcs else "https://example.invalid/internal-material",
        "collected_at": collected,
        "trust_level": trust,
        "freshness_until": fresh,
        "position": c["position"],
        "verification": {
            "method": method,
            "sources": srcs,
            "checked_at": collected if (verified or empirical) else None,
        },
    }
    # v0.3 方法段进孪生（骨架句/症状词=列表；判死法/修法=句）——字段名与心网 v4 字段表一致
    if c.get("骨架句"):
        twin["骨架句"] = c["骨架句"]
    if c.get("症状词"):
        twin["症状词"] = c["症状词"]
    if c.get("判死法"):
        twin["判死法"] = "；".join(c["判死法"])
    if c.get("修法"):
        twin["修法"] = "；".join(c["修法"])
    return twin


def main(card_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cards = [parse_card(os.path.join(card_dir, f))
             for f in sorted(os.listdir(card_dir))
             if re.match(r"^\d{2}-.+\.md$", f)]
    # 双闸硬接 2026-10-06：压卡内容入盘前过 background_review（不再依赖人工记得跑）
    review = "/opt/data/scripts/background_review.sh"
    if os.path.exists(review):
        import subprocess
        passed = []
        for c in cards:
            body = open(os.path.join(card_dir, c["file"]), encoding="utf-8").read()
            p = subprocess.run(["bash", review, c["file"]], input=body,
                               capture_output=True, text=True)
            if p.returncode != 0:
                print(f"🚫 双闸拦下不入孪生: {c['file']} — {p.stdout.strip()}")
            else:
                passed.append(c)
        cards = passed
    tiers_report = {}
    for c in cards:
        twin = make_twin(c, None)
        out_path = os.path.join(out_dir, c["file"].replace(".md", ".json"))
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(twin, f, ensure_ascii=False, indent=2)
        tiers_report[c["file"]] = [
            {"url": u, "tier": tier_of(u)[0], "source": tier_of(u)[1]} for u in c["urls"]
        ]
    with open(os.path.join(os.path.dirname(out_dir.rstrip("/")) or ".", "tiers_report.json"), "w", encoding="utf-8") as f:
        json.dump(tiers_report, f, ensure_ascii=False, indent=2)
    print(f"孪生卡生成: {len(cards)} → {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

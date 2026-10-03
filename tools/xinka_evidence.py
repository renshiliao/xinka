#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xinka_evidence.py — 引文绑定与源分级底层（stdlib only）

被 xinka_pipeline.py / xinka_mcp.py 共用。功能:
  fetch_text(url)      — 抓取页面正文（超时/失败=硬信号，调用方负责拦）
  bind_quote(...)      — 引文绑定: 校验引文逐字出现在正文中, 返回正文 sha256
  classify_tier(url, claimed_tier, note) — R9 源分级机器核验
  snapshot(url)        — web.archive.org 快照存档（尽力而为, 失败不拦）
Created by Ren Shiliao（任世燎）· Xinka Spec v0.1→0.2
"""
import hashlib
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Xinka-Evidence/0.2; +https://xinka.ai)"}

# R9 一手源域名白名单（政府/标准组织/交易所披露/学术——机器可核验的第一方）
TIER1_DOMAINS = {
    # 政府/国际组织
    "gov", "gov.cn", "europa.eu", "who.int", "un.org", "nist.gov", "census.gov",
    "destatis.de", "samr.gov.cn", "stats.gov.cn", "mee.gov.cn", "miit.gov.cn",
    "mof.gov.cn", "npc.gov.cn", "court.gov.cn", "spp.gov.cn", "moj.gov.cn",
    # 标准组织
    "iso.org", "iec.ch", "webstore.iec.ch", "ieee.org", "cen.eu", "cencenelec.eu",
    "gb688.cn", "std.samr.gov.cn", "openstd.samr.gov.cn",
    # 交易所/监管披露
    "sse.com.cn", "szse.cn", "bse.cn", "hkex.com.hk", "sec.gov", "cninfo.com.cn",
    "static.sse.com.cn",
    # 学术
    "arxiv.org", "doi.org", "nature.com", "science.org", "springer.com",
    "wiley.com", "sciencedirect.com", "nber.org", "qje.oxfordjournals.org",
    "academic.oup.com",
    # 官方文档/官方商城（产品参数的第一方）
    "docs.python.org", "developer.android.com", "platform.claude.com",
    "mall.hisense.com", "mi.com", "xiaomi.com", "apple.com", "xgimi.com",
}

# R9 三级源（聚合/UGC——不可单独作为一手证）
TIER3_DOMAINS = {
    "wikipedia.org", "zh.wikipedia.org", "baike.baidu.com", "zhihu.com",
    "sohu.com", "163.com", "toutiao.com", "csdn.net", "jianshu.com",
    "bilibili.com", "douyin.com", "weibo.com", "x.com", "twitter.com",
    "facebook.com", "reddit.com", "mbd.baidu.com", "smzdm.com", "ithome.com",
}


def domain_of(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _host_matches(dom, pool):
    return any(dom == d or dom.endswith("." + d) for d in pool)


def normalize(text):
    """正文归一: 去 HTML 标签/折叠空白——引文比对与哈希同口径"""
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_text(url, timeout=12):
    """抓取并归一化正文。失败抛异常（调用方硬拦）。"""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(2_000_000)
    try:
        html = raw.decode("utf-8", errors="ignore")
    except Exception:
        html = raw.decode("latin-1", errors="ignore")
    return normalize(html)


def bind_quote(url, quote, fetched_text=None):
    """R10 引文绑定: 引文必须逐字出现在抓取正文中；返回 evidence 三元组。

    返回 dict: {url, quote, sha256, fetched_at, ok, reason}
    """
    from datetime import datetime, timezone
    if fetched_text is None:
        fetched_text = fetch_text(url)
    nq = normalize(quote)
    ok = len(nq) >= 8 and nq in fetched_text
    return {
        "url": url,
        "quote": quote[:300],
        "sha256": hashlib.sha256(fetched_text.encode("utf-8")).hexdigest(),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": ok,
        "reason": "" if ok else ("引文未在正文中找到——疑似编造引文或源已改稿" if len(nq) >= 8 else "引文过短（<8 字）不足以绑定"),
    }


def classify_tier(url, claimed_tier, note=""):
    """R9 机器核验源分级。返回 (tier, error|None)"""
    dom = domain_of(url)
    if _host_matches(dom, TIER3_DOMAINS):
        if claimed_tier == "first-party":
            return "aggregator", f"R9 {dom} 属聚合/UGC 域名，不可申报 first-party"
        return claimed_tier or "aggregator", None
    if _host_matches(dom, TIER1_DOMAINS):
        return "first-party", None
    # 未分类域名: first-party 须附 note（人工依据），否则降 media
    if claimed_tier == "first-party":
        if note.strip():
            return "first-party", None
        return "media", f"R9 {dom} 不在一手源白名单且未附 first_party_note"
    return claimed_tier or "media", None


def snapshot(url, timeout=20):
    """web.archive.org 快照存档（尽力而为）。返回快照 URL 或 None。"""
    try:
        save = "https://web.archive.org/save/" + url
        req = urllib.request.Request(save, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            loc = r.headers.get("Content-Location") or ""
        if loc.startswith("/web/"):
            return "https://web.archive.org" + loc
        if loc.startswith("http"):
            return loc
        return "https://web.archive.org/web/2/" + url  # 提交成功但未回读时间戳
    except Exception:
        return None

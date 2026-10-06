#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xinka check — Xinka（信卡）免费校验器
校验单张或多张信卡的格式合法性与内部一致性（无需第三方依赖，Python 3.8+ 即可运行）。

用法:
    python3 xinka_check.py card.json            # 校验单张
    python3 xinka_check.py cards/*.json         # 校验多张
    python3 xinka_check.py --example            # 输出一张示例卡

规则（Xinka Spec v0.1 / v0.2）:
    R1  六要素必填齐备（源/采/信/鲜/位/证）——含值类型与非空检查
    R2  时间格式 RFC 3339（必须带时区偏移）；collected_at 必须早于 freshness_until
    R3  trust_level 只能是 verified / pending
    R4  verified 卡必须有 >=3 个互不相同的互证来源
    R5  保鲜期已过（now > freshness_until）且未复核 -> 强制降级提示
    R6  verification.checked_at 不得早于 collected_at
    R7  source_url 必须 http(s)，position 坐标合法
    R8  三源独立性由 pipeline 预检 / MCP 执行（本校验器不重复检查）
    R9  源分级（v0.2）: verified 卡须含 >=1 一手源(first-party)，聚合/UGC 不可单独成证
    R10 引文绑定（v0.2）: evidence 引文 >=8 字、逐字出自对应源、附 sha256 指纹

schema 上限内联校验（claim 4-500、quote 8-300、position <=200、拒额外字段、拒伪 URL）。

v0.1 卡按 R1-R7 校验（向后兼容）；v0.2 卡追加 R9/R10。
引文逐字核对与 sha256 复核（抓取比对）由 xinka_evidence.py / pipeline --reverify 完成。

Xinka Specification Early Draft v0.2
Created by Ren Shiliao (任世燎) · 2026 · xinka.ai
"""

import json
import re
import sys
from datetime import datetime, timezone

REQUIRED = ["xinka_version", "claim", "source_url", "collected_at",
            "trust_level", "freshness_until", "position", "verification"]
VERIF_REQUIRED = ["method", "sources", "checked_at"]
POSITION_RE = re.compile(r"^[a-z0-9\-]+(/[a-z0-9\-\.]+)*$")
SCHEMA_TOP_KEYS = set(REQUIRED) | {"evidence", "snapshots"}
SCHEMA_VERIF_KEYS = set(VERIF_REQUIRED) | {"first_party_note"}
# schema 上限内联（xinka-0.2.schema.json 对照）
LIMITS = {"claim": (4, 500), "quote": (8, 300), "position": (1, 200)}

EXAMPLE = {
    "xinka_version": "0.1",
    "claim": "示例：MiMo-V2.6-Pro 为 1.02T 参数、激活 42B 的开源大模型",
    "source_url": "https://example.com/official-model-card",
    "collected_at": "2026-10-01T10:00:00Z",
    "trust_level": "pending",
    "freshness_until": "2027-04-01T10:00:00Z",
    "position": "ai/models/open-weights/mimo",
    "verification": {
        "method": "three-source cross-check",
        "sources": [],
        "checked_at": None
    }
}


def parse_time(v):
    """RFC 3339 -> aware datetime（必须带时区偏移；拒绝 naive/紧凑格式）"""
    if not isinstance(v, str):
        return None
    s = v.strip()
    # RFC 3339 必须带时区：Z 或 ±HH:MM
    if not re.search(r"(Z|[+-]\d{2}:\d{2})$", s):
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else None


def _src_url(s):
    """v0.2 sources 可为字符串或 {url, tier, note} 对象——统一取 url"""
    return s.get("url", "") if isinstance(s, dict) else str(s)


def _src_tier(s):
    return s.get("tier") if isinstance(s, dict) else None


def _src_note(s):
    return s.get("note", "") if isinstance(s, dict) else ""


def _chk_limits(errors):
    """schema 上限/类型内联校验（BUG-6 修复：与 xinka-0.2.schema.json 对照）"""
    pass  # 由 check_card 内联调用，占位防误用


def check_card(card, now=None):
    """返回 (errors, warnings) 列表。errors 空 = 通过。"""
    errors, warnings = [], []
    now = now or datetime.now(timezone.utc)

    # R1 六要素必填（BUG-1/3/4 修复：不只查键，还查值类型与非空）
    if not isinstance(card, dict):
        return ["R1 根对象必须是 JSON object"], []
    for k in REQUIRED:
        if k not in card:
            errors.append(f"R1 缺要素【{k}】——六要素必填齐备")
    # 额外字段（schema additionalProperties:false）
    for k in card:
        if k not in SCHEMA_TOP_KEYS:
            errors.append(f"R1 额外字段【{k}】——schema 不允许 additionalProperties")

    claim = card.get("claim")
    if "claim" in card:
        if not isinstance(claim, str):
            errors.append(f"R1 claim 必须是 string（当前 {type(claim).__name__}）")
        elif not claim.strip():
            errors.append("R1 claim 不可为空")
        elif not (LIMITS["claim"][0] <= len(claim) <= LIMITS["claim"][1]):
            errors.append(f"R1 claim 长度须 {LIMITS['claim'][0]}-{LIMITS['claim'][1]}（当前 {len(claim)}）")

    xkv = card.get("xinka_version")
    if "xinka_version" in card and (not isinstance(xkv, str) or not re.match(r"^0\.[0-9]+$", xkv)):
        errors.append(f"R1 xinka_version 非法: {xkv!r}（形如 0.2）")

    # R7 source_url / position（BUG-4 修复：空串按非法）
    su = card.get("source_url")
    if "source_url" in card:
        if not isinstance(su, str) or not su.strip():
            errors.append("R7 source_url 不可为空（无出处则任何引用不成立）")
        elif not re.match(r"^https?://", su):
            errors.append("R7 source_url 必须以 http(s):// 开头")
    pos = card.get("position")
    if "position" in card:
        if not isinstance(pos, str) or not pos.strip():
            errors.append("R7 position 不可为空")
        elif not POSITION_RE.match(pos):
            errors.append("R7 position 坐标非法（小写字母/数字/连字符，层级用 / 分隔）")
        elif len(pos) > LIMITS["position"][1]:
            errors.append(f"R7 position 超长（>{LIMITS['position'][1]}）")

    # R3 trust_level
    tl = card.get("trust_level")
    if "trust_level" in card:
        if not isinstance(tl, str) or tl not in ("verified", "pending"):
            errors.append(f"R3 trust_level 非法: {tl!r}（只允许 verified / pending）")

    # R2 时间格式与顺序（BUG-2 修复：无时区=R2 拒绝，不再放行后崩）
    ca_raw, fu_raw = card.get("collected_at"), card.get("freshness_until")
    ca = parse_time(ca_raw) if ca_raw is not None else None
    fu = parse_time(fu_raw) if fu_raw is not None else None
    if "collected_at" in card:
        if ca_raw is not None and ca is None:
            errors.append("R2 collected_at 非 RFC 3339 时间格式（须带时区，如 ...Z 或 +08:00）")
    if "freshness_until" in card:
        if fu_raw is not None and fu is None:
            errors.append("R2 freshness_until 非 RFC 3339 时间格式（须带时区，如 ...Z 或 +08:00）")
    if ca and fu and ca >= fu:
        errors.append("R2 collected_at 必须早于 freshness_until")

    # R5 保鲜期降级
    if fu and now > fu and tl == "verified":
        warnings.append("R5 保鲜期已过——trust_level 应降级为 pending 直至复核")
    elif fu and now > fu:
        warnings.append("R5 保鲜期已过——待复核（当前已是 pending）")

    # verification 结构（BUG-3 修复：None 不再静默通过）
    ver = card.get("verification")
    is_v02 = str(card.get("xinka_version", "")).startswith("0.2")
    if ver is None:
        if "verification" in card:
            errors.append("R1 verification 必须是 object（不可为 null）")
    elif not isinstance(ver, dict):
        errors.append("R1 verification 必须是 object")
    else:
        for k in VERIF_REQUIRED:
            if k not in ver:
                errors.append(f"R1 verification 缺字段【{k}】")
        for k in ver:
            if k not in SCHEMA_VERIF_KEYS:
                errors.append(f"R1 verification 额外字段【{k}】")
        srcs = ver.get("sources", [])
        if not isinstance(srcs, list):
            errors.append("R6 verification.sources 必须是数组")
            srcs = []
        urls = [_src_url(s) for s in srcs]
        # R4 verified 需 >=3 独立源
        if tl == "verified":
            uniq = set(urls)
            if len(uniq) < 3:
                errors.append(f"R4 verified 卡须 >=3 个互不相同的互证来源（当前 {len(uniq)}）")
        # 独立性提示
        elif len(set(urls)) != len(urls):
            warnings.append("R4 sources 中存在重复来源——独立性存疑")
        # source 条目结构与 URL 合法性
        for i, s in enumerate(srcs):
            u = _src_url(s)
            if not isinstance(u, str) or not re.match(r"^https?://", u):
                errors.append(f"R7 verification.sources[{i}] 非法 URL: {u!r}")
        # R9 源分级（v0.2）
        if is_v02:
            tiers = [_src_tier(s) for s in srcs]
            if tl == "verified" and not any(t == "first-party" for t in tiers):
                errors.append("R9 verified 卡须含 >=1 一手源（first-party）——聚合/UGC 不可单独成证")
            for s in srcs:
                t = _src_tier(s)
                if t is not None and t not in ("first-party", "media", "aggregator", "unknown"):
                    errors.append(f"R9 源分级非法: {t!r}（只允许 first-party/media/aggregator/unknown）")
        # R10 引文绑定（v0.2）
        ev = card.get("evidence")
        if is_v02:
            if not isinstance(ev, list) or not ev:
                errors.append("R10 缺 evidence 引文绑定——v0.2 卡必须附引文+指纹")
            else:
                for i, e in enumerate(ev):
                    if not isinstance(e, dict):
                        errors.append(f"R10 evidence[{i}] 必须是 object")
                        continue
                    q_raw = e.get("quote", "")
                    q = normalize_local(q_raw)
                    if not isinstance(q_raw, str) or len(q) < LIMITS["quote"][0]:
                        errors.append(f"R10 evidence[{i}] 引文过短（<{LIMITS['quote'][0]} 字）不足以绑定")
                    elif len(q) > LIMITS["quote"][1]:
                        errors.append(f"R10 evidence[{i}] 引文超长（>{LIMITS['quote'][1]}）")
                    if not e.get("sha256") or not re.match(r"^[0-9a-f]{64}$", str(e.get("sha256"))):
                        errors.append(f"R10 evidence[{i}] 缺合法 sha256 指纹")
                    if e.get("url") not in urls and e.get("url") != card.get("source_url"):
                        errors.append(f"R10 evidence[{i}] url 不在 sources 内——引文须绑定到证源")
        elif ev is not None:
            warnings.append("R10 检测到 evidence 字段但 xinka_version 非 0.2——建议升版")
        # R6 checked_at 顺序
        chk = ver.get("checked_at")
        if chk is not None:
            ct = parse_time(chk)
            if ct is None:
                errors.append("R6 verification.checked_at 非 RFC 3339 格式（须带时区）")
            elif ca and ct < ca:
                errors.append("R6 checked_at 不得早于 collected_at")

    return errors, warnings


def normalize_local(text):
    """引文归一（与 xinka_evidence.normalize 同口径的轻量版）"""
    return re.sub(r"\s+", " ", str(text)).strip()


def main(argv):
    if "--example" in argv:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return 0
    if not argv:
        print(__doc__)
        return 1

    failed = 0
    for path in argv:
        try:
            with open(path, encoding="utf-8") as f:
                card = json.load(f)
        except FileNotFoundError:
            print(f"✗ {path}: 文件不存在")
            failed += 1
            continue
        except json.JSONDecodeError as e:
            print(f"✗ {path}: JSON 解析失败——{e}")
            failed += 1
            continue

        errors, warnings = check_card(card)
        # BUG-1 修复：claim 非法类型不再崩栈
        claim = card.get("claim", path) if isinstance(card, dict) else path
        if not isinstance(claim, str):
            claim = repr(claim)
        name = claim[:40]
        if errors:
            failed += 1
            print(f"✗ {path}")
            for e in errors:
                print(f"    ERROR  {e}")
        else:
            print(f"✓ {path}  [{name}…]  信卡合法")
        for w in warnings:
            print(f"    WARN   {w}")

    print(f"\n{'—' * 46}\n校验完成: {len(argv) - failed}/{len(argv)} 通过"
          + (f" · {failed} 张未通过" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

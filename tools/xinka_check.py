#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xinka check — Xinka（信卡）免费校验器
校验单张或多张信卡的格式合法性与内部一致性（无需第三方依赖，Python 3.8+ 即可运行）。

用法:
    python3 xinka_check.py card.json            # 校验单张
    python3 xinka_check.py cards/*.json         # 校验多张
    python3 xinka_check.py --example            # 输出一张示例卡

规则（Xinka Spec v0.1）:
    R1  六要素必填齐备（源/采/信/鲜/位/证）
    R2  时间格式 RFC 3339；collected_at 必须早于 freshness_until
    R3  trust_level 只能是 verified / pending
    R4  verified 卡必须有 >=3 个互不相同的互证来源
    R5  保鲜期已过（now > freshness_until）且未复核 -> 强制降级提示
    R6  verification.checked_at 不得早于 collected_at
    R7  source_url 必须 http(s)，position 坐标合法

Xinka Specification Early Draft v0.1
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
    """RFC 3339 -> datetime（容忍 Z 后缀）"""
    if not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


def check_card(card, now=None):
    """返回 (errors, warnings) 列表。errors 空 = 通过。"""
    errors, warnings = [], []
    now = now or datetime.now(timezone.utc)

    # R1 六要素必填
    if not isinstance(card, dict):
        return ["R1 根对象必须是 JSON object"], []
    for k in REQUIRED:
        if k not in card:
            errors.append(f"R1 缺要素【{k}】——六要素必填齐备")

    # R7 source_url / position
    su = card.get("source_url", "")
    if su and not re.match(r"^https?://", str(su)):
        errors.append("R7 source_url 必须以 http(s):// 开头")
    pos = card.get("position", "")
    if pos and (not isinstance(pos, str) or not POSITION_RE.match(pos)):
        errors.append("R7 position 坐标非法（小写字母/数字/连字符，层级用 / 分隔）")

    # R3 trust_level
    tl = card.get("trust_level")
    if tl and tl not in ("verified", "pending"):
        errors.append(f"R3 trust_level 非法: {tl!r}（只允许 verified / pending）")

    # R2 时间格式与顺序
    ca = parse_time(card.get("collected_at"))
    fu = parse_time(card.get("freshness_until"))
    if card.get("collected_at") and ca is None:
        errors.append("R2 collected_at 非 RFC 3339 时间格式")
    if card.get("freshness_until") and fu is None:
        errors.append("R2 freshness_until 非 RFC 3339 时间格式")
    if ca and fu and ca >= fu:
        errors.append("R2 collected_at 必须早于 freshness_until")

    # R5 保鲜期降级
    if fu and now > fu and tl == "verified":
        warnings.append("R5 保鲜期已过——trust_level 应降级为 pending 直至复核")
    elif fu and now > fu:
        warnings.append("R5 保鲜期已过——待复核（当前已是 pending）")

    # verification 结构
    ver = card.get("verification")
    if isinstance(ver, dict):
        for k in VERIF_REQUIRED:
            if k not in ver:
                errors.append(f"R1 verification 缺字段【{k}】")
        srcs = ver.get("sources", [])
        if not isinstance(srcs, list):
            errors.append("R6 verification.sources 必须是数组")
            srcs = []
        # R4 verified 需 >=3 独立源
        if tl == "verified":
            uniq = set(map(str, srcs))
            if len(uniq) < 3:
                errors.append(f"R4 verified 卡须 >=3 个互不相同的互证来源（当前 {len(uniq)}）")
        # 独立性提示
        elif len(set(map(str, srcs))) != len(srcs):
            warnings.append("R4 sources 中存在重复来源——独立性存疑")
        # R6 checked_at 顺序
        chk = ver.get("checked_at")
        if chk is not None:
            ct = parse_time(chk)
            if ct is None:
                errors.append("R6 verification.checked_at 非 RFC 3339 格式")
            elif ca and ct < ca:
                errors.append("R6 checked_at 不得早于 collected_at")
    elif ver is not None:
        errors.append("R1 verification 必须是 object")

    return errors, warnings


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
        name = card.get("claim", path)[:40] if isinstance(card, dict) else path
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

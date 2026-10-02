#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xinka_gen — Xinka 信卡参考实现（生成器）
一条命令把「断言+出处」变成合规信卡 JSON（六要素自动补全）。

用法:
    from xinka_gen import make_card
    card = make_card(
        claim="地球赤道周长约 40075 公里",
        source_url="https://education.nationalgeographic.org/resource/equator/",
        position="science/geography/earth",
        extra_sources=["https://…", "https://…"],   # 凑满 3 源自动升 verified
        freshness_years=2,
    )

规则内建：3 源自动升 verified；不足则 pending；保鲜期按年限算；时间全 RFC 3339。
Xinka Reference Implementation v0.1 · Created by Ren Shiliao (任世燎) 2026
"""
import json
from datetime import datetime, timedelta, timezone


def make_card(claim: str, source_url: str, position: str,
              extra_sources: list = None, freshness_years: float = 2,
              trust_level: str = None) -> dict:
    """生成一张合规的 Xinka 信卡。"""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    sources = [source_url] + list(extra_sources or [])
    # 独立来源去重
    uniq = list(dict.fromkeys(sources))
    # 三源互证 → verified，否则 pending
    if trust_level is None:
        trust_level = "verified" if len(uniq) >= 3 else "pending"
    return {
        "xinka_version": "0.1",
        "claim": claim,
        "source_url": source_url,
        "collected_at": now.isoformat().replace("+00:00", "Z"),
        "trust_level": trust_level,
        "freshness_until": (now + timedelta(days=365 * freshness_years)).isoformat().replace("+00:00", "Z"),
        "position": position,
        "verification": {
            "method": "three-source cross-check",
            "sources": uniq,
            "checked_at": now.isoformat().replace("+00:00", "Z") if len(uniq) >= 3 else None,
        },
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    card = make_card(sys.argv[1], sys.argv[2], sys.argv[3],
                     extra_sources=sys.argv[4:])
    print(json.dumps(card, ensure_ascii=False, indent=2))

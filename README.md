# Xinka 信卡

> **Xinka: The Minimal Unit of Trustworthy Knowledge**
> 可信知识的最小单元——AI 时代的「信任」度量衡。

[![Status](https://img.shields.io/badge/status-early_draft-orange)](#)
[![License](https://img.shields.io/badge/license-coming_soon-lightgrey)](#)
[![Website](https://img.shields.io/badge/website-xinka.ai-blue)](https://xinka.ai)

**问得到，更信得过——每条答案带户口本。**

---

## Why · 为什么

AI 什么都能答，但答案**不敢信、不敢引、不敢用**：引用怕编造、数据怕幻觉、决策怕翻车。

大模型给的是答案的**流畅度**，Xinka 给的是答案的**可信度**。不是更会说，是**说了不算瞎说**。

## What · 什么是信卡

一张 **Xinka（信卡）** = 一条知识的「户口本」，六要素齐全：

| 要素 | 英文 | 含义 |
|---|---|---|
| **【源】** | Source | 结论从哪来——原始出处 URL，可点、可查、可回溯 |
| **【采】** | Collected | 何时采集——时间明标，时效一眼可判 |
| **【信】** | Trust | 多可信——已验证 / 待核验，置信度明码实价 |
| **【鲜】** | Freshness | 保鲜期——知识也有保质期，到期提醒复核 |
| **【位】** | Position | 藏在哪——树内坐标可查，知识成体系不成孤岛 |
| **【证】** | Verified | 怎么证的——三源互证，孤证不立 |

```text
一张信卡 = 源 + 采 + 信 + 鲜 + 位 + 证
```

## How · 和现有方案的区别

| 对比 | 他们给 | Xinka 给 |
|---|---|---|
| AI 对话产品 | 快、全、流畅 | 可验、可信、可溯 |
| 搜索引擎 | 链接一堆自己挑 | 已核验的结论 + 出处 |
| 百科 / 问答社区 | 人多说法杂 | 三源互证 + 置信度明标 |
| 媒体溯源（C2PA） | 媒体文件的出处 | **知识 / 文本结论的出处**（此格目前空着） |

**护城河**：抄袭者抄得走界面，抄不走为每条答案背的书。

## Roadmap · 路线

- [x] 概念定义（六要素模型）
- [x] 白皮书 v0.1（[中文版](whitepaper/XINKA_WHITEPAPER_ZH.md) · 在线版 [xinka.ai/whitepaper](https://xinka.ai/whitepaper/)）
- [x] schema 规范（[`schema/xinka-0.1.schema.json`](schema/xinka-0.1.schema.json)）
- [x] 免费校验器 CLI（[`tools/xinka_check.py`](tools/xinka_check.py)）
- [ ] 校验器 Web 版
- [ ] 参考实现与示例卡集

## Validator · 校验器

零依赖（Python 3.8+），开箱即用：

```bash
python3 tools/xinka_check.py --example     # 输出一张示例信卡
python3 tools/xinka_check.py card.json     # 校验：通过 ✓ / 未过 ✗（R1-R7 七条规则）
```

七条规则：R1 六要素齐备 · R2 时间合法且采集早于保鲜期 · R3 置信两档 · R4 已验证须≥3 独立源 · R5 保鲜到期自动降级提示 · R6 校验时序 · R7 出处与坐标格式。

## Get Involved · 参与

标准尚在早期草案（early draft），欢迎 issue 讨论。
网站：[xinka.ai](https://xinka.ai)

---

**Created by Ren Shiliao（任世燎）· 2026**

_Xinka（信卡）= Xin（信 · trust）+ ka（卡 · card）——把「信任」做成 AI 时代的度量衡。_

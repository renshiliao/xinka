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
- [x] 校验器 Web 版（[xinka.ai/validate.html](https://xinka.ai/validate.html)·与 CLI 同源规则）
- [x] 参考实现与示例卡集（[`examples/`](examples/)·10 张示例卡+期望错误表）
- [x] v0.2：R9 源分级 + R10 引文绑定（[`schema/xinka-0.2.schema.json`](schema/xinka-0.2.schema.json)）——白皮书信任模型升四机制
- [x] 自动收录流水线（[`tools/xinka_pipeline.py`](tools/xinka_pipeline.py)·成卡/保鲜扫描/**指纹复检 reverify**）
- [x] MCP 插座（[`tools/xinka_mcp.py`](tools/xinka_mcp.py)）+ [接入页](https://xinka.ai/integrate.html)（提示词模板即贴即用）
- [ ] v1.0 正式化（版本语义冻结·变更流程·贡献者协议）——量柱到位后发布

## Validator · 校验器

零依赖（Python 3.8+），开箱即用：

```bash
python3 tools/xinka_check.py --example     # 输出一张示例信卡
python3 tools/xinka_check.py card.json     # 校验：通过 ✓ / 未过 ✗（R1-R10 规则）
```

规则（v0.2）：R1 六要素齐备 · R2 时间合法且采集早于保鲜期 · R3 置信两档 · R4 已验证须≥3 独立源 · R5 保鲜到期自动降级提示 · R6 校验时序 · R7 出处与坐标格式 · R8 独立性（三源同域名=转载互抄，拦下）· R9 源分级（verified 须含 ≥1 一手源）· R10 引文绑定（引文逐字出自源+sha256 正文指纹）。v0.1 卡按 R1-R7 校验，向后兼容。

## Maintenance · 维护状态

**本仓库为规范存档性仓库（spec-archive），不设 SLA。** 声明如下：

- **冻结层**：schema 规范、白皮书、校验器、示例卡集维持存档状态，**不再新增功能**；schema 仅接受纯结构小版本（R 规则不动则不动）。
- **无服务承诺**：issue / PR 不保证响应时效（no SLA），欢迎讨论，但勿据此排期。
- **方向**：Xinka 的运行时实现与数据资产在闭源侧演进；本仓库只承载「信卡是什么」（结构与信任模型），不承载「谁在用它跑什么」。
- **不可逆**：已发布的 schema 许可永久、免版税——开放规范、闭源实现，两者不互斥（C2PA 同款法理）。

> 维护状态自 2026-10-05 起生效；如需恢复常规维护，另行公告。

## Get Involved · 参与

标准尚在早期草案（early draft），欢迎 issue 讨论。

## Website · 官网

🌐 [xinka.ai](https://xinka.ai) — 官网（阿里云 HK + Cloudflare）
📖 [xinka.ai/whitepaper](https://xinka.ai/whitepaper/) — 白皮书 v0.1
🔧 [xinka.ai/validate](https://xinka.ai/validate.html) — 在线校验器（纯前端）
💬 [xinka.ai/guestbook](https://xinka.ai/guestbook.html) — 留言板
✉ hi@xinka.ai — 联系邮箱

服务端代码（留言板 API/管理端）见 [`server/`](server/)。

---

**Created by Ren Shiliao（任世燎）· 2026**

_Xinka（信卡）= Xin（信 · trust）+ ka（卡 · card）——把「信任」做成 AI 时代的度量衡。_

## 自动收录流水线（2026-10-03 新增）
`tools/xinka_pipeline.py` — 采集→独立性预检(R8)→生成卡→过校验器(R1-R7)→入库登记 一键完成：

```bash
# 批量成卡（request.json 填 claim/sources/position）
python3 tools/xinka_pipeline.py run request.json --out cards/
# 保鲜期扫描（过期/临期清单——催办复核）
python3 tools/xinka_pipeline.py scan cards/
```

R8 独立性预检：verified 卡三源须跨 ≥2 个独立域名——三篇转载稿冒充三源直接拦下（防伪互证）。

## MCP 插座（2026-10-03 新增）
`tools/xinka_mcp.py` — 标准 MCP 服务器（stdio·零依赖），任何支持 MCP 的 AI 客户端即插即用：

```json
{"command": "python3", "args": ["tools/xinka_mcp.py"]}
```

暴露三个工具：
| 工具 | 作用 |
|---|---|
| `xinka_make_card` | 断言+三源→信卡 JSON（单源自降 pending·同域名伪互证拒收） |
| `xinka_check_card` | 信卡→R1-R7+R8 独立性校验 |
| `xinka_freshness` | 扫卡目录→过期/临期清单 |

## 提示词模板
`prompts/XINKA_AGENT_PROMPT.md` — 给任何 AI 的"户口本作业规程"（角色/五条铁律/JSON 模板/自检清单/边界），粘贴即用。

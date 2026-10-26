# Xinka v0.3 更新记录（2026-10-27）

> 本次为**标准完善、版本结构演进**（为将来做好准备）：卡种立名分、方法段进机读形制、信任档补实证型。规则本体 R1-R10 不动，新增 R11/R12。

## 一、标准：schema v0.2 → v0.3

新增 [`schema/xinka-0.3.schema.json`](schema/xinka-0.3.schema.json)（0.1/0.2 冻结不动）：

| 落点 | 内容 |
|---|---|
| `card_type` 必填枚举 | knowledge（知识）/ ability（能力）/ troubleshoot（排障）/ ledger（台账）/ mind（心法）——卡种立名分，机器可分类 |
| 能力卡必填「骨架句」 | 事情骨架：步可跑、名物可换（字段名与 v4 字段表一致，禁改名） |
| 排障卡必填三段 | `症状词` / `判死法` / `修法`——事故件可机读 |
| `trust_level` 增 empirical 档 | 实证型：凭一手实证记录 + 复现判死法成档，不强求 3 外部源；R4 三源互证保留给外部事实断言 |
| R10 引文绑定分型 | empirical 档经验卡免绑；其余档必绑 |

## 二、校验器与工具链

- [`tools/xinka_check.py`](tools/xinka_check.py) 升 v0.3：R11 卡种版本闸（缺 `card_type` 一律报错）+ R12 卡种必填段校验；R3 三档；R4 empirical 分支；R9/R10 绑定分型。
- [`validate.html`](validate.html) Web 校验器与 CLI 同步 R1-R12（同夹具回归一致）。
- [`tools/md2xinka.py`](tools/md2xinka.py) 入库（此前文档已列未随包）：md→JSON 机读孪生补收 `card_type` + 骨架句/症状词/判死法/修法——方法段进机读形制，不再丢失。
- [`examples/xinka_gen.py`](examples/xinka_gen.py)：生成卡必带 `card_type`。

## 三、示例回归集（[examples/](examples/)）

- good 6/6 通过、bad 8/8 规则号与 [`expected_errors.json`](examples/expected_errors.json) 全匹配。
- 全部示例卡补 `card_type`；新增 `bad/bad_v03_no_card_type.json`（R11 版本闸回归夹具）。

## 四、七项标准完善条目的落点对照

| 条目 | 落点 |
|---|---|
| 1 卡种立名分 | schema `card_type` 枚举 + 校验器 R11/R12 + 体例 META「组块」对应 |
| 2 方法提示结构化 | `骨架句`/`症状词`/`判死法`/`修法` 字段（对齐 v4 字段表）+ md2xinka 抽取进孪生 |
| 3 事件→卡接口 | 卡向列 + 催办脚本（内部时间轴侧，见内部条律详档） |
| 4 实证型信任档 | `trust_level` 增 empirical + R4/R9/R10 分型 |
| 5 三卡联动定式 | 三卡联动生成 SOP（草稿，内部条律详档候审） |
| 6 保鲜分型 | 保鲜/代谢分型小节（内部信卡管理规程）：实证卡复测复现、机械判定下放、生成后必重绑 |
| 7 事故反挂 | 反挂词表起步文件（症状词→排障卡号，内部信卡库侧） |

## 五、兼容与迁移

- **旧格式卡（无 `card_type`）过 v0.3 校验器必报 R11**——补卡种枚举即过（一行改动）。
- v0.1/v0.2 卡其余规则范围不变；引文绑定要求不变（0.2 必绑；0.3 empirical 免绑，其余必绑）。
- 双闸（background_review）与 reverify 指纹复检流程不变；重生成孪生后须重绑引文、重跑检索索引。

Created · 2026-10-27 · Ren Shiliao（任世燎）

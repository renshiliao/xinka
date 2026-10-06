# Xinka 更新说明 · 2026-10-06（缺陷修复 + 机制实证批次）

## 一、修复（14 BUG + 3 盲区·commit 516f336）
- 校验器 xinka_check.py：claim/verification 值类型校验（null/int 不再崩栈）、RFC 3339 强制带时区、schema 上限内联（claim 4-500、引文 8-300、拒额外字段）
- pipeline.py：RFC 3339 兼容 +08:00、先校验后写盘、slug 无歧义映射（防覆盖）、坏卡不入库、scan 坏卡计数、全部用户输入错误一行报错不裸崩
- evidence.py / mcp.py：lstrip 字符集剥离 bug 修复（wikipedia 不可伪报一手源）、dict 源 R8 误报修复、IRI 中文 URL 抓取修复
- validate.html：JS 端类型防御与 CLI 对齐、规则文案 R1-R10 修正
- README：R8 归属明文化（pipeline 预检/MCP 执行）
- xinka_http.py：Content-Length 1MB 上限（DoS 防护）
- examples：补齐 v0.2 回归集（R9/R10），good 6/6 · bad 7/7 全绿

## 二、机制实证（体验包 19 卡·spike_体验包/）
白皮书四机制从承诺变为运行实证：
- R5 保鲜降级：pipeline scan 真跑出到期清单（保鲜期按结论类型分层：定律 5 年/定义 3 年/经验值 1 年/教材 0.5 年）
- R9 源分级：18+1 卡互证源全量贴 tier（一手源/媒体/聚合）+ 卡内「源分级」段
- R10 引文绑定：6 张高价值卡绑定内档快照逐字引文+sha256（source_form=local-snapshot 诚实标注；网源绑定因反爬不可得，业务卡走 bind_quote 正道）
- 指纹复检 reverify：三态实弹全过（正常/指纹漂移现形/引文丢失现形）
- 新增第 19 卡：维护系数与折损（GB 50034 表 4.1.7 原文·MF 0.8/0.7/0.6/0.65）
- 工具链：md2xinka.py（md→JSON 机读孪生）、bind_local_snapshot.py、reverify_local.py、xinka_query.py（检索/关联/统计）

## 三、官网同步待命
心网开源包（信卡熔炉·安全约束层）已就绪于本机，待心网开源准备完成后随官网一并更新。

Created · 2026-10-06

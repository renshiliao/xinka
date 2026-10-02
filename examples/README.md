# Xinka 示例卡集（Examples）

标准的活证据 + 校验器回归测试集。所有 `good/` 卡的出处 URL 均为真实公开来源；`bad/` 卡故意触犯规则，用于测试。

## 目录

| 目录/文件 | 用途 |
|---|---|
| `good/`（5 张） | 合规信卡——`xinka_check.py` 校验应全部零错误 |
| `bad/`（5 张） | 违规信卡——每张恰触犯一条规则（R1/R2/R3/R4/R7） |
| `expected_errors.json` | 回归基准：bad 卡 → 应触发的规则号 |
| `xinka_gen.py` | 参考实现（生成器）：断言+出处 → 合规信卡 |

## 回归测试（一行跑完）

```bash
for f in examples/good/*.json; do python3 tools/xinka_check.py "$f"; done   # 应 5/5 通过
for f in examples/bad/*.json;  do python3 tools/xinka_check.py "$f"; done   # 应每张报错
```

对照 `expected_errors.json` 核对规则号即可（10/10 匹配 = 校验器健康）。

## 生成器用法

```python
from examples.xinka_gen import make_card

card = make_card(
    claim="地球赤道周长约 40075 公里",
    source_url="https://education.nationalgeographic.org/resource/equator/",
    position="science/geography/earth",
    extra_sources=["https://…", "https://…"],  # 凑满 3 独立源自动升 verified
    freshness_years=2,
)
```

或命令行：

```bash
python3 examples/xinka_gen.py "断言" "https://源1" "位置" ["https://源2" "https://源3"]
```

**Created by Ren Shiliao（任世燎）· 2026 · xinka.ai**

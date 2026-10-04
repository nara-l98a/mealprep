# mealprep

`mealprep` 是一个主题专属的 Python 3.10+ 命令行工具，用 JSON 管理**食材、食谱和按日期/餐次的膳食计划**，并把指定日期区间的食谱份数换算成合并后的购物清单。

## 功能边界

- 录入食材目录（名称、数量、单位），拒绝非有限正数及同名同单位重复项。
- 创建食谱：食谱含份数和多项 `名称:数量:单位` 食材。
- 将已存在食谱排入早餐、午餐、晚餐或加餐；同一日期同一餐次不能重复。
- 按起止日期生成购物清单；同名且**单位完全相同**的食材合并，单位不同不会擅自换算；食谱份数会按计划份数缩放。
- `validate` 检查计划日期、重复餐次、餐次枚举、份数、食谱引用，以及库存/食谱食材结构和数量。
- 不包含营养分析、单位换算、云同步、用户账户、实际库存扣减或库存预留。录入的食材目录不会自动抵扣购物清单。

## Python 版本与安装

需要 Python 3.10 或更高版本，仅使用标准库运行。

```bash
python -m pip install .
mealprep --help
# 开发安装可用：python -m pip install -e .
```

也可直接运行：`python -m mealprep ...`。所有命令都通过 `--data FILE`（别名 `--db FILE`）指定本地 JSON；未指定时使用 `MEALPREP_DATA`，再无环境变量则使用当前目录 `mealprep.json`。

## 完整 CLI 示例

```bash
mealprep --data /tmp/week.json add-ingredient 番茄 4 个
mealprep --data /tmp/week.json add-recipe 番茄意面 --servings 2 --ingredient 意面:200:克 --ingredient 番茄:2:个
mealprep --data /tmp/week.json plan 2025-01-06 晚餐 番茄意面 --servings 2
mealprep --data /tmp/week.json plan 2025-01-07 午餐 番茄意面 --servings 1
mealprep --data /tmp/week.json validate
mealprep --data /tmp/week.json shopping-list 2025-01-06 2025-01-12
```

示例输出：

```text
已保存食谱：番茄意面（2 份）
已安排：2025-01-06 晚餐 ← 番茄意面（2 份）
校验通过
购物清单（2025-01-06 至 2025-01-12）
- 意面: 300 克
- 番茄: 3 个
```

## 全部命令参数

全局参数（必须放在子命令前）：

- `--data FILE` / `--db FILE`：数据文件路径。

子命令：

- `add-ingredient NAME QUANTITY UNIT`：数量必须为有限正数，名称与单位不能为空。
- `add-recipe NAME --servings N --ingredient NAME:QUANTITY:UNIT`：`--ingredient` 可重复且至少一次，份数和数量必须为有限正数。
- `plan YYYY-MM-DD MEAL RECIPE [--servings N]`：`MEAL` 只能是 `早餐`、`午餐`、`晚餐`、`加餐`；食谱必须先创建；同一天同一餐次只允许一项。
- `shopping-list START END`：日期均为标准 ISO `YYYY-MM-DD`；包含端点，且开始日期不能晚于结束日期。
- `validate`：返回 `0` 表示通过，发现问题返回 `1`；参数格式错误或文件错误返回 `2`。

无效日期、零/负/非有限数量、损坏 JSON、不存在的食谱、重复食材和重复日期餐次会给出中文错误，不会写入变更。对手工编辑后结构损坏的数据，`validate` 会报告具体类别；购物清单也会先校验数据，避免输出不可信结果。

## 数据格式

文件是 UTF-8 JSON 对象：

```json
{
  "version": 1,
  "ingredients": [{"name": "番茄", "unit": "个", "quantity": 4}],
  "recipes": [{"name": "番茄意面", "servings": 2, "ingredients": [{"name": "意面", "quantity": 200, "unit": "克"}]}],
  "plans": [{"date": "2025-01-06", "meal": "晚餐", "recipe": "番茄意面", "servings": 2}]
}
```

无数据文件时程序会创建上述结构。`examples/week.json` 提供无个人数据的示例。

## 隐私与安全

数据只读写用户指定的本地路径，不联网、不上传、不读取凭据或 Token。保存时先在同目录写入临时文件、刷新并 `fsync`，再原子替换目标文件；但断电保护和文件系统权限仍取决于操作系统。请自行备份数据并避免把含敏感信息的文件提交到版本库。

## 开发与测试

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

测试使用 `tempfile.TemporaryDirectory` 隔离数据，不触碰真实用户文件。项目通过 GitHub Actions 在 Python 3.10 上运行同一测试命令。

## 许可证

MIT，详见 [LICENSE](LICENSE)。

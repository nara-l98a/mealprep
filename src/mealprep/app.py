from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA = {"version": 1, "ingredients": [], "recipes": [], "plans": []}


def data_path(value: str | None) -> Path:
    return Path(value or os.environ.get("MEALPREP_DATA", "mealprep.json")).expanduser()


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(SCHEMA))
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取数据文件 {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("数据文件根对象必须是 JSON 对象")
    for key in ("ingredients", "recipes", "plans"):
        if not isinstance(obj.get(key, []), list):
            raise ValueError(f"数据字段 {key} 必须是数组")
    obj.setdefault("version", 1)
    return obj


def save(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def positive(value: str) -> float:
    try: result = float(value)
    except ValueError as exc: raise argparse.ArgumentTypeError("数量必须是数字") from exc
    if not math.isfinite(result) or result <= 0: raise argparse.ArgumentTypeError("数量必须是有限的正数")
    return result


def valid_day(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value: raise ValueError
    except ValueError as exc: raise argparse.ArgumentTypeError("日期必须为 YYYY-MM-DD") from exc
    return value


def find_recipe(db: dict, name: str) -> dict | None:
    return next((r for r in db["recipes"] if r.get("name") == name), None)


def cmd_add_ingredient(db: dict, args: argparse.Namespace) -> str:
    name, unit = args.name.strip(), args.unit.strip()
    if not name or not unit: raise ValueError("食材名称和单位不能为空")
    if any(i.get("name", "").casefold() == name.casefold() and i.get("unit", "").casefold() == unit.casefold() for i in db["ingredients"]):
        raise ValueError("同名同单位食材已存在")
    db["ingredients"].append({"name": name, "unit": unit, "quantity": args.quantity})
    return f"已录入食材：{name} {args.quantity:g}{unit}"


def cmd_add_recipe(db: dict, args: argparse.Namespace) -> str:
    name = args.name.strip()
    if not name: raise ValueError("食谱名称不能为空")
    if find_recipe(db, name): raise ValueError("同名食谱已存在")
    items = []
    for raw in args.ingredient:
        parts = raw.split(":")
        if len(parts) != 3 or not parts[0].strip() or not parts[1].strip():
            raise ValueError("--ingredient 格式应为 名称:数量:单位")
        try: qty = float(parts[1])
        except ValueError as exc: raise ValueError(f"食谱食材数量无效：{raw}") from exc
        ingredient_name, unit = parts[0].strip(), parts[2].strip()
        if not ingredient_name or not unit: raise ValueError("食材名称和单位不能为空")
        if not math.isfinite(qty) or qty <= 0: raise ValueError("食谱食材数量必须是有限的正数")
        items.append({"name": ingredient_name, "quantity": qty, "unit": unit})
    if not items: raise ValueError("食谱至少需要一个 --ingredient")
    db["recipes"].append({"name": name, "servings": args.servings, "ingredients": items})
    return f"已保存食谱：{name}（{args.servings:g} 份）"


def cmd_plan(db: dict, args: argparse.Namespace) -> str:
    recipe = find_recipe(db, args.recipe)
    if not recipe: raise ValueError(f"计划引用了不存在的食谱：{args.recipe}")
    if any(p.get("date") == args.date and p.get("meal") == args.meal for p in db["plans"]):
        raise ValueError(f"该日期餐次已安排：{args.date} {args.meal}")
    db["plans"].append({"date": args.date, "meal": args.meal, "recipe": args.recipe, "servings": args.servings})
    return f"已安排：{args.date} {args.meal} ← {args.recipe}（{args.servings:g} 份）"


def validate(db: dict) -> list[str]:
    errors = []
    seen = set()
    for r in db["recipes"]:
        if not r.get("name"): errors.append("存在无名称食谱")
        for x in r.get("ingredients", []):
            if not x.get("name") or not x.get("unit") or not isinstance(x.get("quantity"), (int, float)) or x["quantity"] <= 0:
                errors.append(f"食谱 {r.get('name', '?')} 含无效食材")
    for p in db["plans"]:
        key = (p.get("date"), p.get("meal"))
        if key in seen: errors.append(f"同一日期餐次重复：{p.get('date')} {p.get('meal')}")
        seen.add(key)
        if not find_recipe(db, p.get("recipe", "")): errors.append(f"计划引用不存在的食谱：{p.get('recipe')}")
        try: date.fromisoformat(p.get("date", ""))
        except ValueError: errors.append(f"计划日期无效：{p.get('date')}")
    return errors


def cmd_shopping(db: dict, args: argparse.Namespace) -> str:
    if args.start > args.end:
        raise ValueError("购物日期范围的开始日期不能晚于结束日期")
    errors = validate(db)
    if errors: raise ValueError("数据校验失败：" + "；".join(errors))
    totals = defaultdict(float)
    labels = defaultdict(list)
    for p in db["plans"]:
        if args.start <= p["date"] <= args.end:
            r = find_recipe(db, p["recipe"])
            scale = p["servings"] / r["servings"]
            for x in r["ingredients"]:
                key = (x["name"], x["unit"])
                totals[key] += x["quantity"] * scale
    lines = [f"购物清单（{args.start} 至 {args.end}）"]
    if not totals: lines.append("（无安排）")
    else:
        for (name, unit), qty in sorted(totals.items()): lines.append(f"- {name}: {qty:g} {unit}")
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mealprep", description="食谱、食材与膳食计划工具")
    p.add_argument("--data", "--db", dest="data", help="JSON 数据文件（默认读取 MEALPREP_DATA 或 mealprep.json）")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add-ingredient", help="录入库存食材"); a.add_argument("name"); a.add_argument("quantity", type=positive); a.add_argument("unit"); a.set_defaults(fn=cmd_add_ingredient)
    r = sub.add_parser("add-recipe", help="创建食谱"); r.add_argument("name"); r.add_argument("--servings", type=positive, default=1); r.add_argument("--ingredient", action="append", required=True, help="名称:数量:单位"); r.set_defaults(fn=cmd_add_recipe)
    pl = sub.add_parser("plan", help="安排日期和餐次"); pl.add_argument("date", type=valid_day); pl.add_argument("meal", choices=["早餐", "午餐", "晚餐", "加餐"]); pl.add_argument("recipe"); pl.add_argument("--servings", type=positive, default=1); pl.set_defaults(fn=cmd_plan)
    s = sub.add_parser("shopping-list", help="汇总日期区间购物清单"); s.add_argument("start", type=valid_day); s.add_argument("end", type=valid_day); s.set_defaults(fn=cmd_shopping)
    v = sub.add_parser("validate", help="校验所有计划引用和结构"); v.set_defaults(fn=lambda db, args: "校验通过" if not validate(db) else "校验失败：\n- " + "\n- ".join(validate(db)))
    return p


def main(argv: list[str] | None = None) -> int:
    p = parser()
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    path = data_path(args.data)
    try:
        db = load(path); output = args.fn(db, args)
        if args.command != "validate" or output == "校验通过": save(path, db)
        print(output); return 0 if not output.startswith("校验失败") else 1
    except (ValueError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())

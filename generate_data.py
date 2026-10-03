# -*- coding: utf-8 -*-
"""
generate_data.py
生成电商销售模拟数据（用于「AI运营问答助手」演示）
=====================================================
字段结构与真实电商运营分析的常见维度对齐：
日期 / 品类 / 渠道 / 地区 / 销量 / 单价 / 成本 / 客户数

用法（PowerShell 直接复制）：
    E:/python/python.exe generate_data.py

说明：
    - 本数据为【模拟数据】，随机种子固定，可复现；
    - 你之后可以把 data/ecommerce_sales.csv 换成自己的真实数据，
      只要字段名保持一致，app.py 不需要改。
"""
import csv
import random
from datetime import date, timedelta

random.seed(2026)  # 固定种子，保证每次生成一致

# 业务字典
CATEGORIES = ["数码", "家电", "服饰", "美妆", "食品", "家居"]
CHANNELS = ["天猫", "京东", "抖音", "拼多多", "线下"]
REGIONS = ["华南", "华东", "华北", "西南", "华中", "东北", "西北"]

# 每个品类的价格带（单价区间，元）与成本占比区间
CATEGORY_PRICE = {
    "数码": (300, 6000),
    "家电": (200, 4500),
    "服饰": (60, 800),
    "美妆": (50, 500),
    "食品": (10, 200),
    "家居": (30, 900),
}
CATEGORY_COST_RATIO = {
    "数码": (0.55, 0.75),
    "家电": (0.50, 0.70),
    "服饰": (0.40, 0.65),
    "美妆": (0.35, 0.55),
    "食品": (0.55, 0.80),
    "家居": (0.45, 0.70),
}

# 渠道销量系数（抖音/拼多多量大）
CHANNEL_VOLUME = {"天猫": 1.0, "京东": 0.9, "抖音": 1.6, "拼多多": 1.8, "线下": 0.7}
# 地区销量系数
REGION_VOLUME = {"华南": 1.4, "华东": 1.5, "华北": 1.2, "西南": 0.9, "华中": 1.0, "东北": 0.7, "西北": 0.6}


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def main():
    start = date(2025, 1, 1)
    end = date(2026, 9, 30)
    rows = []
    n = 4000  # 明细行数

    for _ in range(n):
        d = random_date(start, end)
        cat = random.choice(CATEGORIES)
        price_lo, price_hi = CATEGORY_PRICE[cat]
        unit_price = round(random.uniform(price_lo, price_hi), 2)
        cost_lo, cost_hi = CATEGORY_COST_RATIO[cat]
        unit_cost = round(unit_price * random.uniform(cost_lo, cost_hi), 2)
        channel = random.choice(CHANNELS)
        region = random.choice(REGIONS)
        # 销量：基础量 + 品类/渠道/地区系数，加少量波动
        base = random.randint(1, 30)
        volume = int(base * CHANNEL_VOLUME[channel] * REGION_VOLUME[region] * random.uniform(0.8, 1.2))
        volume = max(1, volume)
        customer_count = int(volume * random.uniform(0.55, 0.95))
        rows.append([d.isoformat(), cat, channel, region, volume, unit_price, unit_cost, customer_count])

    # 少量脏数据，用于演示"数据清洗"环节（app.py 会处理）
    # 1) 2 行日期为空
    rows[10][0] = ""
    rows[88][0] = "2026/10/01"   # 2) 日期格式不统一
    rows[120][2] = ""            # 3) 渠道缺失
    rows[500][4] = -5            # 4) 销量异常为负数

    out_path = "data/ecommerce_sales.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "category", "channel", "region", "sales_volume", "unit_price", "unit_cost", "customer_count"])
        writer.writerows(rows)

    print(f"已生成 {len(rows)} 行模拟数据 -> {out_path}")


if __name__ == "__main__":
    main()

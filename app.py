# -*- coding: utf-8 -*-
"""
电商经营 AI 问答助手 (AI Data Q&A Assistant)
==========================================
一个本地运行的"AI应用运营"作品：把电商销售数据变成可以自然语言问答的助手。

架构（面试时讲这套就够）：
    数据层   data/ecommerce_sales.csv（可换成你的真实数据）
    计算层   pandas 清洗 + 预计算业务指标（KPI/品类/月度/渠道/地区）
    问答层   关键词规则路由（拿数据） -> 本地大模型（组织运营语言）
    展示层   Flask 网页仪表盘 + 问答框（浏览器打开即可演示）

用法（PowerShell 直接复制，或双击 start.bat）：
    E:\python\python.exe app.py
然后浏览器访问 http://127.0.0.1:8000
"""
import os
import sys
import json
import re
import threading
import webbrowser

sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台中文不乱码

import pandas as pd
from flask import Flask, request, jsonify, render_template_string
import requests

# ================= 配置区（你只需要改这里） =================
DATA_PATH = "data/ecommerce_sales.csv"

# --- 本地模型（Ollama，默认）---
MODEL_API_BASE = "http://localhost:11434"
MODEL_API_PATH = "/api/chat"          # Ollama 的对话端点
MODEL_NAME = "qwen2.5:7b"

# --- 切换云端大模型（DeepSeek 示例，改这三行即可）---
# MODEL_API_BASE = "https://api.deepseek.com"
# MODEL_API_PATH = "/chat/completions"     # OpenAI 兼容格式
# MODEL_NAME = "deepseek-chat"
# API Key 安全做法：不写死在代码里（否则推到 GitHub/Gitee 会泄露），
# 优先从环境变量 AI_MODEL_API_KEY 读取；没有则留空（本地模型不需要）。

PORT = 8000
# ===========================================================

MODEL_API_KEY = os.environ.get("AI_MODEL_API_KEY", "")

app = Flask(__name__)


# ---------- 1. 数据加载与清洗 ----------
def load_data():
    df = pd.read_csv(DATA_PATH)
    # 日期清洗：空值删除、格式统一
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
    df = df.dropna(subset=["date"])
    # 数值清洗：销量必须为正，关键字段不能为空
    df = df[df["sales_volume"] > 0]
    df = df.dropna(subset=["channel", "region", "unit_price", "unit_cost"])
    # 派生指标
    df["amount"] = df["sales_volume"] * df["unit_price"]
    df["gross_profit"] = (df["unit_price"] - df["unit_cost"]) * df["sales_volume"]
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df


df = load_data()


# ---------- 2. 指标预计算 ----------
def r2(x):
    return round(x, 2)


def compute_metrics(data):
    total_amount = float(data["amount"].sum())
    total_volume = int(data["sales_volume"].sum())
    total_customers = int(data["customer_count"].sum())
    gross_margin = float(data["gross_profit"].sum() / data["amount"].sum() * 100) if total_amount else 0
    avg_order = total_amount / total_customers if total_customers else 0

    by_category = (
        data.groupby("category")
        .agg(amount=("amount", "sum"), volume=("sales_volume", "sum"),
             profit=("gross_profit", "sum"))
        .reset_index()
    )
    by_category["margin"] = by_category["profit"] / by_category["amount"] * 100
    by_category = by_category.sort_values("amount", ascending=False)

    by_month = (
        data.groupby("month")
        .agg(amount=("amount", "sum"), volume=("sales_volume", "sum"))
        .reset_index()
        .sort_values("month")
    )

    by_channel = (
        data.groupby("channel")
        .agg(amount=("amount", "sum"), profit=("gross_profit", "sum"))
        .reset_index()
    )
    by_channel["margin"] = by_channel["profit"] / by_channel["amount"] * 100
    by_channel = by_channel.sort_values("amount", ascending=False)

    by_region = (
        data.groupby("region")
        .agg(amount=("amount", "sum"), profit=("gross_profit", "sum"))
        .reset_index()
    )
    by_region["margin"] = by_region["profit"] / by_region["amount"] * 100
    by_region = by_region.sort_values("amount", ascending=False)

    return {
        "kpi": {
            "total_amount_wan": r2(total_amount / 10000),
            "total_volume": total_volume,
            "avg_order": r2(avg_order),
            "gross_margin": r2(gross_margin),
        },
        "by_category": [
            {"name": r["category"], "amount_wan": r2(r["amount"] / 10000),
             "volume": int(r["volume"]), "margin": r2(r["margin"])}
            for _, r in by_category.iterrows()
        ],
        "by_month": [
            {"name": r["month"], "amount_wan": r2(r["amount"] / 10000),
             "volume": int(r["volume"])}
            for _, r in by_month.iterrows()
        ],
        "by_channel": [
            {"name": r["channel"], "amount_wan": r2(r["amount"] / 10000),
             "margin": r2(r["margin"])}
            for _, r in by_channel.iterrows()
        ],
        "by_region": [
            {"name": r["region"], "amount_wan": r2(r["amount"] / 10000),
             "margin": r2(r["margin"])}
            for _, r in by_region.iterrows()
        ],
    }


M = compute_metrics(df)


# ---------- 3. 数据 -> 给模型的文本 ----------
def fmt_kpi():
    k = M["kpi"]
    return (f"整体KPI：总销售额{k['total_amount_wan']}万元，总销量{k['total_volume']}件，"
            f"客单价{k['avg_order']}元，毛利率{k['gross_margin']}%。")


def fmt_category(with_margin=True):
    parts = []
    for c in M["by_category"]:
        m = f"，毛利率{c['margin']}%" if with_margin else ""
        parts.append(f"{c['name']}(销售额{c['amount_wan']}万元{m})")
    return "品类销售排行：\n" + "；".join(parts)


def fmt_month(limit=12):
    months = M["by_month"][-limit:]
    parts = [f"{m['name']}({m['amount_wan']}万元)" for m in months]
    return f"最近{limit}个月销售额趋势：\n" + "；".join(parts)


def fmt_channel():
    parts = [f"{c['name']}(销售额{c['amount_wan']}万元, 毛利率{c['margin']}%)" for c in M["by_channel"]]
    return "渠道对比：\n" + "；".join(parts)


def fmt_region():
    parts = [f"{r['name']}(销售额{r['amount_wan']}万元, 毛利率{r['margin']}%)" for r in M["by_region"]]
    return "地区对比：\n" + "；".join(parts)


def fmt_summary():
    """模型兜底时给的全量摘要（精简版）"""
    return "\n".join([fmt_kpi(), fmt_category(), fmt_month(12), fmt_channel(), fmt_region()])


# ---------- 4. 问答引擎：规则路由 + 模型组织语言 ----------
RULES = [
    (re.compile(r"毛利率|毛利"), "by_category_margin", "品类毛利率排行"),
    (re.compile(r"最好|最高|top|第一|榜首|冠军|卖得.*好"), "top_category", "销售额TOP品类"),
    (re.compile(r"最差|最低|垫底|倒数|卖得.*差"), "bottom_category", "毛利最低品类"),
    (re.compile(r"趋势|走势|变化|增长|下滑|环比|同比"), "by_month", "按月销售趋势"),
    (re.compile(r"渠道"), "by_channel", "渠道对比"),
    (re.compile(r"地区|区域"), "by_region", "地区对比"),
    (re.compile(r"客单价"), "avg_order", "客单价"),
    (re.compile(r"整体|总销售|总营收|业绩|销售额|营收|生意|kpi"), "kpi", "整体KPI"),
    (re.compile(r"品类|商品|产品"), "by_category", "品类销售排行"),
]


def pick_rule_data(rule_key, question):
    """按命中的规则取对应数据文本；月份问题单独处理。"""
    if rule_key == "kpi":
        return fmt_kpi()
    if rule_key == "by_category":
        return fmt_category()
    if rule_key == "by_category_margin":
        ranked = sorted(M["by_category"], key=lambda x: x["margin"], reverse=True)
        parts = [f"{c['name']}(毛利率{c['margin']}%)" for c in ranked]
        return "品类毛利率排行（从高到低）：\n" + "；".join(parts)
    if rule_key == "top_category":
        c = M["by_category"][0]
        return f"销售额TOP1品类：{c['name']}，销售额{c['amount_wan']}万元，毛利率{c['margin']}%。"
    if rule_key == "bottom_category":
        ranked = sorted(M["by_category"], key=lambda x: x["margin"])
        c = ranked[0]
        return f"毛利率最低品类：{c['name']}，毛利率{c['margin']}%，销售额{c['amount_wan']}万元。"
    if rule_key == "by_month":
        m = re.search(r"(\d{1,2})\s*月", question)
        if m:
            target = f"2026-{int(m.group(1)):02d}"
            hit = [x for x in M["by_month"] if x["name"].endswith(target[5:])]
            if hit:
                x = hit[0]
                return f"{x['name']}销售额{x['amount_wan']}万元，销量{x['volume']}件。"
            return "当前数据中该月份没有记录。"
        return fmt_month()
    if rule_key == "by_channel":
        return fmt_channel()
    if rule_key == "by_region":
        return fmt_region()
    if rule_key == "avg_order":
        k = M["kpi"]
        return f"客单价{k['avg_order']}元（总销售额{k['total_amount_wan']}万元 ÷ 客户数）"
    return fmt_summary()


def call_model(question, data_text):
    """调用大模型，把数据组织成运营语言。模型只负责说话，数据由规则保证。"""
    system = (
        "你是电商运营数据分析助手。只能基于用户提供的数据回答，"
        "数据中没有的信息必须直接说'当前数据中没有'，禁止编造数字。"
        "用中文回答，面向运营决策：先给结论，再给数据依据，最后给一条可执行建议。"
        "不超过150字。"
    )
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"【数据】\n{data_text}\n\n【问题】\n{question}"},
        ],
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {MODEL_API_KEY}"} if MODEL_API_KEY else {}
    url = MODEL_API_BASE.rstrip("/") + MODEL_API_PATH
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=120)
        r.raise_for_status()
        data = r.json()
        # 兼容 Ollama({message}) 与 OpenAI兼容格式({choices[0].message})
        content = data.get("message", {}).get("content") or data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        return (f"（模型服务暂不可用：{e}。以下为规则直接给出的数据结论）\n\n{data_text}")


def answer_question(question):
    question = question.strip()
    if not question:
        return {"answer": "请输入问题。", "matched": "无"}

    matched_key, matched_desc = None, None
    for pattern, key, desc in RULES:
        if pattern.search(question):
            matched_key, matched_desc = key, desc
            break

    if matched_key:
        data_text = pick_rule_data(matched_key, question)
    else:
        data_text = fmt_summary()
        matched_desc = "模型兜底（基于数据摘要）"

    answer = call_model(question, data_text)
    return {"answer": answer, "matched": matched_desc}


# ---------- 5. 网页 ----------
INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>电商经营 AI 问答助手</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  body{margin:0;font-family:"Microsoft YaHei",system-ui,sans-serif;background:#f4f6f8;color:#1f2937}
  .wrap{max-width:980px;margin:0 auto;padding:16px}
  h1{font-size:20px;margin:10px 0 2px}
  .sub{color:#6b7280;font-size:13px;margin-bottom:14px}
  .cards{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}
  .card{flex:1;min-width:140px;background:#fff;border-radius:10px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
  .card .k{color:#6b7280;font-size:12px}
  .card .v{font-size:20px;font-weight:700;margin-top:4px}
  .charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px;margin-bottom:14px}
  .chart-box{background:#fff;border-radius:10px;padding:10px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
  .chart-box .t{font-size:13px;font-weight:600;margin:2px 4px 4px}
  .chart{height:240px}
  .qa{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
  .qa .t{font-size:14px;font-weight:600;margin-bottom:8px}
  textarea{width:100%;box-sizing:border-box;height:60px;border:1px solid #d1d5db;border-radius:8px;padding:8px;font-size:14px;resize:vertical}
  .row{display:flex;gap:8px;margin-top:8px}
  .btn{background:#2563eb;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:14px;cursor:pointer}
  .btn:hover{background:#1d4ed8}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .chip{background:#eef2f7;border:none;border-radius:20px;padding:4px 10px;font-size:12px;color:#374151;cursor:pointer}
  .chip:hover{background:#dbe4ee}
  .result{margin-top:12px;white-space:pre-wrap;background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:10px;font-size:14px;line-height:1.7;display:none}
  .result .tag{display:inline-block;background:#e0e7ff;color:#3730a3;font-size:11px;border-radius:4px;padding:1px 6px;margin-bottom:6px}
  .loading{color:#6b7280;font-size:13px;margin-top:8px;display:none}
</style>
</head>
<body>
<div class="wrap">
  <h1>电商经营 AI 问答助手</h1>
  <div class="sub">本地Qwen模型 + 电商销售数据 · 示例作品（数据为模拟数据，可替换为真实CSV）</div>

  <div class="cards">
    <div class="card"><div class="k">总销售额</div><div class="v">{{ kpi.total_amount_wan }}<span style="font-size:12px">万元</span></div></div>
    <div class="card"><div class="k">总销量</div><div class="v">{{ kpi.total_volume }}<span style="font-size:12px">件</span></div></div>
    <div class="card"><div class="k">客单价</div><div class="v">{{ kpi.avg_order }}<span style="font-size:12px">元</span></div></div>
    <div class="card"><div class="k">毛利率</div><div class="v">{{ kpi.gross_margin }}<span style="font-size:12px">%</span></div></div>
  </div>

  <div class="charts">
    <div class="chart-box"><div class="t">品类销售额（万元）</div><div id="c1" class="chart"></div></div>
    <div class="chart-box"><div class="t">月度销售额趋势（万元）</div><div id="c2" class="chart"></div></div>
    <div class="chart-box"><div class="t">渠道销售额占比</div><div id="c3" class="chart"></div></div>
  </div>

  <div class="qa">
    <div class="t">向数据提问（试试下面的问题）</div>
    <textarea id="q" placeholder="例如：哪个品类卖得最好？3月的销售趋势怎么样？"></textarea>
    <div class="row">
      <button class="btn" onclick="ask()">提问</button>
      <div class="loading" id="loading">模型思考中（本地7B模型，首次约需20-60秒）...</div>
    </div>
    <div class="chips" id="chips"></div>
    <div class="result" id="result"></div>
  </div>
</div>

<script>
var cat = {{ category_json | safe }};
var month = {{ month_json | safe }};
var channel = {{ channel_json | safe }};

function draw() {
  if (typeof echarts === "undefined") { return; }
  var c1 = echarts.init(document.getElementById("c1"));
  c1.setOption({tooltip:{},grid:{left:60,right:20,top:20,bottom:30},
    xAxis:{type:"value"},yAxis:{type:"category",data:cat.map(function(x){return x.name}).reverse()},
    series:[{type:"bar",data:cat.map(function(x){return x.amount_wan}).reverse(),barWidth:14,
      itemStyle:{color:"#3b82f6"}}]});
  var c2 = echarts.init(document.getElementById("c2"));
  c2.setOption({tooltip:{trigger:"axis"},grid:{left:50,right:16,top:20,bottom:30},
    xAxis:{type:"category",data:month.map(function(x){return x.name})},
    yAxis:{type:"value"},
    series:[{type:"line",smooth:true,data:month.map(function(x){return x.amount_wan}),
      itemStyle:{color:"#10b981"},areaStyle:{opacity:0.15}}]});
  var c3 = echarts.init(document.getElementById("c3"));
  c3.setOption({tooltip:{trigger:"item"},legend:{bottom:0,textStyle:{fontSize:11}},
    series:[{type:"pie",radius:["35%","62%"],center:["50%","44%"],
      data:channel.map(function(x){return {name:x.name,value:x.amount_wan}})}]});
}
window.addEventListener("resize", draw);
draw();

var chips = ["哪个品类卖得最好？","整体销售情况怎么样？","哪个品类毛利率最低？","3月的销售怎么样？","抖音渠道表现如何？","华东地区销售额多少？"];
var box = document.getElementById("chips");
chips.forEach(function(t){ var b=document.createElement("button"); b.className="chip"; b.textContent=t;
  b.onclick=function(){ document.getElementById("q").value=t; ask(); }; box.appendChild(b); });

function ask(){
  var q = document.getElementById("q").value.trim();
  if(!q){return;}
  var res = document.getElementById("result");
  var loading = document.getElementById("loading");
  res.style.display="none"; loading.style.display="block";
  fetch("/api/ask",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({question:q})})
    .then(function(r){return r.json();})
    .then(function(d){
      loading.style.display="none";
      res.innerHTML = '<span class="tag">命中：'+d.matched+'</span><br>'+escapeHtml(d.answer);
      res.style.display="block";
    })
    .catch(function(e){ loading.style.display="none"; res.innerHTML="请求失败："+e; res.style.display="block"; });
}
function escapeHtml(s){ return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(
        INDEX_HTML,
        kpi=M["kpi"],
        category_json=json.dumps(M["by_category"], ensure_ascii=False),
        month_json=json.dumps(M["by_month"], ensure_ascii=False),
        channel_json=json.dumps(M["by_channel"], ensure_ascii=False),
    )


@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json(force=True)
    question = data.get("question", "")
    return jsonify(answer_question(question))


def open_browser():
    try:
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    except Exception:
        pass


if __name__ == "__main__":
    print("=" * 52)
    print(" 电商经营 AI 问答助手 已启动")
    print(f" 数据: {DATA_PATH}")
    print(f" 模型: {MODEL_NAME} @ {MODEL_API_BASE}")
    print(f" 打开: http://127.0.0.1:{PORT}")
    print(" 关闭本窗口即停止服务")
    print("=" * 52)
    threading.Timer(1.0, open_browser).start()
    app.run(host="127.0.0.1", port=PORT, debug=False)

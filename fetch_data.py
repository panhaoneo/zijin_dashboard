"""
fetch_data.py
每日由 GitHub Actions 执行。

输出两个文件：
  data.json     — 当日最新快照（价格、涨跌、COMEX库存）
  history.json  — 累积历史，每天 append 一条，长期保留

依赖：pip install yfinance xlrd pytz
"""

import json
import sys
import os
import urllib.request
from datetime import datetime
import pytz

try:
    import yfinance as yf
except ImportError:
    print("请安装依赖：pip install yfinance xlrd pytz")
    sys.exit(1)

# ─────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────

TICKERS = {
    "zijin_a": "601899.SS",
    "zijin_h": "2899.HK",
    "gold":    "GC=F",
    "silver":  "SI=F",
    "gdx":     "GDX",
    "copper":  "HG=F",
    "bhp":     "BHP",
    "fcx":     "FCX",
    "dxy":     "DX-Y.NYB",
    "tnx":     "^TNX",
    "spx":     "^GSPC",
    "vix":     "^VIX",
}

# history.json 最多保留多少条（约等于交易日数）
MAX_HISTORY = 365

# history.json 里记录哪些字段的收盘价
HISTORY_FIELDS = ["gold", "silver", "copper", "dxy", "zijin_a", "zijin_h",
                  "spx", "vix", "tnx", "gdx"]

# ─────────────────────────────────────────────────────
# 报价抓取
# ─────────────────────────────────────────────────────

def fetch_quote(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="2d")
        if hist.empty or len(hist) < 1:
            return None
        price      = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
        change     = round(price - prev_close, 4)
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0
        volume     = int(hist["Volume"].iloc[-1]) if hist["Volume"].iloc[-1] else None
        return {"price": round(price, 4), "change": change,
                "change_pct": change_pct, "volume": volume}
    except Exception as e:
        print(f"  ✗ {symbol}: {e}")
        return None

# ─────────────────────────────────────────────────────
# COMEX 白银实物库存
# ─────────────────────────────────────────────────────

def fetch_comex_silver():
    url = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"
    try:
        import xlrd
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "xlrd", "-q"])
        import xlrd
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        wb = xlrd.open_workbook(file_contents=data)
        sh = wb.sheets()[0]

        header_row = None
        for r in range(min(6, sh.nrows)):
            vals = [str(sh.cell_value(r, c)).strip().lower() for c in range(sh.ncols)]
            if any("registered" in v for v in vals):
                header_row = r
                break
        if header_row is None:
            return None

        hdrs = [str(sh.cell_value(header_row, c)).strip().lower() for c in range(sh.ncols)]
        def colidx(name):
            for i, h in enumerate(hdrs):
                if name in h: return i
            return None

        ci = {k: colidx(k) for k in ["received", "withdrawn", "registered", "eligible", "total"]}

        totals = {k: 0.0 for k in ci}
        found_total_row = False
        for r in range(header_row + 1, sh.nrows):
            dep = str(sh.cell_value(r, 0)).strip().upper()
            if not dep:
                continue
            def sf(idx):
                if idx is None: return 0.0
                try: return float(sh.cell_value(r, idx) or 0)
                except: return 0.0
            if "TOTAL" in dep:
                for k, idx in ci.items():
                    totals[k] = sf(idx)
                found_total_row = True
                break
            else:
                for k, idx in ci.items():
                    totals[k] += sf(idx)

        moz = lambda oz: round(oz / 1_000_000, 3)
        result = {
            "registered": moz(totals["registered"]),
            "eligible":   moz(totals["eligible"]),
            "received":   moz(totals["received"]),
            "withdrawn":  moz(totals["withdrawn"]),
        }
        print(f"  ✓ registered={result['registered']} eligible={result['eligible']} "
              f"received={result['received']} withdrawn={result['withdrawn']}")
        return result
    except Exception as e:
        print(f"  ✗ COMEX silver: {e}")
        return None

# ─────────────────────────────────────────────────────
# history.json 读写
# ─────────────────────────────────────────────────────

def load_history(path="history.json"):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_history(records, path="history.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"))

def append_history(snapshot, quotes, comex):
    """
    向 history.json 追加一条当日记录。
    格式：
    [
      {
        "date": "2026-02-28",
        "gold": 2918.4,
        "silver": 32.15,
        "copper": 4.62,
        "dxy": 106.8,
        "zijin_a": 39.63,
        "zijin_h": 14.28,
        "spx": 5842,
        "vix": 16.2,
        "tnx": 4.32,
        "gdx": 42.3,
        "cs_registered": 84.2,
        "cs_eligible": 312.5,
        "cs_withdrawn": 3.42
      },
      ...
    ]
    """
    records = load_history()

    today = snapshot  # "YYYY-MM-DD"

    # 如果今天已有记录则覆盖（Actions 重跑时不重复追加）
    records = [r for r in records if r.get("date") != today]

    entry = {"date": today}
    for field in HISTORY_FIELDS:
        q = quotes.get(field)
        entry[field] = q["price"] if q else None

    if comex:
        entry["cs_registered"] = comex.get("registered")
        entry["cs_eligible"]   = comex.get("eligible")
        entry["cs_withdrawn"]  = comex.get("withdrawn")

    records.append(entry)

    # 按日期排序，截断到最大条数
    records.sort(key=lambda r: r.get("date", ""))
    if len(records) > MAX_HISTORY:
        records = records[-MAX_HISTORY:]

    save_history(records)
    print(f"  ✓ history.json 现有 {len(records)} 条记录，最新：{today}")

# ─────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────

def main():
    print("=" * 52)
    print("zijin-dashboard · 数据抓取")
    print("=" * 52)

    tz  = pytz.timezone("Asia/Shanghai")
    now = datetime.now(tz)
    today_str   = now.strftime("%Y-%m-%d")
    updated_at  = now.strftime("%Y-%m-%d %H:%M CST")

    # 1. 抓取最新报价
    print(f"\n[1/3] 抓取报价...")
    quotes = {}
    for key, sym in TICKERS.items():
        print(f"  → {key:10s} ({sym})", end="  ")
        q = fetch_quote(sym)
        quotes[key] = q
        if q:
            sign = "+" if q["change"] >= 0 else ""
            print(f"✓  {q['price']}  {sign}{q['change']} ({sign}{q['change_pct']}%)")
        else:
            print("✗ 失败")

    # 2. 抓取 COMEX 白银库存
    print(f"\n[2/3] 抓取 COMEX 白银实物库存...")
    comex = fetch_comex_silver()

    # 3. 更新 history.json
    print(f"\n[3/3] 更新 history.json...")
    append_history(today_str, quotes, comex)

    # 4. 写 data.json（当日快照，不含历史序列）
    snapshot = {k: v for k, v in quotes.items()}
    snapshot["comex_silver"] = comex
    snapshot["updated_at"]   = updated_at

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成  {updated_at}")
    print(f"   data.json    — 当日快照")
    print(f"   history.json — 累积历史")
    print("=" * 52)


if __name__ == "__main__":
    main()

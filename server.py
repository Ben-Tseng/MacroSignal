"""
启动方式：
  1. 安装依赖：pip install requests flask flask-cors yfinance
  2. 设置你的FRED API Key（只需做一次）：
       Mac/Linux:  export FRED_API_KEY=你的32位Key
       Windows:    set FRED_API_KEY=你的32位Key
  3. 启动服务：python server.py
  4. 用浏览器打开 index.html 即可

服务会在本地 http://localhost:5100 运行，刷新网页时自动拉取最新数据。
"""

import os
from datetime import datetime, timedelta
import requests
import yfinance as yf
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

FRED_BASE     = "https://api.stlouisfed.org/fred/series/observations"
TREASURY_BASE = "https://www.treasurydirect.gov/TA_WS/securities/search"
API_KEY       = os.environ.get("FRED_API_KEY", "")


@app.route("/fred")
def fred_proxy():
    if not API_KEY:
        return jsonify({"error": "未设置 FRED_API_KEY 环境变量"}), 500

    series_id = request.args.get("series_id", "")
    limit     = request.args.get("limit", "2")

    if not series_id:
        return jsonify({"error": "缺少 series_id 参数"}), 400

    try:
        resp = requests.get(FRED_BASE, params={
            "series_id":  series_id,
            "api_key":    API_KEY,
            "sort_order": "desc",
            "limit":      limit,
            "file_type":  "json",
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "error_code" in data:
            return jsonify({"error": data.get("error_message", "FRED API错误")}), 400

        obs = [
            {"date": o["date"], "value": o["value"]}
            for o in data.get("observations", [])
            if o["value"] not in (".", "")
        ]
        return jsonify(obs)

    except requests.Timeout:
        return jsonify({"error": "FRED API请求超时"}), 504
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


@app.route("/gold")
def gold_price():
    """
    拉取黄金期货近N个交易日收盘价。
    数据来源：Yahoo Finance GC=F（黄金期货），无需API Key，每日更新。
    返回格式：[{"date":"2025-06-01","value":"3280.5"}, ...]，按日期降序。
    """
    limit = int(request.args.get("limit", 60))

    try:
        ticker = yf.Ticker("GC=F")
        # 拉取过去6个月数据，足够覆盖60个交易日
        hist = ticker.history(period="6mo", interval="1d", auto_adjust=True)

        if hist.empty:
            return jsonify({"error": "Yahoo Finance返回空数据"}), 502

        results = []
        for date, row in hist.iterrows():
            close = row["Close"]
            if close and close > 0:
                results.append({
                    "date":  date.strftime("%Y-%m-%d"),
                    "value": str(round(float(close), 2)),
                })

        # 按日期降序，取最近N条
        results.sort(key=lambda x: x["date"], reverse=True)
        return jsonify(results[:limit])

    except Exception as e:
        return jsonify({"error": f"黄金数据获取失败: {str(e)}"}), 502


@app.route("/treasury/btc")
def treasury_btc():
    """
    拉取最近N场10年期国债拍卖的认购倍数（Bid-to-Cover Ratio）。
    数据来源：美国财政部 TreasuryDirect 公开API，无需Key。
    返回格式：[{"date":"2025-05-14","btc":2.53}, ...]，按日期降序。
    """
    limit = int(request.args.get("limit", 10))

    try:
        start = (datetime.today() - timedelta(days=730)).strftime("%Y-%m-%d")

        resp = requests.get(TREASURY_BASE, params={
            "type":          "Note",
            "dateFieldName": "auctionDate",
            "startDate":     start,
            "format":        "json",
        }, timeout=15)
        resp.raise_for_status()
        securities = resp.json()

        results = []
        for s in securities:
            term = s.get("term", "")
            btc  = s.get("bidToCoverRatio")
            date = s.get("auctionDate", "")[:10]
            if "10-Year" in term and btc and float(btc) > 0:
                results.append({
                    "date": date,
                    "btc":  round(float(btc), 2),
                    "term": term,
                })

        results.sort(key=lambda x: x["date"], reverse=True)
        return jsonify(results[:limit])

    except requests.Timeout:
        return jsonify({"error": "财政部API请求超时"}), 504
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": f"数据解析失败: {str(e)}"}), 500


@app.route("/health")
def health():
    return jsonify({"ok": True, "api_key_set": bool(API_KEY)})


if __name__ == "__main__":
    if not API_KEY:
        print("\n⚠  警告：未检测到 FRED_API_KEY 环境变量。")
        print("   请先运行：export FRED_API_KEY=你的32位Key\n")
    else:
        print(f"\n✓  FRED API Key 已加载（{API_KEY[:6]}...）")
    port = int(os.environ.get("PORT", 5100))
    print(f"✓  本地代理启动中：http://localhost:{port}")
    print("   用浏览器打开 index.html 即可使用\n")
    app.run(host="0.0.0.0", port=port, debug=False)

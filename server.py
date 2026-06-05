"""
启动方式：
  1. 安装依赖：pip install requests flask flask-cors
  2. 设置你的FRED API Key（只需做一次）：
       Mac/Linux:  export FRED_API_KEY=你的32位Key
       Windows:    set FRED_API_KEY=你的32位Key
  3. 启动服务：python server.py
  4. 用浏览器打开 index.html 即可

服务会在本地 http://localhost:5100 运行，刷新网页时自动拉取最新FRED数据。
"""

import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 允许本地网页调用

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
API_KEY   = os.environ.get("FRED_API_KEY", "")

@app.route("/fred")
def fred_proxy():
    if not API_KEY:
        return jsonify({"error": "未设置 FRED_API_KEY 环境变量"}), 500

    series_id = request.args.get("series_id", "")
    limit      = request.args.get("limit", "2")

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

        # 过滤掉缺失值，返回简洁格式
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

@app.route("/health")
def health():
    key_set = bool(API_KEY)
    return jsonify({"ok": True, "api_key_set": key_set})

if __name__ == "__main__":
    if not API_KEY:
        print("\n⚠  警告：未检测到 FRED_API_KEY 环境变量。")
        print("   请先运行：export FRED_API_KEY=你的32位Key\n")
    else:
        print(f"\n✓  FRED API Key 已加载（{API_KEY[:6]}...）")
    print("✓  本地代理启动中：http://localhost:5100")
    print("   用浏览器打开 index.html 即可使用\n")
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port, debug=False)

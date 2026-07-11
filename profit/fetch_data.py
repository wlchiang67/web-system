# -*- coding: utf-8 -*-
"""從「通路獲利分析」Google Sheet 抽資料產 data/profit.json（唯讀）。
用法：python fetch_data.py
金鑰：%USERPROFILE%/.claude/secrets/sa_key.json（SA 需有該表檢視權）
"""
import json, os, sys, io, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests as rq
import google.auth.transport.requests
from google.oauth2 import service_account

SID = "1ouBAnNQ52l1s3Ycd3su2GiQfgSoCWZ-ZsDvVlqPThUc"
BASE = f"https://sheets.googleapis.com/v4/spreadsheets/{SID}"
KEY = os.path.join(os.path.expanduser("~"), ".claude", "secrets", "sa_key.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "profit.json")

info = json.load(open(KEY, encoding="utf-8"))
info.setdefault("token_uri", "https://oauth2.googleapis.com/token")
creds = service_account.Credentials.from_service_account_info(
    info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
creds.refresh(google.auth.transport.requests.Request())
hdr = {"Authorization": f"Bearer {creds.token}"}

def fetch(a1):
    r = rq.get(f"{BASE}/values/{rq.utils.quote(a1, safe='')}",
               headers=hdr, params={"valueRenderOption": "UNFORMATTED_VALUE"})
    r.raise_for_status()
    return r.json().get("values", [])

def num(v):
    if v in (None, ""): return 0
    if isinstance(v, (int, float)): return round(float(v))
    try: return round(float(str(v).replace(",", "")))
    except ValueError: return 0

# 明細: A月份 B年 C平台 D編碼 E分類 F營收 G成本 H內扣 I外付 ... Q完整期
ch = fetch("明細!A2:Q100000")
channel_rows = []
fees_through = None
for r in ch:
    g = lambda j: r[j] if len(r) > j else None
    ym = g(0)
    if not ym: continue
    flag = g(16)
    if flag == "Y":
        fees_through = max(fees_through or ym, ym)
    channel_rows.append([ym, g(3), g(2), g(4), num(g(5)), num(g(6)), num(g(7)), num(g(8))])

# 品牌明細: A月份 B平台 C編碼 D品牌 E營收 F成本 G毛利 H分攤費用
br = fetch("品牌明細!A2:J100000")
brand_rows = []
for r in br:
    g = lambda j: r[j] if len(r) > j else None
    if not g(0): continue
    brand_rows.append([g(0), g(2), g(3), num(g(4)), num(g(5)), num(g(7))])

out = {
    "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    "fees_through": fees_through,
    "channel_rows": channel_rows,   # [ym, code, platform, team, rev, cogs, feeK, feeM]
    "brand_rows": brand_rows,       # [ym, code, brand, rev, cogs, feeAlloc]
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("channel_rows:", len(channel_rows), "| brand_rows:", len(brand_rows),
      "| fees_through:", fees_through)
print("saved ->", OUT, f"({os.path.getsize(OUT)//1024} KB)")

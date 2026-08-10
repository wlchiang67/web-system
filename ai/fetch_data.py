# -*- coding: utf-8 -*-
"""從 BQ ai_citations_daily / ai_traffic_daily 產 data/ai.json（唯讀）。
用法：python fetch_data.py
金鑰：%USERPROFILE%/.claude/secrets/bq_sa.json
每日 07:40 由 ai_citation_snapshot 排程在快照寫入後自動呼叫並推上 GitHub Pages。
"""
import datetime
import json
import os

from google.cloud import bigquery
from google.oauth2 import service_account

KEY = os.path.join(os.path.expanduser("~"), ".claude", "secrets", "bq_sa.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ai.json")
PROJECT = "igogo-sales-dw"

creds = service_account.Credentials.from_service_account_file(KEY)
bq = bigquery.Client(project=PROJECT, credentials=creds, location="asia-east1")

cit = [
    [str(r.snapshot_date), r.site, r.platform, int(r.citations), int(r.pages)]
    for r in bq.query(
        "SELECT snapshot_date, site, platform, citations, pages "
        "FROM `igogo-sales-dw.sales.ai_citations_daily` ORDER BY snapshot_date, site, platform"
    ).result()
]
traf = [
    [str(r.data_date), r.site, r.source, int(r.sessions)]
    for r in bq.query(
        "SELECT data_date, site, source, sessions "
        "FROM `igogo-sales-dw.sales.ai_traffic_daily` ORDER BY data_date, site"
    ).result()
]

out = {
    "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    "citations": cit,   # [snapshot_date, site, platform, citations, pages]
    "traffic": traf,    # [data_date, site, source, sessions]
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("citations:", len(cit), "| traffic:", len(traf), "| saved ->", OUT)

# -*- coding: utf-8 -*-
"""igogosport Google Merchant 饋給轉換器。
來源：Shopline 內建饋給 XML（每店一份、不可設定）。
做的事：每支商品加 custom_label_0（形態）、custom_label_1（福利品）、修 brand；其餘欄位原封不動。
輸出：feeds/igogosport_google.xml（GitHub Pages 服務）＋ feeds/feed_report.json（分布統計，給日報盯）。
規則順序＝優先權，第一條命中就停。標題優先、product_type 備援。"""
import re, sys, json, html, datetime, pathlib, urllib.request

SRC = "https://shopline-feeds.s3.amazonaws.com/majority/eric483.xml"
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "igogosport_google.xml"
REPORT = HERE / "feed_report.json"

# (標籤, 標題 regex, product_type 關鍵字) —— 由上往下
FORM_RULES = [
    ("kids_watch",     r"兒童手錶|\bFone\b",                                  ["兒童手錶"]),
    ("kids_cam",       r"兒童相機",                                            ["兒童相機"]),
    ("kids_hp",        r"兒童.{0,6}耳機|兒童耳機",                              ["兒童耳機"]),
    ("3dpen",          r"3D ?列印筆|3D Pen",                                  ["3D列印筆"]),
    ("cardo_outdoor",  r"OUTDOOR|戶外運動",                                   ["戶外運動藍牙耳機"]),
    ("cardo_moto",     r"安全帽",                                              ["安全帽藍牙耳機", "車用耳機"]),
    # 喇叭先於耳機規則：JBuds Party／JBL Clip 4 等喇叭標題會撞 Buds／Clip
    ("soundbar",       r"Soundbar|聲霸",                                       ["SoundBar"]),
    ("speaker",        r"喇叭|Speaker|音響|唱盤|收音機",                           ["藍牙喇叭", "WiFi 喇叭"]),
    ("bone",           r"骨傳導",                                              ["骨傳導耳機"]),
    ("open",           r"開放式|耳夾|\bClip\b|JLab FLEX|\bARC\b|Open Jump|OPEN SPORT", ["開放式耳機"]),
    ("tws",            r"真無線|Pods|Buds|Air Pro|Free Pro|\bAir 2\b|Minor IV|\bTWS\b|\bJ1\b", ["真無線藍牙耳機"]),
    ("overear",        r"耳罩|頭戴|監聽|Headphone|Lux ANC|Wave Pro|Major\b|Studio|Monitor \d|M20x|S220", ["耳罩式"]),
    ("neckband",       r"頸掛",                                                ["頸掛式耳機"]),
    ("wired",          r"有線耳機|耳道式|線控",                                  ["有線耳機"]),
    ("transmitter",    r"發射|接收器|Transmitter",                              ["藍牙發射"]),
    ("webcam",         r"攝影機|視訊會議|會議系統|PANA|Desk Mate",                 ["網路攝影機", "視訊會議", "會議系統"]),
    ("mic",            r"麥克風",                                              ["辦公專區>麥克風"]),
    ("cricut_machine", r"裁切機|燙印機|EasyPress|Cricut (Joy|Maker|Explore|Venture)\b", ["裁切機/燙印機"]),
    ("cricut_acc",     r"Cricut",                                              ["Cricut｜"]),
    ("marker",         r"麥克筆|素描本|Ohuhu",                                   ["麥克筆", "繪畫用具"]),
    ("guitar",         r"吉他",                                                ["無弦吉他"]),
    ("case",           r"手機殼|保護殼|殼$|FlexFolio|EvoShe|MagSafe",            ["手機殼", "保護殼"]),
    ("travel",         r"Skross|萬國|轉接頭|行李|旅行",                           ["萬國插", "旅遊專區"]),
    ("charger",        r"充電|行動電源|快充",                                    ["充電專區"]),
    ("cleaner",        r"WHOOSH|清潔",                                         ["螢幕清潔"]),
    ("hearing",        r"輔聽",                                                ["輔聽器"]),
    ("watchband",      r"錶帶|Apple watch",                                    ["Apple Watch錶帶"]),
    ("hrm",            r"心跳帶",                                              ["心跳帶"]),
    ("accessory",      r"配件|支架|吊飾|磁鐵|頸枕|按摩|鬧鐘|保溫瓶|風扇",              ["周邊配件", "配件"]),
]
OUTLET_RE = re.compile(r"福利品|盒損品|展示品|爆品")
BRANDS = ["JLab", "EarFun", "Earfun", "Cleer", "myFirst", "Cardo", "iClever", "Tribit", "Audio Pro", "Cricut", "Ohuhu",
          "OXS", "Skross", "瑞士Skross", "Puro", "Creative", "Kaibo", "Marley", "Enya", "Coolpo", "Philips", "PHILIPS",
          "OneOdio", "Marshall", "BUTTONS", "DECODED", "Decoded", "Tech21", "WHOOSH", "Whoosh", "Motorola", "Nuheara",
          "Urbanista", "BeHear", "JBL", "UE", "Harman Kardon", "Blue", "1Mii", "Looki", "DOSHISHA", "LEXON", "Scosche",
          "Kreafunk", "ANFAST", "JAM", "Ampere", "Lexin", "ENACFIRE", "LinearFlux", "WhalesBot", "Garmin", "Apple",
          "Steve Madden", "Nine West", "鐵三角", "Audio-Technica", "ATH"]
BRAND_CANON = {"earfun": "EarFun", "瑞士skross": "Skross", "philips": "Philips", "decoded": "Decoded", "whoosh": "Whoosh",
               "鐵三角": "Audio-Technica", "ath": "Audio-Technica", "ue": "Ultimate Ears"}

def strip_tags(s): return re.sub(r"[💰⭐✨🔥🎮]", "", html.unescape(s))

def label0(title, ptype):
    for lab, trx, pkeys in FORM_RULES:
        if re.search(trx, title, re.I): return lab, "title"
    for lab, trx, pkeys in FORM_RULES:
        if any(k in ptype for k in pkeys): return lab, "ptype"
    return "", ""

def brand_of(title, ptype):
    m = re.search(r"(?:找品牌|更多品牌)\s*>\s*([^｜>|]+)｜", ptype)
    if m:
        b = m.group(1).strip(); return BRAND_CANON.get(b.lower(), b)
    t = re.sub(r"^【[^】]*】\s*", "", title)
    for b in sorted(BRANDS, key=len, reverse=True):
        if re.match(re.escape(b) + r"(\b|[^A-Za-z])", t, re.I): return BRAND_CANON.get(b.lower(), b)
    return ""

def main():
    raw = urllib.request.urlopen(SRC, timeout=120).read().decode("utf-8")
    items = re.findall(r"<item>.*?</item>", raw, flags=re.S)
    if len(items) < 500: sys.exit(f"ABORT: only {len(items)} items — source looks broken, keep previous feed")
    stats = {"label0": {}, "label1": {}, "brand": {}, "label0_source": {}, "unlabeled_instock": []}
    def rewrite(item):
        title = strip_tags(re.search(r"<g:title>(.*?)</g:title>", item, re.S).group(1))
        pt_m = re.search(r"<g:product_type>(.*?)</g:product_type>", item, re.S)
        ptype = strip_tags(pt_m.group(1)) if pt_m else ""
        avail = re.search(r"<g:availability>(.*?)</g:availability>", item).group(1)
        l0, src = label0(title, ptype)
        l1 = "outlet" if (OUTLET_RE.search(title) or "福利品" in ptype or "盒損品" in ptype) else ""
        br = brand_of(title, ptype)
        stats["label0"][l0 or "(none)"] = stats["label0"].get(l0 or "(none)", 0) + 1
        stats["label1"][l1 or "(none)"] = stats["label1"].get(l1 or "(none)", 0) + 1
        stats["brand"][br or "(none)"] = stats["brand"].get(br or "(none)", 0) + 1
        stats["label0_source"][src or "(none)"] = stats["label0_source"].get(src or "(none)", 0) + 1
        if not l0 and avail == "in stock" and not l1: stats["unlabeled_instock"].append(title)
        add = f"<g:custom_label_0>{html.escape(l0)}</g:custom_label_0><g:custom_label_1>{html.escape(l1)}</g:custom_label_1>"
        item = re.sub(r"</item>\s*$", add + "</item>", item)
        if br: item = re.sub(r"<g:brand>.*?</g:brand>", f"<g:brand>{html.escape(br)}</g:brand>", item, count=1, flags=re.S)
        return item
    pos = 0; out = []
    for m in re.finditer(r"<item>.*?</item>", raw, flags=re.S):
        out.append(raw[pos:m.start()]); out.append(rewrite(m.group(0))); pos = m.end()
    out.append(raw[pos:])
    OUT.write_text("".join(out), encoding="utf-8")
    stats["generated_at"] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")
    stats["items"] = len(items)
    REPORT.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"items {len(items)} | label0 {dict(sorted(stats['label0'].items(), key=lambda kv: -kv[1]))}")
    print(f"label0 source {stats['label0_source']} | outlet {stats['label1']}")
    print(f"brand (none) = {stats['brand'].get('(none)', 0)} | unlabeled in-stock = {len(stats['unlabeled_instock'])}")
    for t in stats["unlabeled_instock"][:30]: print("   ", t)

if __name__ == "__main__":
    main()

"""本機用：從「低價股_規則名單.xlsx」產生 site/stocks.json（名單、理由、風險）。"""
import json
import os
from openpyxl import load_workbook

H = os.path.dirname(os.path.abspath(__file__))
ws = load_workbook(os.path.join(H, "..", "低價股_規則名單.xlsx"))["名單"]
out = []
for r in ws.iter_rows(min_row=3, values_only=True):
    risk = [x.replace("近20日急跌", "入選前 20 日急跌") for x in (r[9] or "").split("、") if x and x != "還在破底"]
    out.append(dict(id=str(r[0]), name=r[1], industry=r[2], base=r[3], why=r[8].split("、"), risk=risk))
with open(os.path.join(H, "site", "stocks.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(len(out))

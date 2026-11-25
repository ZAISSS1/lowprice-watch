"""抓 FinMind 公開日線（不需金鑰）→ site/data.json；時間到時產生提醒內文 note.md。
用法：python update.py close | open | refresh
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

H = os.path.dirname(os.path.abspath(__file__))
TW = timezone(timedelta(hours=8))
BASE = "2026-11-20"
URL = "https://zaisss1.github.io/lowprice-watch/"
mode = sys.argv[1] if len(sys.argv) > 1 else "refresh"
now = datetime.now(TW)
today = now.strftime("%Y-%m-%d")


def P(*a):
    return os.path.join(H, *a)


def fetch(url):
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lowprice-watch"})
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:  # noqa: BLE001
            print("重試", k, type(e).__name__)
            time.sleep(8 * (k + 1))
    raise RuntimeError("資料來源連不上，這次不更新、不提醒")


def daily(sid):
    j = fetch(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={sid}&start_date=2026-09-01")
    r = [x for x in j["data"] if x["close"] > 0]
    if len(r) < 2:
        raise RuntimeError(f"{sid} 沒有資料")
    return r


def is_holiday():
    try:
        k = f"{now.year - 1911}{now:%m%d}"
        for x in fetch("https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"):
            if x["Date"] == k and "開始交易" not in x["Name"] and "最後交易" not in x["Name"]:
                return True
    except Exception:  # noqa: BLE001  查不到休市表就照常提醒
        pass
    return False


def finish(flag):
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as f:
        f.write(f"notify={'1' if flag else ''}\n")
    print("提醒" if flag else "不提醒")
    sys.exit(0)


with open(P("site", "stocks.json"), encoding="utf-8") as f:
    stocks = json.load(f)
state = {}
if os.path.exists(P("state.json")):
    with open(P("state.json"), encoding="utf-8") as f:
        state = json.load(f)

if mode in state and state[mode] == today:
    finish(False)
if mode == "open" and (now.weekday() >= 5 or is_holiday()):
    finish(False)

tx = daily("TAIEX")
last = tx[-1]["date"]
out = []
for s in stocks:
    r = daily(s["id"])
    b = next((x["close"] for x in reversed(r) if x["date"] <= BASE), s["base"])
    after = [x["close"] for x in r if x["date"] >= BASE]
    c, p = r[-1], r[-2]
    low = min(after)
    out.append(dict(id=s["id"], date=c["date"], close=c["close"], chg=c["close"] / p["close"] - 1,
                    since=c["close"] / b - 1, newlow=len(after) > 1 and c["close"] < min(after[:-1]),
                    fromlow=c["close"] / low - 1, spark=[x["close"] for x in r[-40:]]))
    time.sleep(.4)
tbase = next(x["close"] for x in tx if x["date"] == BASE)
data = dict(updated=now.strftime("%Y-%m-%d %H:%M"), date=last, base=BASE, rows=out,
            taiex=dict(close=tx[-1]["close"], chg=tx[-1]["close"] / tx[-2]["close"] - 1, since=tx[-1]["close"] / tbase - 1))
with open(P("site", "data.json"), "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print("資料日", last, len(out))

if mode == "refresh":
    finish(False)
# 今天的收盤還沒齊就不提醒，留給下一個排程再試
if mode == "close" and (last != today or sum(x["date"] == today for x in out) < len(out) - 2):
    finish(False)
if mode == "open" and last >= today:
    finish(False)

nm = {s["id"]: s["name"] for s in stocks}


def pc(v):
    return f"{'🔴' if v > 0 else '🟢' if v < 0 else '⚪'} {v:+.1%}"


t = data["taiex"]
L = [f"## {'今日收盤' if mode == 'close' else '開盤提醒：上一個交易日收盤'}（{last}）", "",
     f"加權指數 **{t['close']:,.0f}**　{pc(t['chg'])}　自 11/20 {t['since']:+.1%}", "",
     "| 股票 | 收盤 | 當日 | 自 11/20 | 狀態 |", "|:-:|:-:|:-:|:-:|:-:|"]
for x in sorted(out, key=lambda v: -v["chg"]):
    st = "創新低" if x["newlow"] else f"離低點 {x['fromlow']:+.1%}"
    if x["date"] != last:
        st = f"未成交（資料 {x['date'][5:]}）"
    L.append(f"| {x['id']} {nm[x['id']]} | {x['close']:.2f} | {pc(x['chg'])} | {x['since']:+.1%} | {st} |")
nl = [nm[x["id"]] for x in out if x["newlow"]]
L += ["", f"上漲 {sum(x['chg'] > 0 for x in out)} 檔、下跌 {sum(x['chg'] < 0 for x in out)} 檔；" + (f"創新低：{'、'.join(nl)}" if nl else "沒有創新低"),
      "", f"[看網頁]({URL})", "", "歷史回測、有存活者偏差、不是投資建議。🔴＝漲、🟢＝跌。"]
with open(P("note.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
up, dn = sum(x["chg"] > 0 for x in out), sum(x["chg"] < 0 for x in out)
avg = sum(x["since"] for x in out) / len(out)
msg = [f"加權 {t['close']:,.0f}（{t['chg']:+.1%}）", f"漲 {up}／跌 {dn}，9 檔自 11/20 平均 {avg:+.1%}", "創新低：" + ("、".join(nl) if nl else "無")]
msg += [f"{nm[x['id']]} {x['close']:.2f}（{x['chg']:+.1%}）" + ("" if x["date"] == last else " 未成交") for x in sorted(out, key=lambda v: -v["chg"])]
msg += ["不是投資建議"]
with open(P("push.json"), "w", encoding="utf-8") as f:
    json.dump(dict(topic=os.environ.get("NTFY_TOPIC", ""), title=f"{'收盤提醒' if mode == 'close' else '09:00 開盤提醒：上個交易日'} {last[5:]}",
                   message="
".join(msg), click=URL), f, ensure_ascii=False)
state[mode] = today
with open(P("state.json"), "w", encoding="utf-8") as f:
    json.dump(state, f)
finish(True)

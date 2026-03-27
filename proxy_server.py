#!/usr/bin/env python3
"""
盯盘仪表盘 - 轻量级 API 代理服务器
为前端提供跨域数据中转，解决 CORS 问题
"""

import os
import json
import time
import datetime
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
import ssl
import threading
import traceback

try:
    import akshare as ak
    HAS_AK = True
except ImportError:
    HAS_AK = False
    print("[提示] akshare 未安装，新闻功能将使用备用源")

PORT = 9999
WORKSPACE = "/Users/zhangxiang/Desktop/AI work"

# ── 股票池 ──
STOCK_POOL = [
    ("sh000001", "上证指数",   "A股",   "idx"),
    ("sz399001", "深证成指",   "A股",   "idx"),
    ("sz399006", "创业板指",   "A股",   "idx"),
    ("sh000300", "沪深300",    "A股",   "idx"),
    ("hkHSI",    "恒生指数",   "港股",  "idx"),
    ("hkHSCE",   "恒生国企",   "港股",  "idx"),
    ("gb_IXIC",  "纳斯达克",   "美股",  "idx"),
    ("gb_DJI",   "道琼斯",     "美股",  "idx"),
    ("gb_INX",   "标普500",    "美股",  "idx"),
    ("gb_nvda",  "英伟达",     "美股",  "stk"),
    ("gb_aapl",  "苹果",       "美股",  "stk"),
    ("gb_tsla",  "特斯拉",     "美股",  "stk"),
    ("gb_googl", "谷歌A类股",  "美股",  "stk"),
    ("hk00700",  "腾讯控股",   "港股",  "stk"),
    ("sz000993", "闽东电力",   "A股",   "stk"),
    ("sh603601", "再升科技",   "A股",   "stk"),
    ("sz002182", "宝武镁业",   "A股",   "stk"),
    ("sz000338", "潍柴动力",   "A股",   "stk"),
    ("hk00883",  "中国海洋石油", "港股",  "stk"),
    ("hk00100",  "MINIMAX",    "港股",  "stk"),
    ("hk02526",  "德适-B",     "港股",  "stk"),
    ("gb_gc=f",  "黄金COMEX",  "商品",  "cmd"),
    ("gb_si=f",  "白银",       "商品",  "cmd"),
    ("gb_cl=f",  "WTI原油",    "商品",  "cmd"),
    ("gb_hg=f",  "铜",         "商品",  "cmd"),
]

def sf(v, default=0.0):
    try:
        return float(v)
    except:
        return default

# ── 新浪行情 ──
def fetch_sina_stocks():
    codes = [c for c, *_ in STOCK_POOL]
    sina_codes = ",".join(codes)
    url = f"https://hq.sinajs.cn/list={sina_codes}"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    try:
        req = Request(url, headers=headers)
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=10, context=ctx) as resp:
            text = resp.read().decode("gbk", errors="replace")
        return parse_sina(text, codes)
    except Exception as e:
        print(f"[新浪行情] {e}")
        return []

def parse_sina(text, codes):
    import re
    results = []
    pool = {c: (n, m, t) for c, n, m, t in STOCK_POOL}
    
    for line in text.strip().split("\n"):
        m = re.search(r'hq_str_(\w+)="([^"]*)"', line)
        if not m:
            continue
        sc, raw = m.group(1), m.group(2)
        parts = raw.split(",")
        if len(parts) < 6:
            continue
        
        pE = pool.get(sc)
        if not pE:
            continue
        oN, mk, ty = pE
        
        price = chg = chgPct = 0
        lc = sc.lower()
        
        if lc in ("inx", "ixic", "dji"):
            price = sf(parts[1])
            chg = sf(parts[2])
            chgPct = chg / (price - chg) * 100 if (price - chg) != 0 else 0
        elif lc in ("nvda", "aapl", "tsla", "googl", "gc=f", "si=f", "cl=f", "hg=f",
                    "gb_nvda", "gb_aapl", "gb_tsla", "gb_googl",
                    "gb_gc=f", "gb_si=f", "gb_cl=f", "gb_hg=f"):
            # 新浪美股: parts[1]=现价, parts[2]=涨跌额, parts[3]=时间戳, parts[4]=无用
            # 正确涨跌幅 = 涨跌额 / (现价 - 涨跌额) * 100
            price = sf(parts[1])
            chg = sf(parts[2])
            chgPct = chg / (price - chg) * 100 if (price - chg) != 0 else 0
        elif sc.startswith("hk"):
            price = sf(parts[3])
            prev = sf(parts[4])
            if prev:
                chg = price - prev
                chgPct = (chg / prev * 100)
        else:
            price = sf(parts[3])
            prev = sf(parts[4])
            if prev:
                chg = price - prev
                chgPct = (chg / prev * 100)
        
        # 信号
        if chgPct > 2:
            sig, st = "sb", "强势买入"
        elif chgPct > 0.5:
            sig, st = "bu", "谨慎买入"
        elif chgPct < -2:
            sig, st = "ss", "注意止损"
        elif chgPct < -0.5:
            sig, st = "sl", "减仓观望"
        else:
            sig, st = "hd", "观望"
        
        results.append({
            "code": sc,
            "n": parts[0] or oN,
            "m": mk,
            "t": ty,
            "p": round(price, 2) if price else None,
            "c": round(chg, 2),
            "cp": round(chgPct, 2),
            "sg": sig,
            "st": st,
        })
        time.sleep(0.05)
    
    return results

# ── 板块 ──
def fetch_sectors():
    url = "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class"
    headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
    try:
        req = Request(url, headers=headers)
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=10, context=ctx) as resp:
            text = resp.read().decode("gbk", errors="replace")
        return parse_sectors(text)
    except Exception as e:
        print(f"[板块] {e}")
        return []

def parse_sectors(text):
    import re
    m = re.search(r"=\s*(\{.*\})", text, re.DOTALL)
    if not m:
        return []
    items = []
    raw = m.group(1).strip()
    pattern = re.compile(r'"([^"]+)":"([^"]+)"')
    groups = {}
    for key, val in pattern.findall(raw):
        groups[key] = val
    for key, val in groups.items():
        parts = val.split(",")
        if len(parts) < 6:
            continue
        try:
            chg = float(parts[5])
        except:
            continue
        name = parts[1]
        if not name:
            continue
        lead = parts[-1] if parts[-1] else (parts[9] if len(parts) > 9 else "")
        items.append({
            "n": name,
            "cp": round(chg, 2),
            "l": "ht" if chg > 3 else "wr" if chg > 1 else "nm",
            "lead": lead,
        })
    items.sort(key=lambda x: x["cp"], reverse=True)
    return items[:20]

# ── 东方财富港股 ──
def fetch_em_hk(code, name):
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid=116.{code}&fields=f43,f58,f169,f170"
    headers = {"Referer": "https://quote.eastmoney.com/", "User-Agent": "Mozilla/5.0"}
    try:
        req = Request(url, headers=headers)
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=8, context=ctx) as resp:
            data = json.loads(resp.read())
        d = data.get("data", {})
        if not d or not d.get("f43"):
            return None
        price = d.get("f43", 0) / 1000
        chg = d.get("f169", 0) / 1000
        cp = d.get("f170", 0) / 100
        if cp > 2:
            sig, st = "sb", "强势买入"
        elif cp > 0.5:
            sig, st = "bu", "谨慎买入"
        elif cp < -2:
            sig, st = "ss", "注意止损"
        elif cp < -0.5:
            sig, st = "sl", "减仓观望"
        else:
            sig, st = "hd", "观望"
        return {
            "code": "hk" + code,
            "n": d.get("f58", name),
            "m": "港股",
            "t": "stk",
            "p": round(price, 2),
            "c": round(chg, 2),
            "cp": round(cp, 2),
            "sg": sig,
            "st": st,
        }
    except Exception as e:
        print(f"[EM港股 {code}] {e}")
        return None

# ── 快讯（真实新闻源） ──
def _classify_news(text):
    """根据新闻内容判断情绪"""
    pos_kws = ["涨", "强", "净买入", "反弹", "突破", "超预期", "创新高", "大涨", "利好", "增持", "看涨"]
    neg_kws = ["跌", "回调", "减", "净流出", "风险", "大跌", "利空", "减持", "看跌", "警示", "警告"]
    # 计算正负关键词命中次数
    pos = sum(1 for k in pos_kws if k in text)
    neg = sum(1 for k in neg_kws if k in text)
    if pos > neg:
        return "ps"
    elif neg > pos:
        return "ng"
    return "ne"


def _fetch_real_news(max_items=8, max_age_hours=72):
    """从真实来源抓取近期财经快讯"""
    now = datetime.datetime.now()
    ts  = now.strftime("%H:%M")
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=max_age_hours)
    results = []

    # ── 来源1: 财新财经快讯 (akshare) ──
    if HAS_AK:
        try:
            df = ak.stock_news_main_cx()
            if df is not None and len(df) > 0:
                for _, row in df.iterrows():
                    summary = str(row.get("summary", ""))
                    tag     = str(row.get("tag", ""))
                    url     = str(row.get("url", ""))
                    if not summary or len(summary) < 10:
                        continue
                    # 提取时间（从URL中取日期）
                    item_date_str = ""
                    try:
                        # URL格式: https://database.caixin.com/YYYY-MM-DD/...
                        import re
                        m = re.search(r"(\d{4}-\d{2}-\d{2})", url)
                        if m:
                            item_date_str = m.group(1)
                            item_date = datetime.datetime.strptime(item_date_str, "%Y-%m-%d")
                            if item_date < cutoff:
                                continue
                    except Exception:
                        pass  # 解析失败不丢弃，过滤掉没有日期的行

                    # 标题简短（取summary前80字）
                    title = summary[:100].strip()
                    results.append({
                        "text": f"【{tag}】{title}",
                        "time": item_date_str[-5:] if item_date_str else ts,
                        "tp":   _classify_news(summary),
                        "src":  "财新",
                    })
        except Exception as e:
            print(f"[新闻-财新] {e}")

    # ── 来源2: 东方财富监管/公告快讯 (直接HTTP) ──
    try:
        import requests
        em_url = (
            "https://np-anotice-stock.eastmoney.com/api/security/ann"
            "?cb=jQuery&sr=-1&page_size=20&page_index=1"
            "&ann_type=SHA,CYB,SZA&client_source=web&f_node=0&s_node=0"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": "https://www.eastmoney.com",
        }
        resp = requests.get(em_url, timeout=8, headers=headers)
        text = resp.text
        import re
        # 解析 jQuery JSONP
        json_str = re.sub(r"^jQuery\(", "", text.rstrip().rstrip(")"))
        data = json.loads(json_str)
        for item in data.get("data", {}).get("list", []):
            title   = str(item.get("title_ch", item.get("title", "")))
            notice_date = str(item.get("notice_date", ""))[:10]
            codes_list  = item.get("codes", [])
            col_name    = ""
            for c in codes_list:
                col_name = str(c.get("column_name", ""))
                break
            if len(title) < 10:
                continue
            try:
                nd = datetime.datetime.strptime(notice_date, "%Y-%m-%d")
                if nd < cutoff:
                    continue
            except Exception:
                pass

            prefix = col_name if col_name else "公告速递"
            results.append({
                "text": f"【{prefix}】{title[:80]}",
                "time": notice_date[-5:] if notice_date else ts,
                "tp":   _classify_news(title),
                "src":  "东方财富",
            })
    except Exception as e:
        print(f"[新闻-东财] {e}")

    # ── 去重 & 按时间排序 ──
    seen = set()
    deduped = []
    for item in results:
        key = item["text"][:60]  # 按前60字去重
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    # 按时间倒序，取最新的
    deduped.sort(key=lambda x: x.get("time", "00:00"), reverse=True)
    return deduped[:max_items]


def gen_news():
    """返回格式兼容的新闻列表"""
    now = datetime.datetime.now()
    ts  = now.strftime("%H:%M")

    news_items = _fetch_real_news(max_items=8, max_age_hours=72)

    if not news_items:
        # 兜底：3天内硬编码快讯
        print("[新闻] 真实来源为空，使用备用池")
        pool = [
            "DeepSeek/国产大模型持续发酵，算力需求爆发式增长",
            "消费电子板块走强，AI手机换机潮预期持续升温",
            "新能源储能板块反弹，政策+订单双轮驱动",
            "南向资金持续净买入，腾讯、阿里获机构青睐",
            "英伟达Blackwell芯片需求超预期，AI产业链持续受益",
            "美联储降息预期升温，科技股估值支撑较强",
            "COMEX黄金高位震荡，避险需求提供下方支撑",
            "WTI原油突破80美元，OPEC+减产持续推进",
        ]
        h = now.hour
        random.seed(h * 60 + now.minute)
        selected = random.sample(pool, min(8, len(pool)))
        random.seed()
        return [{"tp": _classify_news(t), "t": t, "ts": ts} for t in selected]

    return [
        {"tp": item["tp"], "t": item["text"], "ts": item.get("time", ts)}
        for item in news_items
    ]

# ── 建议 ──
def gen_advice(stocks):
    now = datetime.datetime.now()
    ts = now.strftime("%H:%M")
    a_idx = [s for s in stocks if s["m"] == "A股" and s["t"] == "idx" and s["p"]]
    avg = sum(s["cp"] for s in a_idx) / len(a_idx) if a_idx else 0
    r = []
    if avg > 1.5:
        r.append({"tp": "bu", "t": f"【A股整体】三大指数强势上涨+{avg:.2f}%，趋势向好，可适度加仓顺势而为", "ts": ts})
    elif avg > 0.3:
        r.append({"tp": "hd", "t": "【A股整体】市场偏强震荡，结构性机会为主，建议轻仓布局主线板块", "ts": ts})
    elif avg < -1.5:
        r.append({"tp": "sl", "t": f"【A股整体】指数大幅回落{avg:.2f}%，注意控制仓位，等待企稳信号", "ts": ts})
    else:
        r.append({"tp": "hd", "t": "【A股整体】市场震荡整理，观望为主，控制仓位", "ts": ts})
    strong = [s for s in stocks if s["sg"] in ("sb", "bu") and s["t"] == "stk"]
    if strong:
        names = "、".join(f"{s['n']}({'+' if s['cp']>0 else ''}{s['cp']:.2f}%)" for s in strong[:3])
        r.append({"tp": "bu", "t": f"【个股机会】强势信号：{names}，可逢低关注", "ts": ts})
    danger = [s for s in stocks if s["sg"] in ("ss", "sl") and s["t"] == "stk"]
    if danger:
        names = "、".join(f"{s['n']}({'+' if s['cp']>0 else ''}{s['cp']:.2f}%)" for s in danger[:3])
        r.append({"tp": "sl", "t": f"【风险提示】弱势信号：{names}，注意止损或减仓", "ts": ts})
    return r

# ── HTTP 服务 ──
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/stocks":
            stocks = fetch_sina_stocks()
            # 补充东方财富港股
            for code, name, m, t in STOCK_POOL:
                if code in ("hk00100", "hk02526"):
                    em = fetch_em_hk(code[2:], name)
                    if em:
                        stocks.append(em)
            self.send_json(stocks)
        elif self.path == "/api/sectors":
            sectors = fetch_sectors()
            self.send_json(sectors)
        elif self.path == "/api/news":
            news = gen_news()
            self.send_json(news)
        elif self.path == "/api/advice":
            stocks = fetch_sina_stocks()
            for code, name, m, t in STOCK_POOL:
                if code in ("hk00100", "hk02526"):
                    em = fetch_em_hk(code[2:], name)
                    if em:
                        stocks.append(em)
            advice = gen_advice(stocks)
            self.send_json(advice)
        else:
            self.send_error(404)

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # 静默日志

def main():
    print("🚀 盯盘代理服务启动...")
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"✅ 服务已就绪！")
    print(f"📍 API 地址：http://localhost:{PORT}/api/stocks")
    print(f"📍 前端访问：http://localhost:9999/api/stocks 等")
    print(f"\n按 Ctrl+C 停止服务\n")
    server.serve_forever()

if __name__ == "__main__":
    main()

import os
import uuid
import json
import random
import requests
import base64
import gzip
import io
import zlib
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageEnhance
from flask import Flask, request, render_template_string, send_from_directory

app = Flask(__name__)

# ==================== 生产环境配置 ====================
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 上传限制

# 内存配置存储（Render 免费版重启会清空；永久链接 /p/ 不依赖此处）
USER_CONFIGS = {}

# ==================== Kindle 分辨率规格 ====================
# chrome = 浏览器顶部工具栏占用高度（px，估算值），用于计算可视区域居中
MODELS = {
    "basic":   {"name": "Kindle 基础版 第10代及以前", "w": 600,  "h": 800,  "chrome": 55},
    "basic11": {"name": "Kindle 基础版 第11代",       "w": 758,  "h": 1024, "chrome": 90},
    "pw3":     {"name": "Paperwhite 第7代及以前",     "w": 758,  "h": 1024, "chrome": 90},
    "pw4":     {"name": "Paperwhite 第10代",          "w": 758,  "h": 1024, "chrome": 90},
    "pw5":     {"name": "Paperwhite 第11代",          "w": 1236, "h": 1648, "chrome": 90},
    "oasis":   {"name": "Oasis 第9/10代",             "w": 1264, "h": 1680, "chrome": 90},
    "scribe":  {"name": "Scribe",                     "w": 1860, "h": 2480, "chrome": 90},
}

# ==================== 词库（11 语种，例句附中文翻译） ====================
WORD_BANK = {
    "english": {
        "name": "英语", "flag": "🇺🇸",
        "books": {
            "cet4": {"name": "四级英语词汇", "words": [
                {"word": "abandon", "phonetic": "/əˈbændən/", "meaning": "v. 放弃，抛弃", "example": "He abandoned his car in the snow.", "example_cn": "他把车丢在了雪地里。"},
                {"word": "ability", "phonetic": "/əˈbɪləti/", "meaning": "n. 能力，才能", "example": "She has the ability to speak four languages.", "example_cn": "她会说四种语言。"},
                {"word": "absolute", "phonetic": "/ˈæbsəluːt/", "meaning": "adj. 绝对的", "example": "I have absolute confidence in her.", "example_cn": "我对她有绝对的信心。"},
                {"word": "academic", "phonetic": "/ˌækəˈdemɪk/", "meaning": "adj. 学术的", "example": "She had a brilliant academic career.", "example_cn": "她的学术生涯非常辉煌。"},
                {"word": "access", "phonetic": "/ˈækses/", "meaning": "n. 通道；使用权", "example": "Students need access to books.", "example_cn": "学生需要能接触到书籍。"},
            ]},
            "cet6": {"name": "六级英语词汇", "words": [
                {"word": "ambiguous", "phonetic": "/æmˈbɪɡjuəs/", "meaning": "adj. 模棱两可的", "example": "The instructions were ambiguous.", "example_cn": "这些指示含糊不清。"},
                {"word": "analogy", "phonetic": "/əˈnælədʒi/", "meaning": "n. 类比", "example": "He drew an analogy between the brain and a computer.", "example_cn": "他把大脑比作电脑。"},
            ]},
            "kaoyan": {"name": "考研英语词汇", "words": [
                {"word": "advocate", "phonetic": "/ˈædvəkeɪt/", "meaning": "v. 提倡", "example": "She advocates taking a long-term view.", "example_cn": "她主张从长计议。"},
                {"word": "alleviate", "phonetic": "/əˈliːvieɪt/", "meaning": "v. 减轻", "example": "The medicine alleviated the pain.", "example_cn": "这种药减轻了疼痛。"},
            ]},
            "ielts": {"name": "雅思核心词汇", "words": [
                {"word": "contemporary", "phonetic": "/kənˈtempəreri/", "meaning": "adj. 当代的", "example": "Contemporary art is often controversial.", "example_cn": "当代艺术常常引发争议。"},
            ]},
            "toefl": {"name": "托福核心词汇", "words": [
                {"word": "substantial", "phonetic": "/səbˈstænʃl/", "meaning": "adj. 大量的", "example": "The project requires substantial funding.", "example_cn": "这个项目需要大量资金。"},
            ]},
            "gre": {"name": "GRE词汇", "words": [
                {"word": "abate", "phonetic": "/əˈbeɪt/", "meaning": "v. 减弱", "example": "The storm began to abate.", "example_cn": "暴风雨开始减弱。"},
            ]},
            "business": {"name": "商务英语", "words": [
                {"word": "deadline", "phonetic": "/ˈdedlaɪn/", "meaning": "n. 截止日期", "example": "We must meet the deadline.", "example_cn": "我们必须赶上截止日期。"},
            ]},
        }
    },
    "japanese": {
        "name": "日语", "flag": "🇯🇵",
        "books": {
            "n1": {"name": "JLPT N1", "words": [{"word": "意向", "phonetic": "いこう", "meaning": "意向，打算", "example": "彼の意向を確認した。", "example_cn": "确认了他的意向。"}]},
            "n2": {"name": "JLPT N2", "words": [{"word": "曖昧", "phonetic": "あいまい", "meaning": "暧昧，含糊", "example": "曖昧な返事をするな。", "example_cn": "别给含糊的答复。"}]},
            "n3": {"name": "JLPT N3", "words": [{"word": "余計", "phonetic": "よけい", "meaning": "多余", "example": "余計な心配をした。", "example_cn": "白担心了一场。"}]},
            "n4": {"name": "JLPT N4", "words": [{"word": "約束", "phonetic": "やくそく", "meaning": "约定", "example": "約束を守ってください。", "example_cn": "请遵守约定。"}]},
            "n5": {"name": "JLPT N5", "words": [{"word": "学生", "phonetic": "がくせい", "meaning": "学生", "example": "私は大学生です。", "example_cn": "我是大学生。"}]},
        }
    },
    "french": {
        "name": "法语", "flag": "🇫🇷",
        "books": {
            "tef": {"name": "TEF/TCF核心词", "words": [{"word": "bonjour", "phonetic": "/bɔ̃ʒuʁ/", "meaning": "你好", "example": "Bonjour, comment allez-vous?", "example_cn": "你好，你好吗？"}]},
            "basic_fr": {"name": "法语入门", "words": [{"word": "amour", "phonetic": "/amuʁ/", "meaning": "爱", "example": "L'amour est aveugle.", "example_cn": "爱情是盲目的。"}]},
        }
    },
    "russian": {
        "name": "俄语", "flag": "🇷🇺",
        "books": {
            "basic_ru": {"name": "俄语入门", "words": [{"word": "привет", "phonetic": "privet", "meaning": "你好", "example": "Привет, как дела?", "example_cn": "你好，最近怎么样？"}]},
        }
    },
    "korean": {
        "name": "韩语", "flag": "🇰🇷",
        "books": {
            "topik1": {"name": "TOPIK I", "words": [{"word": "안녕하세요", "phonetic": "annyeonghaseyo", "meaning": "你好", "example": "안녕하세요, 만나서 반갑습니다.", "example_cn": "你好，很高兴见到你。"}]},
        }
    },
    "german": {
        "name": "德语", "flag": "🇩🇪",
        "books": {
            "testdaf": {"name": "德福核心词", "words": [{"word": "Danke", "phonetic": "/ˈdaŋkə/", "meaning": "谢谢", "example": "Danke schön!", "example_cn": "非常感谢！"}]},
        }
    },
    "italian": {
        "name": "意大利语", "flag": "🇮🇹",
        "books": {
            "basic_it": {"name": "意大利语入门", "words": [{"word": "ciao", "phonetic": "/ˈtʃaːo/", "meaning": "你好/再见", "example": "Ciao, come stai?", "example_cn": "你好，你怎么样？"}]},
        }
    },
    "spanish": {
        "name": "西班牙语", "flag": "🇪🇸",
        "books": {
            "dele": {"name": "DELE核心词", "words": [{"word": "hola", "phonetic": "/ˈola/", "meaning": "你好", "example": "¡Hola! ¿Cómo estás?", "example_cn": "你好！你好吗？"}]},
        }
    },
    "cantonese": {
        "name": "粤语", "flag": "🇭🇰",
        "books": {
            "basic_yue": {"name": "粤语入门", "words": [{"word": "你好", "phonetic": "nei5 hou2", "meaning": "你好", "example": "你好，我係陳先生。", "example_cn": "你好，我是陈先生。"}]},
        }
    },
    "portuguese": {
        "name": "葡萄牙语", "flag": "🇵🇹",
        "books": {
            "basic_pt": {"name": "葡萄牙语入门", "words": [{"word": "olá", "phonetic": "/oˈla/", "meaning": "你好", "example": "Olá, como estás?", "example_cn": "你好，你好吗？"}]},
        }
    },
    "chinese": {
        "name": "中文", "flag": "🇨🇳",
        "books": {
            "chengyu": {"name": "成语词典", "words": [{"word": "画龙点睛", "phonetic": "huà lóng diǎn jīng", "meaning": "比喻在关键处点明实质", "example": "这篇文章结尾真是画龙点睛。", "example_cn": ""}]},
            "gushi": {"name": "古诗词名句", "words": [{"word": "海内存知己", "phonetic": "hǎi nèi cún zhī jǐ", "meaning": "四海之内有知心朋友", "example": "海内存知己，天涯若比邻。", "example_cn": ""}]},
        }
    },
}

# ==================== 远程扩充词库（启动时拉取，失败用内置词库兜底） ====================
# 词库来源清单维护在仓库 wordbank_sources.txt（以后更新词库只改该文件，无需动代码）：
#   json <url>  —— 明文 JSON 词库（兼容旧的 zlib+base64 封装）
#   b64  <url>  —— gzip+base64 分片，按行序拼接解码为一个 JSON 词库
# 英语词条/音标/释义来自 ECDICT（MIT 开源词典）；例句来自 tatoeba.org（CC-BY 2.0 FR），
# 例句中文翻译 = Tatoeba 中文句对 + 人工补译。单个来源失败不影响其它。
SOURCES_URL = "https://raw.githubusercontent.com/serenashenn3-art/kindle-display-render/main/wordbank_sources.txt"
EMBEDDED_SOURCES = """
json https://paste.rs/PydxG
json https://paste.rs/I4hhZ
json https://paste.rs/49Blh
json https://paste.rs/TQrbu
b64 https://paste.rs/OZSpM
b64 https://paste.rs/FtU4T
b64 https://paste.rs/br2m6
b64 https://paste.rs/6Egnm
b64 https://paste.rs/GCUlE
b64 https://paste.rs/MGKQL
b64 https://paste.rs/Mpx8f
b64 https://paste.rs/tXX1A
b64 https://paste.rs/vXG3M
b64 https://paste.rs/avC5q
"""

def _merge_bank(data):
    n = 0
    for lang, lpack in (data or {}).items():
        if lang == "meta" or lang not in WORD_BANK or not isinstance(lpack, dict):
            continue
        for bk, pack in lpack.items():
            words = pack.get("words") if isinstance(pack, dict) else pack
            if bk in WORD_BANK[lang]["books"] and words:
                WORD_BANK[lang]["books"][bk]["words"] = [
                    {"word": w["w"], "phonetic": w.get("p", ""), "meaning": w.get("m", ""),
                     "example": w.get("e", ""), "example_cn": w.get("c", "")}
                    for w in words]
                if isinstance(pack, dict) and pack.get("name"):
                    WORD_BANK[lang]["books"][bk]["name"] = pack["name"]
                n += len(words)
    return n

def _parse_bank_payload(raw):
    for algo in ("gzip", "zlib", "plain"):
        try:
            if algo == "gzip":
                return json.loads(gzip.decompress(base64.b64decode(raw)).decode("utf-8"))
            if algo == "zlib":
                return json.loads(zlib.decompress(base64.b64decode(raw)).decode("utf-8"))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            continue
    return None

def load_remote_bank():
    try:
        src = requests.get(SOURCES_URL, timeout=8).text
        if "json" not in src and "b64" not in src:
            src = EMBEDDED_SOURCES
    except Exception:
        src = EMBEDDED_SOURCES
    json_urls, b64_urls = [], []
    for line in src.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        kind, url = parts
        if kind == "json":
            json_urls.append(url)
        elif kind == "b64":
            b64_urls.append(url)
    total = 0
    for url in json_urls:
        try:
            data = _parse_bank_payload(requests.get(url, timeout=15).content)
            if data:
                total += _merge_bank(data)
                print(f"[wordbank] merged {url}")
        except Exception as exc:
            print(f"[wordbank] fetch failed {url}: {exc}")
    if b64_urls:
        try:
            blob = "".join(requests.get(u, timeout=15).text for u in b64_urls)
            data = json.loads(gzip.decompress(base64.b64decode(blob)).decode("utf-8"))
            total += _merge_bank(data)
            print(f"[wordbank] merged {len(b64_urls)} b64 shards")
        except Exception as exc:
            print(f"[wordbank] b64 shards failed: {exc}")
    print(f"[wordbank] total remote words: {total}")
    return total > 100

try:
    load_remote_bank()
except Exception:
    pass

# ==================== 天气 API ====================
CITY_COORDS = {
    "beijing": (39.9042, 116.4074), "shanghai": (31.2304, 121.4737),
    "guangzhou": (23.1291, 113.2644), "shenzhen": (22.5431, 114.0579),
    "chengdu": (30.5728, 104.0668), "hangzhou": (30.2741, 120.1551),
    "wuhan": (30.5928, 114.3055), "xian": (34.3416, 108.9398),
    "nanjing": (32.0603, 118.7969), "chongqing": (29.5630, 106.5516),
    "tianjin": (39.0842, 117.2009), "suzhou": (31.2989, 120.5853),
    "tokyo": (35.6762, 139.6503), "newyork": (40.7128, -74.0060),
    "london": (51.5074, -0.1278), "paris": (48.8566, 2.3522),
}

CITY_TZ = {
    "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "guangzhou": "Asia/Shanghai", "shenzhen": "Asia/Shanghai",
    "chengdu": "Asia/Shanghai", "hangzhou": "Asia/Shanghai",
    "wuhan": "Asia/Shanghai", "xian": "Asia/Shanghai",
    "nanjing": "Asia/Shanghai", "chongqing": "Asia/Shanghai",
    "tianjin": "Asia/Shanghai", "suzhou": "Asia/Shanghai",
    "tokyo": "Asia/Tokyo", "newyork": "America/New_York",
    "london": "Europe/London", "paris": "Europe/Paris",
}
DEFAULT_TZ = "Asia/Shanghai"

WEATHER_CODES = {
    0: "晴", 1: "多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "小雨", 55: "中雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "阵雨", 82: "暴雨",
    95: "雷雨", 96: "雷雨伴冰雹", 99: "雷雨伴冰雹",
}

def get_weather(city_key):
    if city_key not in CITY_COORDS:
        return {"temp": "--", "weather": "未知", "city": city_key}
    lat, lon = CITY_COORDS[city_key]
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&current=temperature_2m,weather_code")
        r = requests.get(url, timeout=5)
        data = r.json()
        cur = data.get("current") or {}
        if "temperature_2m" in cur:
            temp = cur["temperature_2m"]
            code = cur.get("weather_code", 0)
            return {"temp": f"{int(temp)}°C", "weather": WEATHER_CODES.get(code, "多云"), "city": city_key.capitalize()}
        raise ValueError("unexpected response shape")
    except Exception:
        try:
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                   f"&current_weather=true")
            r = requests.get(url, timeout=5)
            data = r.json()
            cw = data.get("current_weather") or {}
            if "temperature" in cw:
                temp = cw["temperature"]
                code = cw.get("weathercode", 0)
                return {"temp": f"{int(temp)}°C", "weather": WEATHER_CODES.get(code, "多云"), "city": city_key.capitalize()}
        except Exception:
            pass
        return {"temp": "--°C", "weather": "获取失败", "city": city_key.capitalize()}


# ==================== 刷新策略选择器（各模式默认不同） ====================
REFRESH_OPTIONS = [
    ("5", "5 秒（极速轮播）"),
    ("10", "10 秒（番茄钟推荐）"),
    ("15", "15 秒"),
    ("30", "30 秒（相框推荐）"),
    ("60", "1 分钟（时钟推荐）"),
    ("180", "3 分钟"),
    ("300", "5 分钟（看板/单词推荐）"),
    ("600", "10 分钟"),
    ("1800", "30 分钟"),
    ("3600", "1 小时"),
    ("0", "不自动刷新（纯静态）"),
]

def build_refresh_select(default_value="300"):
    options = ""
    for val, label in REFRESH_OPTIONS:
        selected = "selected" if val == default_value else ""
        options += f'<option value="{val}" {selected}>{label}</option>\n'
    return f"""
    <label>刷新策略</label>
    <select name="interval">
        {options}
    </select>
    <p class="hint">「不自动刷新」适合固定展示，Kindle 按刷新键手动更新</p>
    """

# ==================== 看板/阅读 数据计算（生成与永久链接渲染共用） ====================
def compute_events(events_raw):
    events = []
    for er in events_raw:
        if "|" in er:
            name, date_str = er.split("|", 1)
            try:
                target = datetime.strptime(date_str.strip(), "%Y-%m-%d")
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                delta = (target - today).days
                if delta < 0:
                    events.append({"name": name.strip(), "days": "已过去"})
                elif delta == 0:
                    events.append({"name": name.strip(), "days": "就是今天！"})
                else:
                    events.append({"name": name.strip(), "days": f"还有 {delta} 天"})
            except Exception:
                events.append({"name": name.strip(), "days": "日期格式错误"})
    return events

def compute_habits(habits):
    habits_out = []
    for i, h in enumerate(habits):
        pct = ((i * 37 + datetime.now().day * 13) % 100)
        habits_out.append({"name": h, "pct": pct})
    return habits_out

def compute_books(books_raw):
    books = []
    for br in books_raw:
        if "|" in br:
            parts = br.split("|")
            if len(parts) >= 3:
                try:
                    cur, tot = int(parts[1].strip()), int(parts[2].strip())
                    pct = min(100, max(0, int(cur / tot * 100)))
                    books.append({"name": parts[0].strip(), "current": cur, "total": tot, "pct": pct})
                except Exception:
                    pass
    return books

# ==================== 永久链接（配置压缩编码进 URL，重启不过期） ====================
def encode_cfg(tc):
    raw = json.dumps(tc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")

def decode_cfg(token):
    pad = "=" * (-len(token) % 4)
    raw = zlib.decompress(base64.urlsafe_b64decode(token + pad))
    return json.loads(raw.decode("utf-8"))

def expand_token_cfg(tc):
    """把 URL 里的紧凑配置还原成渲染用的完整配置"""
    m = tc.get("m")
    if m not in ("info", "board", "reading", "pomodoro", "words"):
        raise ValueError("unknown mode")
    cfg = {"mode": m, "model": tc.get("md", "pw4"), "interval": int(tc.get("i", 300))}
    if m == "info":
        cfg["city"] = tc.get("c", "beijing")
    elif m == "board":
        cfg["todos"] = tc.get("t", [])
        cfg["events"] = compute_events(tc.get("e", []))
        cfg["habits"] = compute_habits(tc.get("hb", []))
    elif m == "reading":
        cfg["books"] = compute_books(tc.get("bk", []))
    elif m == "pomodoro":
        cfg["duration"] = int(tc.get("d", 25))
        cfg["task_name"] = tc.get("t", "专注中") or "专注中"
        cfg["start_time"] = tc.get("s") or datetime.now().isoformat()
    elif m == "words":
        lang = tc.get("l", "english")
        book = tc.get("b", "cet4")
        book_info = WORD_BANK.get(lang, {}).get("books", {}).get(book, {})
        words = book_info.get("words", [])
        cfg.update({
            "language": lang,
            "book": book,
            "words": words,
            "total": len(words),
            "book_name": book_info.get("name", ""),
            "lang_flag": WORD_BANK.get(lang, {}).get("flag", "🇺🇸"),
            "show_phonetic": bool(tc.get("sp", 1)),
            "show_meaning": bool(tc.get("sm", 1)),
            "show_progress": bool(tc.get("sg", 1)),
        })
    return cfg

# ==================== 配置页面（纯链接切换，零 JavaScript，兼容 Kindle 老浏览器） ====================
MODE_DEFS = [
    ("info", "📊", "信息面板"),
    ("board", "📋", "个人看板"),
    ("frame", "🖼", "电子相框"),
    ("reading", "📚", "阅读进度"),
    ("pomodoro", "🍅", "番茄钟"),
    ("words", "🔤", "单词卡片"),
]

CONFIG_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kindle 展示中心</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f5f6fa; padding:16px; max-width:560px; margin:0 auto; color:#1a1a1a; }
.header { text-align:center; padding:24px 0 12px; }
.header h1 { font-size:24px; margin-bottom:6px; }
.header p { color:#666; font-size:14px; }
.mode-grid { margin:16px 0; }
.mode-card { display:inline-block; width:31%; margin:0 1% 10px 0; vertical-align:top; background:#fff; border:2px solid #e5e5e5; border-radius:14px; padding:16px 8px; text-align:center; text-decoration:none; color:#1a1a1a; }
.mode-card:hover { border-color:#999; }
.mode-card.active { border-color:#1a1a1a; background:#1a1a1a; color:#fff; }
.mode-card .icon { font-size:28px; margin-bottom:6px; display:block; }
.mode-card .title { font-size:13px; font-weight:600; }
.card { background:#fff; border-radius:14px; padding:20px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
.card h2 { font-size:15px; font-weight:600; margin-bottom:14px; color:#333; }
label { display:block; margin-bottom:6px; font-size:14px; color:#444; font-weight:500; }
input[type="text"], input[type="number"], input[type="date"], textarea, select {
    width:100%; padding:12px; border:1.5px solid #e5e5e5; border-radius:10px; font-size:15px; margin-bottom:12px; background:#fafafa;
}
textarea { min-height:80px; resize:vertical; font-family:inherit; }
.hint { font-size:12px; color:#999; margin-top:-8px; margin-bottom:12px; }
.btn { width:100%; padding:16px; background:#1a1a1a; color:#fff; border:none; border-radius:14px; font-size:16px; font-weight:600; cursor:pointer; margin-top:8px; }
.tip { font-size:13px; color:#666; margin-top:16px; line-height:1.7; background:#fff; padding:16px; border-radius:14px; }
.tip code { background:#f0f0f0; padding:2px 6px; border-radius:4px; font-family:monospace; }
.checkbox-row { margin-bottom:10px; }
.checkbox-row input { width:20px; height:20px; accent-color:#1a1a1a; vertical-align:middle; }
.checkbox-row span { vertical-align:middle; }
.file-input { padding:10px; border:2px dashed #ddd; border-radius:10px; text-align:center; margin-bottom:12px; }
.chip { display:inline-block; padding:8px 12px; border:1.5px solid #e5e5e5; border-radius:20px; margin:0 6px 8px 0; font-size:14px; color:#1a1a1a; text-decoration:none; background:#fafafa; }
.chip.active { background:#1a1a1a; color:#fff; border-color:#1a1a1a; }
</style>
</head>
<body>

<div class="header">
    <h1>📖 Kindle 展示中心</h1>
    <p>6 种展示模式 · 刷新策略自由选 · 零越狱</p>
</div>

<div class="mode-grid">
    {% for key, icon, title in modes %}
    <a class="mode-card{% if key == mode %} active{% endif %}" href="/?mode={{ key }}">
        <span class="icon">{{ icon }}</span>
        <span class="title">{{ title }}</span>
    </a>
    {% endfor %}
</div>

<form action="/generate" method="POST" enctype="multipart/form-data">
    <input type="hidden" name="mode" value="{{ mode }}">

    <div class="card">
        <h2>通用设置</h2>
        <label>Kindle 型号</label>
        <select name="model">
            <option value="pw4" selected>Paperwhite 第10代 (758×1024)</option>
            <option value="pw5">Paperwhite 第11代 (1236×1648)</option>
            <option value="pw3">Paperwhite 第7代及以前 (758×1024)</option>
            <option value="basic11">Kindle 基础版 第11代 (758×1024)</option>
            <option value="basic">Kindle 基础版 第10代及以前 (600×800)</option>
            <option value="oasis">Oasis 第9/10代 (1264×1680)</option>
            <option value="scribe">Scribe (1860×2480)</option>
        </select>
    </div>

    {% if mode == "info" %}
    <div class="card">
        <h2>📊 信息面板设置</h2>
        <label>城市</label>
        <select name="city">
            <option value="beijing">北京</option>
            <option value="shanghai">上海</option>
            <option value="guangzhou">广州</option>
            <option value="shenzhen">深圳</option>
            <option value="chengdu">成都</option>
            <option value="hangzhou">杭州</option>
            <option value="wuhan">武汉</option>
            <option value="xian">西安</option>
            <option value="nanjing">南京</option>
            <option value="chongqing">重庆</option>
            <option value="tianjin">天津</option>
            <option value="suzhou">苏州</option>
            <option value="tokyo">东京</option>
            <option value="newyork">纽约</option>
            <option value="london">伦敦</option>
            <option value="paris">巴黎</option>
        </select>
        """ + build_refresh_select("60") + """
    </div>
    {% endif %}

    {% if mode == "board" %}
    <div class="card">
        <h2>📋 个人看板设置</h2>
        <label>待办事项（每行一个）</label>
        <textarea name="todos" placeholder="完成报告&#10;预约牙医&#10;买牛奶"></textarea>
        <label>纪念日（格式：名称|日期，每行一个）</label>
        <textarea name="events" placeholder="结婚纪念日|2025-05-20&#10;生日|1995-08-15"></textarea>
        <p class="hint">日期格式：YYYY-MM-DD，自动计算剩余天数</p>
        <label>习惯打卡（每行一个）</label>
        <textarea name="habits" placeholder="早起&#10;阅读30分钟&#10;运动"></textarea>
        """ + build_refresh_select("300") + """
    </div>
    {% endif %}

    {% if mode == "frame" %}
    <div class="card">
        <h2>🖼 电子相框设置</h2>
        <label>上传照片（可多张，建议 3-10 张）</label>
        <input type="file" name="photos" multiple accept="image/*" class="file-input">
        <p class="hint">后端自动转为 E-ink 灰度高对比度图片（建议在手机上配置上传）</p>
        """ + build_refresh_select("30") + """
    </div>
    {% endif %}

    {% if mode == "reading" %}
    <div class="card">
        <h2>📚 阅读进度设置</h2>
        <label>书籍信息（格式：书名|当前页|总页数，每行一本）</label>
        <textarea name="books" placeholder="三体|280|400&#10;百年孤独|120|360&#10;人类简史|45|300"></textarea>
        <p class="hint">自动计算阅读百分比并渲染进度条</p>
        """ + build_refresh_select("300") + """
    </div>
    {% endif %}

    {% if mode == "pomodoro" %}
    <div class="card">
        <h2>🍅 番茄钟设置</h2>
        <label>专注时长（分钟）</label>
        <input type="number" name="duration" value="25" min="1" max="120">
        <label>任务名称</label>
        <input type="text" name="task_name" placeholder="例如：写论文、背单词">
        <label>倒计时刷新精度</label>
        <select name="interval">
            <option value="1">1 秒（高精度，Kindle 刷新频繁）</option>
            <option value="5">5 秒</option>
            <option value="10" selected>10 秒（推荐平衡）</option>
            <option value="30">30 秒</option>
            <option value="60">1 分钟</option>
            <option value="0">不自动刷新（需手动按刷新键）</option>
        </select>
        <p class="hint">E-ink 屏幕刷新有闪烁，10 秒是精度与体验的平衡</p>
    </div>
    {% endif %}

    {% if mode == "words" %}
    <div class="card">
        <h2>🔤 单词卡片设置</h2>
        <label>语种（点击切换，页面会刷新）</label>
        <div class="chip-row">
            {% for k, v in wordbank.items() %}
            <a class="chip{% if k == lang %} active{% endif %}" href="/?mode=words&lang={{ k }}">{{ v.flag }} {{ v.name }}</a>
            {% endfor %}
        </div>
        <input type="hidden" name="language" value="{{ lang }}">
        <label>词书</label>
        <select name="book">
            {% for bk, bv in books.items() %}
            <option value="{{ bk }}">{{ bv.name }}</option>
            {% endfor %}
        </select>
        <label>显示内容</label>
        <div class="checkbox-row"><input type="checkbox" name="show_phonetic" checked> <span>音标/发音</span></div>
        <div class="checkbox-row"><input type="checkbox" name="show_meaning" checked> <span>释义</span></div>
        <div class="checkbox-row"><input type="checkbox" name="show_progress" checked> <span>进度</span></div>
        <p class="hint">例句和中文翻译始终显示</p>
        """ + build_refresh_select("300") + """
    </div>
    {% endif %}

    <button type="submit" class="btn">生成 Kindle 展示链接</button>
</form>

<div class="tip">
    <strong>📌 Kindle 使用步骤：</strong><br>
    1. 连接 WiFi → 打开「体验版浏览器」<br>
    2. 输入生成的链接地址<br>
    3. 在搜索框输入 <code>~ds</code> 并按回车（禁止锁屏）<br>
    4. 插上电源，即可长期展示
</div>

</body>
</html>
"""

# ==================== Kindle 展示模板 ====================
# vh = 可视区域高度（屏幕高 - 浏览器工具栏），用于垂直居中

TMPL_INFO = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Info</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; overflow:hidden; position:relative; }
.vc { display:table; width:100%; height:100%; }
.vc-cell { display:table-cell; vertical-align:middle; text-align:center; }
.time { font-size:{{ t_time }}px; font-weight:bold; margin-bottom:10px; letter-spacing:2px; }
.date { font-size:{{ t_date }}px; color:#333; margin-bottom:30px; }
.divider { width:60px; height:2px; background:#000; margin:20px auto; }
.weather-row { font-size:{{ t_body }}px; }
.weather-item { display:inline-block; text-align:center; margin:0 18px; }
.weather-label { font-size:{{ t_small }}px; color:#666; margin-bottom:4px; }
.city { position:absolute; top:{{ pad }}px; right:{{ pad }}px; font-size:{{ t_small }}px; color:#777; border:1px solid #999; padding:4px 10px; border-radius:12px; }
.footer { position:absolute; bottom:{{ pad }}px; left:0; right:0; text-align:center; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad }}px; left:{{ pad }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<div class="city">{{ city }}</div>
<div class="vc"><div class="vc-cell">
<div class="time">{{ time }}</div>
<div class="date">{{ date }}</div>
<div class="divider"></div>
<div class="weather-row">
    <div class="weather-item"><div class="weather-label">天气</div><div>{{ weather }}</div></div>
    <div class="weather-item"><div class="weather-label">温度</div><div>{{ temp }}</div></div>
</div>
</div></div>
<div class="footer">Kindle Info Panel</div>
</body></html>
"""

TMPL_BOARD = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Board</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; padding:{{ pad }}px; overflow:hidden; position:relative; }
h1 { font-size:{{ t_title }}px; margin-bottom:16px; border-bottom:2px solid #000; padding-bottom:8px; }
.section { margin-bottom:20px; }
.section-title { font-size:{{ t_sub }}px; font-weight:bold; margin-bottom:8px; color:#333; }
.todo-item, .event-item, .habit-item { font-size:{{ t_body }}px; margin-bottom:6px; line-height:1.4; }
.event-days { color:#d32f2f; font-weight:bold; }
.habit-bar { width:100%; height:8px; background:#eee; border-radius:4px; margin-top:4px; overflow:hidden; }
.habit-fill { height:100%; background:#000; border-radius:4px; }
.footer { position:absolute; bottom:{{ pad }}px; left:{{ pad }}px; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad }}px; right:{{ pad }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<h1>📋 今日看板</h1>
{% if todos %}
<div class="section">
    <div class="section-title">待办事项</div>
    {% for t in todos %}<div class="todo-item">• {{ t }}</div>{% endfor %}
</div>
{% endif %}
{% if events %}
<div class="section">
    <div class="section-title">纪念日</div>
    {% for e in events %}<div class="event-item">{{ e.name }} — <span class="event-days">{{ e.days }}</span></div>{% endfor %}
</div>
{% endif %}
{% if habits %}
<div class="section">
    <div class="section-title">习惯打卡</div>
    {% for h in habits %}
    <div class="habit-item">{{ h.name }}<div class="habit-bar"><div class="habit-fill" style="width:{{ h.pct }}%"></div></div></div>
    {% endfor %}
</div>
{% endif %}
<div class="footer">Kindle Board</div>
</body></html>
"""

TMPL_FRAME = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }};url={{ next_url }}">{% endif %}
<title>Kindle Frame</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#000; overflow:hidden; position:relative; }
.vc { display:table; width:100%; height:100%; }
.vc-cell { display:table-cell; vertical-align:middle; text-align:center; }
img { max-width:100%; max-height:{{ vh }}px; filter:contrast(1.2); }
.counter { position:absolute; bottom:20px; right:20px; font-size:14px; color:#fff;
    background:rgba(0,0,0,0.5); padding:4px 10px; border-radius:10px; font-family:Arial; }
{% if interval == 0 %}.static-badge { position:absolute; top:20px; left:20px; font-size:12px; color:#fff; background:rgba(0,0,0,0.5); padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<div class="vc"><div class="vc-cell"><img src="{{ img_url }}" alt="frame"></div></div>
<div class="counter">{{ cur }} / {{ total }}</div>
</body></html>
"""

TMPL_READING = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Reading</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; padding:{{ pad }}px; overflow:hidden; position:relative; }
h1 { font-size:{{ t_title }}px; margin-bottom:20px; border-bottom:2px solid #000; padding-bottom:8px; }
.book { margin-bottom:18px; }
.book-name { font-size:{{ t_sub }}px; font-weight:bold; margin-bottom:6px; }
.book-meta { font-size:{{ t_body }}px; color:#333; margin-bottom:4px; }
.progress-bg { width:100%; height:10px; background:#eee; border-radius:5px; overflow:hidden; }
.progress-fill { height:100%; background:#000; border-radius:5px; }
.footer { position:absolute; bottom:{{ pad }}px; left:{{ pad }}px; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad }}px; right:{{ pad }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<h1>📚 阅读进度</h1>
{% for b in books %}
<div class="book">
    <div class="book-name">{{ b.name }}</div>
    <div class="book-meta">{{ b.current }} / {{ b.total }} 页 · {{ b.pct }}%</div>
    <div class="progress-bg"><div class="progress-fill" style="width:{{ b.pct }}%"></div></div>
</div>
{% endfor %}
<div class="footer">Kindle Reading</div>
</body></html>
"""

TMPL_POMO = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Pomodoro</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; overflow:hidden; position:relative; }
.vc { display:table; width:100%; height:100%; }
.vc-cell { display:table-cell; vertical-align:middle; text-align:center; }
.task { font-size:{{ t_sub }}px; color:#555; margin:0 auto 20px; text-align:center; max-width:80%; }
.time-left { font-size:{{ t_time }}px; font-weight:bold; margin-bottom:16px; letter-spacing:2px; }
.progress-bg { width:70%; height:14px; background:#eee; border-radius:7px; overflow:hidden; margin:0 auto 10px; }
.progress-fill { height:100%; background:#000; border-radius:7px; }
.pct { font-size:{{ t_body }}px; color:#666; }
.status { font-size:{{ t_sub }}px; margin-top:20px; font-weight:bold; }
.footer { position:absolute; bottom:{{ pad }}px; left:0; right:0; text-align:center; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad }}px; right:{{ pad }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<div class="vc"><div class="vc-cell">
<div class="task">{{ task }}</div>
<div class="time-left">{{ time_left }}</div>
<div class="progress-bg"><div class="progress-fill" style="width:{{ pct }}%"></div></div>
<div class="pct">{{ pct }}%</div>
<div class="status">{{ status }}</div>
</div></div>
<div class="footer">Kindle Pomodoro</div>
</body></html>
"""

TMPL_WORDS = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Word</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; overflow:hidden; position:relative; }
.vc { display:table; width:100%; height:100%; }
.vc-cell { display:table-cell; vertical-align:middle; text-align:center; padding:0 {{ pad }}px; }
.lang-tag { position:absolute; top:{{ pad_s }}px; right:{{ pad_s }}px; font-size:{{ t_small }}px; color:#555; border:1px solid #999; padding:3px 10px; border-radius:12px; font-family:Arial; }
.book-tag { position:absolute; top:{{ pad_s }}px; left:{{ pad_s }}px; font-size:{{ t_small }}px; color:#777; font-family:Arial; }
.word { font-size:{{ t_word }}px; font-weight:bold; margin-bottom:10px; text-align:center; line-height:1.2; }
.phonetic { font-size:{{ t_sub }}px; color:#333; margin-bottom:18px; font-family:Arial; }
.divider { width:50px; height:2px; background:#000; margin:14px auto; }
.meaning { font-size:{{ t_body }}px; margin:0 auto 14px; text-align:center; line-height:1.5; }
.example { font-size:{{ t_small2 }}px; color:#333; font-style:italic; text-align:center; line-height:1.5; margin:0 auto 6px; max-width:85%; }
.example-cn { font-size:{{ t_small }}px; color:#555; text-align:center; line-height:1.5; margin:0 auto; max-width:85%; }
.progress { position:absolute; bottom:{{ pad_s }}px; left:0; right:0; text-align:center; font-size:{{ t_small }}px; color:#555; font-family:Arial; }
.footer-line { position:absolute; bottom:{{ pad_s }}px; left:{{ pad_s }}px; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad_s }}px; right:{{ pad_s }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<div class="book-tag">{{ book_name }}</div>
<div class="lang-tag">{{ lang_flag }}</div>
<div class="vc"><div class="vc-cell">
<div class="word">{{ word }}</div>
{% if show_phonetic %}<div class="phonetic">{{ phonetic }}</div>{% endif %}
<div class="divider"></div>
{% if show_meaning %}<div class="meaning">{{ meaning }}</div>{% endif %}
{% if example %}<div class="example">{{ example }}</div>{% endif %}
{% if example_cn %}<div class="example-cn">{{ example_cn }}</div>{% endif %}
</div></div>
{% if show_progress %}<div class="progress">{{ current }} / {{ total }}</div>{% endif %}
<div class="footer-line">Kindle Word</div>
</body></html>
"""


# ==================== 路由 ====================

@app.route("/")
def index():
    mode = request.args.get("mode", "info")
    valid_modes = {k for k, _, _ in MODE_DEFS}
    if mode not in valid_modes:
        mode = "info"
    lang = request.args.get("lang", "english")
    if lang not in WORD_BANK:
        lang = "english"
    return render_template_string(CONFIG_HTML,
        modes=MODE_DEFS,
        mode=mode,
        lang=lang,
        wordbank=WORD_BANK,
        books=WORD_BANK[lang]["books"])


@app.route("/generate", methods=["POST"])
def generate():
    mode = request.form.get("mode", "info")
    model_key = request.form.get("model", "pw4")
    model = MODELS.get(model_key, MODELS["pw4"])
    cfg_id = str(uuid.uuid4())[:6]

    interval = int(request.form.get("interval", 300))

    base_cfg = {
        "mode": mode,
        "model": model_key,
        "interval": interval,
        "w": model["w"],
        "h": model["h"],
    }
    # 永久链接用的紧凑配置（编码进 URL，不依赖服务器内存）
    token_cfg = {"m": mode, "md": model_key, "i": interval}

    if mode == "info":
        city = request.form.get("city", "beijing")
        base_cfg.update({"city": city})
        token_cfg.update({"c": city})

    elif mode == "board":
        todos = [t.strip() for t in request.form.get("todos", "").split("\n") if t.strip()]
        events_raw = [e.strip() for e in request.form.get("events", "").split("\n") if e.strip()]
        habits = [h.strip() for h in request.form.get("habits", "").split("\n") if h.strip()]
        base_cfg.update({
            "todos": todos,
            "events": compute_events(events_raw),
            "habits": compute_habits(habits),
        })
        token_cfg.update({"t": todos, "e": events_raw, "hb": habits})

    elif mode == "frame":
        files = request.files.getlist("photos")
        processed = []
        for f in files:
            if f and f.filename:
                uid = str(uuid.uuid4())[:8]
                ext = os.path.splitext(f.filename)[1].lower() or ".jpg"
                save_name = f"{cfg_id}_{uid}{ext}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], save_name)
                img = Image.open(f.stream)
                img = img.convert("L")
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.4)
                img.thumbnail((model["w"], model["h"]), Image.LANCZOS)
                img.save(save_path, "JPEG", quality=90)
                processed.append(save_name)
        base_cfg.update({"photos": processed, "photo_count": len(processed)})

    elif mode == "reading":
        books_raw = [b.strip() for b in request.form.get("books", "").split("\n") if b.strip()]
        base_cfg.update({"books": compute_books(books_raw)})
        token_cfg.update({"bk": books_raw})

    elif mode == "pomodoro":
        duration = int(request.form.get("duration", 25))
        task_name = request.form.get("task_name", "专注中") or "专注中"
        start_time = datetime.now().isoformat()
        base_cfg.update({
            "duration": duration,
            "task_name": task_name,
            "start_time": start_time,
        })
        token_cfg.update({"d": duration, "t": task_name, "s": start_time})

    elif mode == "words":
        lang = request.form.get("language", "english")
        book = request.form.get("book", "cet4")
        words = WORD_BANK.get(lang, {}).get("books", {}).get(book, {}).get("words", [])
        base_cfg.update({
            "language": lang,
            "book": book,
            "words": words,
            "total": len(words),
            "book_name": WORD_BANK.get(lang, {}).get("books", {}).get(book, {}).get("name", ""),
            "lang_flag": WORD_BANK.get(lang, {}).get("flag", "🇺🇸"),
            "show_phonetic": "show_phonetic" in request.form,
            "show_meaning": "show_meaning" in request.form,
            "show_progress": "show_progress" in request.form,
        })
        token_cfg.update({
            "l": lang, "b": book,
            "sp": 1 if "show_phonetic" in request.form else 0,
            "sm": 1 if "show_meaning" in request.form else 0,
            "sg": 1 if "show_progress" in request.form else 0,
        })

    USER_CONFIGS[cfg_id] = base_cfg

    show_url = f"{request.host_url}s/{cfg_id}"

    # 永久链接：配置编码进 URL，服务器重启/重新部署也不过期
    # 相框模式除外（照片文件存在服务器磁盘，重启必然丢失）
    perm_block = ""
    if mode != "frame":
        perm_url = f"{request.host_url}p/{encode_cfg(token_cfg)}"
        perm_block = f"""
            <p class="short-label">♾ 永久链接（重启也不过期，推荐 Kindle 输入这个并加书签）：</p>
            <div class="url-box short">{perm_url}</div>"""
    else:
        perm_block = """
            <p class="short-label" style="color:#b71c1c;">⚠ 相框照片存在服务器内存，服务重启后需重新上传生成</p>"""

    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>配置完成</title>
        <style>
            body {{ font-family:-apple-system,sans-serif; padding:20px; max-width:520px; margin:0 auto; background:#f5f6fa; }}
            .card {{ background:#fff; border-radius:16px; padding:24px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
            h1 {{ font-size:20px; margin-bottom:8px; }}
            .subtitle {{ color:#666; font-size:14px; margin-bottom:20px; }}
            .url-box {{ background:#f5f5f5; padding:14px; border-radius:10px; font-family:monospace; font-size:13px; word-break:break-all; border:1px dashed #999; margin:12px 0; }}
            .btn {{ display:block; width:100%; padding:14px; background:#1a1a1a; color:#fff; text-align:center; border-radius:12px; text-decoration:none; margin-top:10px; font-size:15px; }}
            .tip {{ font-size:13px; color:#555; margin-top:16px; line-height:1.7; }}
            .tip code {{ background:#f0f0f0; padding:2px 6px; border-radius:4px; font-family:monospace; }}
            .success {{ color:#4caf50; font-weight:600; margin-bottom:8px; }}
            .badge {{ display:inline-block; background:#1a1a1a; color:#fff; padding:4px 10px; border-radius:8px; font-size:12px; margin-right:6px; }}
            .short-label {{ color:#2e7d32; font-size:14px; font-weight:600; margin-top:6px; }}
            .url-box.short {{ font-size:16px; text-align:center; border:2px solid #4caf50; background:#e8f5e9; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="success">✅ 配置生成成功</div>
            <h1>你的专属 Kindle 展示链接</h1>
            <p class="subtitle">
                <span class="badge">{mode}</span>
                <span class="badge">{model['name']}</span>
                <span class="badge">刷新: {interval if interval > 0 else '静态'}</span>
            </p>
            {perm_block}
            <p class="short-label" style="color:#666; font-weight:400;">临时短链接（服务重启后失效）：</p>
            <div class="url-box">{show_url}</div>
            <a href="{show_url}" class="btn" target="_blank">点击预览效果</a>
            <div class="tip">
                <strong>Kindle 使用步骤：</strong><br>
                1. 连接 WiFi → 打开「体验版浏览器」<br>
                2. 输入上方链接（建议添加到书签）<br>
                3. 在搜索框输入 <code>~ds</code> 并按回车（禁止锁屏）<br>
                4. 插上电源，长期展示即可
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/show")
def show():
    return render_display(request.args.get("id"))


@app.route("/s/<cfg_id>")
def show_short(cfg_id):
    return render_display(cfg_id)


@app.route("/p/<token>")
def show_perm(token):
    try:
        cfg = expand_token_cfg(decode_cfg(token))
    except Exception:
        return "链接无效或已损坏", 400
    return render_cfg(cfg)


def render_display(cfg_id):
    if not cfg_id or cfg_id not in USER_CONFIGS:
        return "配置不存在", 404
    cfg = dict(USER_CONFIGS[cfg_id])
    cfg["_cfg_id"] = cfg_id
    return render_cfg(cfg)


def render_cfg(cfg):
    mode = cfg["mode"]
    m = MODELS.get(cfg.get("model", "pw4"), MODELS["pw4"])
    w, h = m["w"], m["h"]
    vh = h - m.get("chrome", 90)  # 可视区域高度 = 屏幕高 - 浏览器工具栏
    if m["w"] <= 600:
        pad = 36
    elif m["w"] <= 758:
        pad = 48
    elif m["w"] <= 1264:
        pad = 64
    else:
        pad = 96
    interval = cfg.get("interval", 300)

    if mode == "info":
        city_key = cfg.get("city", "beijing")
        try:
            tz = ZoneInfo(CITY_TZ.get(city_key, DEFAULT_TZ))
        except Exception:
            tz = None
        now = datetime.now(tz) if tz else datetime.now()
        weather = get_weather(city_key)
        return render_template_string(TMPL_INFO,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad,
            t_time=int(h*0.12), t_date=int(h*0.045), t_body=int(h*0.035), t_small=int(h*0.022),
            time=now.strftime("%H:%M"),
            date=now.strftime("%Y年%m月%d日 %a"),
            city=weather["city"],
            weather=weather["weather"],
            temp=weather["temp"])

    elif mode == "board":
        return render_template_string(TMPL_BOARD,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad,
            t_title=int(h*0.05), t_sub=int(h*0.032), t_body=int(h*0.026), t_small=int(h*0.02),
            todos=cfg.get("todos", []),
            events=cfg.get("events", []),
            habits=cfg.get("habits", []))

    elif mode == "frame":
        photos = cfg.get("photos", [])
        if not photos:
            return "没有上传图片", 400
        idx = int(request.args.get("idx", 0)) % len(photos)
        next_idx = (idx + 1) % len(photos)
        img_url = f"{request.host_url}uploads/{photos[idx]}"
        next_url = f"{request.host_url}s/{cfg.get('_cfg_id', '')}?idx={next_idx}"
        return render_template_string(TMPL_FRAME,
            interval=interval,
            w=w, h=h, vh=vh,
            img_url=img_url,
            next_url=next_url,
            cur=idx+1, total=len(photos))

    elif mode == "reading":
        return render_template_string(TMPL_READING,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad,
            t_title=int(h*0.05), t_sub=int(h*0.032), t_body=int(h*0.026), t_small=int(h*0.02),
            books=cfg.get("books", []))

    elif mode == "pomodoro":
        start = datetime.fromisoformat(cfg["start_time"])
        duration_min = cfg["duration"]
        total_sec = duration_min * 60
        elapsed = (datetime.now() - start).total_seconds()
        remaining = total_sec - elapsed

        if remaining <= 0:
            time_left = "00:00"
            pct = 100
            status = "✅ 专注完成！"
        else:
            mins, secs = divmod(int(remaining), 60)
            time_left = f"{mins:02d}:{secs:02d}"
            pct = min(100, int((elapsed / total_sec) * 100))
            status = "🔔 专注中..."

        return render_template_string(TMPL_POMO,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad,
            t_time=int(h*0.14), t_sub=int(h*0.04), t_body=int(h*0.03), t_small=int(h*0.022),
            task=cfg.get("task_name", "专注中"),
            time_left=time_left,
            pct=pct,
            status=status)

    elif mode == "words":
        words = cfg.get("words", [])
        if not words:
            return "词书为空", 400
        idx = random.randint(0, len(words) - 1)
        wdata = words[idx]
        return render_template_string(TMPL_WORDS,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad, pad_s=int(pad*0.5),
            t_word=int(h*0.09), t_sub=int(h*0.035), t_body=int(h*0.03), t_small=int(h*0.022), t_small2=int(h*0.025),
            word=wdata["word"],
            phonetic=wdata.get("phonetic", ""),
            meaning=wdata.get("meaning", ""),
            example=wdata.get("example", ""),
            example_cn=wdata.get("example_cn", ""),
            book_name=cfg.get("book_name", ""),
            lang_flag=cfg.get("lang_flag", "🇺🇸"),
            show_phonetic=cfg.get("show_phonetic", True),
            show_meaning=cfg.get("show_meaning", True),
            show_progress=cfg.get("show_progress", True),
            current=idx+1,
            total=cfg.get("total", 1))

    return "未知模式", 400


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

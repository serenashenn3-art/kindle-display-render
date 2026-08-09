#!/usr/bin/env python3
"""Process all word bank data sources and generate a single JSON for upload."""
import csv, json, os, sys, re

DATA_DIR = "/workspace/data"
ECDICT_PATH = "/workspace/data/english/ecdict.csv"
TARGET = 5000
MIN = 4000

# Book name mappings
EN_NAMES = {
    "cet4": "四级英语词汇", "cet6": "六级英语词汇", "kaoyan": "考研英语词汇",
    "ielts": "雅思核心词汇", "toefl": "托福核心词汇", "gre": "GRE词汇",
    "business": "商务英语",
}
JP_NAMES = {"n1": "JLPT N1", "n2": "JLPT N2", "n3": "JLPT N3", "n4": "JLPT N4", "n5": "JLPT N5"}

def strip_entry(d):
    return {k: v for k, v in d.items() if v}

def process_ecdict():
    """Process ECDICT CSV → English word banks by tag."""
    tag_map = {"cet4": "cet4", "cet6": "cet6", "ky": "kaoyan", "ielts": "ielts",
               "toefl": "toefl", "gre": "gre", "bec": "business"}
    books = {bk: [] for bk in tag_map.values()}
    biz_words = []
    with open(ECDICT_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tags = (row.get("tag") or "").split()
            word = (row.get("word") or "").strip()
            phonetic = (row.get("phonetic") or "").strip()
            translation = (row.get("translation") or "").strip()
            frq = 0
            try:
                frq = int(float(row.get("frq") or 0))
            except (ValueError, TypeError):
                pass
            if not word or not translation:
                continue
            p = f"/{phonetic}/" if phonetic else ""
            m = translation.replace("\n", "；").replace("\r", "").strip()
            entry = {"w": word, "p": p, "m": m, "e": "", "c": "", "_frq": frq}
            matched = False
            for tag_key, book_key in tag_map.items():
                if tag_key in tags:
                    books[book_key].append(dict(entry))
                    matched = True
            if not matched and any(kw in translation.lower() for kw in
                ["商业", "贸易", "经济", "金融", "公司", "市场", "管理", "合同", "投资", "利润"]):
                biz_words.append(dict(entry))
    if not books["business"] and biz_words:
        books["business"] = biz_words

    # Build a generic frequency pool for topping up short books
    extra_pool = []
    seen_extra = set()
    with open(ECDICT_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = (row.get("word") or "").strip()
            phonetic = (row.get("phonetic") or "").strip()
            translation = (row.get("translation") or "").strip()
            frq = 0
            try:
                frq = int(float(row.get("frq") or 0))
            except (ValueError, TypeError):
                pass
            if not word or not translation or frq <= 0:
                continue
            tags = (row.get("tag") or "").split()
            if any(t in tag_map for t in tags):
                continue
            if word in seen_extra:
                continue
            seen_extra.add(word)
            p = f"/{phonetic}/" if phonetic else ""
            m = translation.replace("\n", "；").replace("\r", "").strip()
            extra_pool.append({"w": word, "p": p, "m": m, "e": "", "c": "", "_frq": frq})
    extra_pool.sort(key=lambda x: x["_frq"], reverse=True)

    result = {}
    for bk, words in books.items():
        words.sort(key=lambda x: x["_frq"], reverse=True)
        for w in words:
            del w["_frq"]
        have = {w["w"] for w in words}
        for ex in extra_pool:
            if len(words) >= TARGET:
                break
            if ex["w"] not in have:
                e2 = dict(ex)
                del e2["_frq"]
                words.append(e2)
                have.add(ex["w"])
        result[bk] = words[:TARGET]
        print(f"  english/{bk}: {len(result[bk])} words")
    return result

def process_japanese():
    """Process ringooai JLPT CSVs + wordfreq supplement."""
    import pykakasi
    kks = pykakasi.kakasi()
    def reading(text):
        try:
            return "".join(it.get("kana", "") for it in kks.convert(text))
        except Exception:
            return ""

    raw = {}
    for lv in ["n5", "n4", "n3", "n2", "n1"]:
        path = os.path.join(DATA_DIR, "japanese", f"{lv}.csv")
        words = []
        seen = set()
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith("#") or row[0].strip().lower() == "expression":
                    continue
                if len(row) < 3:
                    continue
                w = row[0].strip()
                r = row[1].strip()
                m = row[2].strip()
                if not w or w in seen:
                    continue
                seen.add(w)
                words.append({"w": w, "p": r if r else reading(w), "m": m, "e": "", "c": ""})
        raw[lv] = words
        print(f"  japanese/{lv} base: {len(words)} words")

    # Cumulative merge for higher levels
    order = ["n5", "n4", "n3", "n2", "n1"]
    cum = {}
    for i, lv in enumerate(order):
        merged = []
        seen = set()
        for lower in order[: i + 1]:
            for w in raw[lower]:
                wk = w.get("w", "")
                if wk and wk not in seen:
                    seen.add(wk)
                    merged.append(dict(w))
        cum[lv] = merged

    # Supplement pool from wordfreq
    from wordfreq import top_n_list
    pool = top_n_list("ja", 20000)
    sup = []
    seen_global = set()
    for w in pool:
        if len(w) < 2:
            continue
        if w in seen_global:
            continue
        seen_global.add(w)
        sup.append({"w": w, "p": reading(w), "m": "", "e": "", "c": ""})

    result = {}
    for lv in order:
        words = cum[lv]
        have = {w.get("w", "") for w in words}
        for s in sup:
            if len(words) >= TARGET:
                break
            if s["w"] not in have:
                words.append(dict(s))
                have.add(s["w"])
        result[lv] = words[:TARGET]
        print(f"  japanese/{lv}: {len(result[lv])} words")
    return result

def process_idioms():
    """Process chinese-xinhua idiom.json → Chinese idiom word bank."""
    path = os.path.join(DATA_DIR, "chinese", "idiom.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    words = []
    for entry in data[:TARGET]:
        word = entry.get("word") or ""
        pinyin = entry.get("pinyin") or ""
        explanation = entry.get("explanation") or ""
        example = entry.get("example") or ""
        if not word or not explanation:
            continue
        m = explanation[:300] if len(explanation) > 300 else explanation
        words.append({"w": word, "p": pinyin, "m": m, "e": example, "c": ""})
    print(f"  chinese/chengyu: {len(words)} words")
    return words

def process_gushi():
    """Process Tang poetry JSON → famous lines."""
    from pypinyin import pinyin, Style
    path = os.path.join(DATA_DIR, "chinese", "tang_01.json")
    with open(path, encoding="utf-8") as f:
        poems = json.load(f)
    words = []
    seen = set()
    for pm in poems:
        if len(words) >= TARGET:
            break
        content = (pm.get("content") or "").strip()
        title = (pm.get("title") or "").strip()
        author = (pm.get("author") or "").strip()
        if not content or not title:
            continue
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        if not lines:
            continue
        line = lines[0]
        for sep in ["，", "。", "！", "？", "、"]:
            if sep in line:
                line = line.split(sep)[0]
                break
        if not (4 <= len(line) <= 14):
            continue
        if line in seen:
            continue
        try:
            py = " ".join(p[0] for p in pinyin(line, style=Style.TONE))
        except Exception:
            py = ""
        seen.add(line)
        meaning = f"《{title}》· {author}" if author else f"《{title}》"
        ex = content.replace("\n", " ")
        words.append({"w": line, "p": py, "m": meaning, "e": ex, "c": ""})
    print(f"  chinese/gushi: {len(words)} words")
    return words

def process_frequency_list(code, limit=TARGET):
    """Process a frequency list (word freq per line) → word bank entries."""
    path = os.path.join(DATA_DIR, "freq", f"{code}_50k.txt")
    words = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            word = parts[0]
            if not word or len(word) < 2:
                continue
            words.append({"w": word, "p": "", "m": "", "e": "", "c": ""})
            if len(words) >= limit:
                break
    return words

def process_russian():
    """Process OpenRussian CSV files (tab-separated) → Russian word bank."""
    result = []
    seen = set()
    for fname in ["nouns.csv", "adjectives.csv", "verbs.csv", "others.csv"]:
        path = os.path.join(DATA_DIR, "russian", fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                bare = (row.get("bare") or "").strip()
                accented = (row.get("accented") or "").strip()
                trans = (row.get("translations_en") or "").strip()
                gender = (row.get("gender") or "").strip()
                if not bare or bare in seen:
                    continue
                seen.add(bare)
                m = trans
                if gender:
                    m = f"{gender}. {trans}" if trans else gender
                result.append({"w": bare, "p": accented, "m": m, "e": "", "c": ""})
                if len(result) >= TARGET:
                    break
        if len(result) >= TARGET:
            break
    print(f"  russian/basic_ru: {len(result)} words")
    return result

def process_korean():
    """Process Korean vocabulary TSV → Korean word bank."""
    path = os.path.join(DATA_DIR, "korean", "results.tsv")
    result = []
    seen = set()
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            ko = (row.get("word") or "").strip()
            pos = (row.get("part_of_speech") or "").strip()
            han = (row.get("hanja") or "").strip()
            expl = (row.get("explanation") or "").strip()
            if not ko or len(ko) < 2 or ko in seen:
                continue
            seen.add(ko)
            m = expl
            if pos and expl:
                m = f"{pos}. {expl}"
            elif pos:
                m = pos
            result.append({"w": ko, "p": han, "m": m, "e": "", "c": ""})
            if len(result) >= TARGET:
                break
    print(f"  korean/topik1: {len(result)} words")
    return result

def process_cantonese():
    """Process rime-cantonese word.csv → Cantonese word bank."""
    path = os.path.join(DATA_DIR, "cantonese", "word.csv")
    result = []
    seen = set()
    def is_cjk(ch):
        o = ord(ch)
        return (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF)
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 2:
                continue
            word = row[0].strip()
            jyut = row[1].strip()
            if not word or not jyut or word in seen:
                continue
            if not (2 <= len(word) <= 4):
                continue
            if not all(is_cjk(c) for c in word):
                continue
            seen.add(word)
            result.append({"w": word, "p": jyut, "m": "", "e": "", "c": ""})
            if len(result) >= TARGET:
                break
    print(f"  cantonese/basic_yue: {len(result)} words")
    return result

def get_existing_book(lang_key, book_key):
    """Get existing WORD_BANK entries for a language/book."""
    import ast
    with open("/workspace/app.py", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'WORD_BANK':
                    wb = ast.literal_eval(node.value)
                    words = wb.get(lang_key, {}).get("books", {}).get(book_key, {}).get("words", [])
                    converted = []
                    for w in words:
                        converted.append({
                            "w": w.get("word", ""),
                            "p": w.get("phonetic", ""),
                            "m": w.get("meaning", ""),
                            "e": w.get("example", ""),
                            "c": w.get("example_cn", "")
                        })
                    return converted
    return []

def merge_with_existing(lang_key, book_key, freq_words):
    """Merge frequency list words with existing WORD_BANK entries."""
    existing = get_existing_book(lang_key, book_key)
    existing_set = {w["w"] for w in existing}
    unique = [w for w in freq_words if w["w"] not in existing_set]
    return existing + unique

def main():
    bank = {}
    # English
    print("Processing ECDICT (English)...")
    en_books = process_ecdict()
    bank["english"] = {bk: {"name": EN_NAMES.get(bk, bk), "words": words}
                       for bk, words in en_books.items()}
    # Japanese
    print("Processing JLPT CSVs (Japanese)...")
    jp_books = process_japanese()
    bank["japanese"] = {lv: {"name": JP_NAMES.get(lv, lv), "words": words}
                        for lv, words in jp_books.items()}
    # Chinese idioms and poetry
    print("Processing chinese-xinhua (idioms)...")
    idiom_words = process_idioms()
    print("Processing Tang poetry (gushi)...")
    gushi_words = process_gushi()
    bank["chinese"] = {
        "chengyu": {"name": "成语词典", "words": idiom_words},
        "gushi": {"name": "古诗词名句", "words": gushi_words},
    }
    # Russian
    print("Processing OpenRussian...")
    ru_words = process_russian()
    if ru_words:
        bank["russian"] = {"basic_ru": {"name": "俄语入门", "words": ru_words}}
    # Korean
    print("Processing Korean vocabulary...")
    ko_words = process_korean()
    if ko_words:
        bank["korean"] = {"topik1": {"name": "TOPIK I", "words": ko_words}}
    # Cantonese
    print("Processing Cantonese...")
    yue_words = process_cantonese()
    if yue_words:
        bank["cantonese"] = {"basic_yue": {"name": "粤语入门", "words": yue_words}}
    # Frequency lists for European languages (merge with existing translated entries)
    freq_map = {
        "french": ("fr", [("tef", "TEF/TCF核心词"), ("basic_fr", "法语入门")]),
        "german": ("de", [("testdaf", "德福核心词"), ("basic_de", "德语入门")]),
        "spanish": ("es", [("dele", "DELE核心词"), ("basic_es", "西班牙语入门")]),
        "italian": ("it", [("basic_it", "意大利语入门")]),
        "portuguese": ("pt", [("basic_pt", "葡萄牙语入门")]),
    }
    for lang_name, (code, book_list) in freq_map.items():
        print(f"Processing frequency list ({lang_name})...")
        freq_words = process_frequency_list(code, limit=TARGET * len(book_list) + 500)
        if not freq_words:
            continue
        lang_books = {}
        for i, (book_key, book_name) in enumerate(book_list):
            start = i * TARGET
            end = start + TARGET
            merged = merge_with_existing(lang_name, book_key, freq_words[start:end])
            lang_books[book_key] = {"name": book_name, "words": merged[:TARGET]}
            print(f"  {lang_name}/{book_key}: {len(lang_books[book_key]['words'])} words")
        bank[lang_name] = lang_books

    # Strip empty fields to reduce payload size
    for lang, lpack in bank.items():
        for bk, bpack in lpack.items():
            bpack["words"] = [strip_entry(w) for w in bpack.get("words", [])]

    # Summary
    total = 0
    print("\n=== Summary ===")
    low = []
    for lang, lpack in bank.items():
        for bk, bpack in lpack.items():
            cnt = len(bpack["words"])
            total += cnt
            flag = " OK" if cnt >= MIN else " LOW"
            if cnt < MIN:
                low.append(f"{lang}/{bk}:{cnt}")
            print(f"  {lang}/{bk}: {cnt}{flag}")
    print(f"Total: {total} words")
    if low:
        print(f"LOW books: {low}")
    # Save
    out_path = "/workspace/wordbank_merged.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"\nSaved to {out_path} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()

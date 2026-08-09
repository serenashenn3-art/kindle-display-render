#!/usr/bin/env python3
"""Verify that the uploaded word-bank chunks can be downloaded and decoded."""
import base64, gzip, json, sys, urllib.request, urllib.error

SOURCES_PATH = "/workspace/wordbank_sources.txt"
MIN_PER_BOOK = 4000


def main():
    with open(SOURCES_PATH, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    print(f"Fetching {len(lines)} source line(s)...")
    blob_parts = []
    for i, line in enumerate(lines, start=1):
        parts = line.split()
        if len(parts) != 2:
            print(f"  skip malformed line {i}: {line}")
            continue
        kind, url = parts
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    text = resp.read().decode("utf-8")
                blob_parts.append((kind, text))
                print(f"  [{i}/{len(lines)}] {url} -> {len(text)} chars")
                break
            except Exception as exc:
                print(f"  [{i}/{len(lines)}] attempt {attempt} failed: {exc}")
                if attempt == 3:
                    sys.exit(1)

    json_blob = ""
    b64_blob = ""
    for kind, text in blob_parts:
        if kind == "json":
            json_blob += text
        elif kind == "b64":
            b64_blob += text

    if b64_blob:
        print("\nDecoding b64+gzip payload...")
        raw = gzip.decompress(base64.b64decode(b64_blob)).decode("utf-8")
        data = json.loads(raw)
    elif json_blob:
        print("\nParsing JSON payload...")
        data = json.loads(json_blob)
    else:
        print("No payload found", file=sys.stderr)
        sys.exit(1)

    print("\n=== Verification ===")
    total = 0
    low = []
    for lang, lpack in data.items():
        for bk, bpack in lpack.items():
            cnt = len(bpack.get("words", []))
            total += cnt
            flag = "OK" if cnt >= MIN_PER_BOOK else "LOW"
            print(f"  {lang}/{bk}: {cnt} {flag}")
            if cnt < MIN_PER_BOOK:
                low.append(f"{lang}/{bk}:{cnt}")
    print(f"Total: {total} words")
    if low:
        print(f"LOW books: {low}", file=sys.stderr)
        sys.exit(1)
    print("All books meet the minimum requirement.")


if __name__ == "__main__":
    main()

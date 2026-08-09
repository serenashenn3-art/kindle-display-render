#!/usr/bin/env python3
"""Compress the merged word bank and upload it to paste.rs in base64 chunks."""
import base64, gzip, json, os, subprocess, sys, time

JSON_PATH = "/workspace/wordbank_merged.json"
SOURCES_PATH = "/workspace/wordbank_sources.txt"
CHUNK_SIZE = 76800  # ~75 KiB, well under paste.rs ~80 KiB limit
MAX_ATTEMPTS = 5


def upload_chunk(text: str, idx: int, total: int) -> str:
    """Upload a single chunk to paste.rs with retries."""
    url = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "60", "--data-binary", "@-", "https://paste.rs/"],
                input=text.encode("ascii"),
                capture_output=True,
                timeout=90,
            )
            cand = result.stdout.decode("ascii").strip()
            if cand.startswith("https://"):
                url = cand
                print(f"  chunk {idx}/{total}: OK {url}")
                break
            err = result.stderr.decode("ascii", errors="ignore").strip() or cand[:120]
            print(f"  chunk {idx}/{total} attempt {attempt} failed: {err}")
        except Exception as exc:
            print(f"  chunk {idx}/{total} attempt {attempt} error: {exc}")
        time.sleep(3)
    if not url:
        raise RuntimeError(f"Failed to upload chunk {idx}/{total}")
    return url


def main():
    if not os.path.exists(JSON_PATH):
        print(f"Missing {JSON_PATH}", file=sys.stderr)
        sys.exit(1)

    print("Compressing word bank...")
    with open(JSON_PATH, "rb") as f:
        raw = f.read()
    compressed = gzip.compress(raw, compresslevel=9)
    b64 = base64.b64encode(compressed).decode("ascii")
    print(f"  raw={len(raw):,} bytes, gzip={len(compressed):,} bytes, b64={len(b64):,} bytes")

    chunks = [b64[i : i + CHUNK_SIZE] for i in range(0, len(b64), CHUNK_SIZE)]
    print(f"  uploading {len(chunks)} chunk(s) (~{CHUNK_SIZE} bytes each)")

    urls = []
    for i, chunk in enumerate(chunks, start=1):
        try:
            url = upload_chunk(chunk, i, len(chunks))
            urls.append(url)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            print("Saving partial source list before exiting.")
            with open(SOURCES_PATH, "w", encoding="utf-8") as f:
                for u in urls:
                    f.write(f"b64 {u}\n")
            sys.exit(1)

    with open(SOURCES_PATH, "w", encoding="utf-8") as f:
        for u in urls:
            f.write(f"b64 {u}\n")

    print(f"\nDone. Wrote {len(urls)} URL(s) to {SOURCES_PATH}")


if __name__ == "__main__":
    main()

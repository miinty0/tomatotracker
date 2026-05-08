#!/usr/bin/env python3
import json, re, os, sys
import argparse
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

RETRY_FILE = "retry_list.json"
MAX_RETRIES = 3
RETRY_DELAYS = [5, 10, 20]


def fetch_with_retry(url: str, book_id: str) -> requests.Response | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = SESSION.get(url, timeout=15)
            return resp
        except Exception as e:
            wait = RETRY_DELAYS[attempt]
            print(f"  [fetch] attempt {attempt+1}/{MAX_RETRIES} failed for {book_id}: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                print(f"  [fetch] retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
    return None


def scrape_fanqie(book_id: str) -> dict | None:
    url = f"https://fanqienovel.com/page/{book_id}"

    for attempt in range(MAX_RETRIES):
        result = {"current_chapters": None, "status": None, "last_updated": None}

        resp = fetch_with_retry(url, book_id)
        if resp is None:
            # Network-level failure after fetch retries 
            print(f"  [fanqie] SKIP {book_id}: all retries failed, will retry next run", file=sys.stderr)
            return None

        try:
            if resp.status_code == 404:
                print(f"  [fanqie] {book_id}: book removed/hidden (404)")
                result["status"] = "已删除"
                return result
            resp.raise_for_status()

            # ── Primary: extract from __INITIAL_STATE__ JSON embedded in page ──
            raw = resp.text

            book_id_val = re.search(r'"bookId"\s*:\s*"(\d*)"', raw)
            book_name_val = re.search(r'"bookName"\s*:\s*"([^"]*)"', raw)

            if book_id_val is not None:
                # INITIAL_STATE is present — check if book is removed/hidden
                if not book_id_val.group(1) or not (book_name_val and book_name_val.group(1)):
                    print(f"  [fanqie] {book_id}: removed (empty page state)")
                    result["status"] = "已删除"
                    return result

                # creationStatus: 0 = 已完结, 1 = 连载中
                s_match = re.search(r'"creationStatus"\s*:\s*(\d+)', raw)
                if s_match:
                    s = int(s_match.group(1))
                    result["status"] = "连载中" if s == 1 else "已完结" if s == 0 else None

                # last_updated from lastPublishTime (unix timestamp)
                ts_match = re.search(r'"lastPublishTime"\s*:\s*"(\d+)"', raw)
                if ts_match:
                    result["last_updated"] = datetime.fromtimestamp(
                        int(ts_match.group(1)), tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M")

                # chapter count
                ct_match = re.search(r'"chapterTotal"\s*:\s*(\d+)', raw)
                if ct_match:
                    result["current_chapters"] = int(ct_match.group(1))

            # ── Fallback: parse HTML if JSON missing any field ──
            if any(v is None for v in result.values()):
                soup = BeautifulSoup(resp.text, "html.parser")

                # Detect removed via title tag
                title = soup.find("title")
                if title and title.get_text(strip=True).startswith("小说,番茄小说网"):
                    print(f"  [fanqie] {book_id}: removed (title redirect)")
                    result["status"] = "已删除"
                    return result

                # Detect removed via no-content div (book hidden/restricted, bookId missing from state)
                if soup.find("div", class_="no-content"):
                    print(f"  [fanqie] {book_id}: removed (no-content page)")
                    result["status"] = "已删除"
                    return result

                if result["status"] is None:
                    label_div = soup.find("div", class_="info-label")
                    if label_div:
                        text = label_div.get_text(separator=" ", strip=True)
                        if "连载中" in text:
                            result["status"] = "连载中"
                        elif "已完结" in text:
                            result["status"] = "已完结"

                if result["last_updated"] is None:
                    last_div = soup.find("div", class_="info-last")
                    if last_div:
                        time_span = last_div.find("span", class_="info-last-time")
                        if time_span:
                            result["last_updated"] = time_span.get_text(strip=True)

                if result["current_chapters"] is None:
                    dir_header = soup.find("div", class_="page-directory-header")
                    if dir_header:
                        h3 = dir_header.find("h3")
                        if h3:
                            match = re.search(r"(\d+)\s*章", h3.get_text(strip=True))
                            if match:
                                result["current_chapters"] = int(match.group(1))

            # ── Bot block: all values still None → retry ──
            if all(v is None for v in result.values()):
                wait = RETRY_DELAYS[attempt]
                if attempt < MAX_RETRIES - 1:
                    print(f"  [fanqie] {book_id}: bot block on attempt {attempt+1}/{MAX_RETRIES}, "
                          f"retrying in {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                else:
                    print(f"  [fanqie] {book_id}: bot block on attempt {attempt+1}/{MAX_RETRIES}, "
                          f"giving up → retry next run", file=sys.stderr)
                continue  # next attempt

            # Got data — success
            print(f"  [fanqie] {book_id}: {result['current_chapters']}章, {result['status']}, {result['last_updated']}")
            return result

        except Exception as e:
            print(f"  [fanqie] ERROR {book_id}: {e}", file=sys.stderr)
            return None

    # Exhausted all attempts due to bot block
    return None


def scrape_wiki(wiki_id: str) -> dict:
    encoded_id = wiki_id.replace("~", "%7E")
    url = f"https://wikicv.net/truyen/{encoded_id}"
    result = {"vi_title": None}

    resp = fetch_with_retry(url, wiki_id)
    if resp is None:
        print(f"  [wiki] SKIP {wiki_id}: all retries failed", file=sys.stderr)
        return result

    try:
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cover_info = soup.find("div", class_="cover-info")
        if cover_info:
            h2 = cover_info.find("h2")
            if h2:
                result["vi_title"] = h2.get_text(strip=True)
        print(f"  [wiki] {wiki_id}: {result['vi_title']}")
    except Exception as e:
        print(f"  [wiki] ERROR {wiki_id}: {e}", file=sys.stderr)
    return result


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def apply_fanqie(book: dict, fq: dict, exclude: set = None):
    """Merge scraped fanqie data into a book dict.
    - exclude: set of keys to skip entirely (e.g. {'current_chapters'} for uploading list).
    - 'Tạm dừng' status is always preserved regardless of what the site returns."""
    updates = {k: v for k, v in fq.items() if not exclude or k not in exclude}
    if book.get("status") == "Tạm dừng":
        updates.pop("status", None)
    book.update(updates)


def scrape_and_apply(bid: str, book: dict, in_uploading: bool, mode: str, failed_ids: list):
    """Scrape one book and apply result. Appends to failed_ids if scrape fails."""
    PAUSED_EXCLUDE = {"status"}
    fq = scrape_fanqie(bid)
    if fq is None:
        failed_ids.append(bid)
        return
    if in_uploading:
        exclude = {"current_chapters"} | (PAUSED_EXCLUDE if mode == "paused" else set())
        apply_fanqie(book, fq, exclude=exclude)
        book["fanqie_chapters"] = fq.get("current_chapters")
        if book.get("wiki_id") and not book.get("vi_title"):
            wiki = scrape_wiki(book["wiki_id"])
            book.update(wiki)
            time.sleep(1.0)
    else:
        apply_fanqie(book, fq, exclude=PAUSED_EXCLUDE if mode == "paused" else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['auto', 'completed', 'paused'], default='auto',
                        help='auto: scrape ongoing only; completed: scrape completed only; paused: update chapter count + last_updated for Tạm dừng books only')
    args = parser.parse_args()

    print(f"=== Fanqie Tracker Scraper [{args.mode}] — {datetime.now().isoformat()} ===")
    waiting = load_json("waiting_list.json")
    uploading = load_json("uploading_list.json")

    retry_ids = set(load_json(RETRY_FILE))
    if retry_ids:
        print(f"\n[Retry Queue] {len(retry_ids)} books from previous failed run: {retry_ids}")

    failed_ids = []

    def should_scrape(book):
        s = (book.get("status") or "").strip()
        if args.mode == "completed":
            if s != "已完结":
                return False
            last_updated = book.get("last_updated")
            if last_updated:
                try:
                    lu_dt = datetime.strptime(last_updated[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    age_days = (datetime.now(tz=timezone.utc) - lu_dt).days
                    if age_days > 365:
                        print(f"  [skip] {book.get('fanqie_id','?')}: last_updated {last_updated[:10]} is {age_days}d ago (>12 months)")
                        return False
                except Exception:
                    pass
            return True
        elif args.mode == "paused":
            return s == "Tạm dừng"
        else:  # auto
            return s not in ("已完结", "Tạm dừng")

    # Build lookup maps for retry pass
    waiting_map  = {b["fanqie_id"]: b for b in waiting}
    uploading_map = {b["fanqie_id"]: b for b in uploading}

    # ── RETRY PASS: process previously failed books first ──
    already_scraped = set()
    if retry_ids:
        print(f"\n[Retry Pass] Processing {len(retry_ids)} previously failed books...")
        for bid in list(retry_ids):
            book = waiting_map.get(bid) or uploading_map.get(bid)
            if book is None:
                print(f"  [retry] {bid}: not found in any list, dropping")
                already_scraped.add(bid)
                continue
            scrape_and_apply(bid, book, bid in uploading_map, args.mode, failed_ids)
            already_scraped.add(bid)
            time.sleep(1.5)

    # ── WAITING LIST ──
    print(f"\n[Waiting List] {len(waiting)} books")
    for book in waiting:
        bid = book["fanqie_id"]
        if bid in already_scraped:
            continue
        if not should_scrape(book):
            continue
        scrape_and_apply(bid, book, False, args.mode, failed_ids)
        time.sleep(1.5)

    save_json("waiting_list.json", waiting)
    print(f"  Saved waiting_list.json")

    # ── UPLOADING LIST ──
    print(f"\n[Uploading List] {len(uploading)} books")
    for book in uploading:
        bid = book["fanqie_id"]
        if bid in already_scraped:
            continue
        if not should_scrape(book):
            continue
        scrape_and_apply(bid, book, True, args.mode, failed_ids)
        time.sleep(1.5)

    save_json("uploading_list.json", uploading)
    print(f"  Saved uploading_list.json")

    if failed_ids:
        print(f"\n[Retry Queue] {len(failed_ids)} books failed, saving for next run: {failed_ids}")
    save_json(RETRY_FILE, failed_ids)

    print(f"\n=== Done ===")

if __name__ == "__main__":
    main()

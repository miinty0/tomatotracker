#!/usr/bin/env python3
import json, re, os, sys
import requests
from datetime import datetime
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
    result = {"current_chapters": None, "status": None, "last_updated": None}

    resp = fetch_with_retry(url, book_id)
    if resp is None:
        print(f"  [fanqie] SKIP {book_id}: all retries failed, will retry next run", file=sys.stderr)
        return None  

    try:
        if resp.status_code == 404:
            print(f"  [fanqie] {book_id}: book removed/hidden (404)")
            result["status"] = "已删除"
            return result
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Detect status
        title = soup.find("title")
        if title and title.get_text(strip=True).startswith("小说,番茄小说网"):
            print(f"  [fanqie] {book_id}: removed")
            result["status"] = "已删除"
            return result

        label_div = soup.find("div", class_="info-label")
        if label_div:
            span = label_div.find("span")
            if span:
                status_text = span.get_text(strip=True)
                result["status"] = "连载中" if "连载中" in status_text else "已完结" if "已完结" in status_text else status_text

        last_div = soup.find("div", class_="info-last")
        if last_div:
            time_span = last_div.find("span", class_="info-last-time")
            if time_span:
                result["last_updated"] = time_span.get_text(strip=True)

        dir_header = soup.find("div", class_="page-directory-header")
        if dir_header:
            h3 = dir_header.find("h3")
            if h3:
                match = re.search(r"(\d+)章", h3.get_text())
                if match:
                    result["current_chapters"] = int(match.group(1))

        print(f"  [fanqie] {book_id}: {result['current_chapters']}章, {result['status']}, {result['last_updated']}")
    except Exception as e:
        print(f"  [fanqie] ERROR {book_id}: {e}", file=sys.stderr)
    return result


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


def main():
    print(f"=== Fanqie Tracker Scraper — {datetime.now().isoformat()} ===")
    waiting = load_json("waiting_list.json")
    uploading = load_json("uploading_list.json")

    # Load retry list from previous run
    retry_ids = set(load_json(RETRY_FILE))
    if retry_ids:
        print(f"\n[Retry Queue] {len(retry_ids)} books from previous failed run: {retry_ids}")

    failed_ids = []  

    print(f"\n[Waiting List] {len(waiting)} books")
    for book in waiting:
        bid = book["fanqie_id"]
        fq = scrape_fanqie(bid)
        if fq is None:
            failed_ids.append(bid)  
        else:
            book.update(fq)
            if bid in retry_ids:
                retry_ids.discard(bid)  
        time.sleep(1.5)

    save_json("waiting_list.json", waiting)
    print(f"  Saved waiting_list.json")

    print(f"\n[Uploading List] {len(uploading)} books")
    for book in uploading:
        bid = book["fanqie_id"]
        fq = scrape_fanqie(bid)
        if fq is None:
            failed_ids.append(bid)  
        else:
            book.update({k: v for k, v in fq.items() if k != "current_chapters"})
            book["fanqie_chapters"] = fq.get("current_chapters")
            if bid in retry_ids:
                retry_ids.discard(bid)
        time.sleep(1.5)

        if fq is not None and book.get("wiki_id") and not book.get("vi_title"):
            wiki = scrape_wiki(book["wiki_id"])
            book.update(wiki)
            time.sleep(1.0)

    save_json("uploading_list.json", uploading)
    print(f"  Saved uploading_list.json")

    # Save failed books for next run
    if failed_ids:
        print(f"\n[Retry Queue] {len(failed_ids)} books failed, saving for next run: {failed_ids}")
    save_json(RETRY_FILE, failed_ids)

    print(f"\n=== Done ===")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Novel Tracker - Daily Scraper
Scrapes websites to update waiting_list.json and uploading_list.json
"""

import json
import re
import time
import os
import sys
import requests
from datetime import datetime
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def scrape_fanqie(book_id: str) -> dict:
    """Scrape fanqienovel.com/page/{book_id}"""
    url = f"https://fanqienovel.com/page/{book_id}"
    result = {"current_chapters": None, "status": None, "last_updated": None}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Status: 连载中 or 已完结
        label_div = soup.find("div", class_="info-label")
        if label_div:
            span = label_div.find("span")
            if span:
                status_text = span.get_text(strip=True)
                if "连载中" in status_text:
                    result["status"] = "连载中"
                elif "已完结" in status_text:
                    result["status"] = "已完结"
                else:
                    result["status"] = status_text

        # Last updated
        last_div = soup.find("div", class_="info-last")
        if last_div:
            time_span = last_div.find("span", class_="info-last-time")
            if time_span:
                result["last_updated"] = time_span.get_text(strip=True)

        # Chapter count from directory header:
        dir_header = soup.find("div", class_="page-directory-header")
        if dir_header:
            h3 = dir_header.find("h3")
            if h3:
                text = h3.get_text()
                match = re.search(r"(\d+)章", text)
                if match:
                    result["current_chapters"] = int(match.group(1))

        print(f"  [fanqie] {book_id}: {result['current_chapters']}章, {result['status']}, {result['last_updated']}")
    except Exception as e:
        print(f"  [fanqie] ERROR {book_id}: {e}", file=sys.stderr)
    return result


def scrape_wiki(wiki_id: str) -> dict:
    """Scrape for Vietnamese title"""
    # Handle ~ encoding
    encoded_id = wiki_id.replace("~", "%7E")
    url = f"https://wikicv.net/truyen/{encoded_id}"
    result = {"vi_title": None}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title is in: <div class="cover-info"> > <div> > <h2>
        cover_info = soup.find("div", class_="cover-info")
        if cover_info:
            h2 = cover_info.find("h2")
            if h2:
                result["vi_title"] = h2.get_text(strip=True)

        print(f"  [wiki] {wiki_id}: {result['vi_title']}")
    except Exception as e:
        print(f"  [wiki] ERROR {wiki_id}: {e}", file=sys.stderr)
    return result


def load_json(path: str) -> list:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path: str, data: list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print(f"=== Fanqie Tracker Scraper — {datetime.now().isoformat()} ===")

    waiting = load_json("waiting_list.json")
    uploading = load_json("uploading_list.json")

    # --- Update waiting list ---
    print(f"\n[Waiting List] {len(waiting)} books")
    for book in waiting:
        fq = scrape_fanqie(book["fanqie_id"])
        book.update(fq)
        time.sleep(1.5)  # polite delay

    save_json("waiting_list.json", waiting)
    print(f"  Saved waiting_list.json")

    # --- Update uploading list ---
    print(f"\n[Uploading List] {len(uploading)} books")
    for book in uploading:
        fq = scrape_fanqie(book["fanqie_id"])
        book.update({k: v for k, v in fq.items() if k != "current_chapters"})
        book["fanqie_chapters"] = fq["current_chapters"]
        time.sleep(1.5)

        # Scrape wiki title if we have wiki_id but no title
        if book.get("wiki_id") and not book.get("vi_title"):
            wiki = scrape_wiki(book["wiki_id"])
            book.update(wiki)
            time.sleep(1.0)

    save_json("uploading_list.json", uploading)
    print(f"  Saved uploading_list.json")

    print(f"\n=== Done ===")


if __name__ == "__main__":
    main()

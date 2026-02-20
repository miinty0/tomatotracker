#!/usr/bin/env python3
"""
Process GitHub Issues for fanqie tracker.

Supported issue commands (in issue title):
  ADD_WAITING
  ADD_UPLOADING
  UPDATE_CHAPTERS
  MOVE_TO_UPLOADING
  DELETE_WAITING
  DELETE_UPLOADING

Body format depends on command — see README.
"""

import json
import os
import sys
import re

ISSUE_TITLE = os.environ.get("ISSUE_TITLE", "").strip()
ISSUE_BODY = os.environ.get("ISSUE_BODY", "").strip()
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "?")


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_lines(body):
    return [l.strip() for l in body.splitlines() if l.strip() and not l.startswith("#")]


def main():
    print(f"Issue #{ISSUE_NUMBER}: {ISSUE_TITLE}")
    cmd = ISSUE_TITLE.upper().replace(" ", "_")

    waiting = load_json("waiting_list.json")
    uploading = load_json("uploading_list.json")

    lines = parse_lines(ISSUE_BODY)

    if "ADD_WAITING" in cmd:
        # Format: vi_title | desired_chapters | fanqie_id
        added = 0
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                print(f"  SKIP bad line: {line}", file=sys.stderr)
                continue
            vi_title, desired_str, fanqie_id = parts[0], parts[1], parts[2]
            try:
                desired = int(desired_str)
            except ValueError:
                print(f"  SKIP invalid chapters: {line}", file=sys.stderr)
                continue
            if any(b["fanqie_id"] == fanqie_id for b in waiting):
                print(f"  SKIP duplicate: {fanqie_id}")
                continue
            waiting.append({
                "vi_title": vi_title,
                "desired_chapters": desired,
                "fanqie_id": fanqie_id,
                "current_chapters": None,
                "status": None,
                "last_updated": None
            })
            added += 1
            print(f"  + Added to waiting: {fanqie_id} ({vi_title})")
        save_json("waiting_list.json", waiting)
        print(f"ADD_WAITING: {added} added")

    elif "ADD_UPLOADING" in cmd:
        # Format: wiki_id | uploaded_chapters | fanqie_id
        added = 0
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                print(f"  SKIP bad line: {line}", file=sys.stderr)
                continue
            wiki_id, ch_str, fanqie_id = parts[0], parts[1], parts[2]
            try:
                uploaded = int(ch_str)
            except ValueError:
                print(f"  SKIP invalid chapters: {line}", file=sys.stderr)
                continue
            if any(b["fanqie_id"] == fanqie_id for b in uploading):
                print(f"  SKIP duplicate: {fanqie_id}")
                continue
            uploading.append({
                "vi_title": None,
                "wiki_id": wiki_id,
                "fanqie_id": fanqie_id,
                "uploaded_chapters": uploaded,
                "fanqie_chapters": None,
                "status": None,
                "last_updated": None
            })
            added += 1
            print(f"  + Added to uploading: {fanqie_id}")
        save_json("uploading_list.json", uploading)
        print(f"ADD_UPLOADING: {added} added")

    elif "UPDATE_CHAPTERS" in cmd:
        # Format: fanqie_id | uploaded_chapters
        updated = 0
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue
            fanqie_id, ch_str = parts[0], parts[1]
            try:
                uploaded = int(ch_str)
            except ValueError:
                continue
            for book in uploading:
                if book["fanqie_id"] == fanqie_id:
                    book["uploaded_chapters"] = uploaded
                    updated += 1
                    print(f"  ~ Updated {fanqie_id} -> ch {uploaded}")
        save_json("uploading_list.json", uploading)
        print(f"UPDATE_CHAPTERS: {updated} updated")

    elif "MOVE_TO_UPLOADING" in cmd:
        # Format: fanqie_id | wiki_id (wiki_id optional)
        moved = 0
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            fanqie_id = parts[0]
            wiki_id = parts[1] if len(parts) > 1 else None
            book = next((b for b in waiting if b["fanqie_id"] == fanqie_id), None)
            if not book:
                print(f"  SKIP not in waiting: {fanqie_id}", file=sys.stderr)
                continue
            if any(b["fanqie_id"] == fanqie_id for b in uploading):
                print(f"  SKIP already in uploading: {fanqie_id}")
                waiting.remove(book)
                continue
            uploading.append({
                "vi_title": book.get("vi_title"),
                "wiki_id": wiki_id,
                "fanqie_id": fanqie_id,
                "uploaded_chapters": 0,
                "fanqie_chapters": book.get("current_chapters"),
                "status": book.get("status"),
                "last_updated": book.get("last_updated")
            })
            waiting.remove(book)
            moved += 1
            print(f"  -> Moved {fanqie_id} to uploading")
        save_json("waiting_list.json", waiting)
        save_json("uploading_list.json", uploading)
        print(f"MOVE_TO_UPLOADING: {moved} moved")

    elif "DELETE_WAITING" in cmd:
        # Format: one fanqie_id per line
        before = len(waiting)
        ids = set(lines)
        waiting = [b for b in waiting if b["fanqie_id"] not in ids]
        save_json("waiting_list.json", waiting)
        print(f"DELETE_WAITING: {before - len(waiting)} deleted")

    elif "DELETE_UPLOADING" in cmd:
        before = len(uploading)
        ids = set(lines)
        uploading = [b for b in uploading if b["fanqie_id"] not in ids]
        save_json("uploading_list.json", uploading)
        print(f"DELETE_UPLOADING: {before - len(uploading)} deleted")

    else:
        print(f"Unknown command: {ISSUE_TITLE}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()

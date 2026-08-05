import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
SEEN_PATH = BASE_DIR / "data" / "seen_posts.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_seen():
    if not SEEN_PATH.exists():
        return {}
    with open(SEEN_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen):
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def fetch_channel(channel):
    url = f"https://t.me/s/{channel}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    posts = []
    for block in soup.select(".tgme_widget_message"):
        data_post = block.get("data-post")
        if not data_post or "/" not in data_post:
            continue
        post_id = int(data_post.split("/")[-1])

        text_el = block.select_one(".tgme_widget_message_text")
        text = text_el.get_text("\n", strip=True) if text_el else ""

        time_el = block.select_one(".tgme_widget_message_date time")
        dt_str = time_el.get("datetime") if time_el else None
        dt = datetime.fromisoformat(dt_str) if dt_str else None

        posts.append(
            {
                "channel": channel,
                "post_id": post_id,
                "text": text,
                "link": f"https://t.me/{channel}/{post_id}",
                "date": dt.isoformat() if dt else None,
            }
        )
    return posts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=None, help="Override config's window_hours")
    args = parser.parse_args()

    config = load_config()
    seen = load_seen()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    window_hours = args.hours if args.hours is not None else config.get("window_hours", 48)
    cutoff = now_dt - timedelta(hours=window_hours)

    new_items = []
    for channel in config["channels"]:
        try:
            posts = fetch_channel(channel)
        except requests.RequestException as e:
            print(f"[warn] {channel}: {e}", file=sys.stderr)
            continue

        for post in posts:
            if not post["date"] or datetime.fromisoformat(post["date"]) < cutoff:
                continue

            key = f"{post['channel']}:{post['post_id']}"
            if key not in seen and post["text"]:
                new_items.append(post)
                seen[key] = now

        time.sleep(1)

    save_seen(seen)
    new_items.sort(key=lambda p: p["date"] or "")
    print(json.dumps(new_items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

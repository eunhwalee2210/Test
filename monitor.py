"""카카오뱅크 입찰공고 모니터링 스크립트

카카오뱅크 API에서 입찰공고를 조회하고, 새로운 공고가 있으면
GitHub Issue를 생성합니다.
"""

import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.kakaobank.com"
API_URL = f"{BASE_URL}/api/v1/boards/BIDDING/posts?page=0&size=10"
DETAIL_URL = f"{BASE_URL}/Corp/News/Bidding"
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "eunhwalee2210/test")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
ISSUE_LABEL = "입찰공고"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/Corp/News/Bidding/pages/1",
}

GITHUB_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def fetch_notices():
    """API에서 최신 입찰공고 목록을 가져옵니다."""
    resp = requests.get(API_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "CB0000":
        print(f"API 오류: {data.get('msg')}")
        return []

    notices = []
    for post in data["result"]["content"]:
        # HTML content에서 텍스트 추출
        content_html = post.get("content", "")
        soup = BeautifulSoup(content_html, "html.parser")
        content_text = soup.get_text(separator="\n", strip=True)

        # content에서 입찰공고 링크 추출
        bidding_link = ""
        for a in soup.find_all("a", href=True):
            if "nicedocu.com" in a["href"] or "bid" in a["href"].lower():
                bidding_link = a["href"]
                break

        # 첨부파일 정보
        attachments = []
        for att in post.get("attachments", []):
            attachments.append({
                "name": att.get("label", att.get("filename", "")),
                "url": att.get("download_url", ""),
            })

        notices.append({
            "post_id": post["post_id"],
            "title": post["title"],
            "reg_date": post["reg_date"][:10],  # YYYY-MM-DD
            "content_summary": content_text[:300],
            "bidding_link": bidding_link,
            "detail_url": f"{DETAIL_URL}/{post['post_id']}",
            "attachments": attachments,
        })

    return notices


def get_existing_post_ids():
    """이미 생성된 GitHub Issue에서 post_id 목록을 가져옵니다."""
    if not GITHUB_TOKEN:
        return set()

    post_ids = set()
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers=GITHUB_HEADERS,
            params={
                "labels": ISSUE_LABEL,
                "state": "all",
                "per_page": 100,
                "page": page,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            break

        issues = resp.json()
        if not issues:
            break

        for issue in issues:
            body = issue.get("body", "")
            match = re.search(r"post_id: (\d+)", body)
            if match:
                post_ids.add(int(match.group(1)))

        page += 1

    return post_ids


def ensure_label_exists():
    """GitHub Issue 라벨이 없으면 생성합니다."""
    if not GITHUB_TOKEN:
        return

    resp = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/labels/{ISSUE_LABEL}",
        headers=GITHUB_HEADERS,
        timeout=30,
    )
    if resp.status_code == 404:
        requests.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/labels",
            headers=GITHUB_HEADERS,
            json={
                "name": ISSUE_LABEL,
                "color": "FFA500",
                "description": "카카오뱅크 입찰공고 알림",
            },
            timeout=30,
        )


def create_issue(notice):
    """새 공고에 대한 GitHub Issue를 생성합니다."""
    if not GITHUB_TOKEN:
        print(f"[DRY RUN] Issue 생성: {notice['title']}")
        return True

    attachments_md = ""
    if notice["attachments"]:
        attachments_md = "\n### 첨부파일\n"
        for att in notice["attachments"]:
            attachments_md += f"- [{att['name']}]({att['url']})\n"

    bidding_link_md = ""
    if notice["bidding_link"]:
        bidding_link_md = f"- **입찰공고 링크**: {notice['bidding_link']}\n"

    body = (
        f"## 새로운 입찰공고\n\n"
        f"- **제목**: {notice['title']}\n"
        f"- **등록일**: {notice['reg_date']}\n"
        f"- **카카오뱅크 페이지**: {notice['detail_url']}\n"
        f"{bidding_link_md}"
        f"\n### 내용 요약\n"
        f"{notice['content_summary']}\n"
        f"{attachments_md}"
        f"\n---\n"
        f"post_id: {notice['post_id']}\n"
        f"*이 Issue는 입찰공고 모니터링 봇에 의해 자동 생성되었습니다.*"
    )

    resp = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers=GITHUB_HEADERS,
        json={
            "title": f"[입찰공고] {notice['title']}",
            "body": body,
            "labels": [ISSUE_LABEL],
        },
        timeout=30,
    )

    if resp.status_code == 201:
        print(f"Issue 생성 완료: {notice['title']}")
        return True
    else:
        print(f"Issue 생성 실패: {resp.status_code} - {resp.text}")
        return False


def main():
    print("=== 카카오뱅크 입찰공고 모니터링 시작 ===")

    notices = fetch_notices()
    print(f"조회된 공고 수: {len(notices)}")

    if not notices:
        print("공고를 가져올 수 없습니다.")
        sys.exit(1)

    for n in notices:
        print(f"  - [{n['post_id']}] {n['title']} ({n['reg_date']})")

    existing_ids = get_existing_post_ids()
    print(f"기존 Issue의 post_id 수: {len(existing_ids)}")

    ensure_label_exists()
    new_count = 0
    for notice in notices:
        if notice["post_id"] not in existing_ids:
            if create_issue(notice):
                new_count += 1
            time.sleep(1)

    print(f"새로 생성된 Issue: {new_count}건")
    print("=== 모니터링 완료 ===")


if __name__ == "__main__":
    main()

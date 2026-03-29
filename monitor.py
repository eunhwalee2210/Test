"""카카오뱅크 입찰공고 모니터링 스크립트

주기적으로 입찰공고 페이지를 확인하고, 새로운 공고가 있으면
GitHub Issue를 생성합니다.
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.kakaobank.com"
BIDDING_URL = f"{BASE_URL}/Corp/News/Bidding/pages/1"
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "eunhwalee2210/test")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
ISSUE_LABEL = "입찰공고"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_bidding_page():
    """입찰공고 페이지를 가져옵니다."""
    # 1차: HTML 직접 요청
    try:
        resp = requests.get(BIDDING_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"HTML 요청 실패: {e}")

    # 2차: API 엔드포인트 시도 (Next.js 기반 사이트의 경우)
    api_urls = [
        f"{BASE_URL}/api/corp/news/bidding?page=1",
        f"{BASE_URL}/_next/data/corp/news/bidding/pages/1.json",
    ]
    for url in api_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp.text
        except requests.RequestException:
            continue

    return None


def parse_notices(html):
    """HTML에서 입찰공고 목록을 파싱합니다."""
    notices = []
    soup = BeautifulSoup(html, "html.parser")

    # 패턴 1: 테이블 기반 목록
    for row in soup.select("table tbody tr, .board-list tr, .list-table tr"):
        cols = row.find_all("td")
        if len(cols) < 2:
            continue
        link_tag = row.find("a")
        title = link_tag.get_text(strip=True) if link_tag else cols[1].get_text(strip=True)
        href = link_tag.get("href", "") if link_tag else ""
        notice_url = href if href.startswith("http") else f"{BASE_URL}{href}"

        notice = {
            "title": title,
            "url": notice_url,
            "id": extract_notice_id(href),
        }

        # 날짜 추출 시도
        for col in cols:
            text = col.get_text(strip=True)
            if re.match(r"\d{4}[.\-/]\d{2}[.\-/]\d{2}", text):
                notice["date"] = text
                break

        if title:
            notices.append(notice)

    # 패턴 2: 리스트 기반 목록
    if not notices:
        for item in soup.select(
            ".list-item, .board-item, .notice-item, "
            "[class*='list'] li, [class*='List'] li, "
            "[class*='board'] li, [class*='Board'] li"
        ):
            link_tag = item.find("a")
            if not link_tag:
                continue
            title = link_tag.get_text(strip=True)
            href = link_tag.get("href", "")
            notice_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            notice = {
                "title": title,
                "url": notice_url,
                "id": extract_notice_id(href),
            }

            date_el = item.find(class_=re.compile(r"date|time|day", re.I))
            if date_el:
                notice["date"] = date_el.get_text(strip=True)

            if title:
                notices.append(notice)

    # 패턴 3: JSON-LD 또는 Next.js 데이터
    if not notices:
        for script in soup.find_all("script", {"id": "__NEXT_DATA__"}):
            try:
                data = json.loads(script.string)
                notices = extract_from_next_data(data)
            except (json.JSONDecodeError, TypeError):
                pass

    # 패턴 4: 응답이 JSON인 경우
    if not notices:
        try:
            data = json.loads(html)
            if isinstance(data, dict):
                for key in ("list", "data", "items", "result", "content"):
                    if key in data and isinstance(data[key], list):
                        for item in data[key]:
                            notice = {
                                "title": item.get("title", item.get("subject", "")),
                                "url": build_notice_url(item),
                                "id": str(item.get("id", item.get("seq", item.get("no", "")))),
                                "date": item.get("date", item.get("regDate", item.get("createDate", ""))),
                            }
                            if notice["title"]:
                                notices.append(notice)
                        break
        except (json.JSONDecodeError, TypeError):
            pass

    return notices


def extract_notice_id(href):
    """URL에서 공고 ID를 추출합니다."""
    numbers = re.findall(r"\d+", href)
    return numbers[-1] if numbers else href


def extract_from_next_data(data):
    """Next.js __NEXT_DATA__에서 공고 목록을 추출합니다."""
    notices = []
    props = data.get("props", {}).get("pageProps", {})
    for key in ("list", "data", "items", "biddings", "notices"):
        if key in props and isinstance(props[key], list):
            for item in props[key]:
                notice = {
                    "title": item.get("title", item.get("subject", "")),
                    "url": build_notice_url(item),
                    "id": str(item.get("id", item.get("seq", ""))),
                    "date": item.get("date", item.get("regDate", "")),
                }
                if notice["title"]:
                    notices.append(notice)
            break
    return notices


def build_notice_url(item):
    """공고 아이템에서 상세 URL을 생성합니다."""
    if "url" in item:
        url = item["url"]
        return url if url.startswith("http") else f"{BASE_URL}{url}"
    notice_id = item.get("id", item.get("seq", item.get("no", "")))
    if notice_id:
        return f"{BASE_URL}/Corp/News/Bidding/{notice_id}"
    return BIDDING_URL


def get_existing_issue_titles():
    """이미 생성된 GitHub Issue 제목 목록을 가져옵니다."""
    if not GITHUB_TOKEN:
        return set()

    titles = set()
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={
                "labels": ISSUE_LABEL,
                "state": "all",
                "per_page": 100,
                "page": page,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"GitHub Issue 조회 실패: {resp.status_code}")
            break

        issues = resp.json()
        if not issues:
            break

        for issue in issues:
            titles.add(issue["title"])
        page += 1

    return titles


def ensure_label_exists():
    """GitHub Issue 라벨이 없으면 생성합니다."""
    if not GITHUB_TOKEN:
        return

    resp = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/labels/{ISSUE_LABEL}",
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=30,
    )
    if resp.status_code == 404:
        requests.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/labels",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
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

    date_str = notice.get("date", "날짜 미상")
    body = (
        f"## 새로운 입찰공고\n\n"
        f"- **제목**: {notice['title']}\n"
        f"- **등록일**: {date_str}\n"
        f"- **링크**: {notice['url']}\n\n"
        f"---\n"
        f"*이 Issue는 입찰공고 모니터링 봇에 의해 자동 생성되었습니다.*"
    )

    resp = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        },
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

    # 1. 페이지 가져오기
    html = fetch_bidding_page()
    if not html:
        print("페이지를 가져올 수 없습니다.")
        sys.exit(1)

    # 2. 공고 목록 파싱
    notices = parse_notices(html)
    print(f"파싱된 공고 수: {len(notices)}")

    if not notices:
        print("공고를 찾지 못했습니다. 페이지 구조가 변경되었을 수 있습니다.")
        print("HTML 미리보기:")
        print(html[:2000])
        sys.exit(1)

    # 3. 기존 Issue 확인
    existing_titles = get_existing_issue_titles()
    print(f"기존 Issue 수: {len(existing_titles)}")

    # 4. 새 공고에 대해 Issue 생성
    ensure_label_exists()
    new_count = 0
    for notice in notices:
        issue_title = f"[입찰공고] {notice['title']}"
        if issue_title not in existing_titles:
            if create_issue(notice):
                new_count += 1
            time.sleep(1)  # API rate limit 방지

    print(f"새로 생성된 Issue: {new_count}건")
    print("=== 모니터링 완료 ===")


if __name__ == "__main__":
    main()

"""카카오뱅크 입찰공고 페이지 HTML 구조 분석용 디버그 스크립트"""

import json
import os
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.kakaobank.com"
BIDDING_URL = f"{BASE_URL}/Corp/News/Bidding/pages/1"
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "eunhwalee2210/test")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def main():
    # Fetch main page
    resp = requests.get(BIDDING_URL, headers=HEADERS, timeout=30)
    print(f"Status: {resp.status_code}")
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    # Check if SPA (look for __NEXT_DATA__ or root div)
    next_data = soup.find("script", {"id": "__NEXT_DATA__"})
    if next_data:
        print("\n=== __NEXT_DATA__ found ===")
        data = json.loads(next_data.string)
        print(json.dumps(data, indent=2, ensure_ascii=False)[:5000])
    else:
        print("\n=== No __NEXT_DATA__ ===")

    # Find all links with /Bidding/ in href
    print("\n=== Links containing 'Bidding' ===")
    for a in soup.find_all("a", href=True):
        if "Bidding" in a.get("href", "") or "bidding" in a.get("href", ""):
            print(f"  href={a['href']}  text={a.get_text(strip=True)[:80]}")

    # Find all links with /Corp/ in href
    print("\n=== Links containing '/Corp/News/' ===")
    for a in soup.find_all("a", href=True):
        if "/Corp/News/" in a.get("href", ""):
            print(f"  href={a['href']}  text={a.get_text(strip=True)[:80]}")

    # Print all script tags (look for API calls)
    print("\n=== Script sources ===")
    for s in soup.find_all("script", src=True):
        print(f"  {s['src'][:120]}")

    # Print structure summary
    print(f"\n=== HTML length: {len(html)} ===")
    print(f"=== Title: {soup.title.string if soup.title else 'N/A'} ===")

    # Print main content area (first 3000 chars of body)
    body = soup.find("body")
    if body:
        print("\n=== Body text preview (first 2000 chars) ===")
        print(body.get_text(separator="\n", strip=True)[:2000])

    # Create debug issue with findings
    if GITHUB_TOKEN:
        debug_body = f"## HTML 구조 분석\n\n"
        debug_body += f"- URL: {BIDDING_URL}\n"
        debug_body += f"- Status: {resp.status_code}\n"
        debug_body += f"- HTML length: {len(html)}\n"
        debug_body += f"- Has __NEXT_DATA__: {next_data is not None}\n\n"

        if next_data:
            data = json.loads(next_data.string)
            debug_body += f"### __NEXT_DATA__ (first 3000 chars)\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:3000]}\n```\n\n"

        debug_body += "### /Corp/News/ links\n"
        for a in soup.find_all("a", href=True):
            if "/Corp/News/" in a.get("href", ""):
                debug_body += f"- `{a['href']}` → {a.get_text(strip=True)[:60]}\n"

        debug_body += f"\n### Body text preview\n```\n{body.get_text(separator=chr(10), strip=True)[:2000] if body else 'N/A'}\n```\n"

        resp2 = requests.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "title": "[DEBUG] 입찰공고 페이지 HTML 구조 분석",
                "body": debug_body,
                "labels": ["입찰공고"],
            },
            timeout=30,
        )
        print(f"\nDebug issue created: {resp2.status_code}")


if __name__ == "__main__":
    main()

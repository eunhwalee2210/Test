"""카카오뱅크 입찰공고 API 엔드포인트 탐색"""

import json
import os
import re
import requests

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

API_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}


def main():
    results = []

    # 1. Fetch main page and find JS bundles / API patterns
    resp = requests.get(BIDDING_URL, headers=HEADERS, timeout=30)
    html = resp.text
    results.append(f"## Main page: {resp.status_code}, {len(html)} bytes")

    # Find API URLs in HTML/JS
    api_patterns = re.findall(r'["\'](/api/[^"\']+)["\']', html)
    api_patterns += re.findall(r'["\'](https?://[^"\']*api[^"\']*)["\']', html)
    api_patterns += re.findall(r'["\'](/v\d+/[^"\']+)["\']', html)
    results.append(f"\n### API patterns in HTML ({len(api_patterns)} found)")
    for p in set(api_patterns):
        results.append(f"- `{p}`")

    # Find JS bundle URLs
    js_urls = re.findall(r'src="(/static/js/[^"]+)"', html)
    js_urls += re.findall(r'src="(/_next/[^"]+)"', html)
    js_urls += re.findall(r'src="(/js/[^"]+)"', html)
    js_urls += re.findall(r'src="([^"]+\.js[^"]*)"', html)
    results.append(f"\n### JS bundles ({len(js_urls)} found)")
    for u in js_urls[:10]:
        results.append(f"- `{u}`")

    # 2. Try common API endpoints
    api_candidates = [
        "/api/corp/news/bidding",
        "/api/corp/news/bidding?page=1",
        "/api/corp/news/bidding?page=1&size=10",
        "/api/v1/corp/news/bidding",
        "/api/v1/bidding",
        "/api/bidding",
        "/api/notice/bidding",
        "/Corp/News/Bidding",
        "/api/corp/bidding",
        "/api/board/bidding",
        "/api/board/list?category=bidding",
        "/api/news/bidding",
        "/corp/news/bidding.json",
    ]

    results.append("\n### API endpoint tests")
    for path in api_candidates:
        url = f"{BASE_URL}{path}" if path.startswith("/") else path
        try:
            r = requests.get(url, headers=API_HEADERS, timeout=10)
            preview = r.text[:200].replace("\n", " ")
            results.append(f"- `{path}` → **{r.status_code}** `{preview[:150]}`")
        except Exception as e:
            results.append(f"- `{path}` → ERROR: {e}")

    # 3. Fetch and scan main JS bundle for API paths
    results.append("\n### JS bundle API scan")
    for js_url in js_urls[:5]:
        full_url = js_url if js_url.startswith("http") else f"{BASE_URL}{js_url}"
        try:
            r = requests.get(full_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                # Find API paths in JS
                apis = re.findall(r'["\'](/api/[a-zA-Z0-9/_\-?&=.]+)["\']', r.text)
                apis += re.findall(r'["\'](/Corp/[a-zA-Z0-9/_\-?&=.]+)["\']', r.text)
                apis += re.findall(r'fetch\(["\']([^"\']+)["\']', r.text)
                apis += re.findall(r'axios[.\w]*\(["\']([^"\']+)["\']', r.text)
                bidding_apis = [a for a in set(apis) if 'idding' in a.lower() or 'board' in a.lower() or 'notice' in a.lower() or 'news' in a.lower()]
                if bidding_apis:
                    results.append(f"\n**{js_url}** - bidding-related APIs:")
                    for a in bidding_apis:
                        results.append(f"  - `{a}`")
                else:
                    results.append(f"- `{js_url}`: {len(set(apis))} total APIs, 0 bidding-related")
        except Exception as e:
            results.append(f"- `{js_url}`: ERROR {e}")

    # Post results as issue
    body = "\n".join(results)
    if GITHUB_TOKEN:
        # Close previous debug issue
        issues = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            params={"labels": "입찰공고", "state": "open"},
            timeout=30,
        ).json()
        for issue in issues:
            if "[DEBUG]" in issue["title"]:
                requests.patch(
                    f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue['number']}",
                    headers={"Authorization": f"token {GITHUB_TOKEN}"},
                    json={"state": "closed"},
                    timeout=30,
                )

        requests.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "title": "[DEBUG] API 엔드포인트 탐색 결과",
                "body": body,
                "labels": ["입찰공고"],
            },
            timeout=30,
        )
    print(body)


if __name__ == "__main__":
    main()

"""카카오뱅크 입찰공고 API 데이터 확인"""

import json
import os
import requests

BASE_URL = "https://www.kakaobank.com"
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "eunhwalee2210/test")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/Corp/News/Bidding/pages/1",
}


def main():
    urls = [
        f"{BASE_URL}/api/v1/boards/BIDDING/posts",
        f"{BASE_URL}/api/v1/boards/BIDDING/posts?page=1",
        f"{BASE_URL}/api/v1/boards/BIDDING/posts?page=1&size=10",
        f"{BASE_URL}/api/v1/boards/BIDDING/posts?page=0&size=10",
    ]

    results = []
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            results.append(f"### `{url}`\n- Status: {r.status_code}")
            if r.status_code == 200:
                try:
                    data = r.json()
                    results.append(f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:4000]}\n```")
                except:
                    results.append(f"```\n{r.text[:2000]}\n```")
            else:
                results.append(f"```\n{r.text[:500]}\n```")
        except Exception as e:
            results.append(f"- Error: {e}")

    body = "\n\n".join(results)

    if GITHUB_TOKEN:
        # Close previous debug issues
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
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            json={
                "title": "[DEBUG] BIDDING API 응답 데이터",
                "body": body,
                "labels": ["입찰공고"],
            },
            timeout=30,
        )
    print(body)


if __name__ == "__main__":
    main()

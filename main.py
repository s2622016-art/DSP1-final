import json
import re
import sqlite3
import time

import requests
from bs4 import BeautifulSoup

ORG_REPOS_URL = "https://github.com/orgs/google/repositories"
DB_NAME = "github_repos.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_stars(text: str) -> int:
    
    if not text:
        return 0
    cleaned = text.strip().lower().replace(",", "")
    match = re.search(r"([\d]+(?:\.\d+)?)\s*([km])?\s*(?:star|$)", cleaned)
    if not match:
        match = re.search(r"\b([\d]+(?:\.\d+)?)\s*([km])?\b", cleaned)
    if not match:
        return 0
    num = float(match.group(1))
    unit = match.group(2)
    if unit == "k":
        return int(num * 1000)
    if unit == "m":
        return int(num * 1_000_000)
    return int(num)


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            language TEXT,
            stars INTEGER
        )
        """)
    cursor.execute("DELETE FROM repositories")
    conn.commit()
    return conn


def fetch_page(session: requests.Session, page: int) -> str | None:
    resp = session.get(ORG_REPOS_URL, params={"page": page}, timeout=30)
    if resp.status_code != 200:
        print(f"ページ {page} の取得に失敗しました (status={resp.status_code})")
        return None
    return resp.text


def extract_language_fallback(card, repo_name: str) -> str:
    # 現在のページには itemprop="programmingLanguage" が存在しないため、
    # カード（<li>）全体のテキストから既知の言語名を探す（近似処理）
    common_langs = [
        "Python", "C++", "C#", "JavaScript", "TypeScript", "Java", "Go",
        "Rust", "Dart", "Kotlin", "Swift", "HTML", "Shell", "Ruby",
        "PHP", "Scala", "Lua", "C",
    ]
    tokens = card.get_text(" ", strip=True).replace("•", " ").split()
    for lang in common_langs:
        if lang in tokens:
            return lang
    return "Unknown"


def extract_stars_fallback(card, repo_name: str) -> int:
    
    star_link = card.find("a", href=f"/google/{repo_name}/stargazers")
    if star_link:
        return parse_stars(star_link.get_text(" ", strip=True))
    return 0


def extract_repos_from_html(html: str) -> tuple[list[tuple[str, str, int]], dict]:
    """1ページ分のHTMLから (名前, 言語, スター数) のリストとページ情報を返す。

    第1優先：HTML埋め込みJSON（starsCount = 正確な整数）
    フォールバック：<li> カードからの表示テキスト抽出（スター数は近似になる）
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- 第1優先：埋め込みJSON ---
    script = soup.find("script", attrs={"data-target": "react-app.embeddedData"})
    if script and script.string:
        try:
            data = json.loads(script.string)
            route = data["payload"]["orgReposPageRoute"]
            repos = []
            for repo in route["repositories"]:
                name = repo["name"]
                lang_data = repo.get("primaryLanguage")
                language = lang_data["name"] if lang_data else "Unknown"
                stars = int(repo["starsCount"])
                repos.append((name, language, stars))
            page_info = {
                "page_count": route.get("pageCount"),
                "total_count": route.get("repositoryCount"),
            }
            return repos, page_info
        except (KeyError, ValueError, TypeError):
            print("埋め込みJSONの解析に失敗したため、HTML表示側から抽出します")

    # --- フォールバック：表示HTML（<li> が1リポジトリのカード） ---
    results: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for link in soup.select('a[href^="/google/"]'):
        href = link.get("href", "").strip("/")
        parts = href.split("/")
        if len(parts) != 2 or parts[0] != "google":
            continue
        repo_name = parts[1]
        if not repo_name or repo_name in seen_names:
            continue
        card = link.find_parent("li") 
        if card is None:
            continue
        language = extract_language_fallback(card, repo_name)
        stars = extract_stars_fallback(card, repo_name)
        seen_names.add(repo_name)
        results.append((repo_name, language, stars))
    return results, {"page_count": None, "total_count": None}


def scrape_all_google_repos() -> list[tuple[str, str, int]]:
    session = requests.Session()
    session.headers.update(HEADERS)

    all_repos: list[tuple[str, str, int]] = []
    seen_global: set[str] = set()
    page = 1
    page_count = None
    total_count = None

    while True:
        html = fetch_page(session, page)
        if not html:
            break

        page_repos, page_info = extract_repos_from_html(html)
        if page_info.get("page_count"):
            page_count = page_info["page_count"]
            total_count = page_info["total_count"]

        new_items = [r for r in page_repos if r[0] not in seen_global]
        if not new_items:
            print(f"ページ {page} に新規リポジトリがないため終了します。")
            break

        for item in new_items:
            seen_global.add(item[0])
            all_repos.append(item)

        progress = f" / 全{page_count}ページ" if page_count else ""
        print(
            f"ページ {page}{progress} 完了: 新規 {len(new_items)} 件"
            f"（累計 {len(all_repos)} 件 / 全{total_count}件）"
        )

        if page_count is not None and page >= page_count:
            print("最終ページまで取得しました。")
            break

        page += 1
        time.sleep(1)  # 課題の必須ルール：リクエストのループで time.sleep(1)

    return all_repos


def save_and_display(repos: list[tuple[str, str, int]], db_path: str) -> None:
    conn = init_db(db_path)
    cursor = conn.cursor()

    for name, language, stars in repos:
        cursor.execute(
            """
            INSERT OR REPLACE INTO repositories (name, language, stars)
            VALUES (?, ?, ?)
            """,
            (name, language, stars),
        )
    conn.commit()

    print("\n--- SELECT * FROM repositories ---")
    cursor.execute(
        "SELECT id, name, language, stars FROM repositories ORDER BY id ASC"
    )
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    print(f"\n合計保存件数: {len(rows)} 件")
    conn.close()


if __name__ == "__main__":
    repos = scrape_all_google_repos()
    save_and_display(repos, DB_NAME)
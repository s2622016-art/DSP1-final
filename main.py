import json
import sqlite3
import time

import requests
from bs4 import BeautifulSoup

# スクレイピング対象：Google組織のリポジトリ一覧ページ
URL = "https://github.com/orgs/google/repositories"
HEADERS = {"User-Agent": "Mozilla/5.0 (DS-Programming Final Assignment)"}
DB_NAME = "github_repos.db"


def scrape_google_repos():
    """一覧ページのHTMLをスクレイピングして (名前, 言語, スター数) のリストを返す。

    現在のGitHubの一覧ページは、リポジトリ情報がHTML内に
    JSON形式で埋め込まれている。その部分をBeautifulSoupで取り出して解析する。
    ※ api.github.com へのアクセスはしていない（あくまでWebページの取得）。
    """
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    script = soup.find("script", attrs={"data-target": "react-app.embeddedData"})
    if script is None:
        raise RuntimeError("ページからリポジトリ情報が見つかりませんでした")

    data = json.loads(script.string)
    repositories = data["payload"]["orgReposPageRoute"]["repositories"]

    repos = []
    for repo in repositories:
        name = repo["name"]
        language_data = repo.get("primaryLanguage")
        language = language_data["name"] if language_data else "不明"
        stars = repo["starsCount"]
        repos.append((name, language, stars))
    return repos


def main():
    # 1. データベースの接続とテーブル作成
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            language TEXT,
            stars INTEGER
        )
        """
    )
    # 再実行したときにデータが二重にならないよう、一度空にする
    cursor.execute("DELETE FROM repositories")
    conn.commit()

    # 2. スクレイピングで実際のデータを取得する
    print("GitHubのGoogleのリポジトリ一覧をスクレイピング中...")
    repos = scrape_google_repos()
    print(f"{len(repos)}件取得しました。データベースへ保存します。")

    # 3. 取得したデータを1件ずつDBへ保存する（1件ごとに time.sleep(1)）
    for name, language, stars in repos:
        cursor.execute(
            "INSERT INTO repositories (name, language, stars) VALUES (?, ?, ?)",
            (name, language, stars),
        )
        print(f"保存: {name} / {language} / {stars}")
        time.sleep(1)

    conn.commit()
    print("データの保存が完了しました！")

    # 4. 保存したデータをSELECT文で表示する
    print("\n--- データベース内のデータ一覧 (SELECT結果) ---")
    cursor.execute("SELECT * FROM repositories ORDER BY stars DESC")
    for row in cursor.fetchall():
        print(row)

    conn.close()


if __name__ == "__main__":
    main()

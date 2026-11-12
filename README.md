# DSプログラミング 最終課題

GitHubのGoogle（`google` 組織）のリポジトリ情報をスクレイピングし、
SQLiteデータベースに保存して、SELECT文で表示するプログラムです。

## 取得する情報

- リポジトリ名
- 主要な言語
- スターの数

対象ページ: https://github.com/orgs/google/repositories （1ページ目・30件）

## 課題のルールへの対応

- GitHubのAPI（api.github.com）は使わず、WebページのHTMLを取得して解析しています
- データ保存の際、1件ごとに `time.sleep(1)` を入れています
- 保存したデータは `SELECT * FROM repositories ORDER BY stars DESC` で表示します

## 実行方法

```bash
pip install -r requirements.txt
python main.py
```

実行すると `github_repos.db`（SQLite）が作成され、
取得したリポジトリが保存されたあと、一覧がスター数の多い順に表示されます。

## ファイル構成

- `main.py` — スクレイピング〜DB保存〜SELECT表示の本体
- `requirements.txt` — 必要なライブラリ（requests / beautifulsoup4）
- `github_repos.db` — 実行時に自動生成されるデータベース

# Amour — 恋愛パターン・ジャーナル

Flaskベースの恋愛コーチングWebアプリ。

## セットアップ

```bash
# 1. 依存関係インストール
pip install -r requirements.txt

# 2. 起動
python app.py

# → http://localhost:5000 でアクセス
```

## アカウント種別

| 種別   | 説明 |
|--------|------|
| ユーザー | クライアント。4ステップのワークを記入し、履歴を閲覧できる |
| コーチ  | `/coach` にアクセス可能。全ユーザーの回答をセッション前に確認し、メモを追加できる |

新規登録時にアカウント種別を選択してください。

## 機能一覧

- ✅ メール＋パスワードでのユーザー登録・ログイン
- ✅ セッションごとの自動保存（デバウンス800ms）
- ✅ 過去セッションの履歴閲覧・再編集
- ✅ コーチ管理画面（全クライアント一覧）
- ✅ コーチによるセッション事前確認
- ✅ コーチメモの追加・削除

## 本番環境

```bash
# 環境変数を設定
export SECRET_KEY="your-secure-random-key"
export DATABASE_URL="sqlite:///amour.db"  # またはPostgreSQL URL

# gunicornで起動
pip install gunicorn
gunicorn app:app
```

## 画面構成

```
/ → /login (未ログイン) or /dashboard (ユーザー) or /coach (コーチ)
/dashboard          ユーザーのセッション一覧
/session/new        新しいセッション開始
/session/<id>/step1 STEP1: 恋愛年表（動的追加・自動保存）
/session/<id>/step2 STEP2: 各恋愛を振り返る（タブ切替・自動保存）
/session/<id>/step3 STEP3: パターン分析（自動保存）
/session/<id>/summary まとめ（自動保存）
/session/<id>/view  完了セッションの閲覧
/coach              コーチ: クライアント一覧
/coach/user/<id>    コーチ: クライアントのセッション一覧
/coach/session/<id> コーチ: 回答全文確認＋メモ追加
```

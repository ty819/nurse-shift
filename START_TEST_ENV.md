# テスト環境起動ガイド

## ✅ テスト環境が起動しました！

### 🌐 アクセスURL

| サービス | URL | 説明 |
|---------|-----|------|
| **フロントエンド** | http://localhost:3000 | メインアプリケーション |
| **バックエンドAPI** | http://localhost:8000/docs | FastAPI Swagger UI |
| **バックエンドルート** | http://localhost:8000 | API エンドポイント |

---

## 🚀 起動済みサービス

### 1. バックエンドAPI（FastAPI）
```bash
✅ ポート: 8000
✅ ステータス: 起動中
✅ OR-Tools: 9.14.6206
✅ FastAPI: 0.115.0
✅ Python: 3.13.3
```

**確認方法:**
```bash
curl http://localhost:8000/docs
```

### 2. フロントエンド（Next.js）
```bash
✅ ポート: 3000
✅ ステータス: 起動中
✅ Next.js: 14.2.7
✅ React: 18.3.1
✅ Node.js: 24.3.0
```

**確認方法:**
```bash
curl http://localhost:3000
```

---

## 📋 基本的な使い方

### ステップ1: ブラウザでアクセス
1. ブラウザで http://localhost:3000 を開く
2. トップページが表示される

### ステップ2: シフトを最適化
1. **対象月を選択** （例: 2025-10）
2. **案数を設定** （1〜10、デフォルト: 3）
3. **「既存条件で最適化」ボタンをクリック**
4. シフト表が表示される

### ステップ3: 手動編集（オプション）
1. セルをクリックしてシフトを変更
2. 自動的にロックされ、再最適化が実行される

### ステップ4: エクスポート
1. **CSV出力** または **PDF出力** をクリック
2. ファイルがダウンロードされる

---

## 🔧 APIエンドポイント一覧

### 主要エンドポイント

#### 1. デフォルト条件で最適化
```bash
POST http://localhost:8000/optimize/default-md?year=2025&month=10&alternatives=3
```

#### 2. 固定条件付き再最適化
```bash
POST http://localhost:8000/reoptimize
Content-Type: application/json

{
  "assignments": [...],
  "fixed": [{"nurse_id": "1", "date": "2025-10-01", "shift": "DAY"}],
  "year": 2025,
  "month": 10,
  "alternatives": 1
}
```

#### 3. 制約チェック・推奨取得
```bash
POST http://localhost:8000/recommend
Content-Type: application/json

{
  "assignments": [...],
  "year": 2025,
  "month": 10
}
```

#### 4. CSV出力
```bash
POST http://localhost:8000/export/csv
Content-Type: application/json

{
  "assignments": [...]
}
```

#### 5. PDF出力
```bash
POST http://localhost:8000/export/pdf
Content-Type: application/json

{
  "assignments": [...],
  "nurses": [...],
  "days": [...],
  "summary": {...},
  "warnings": []
}
```

---

## 🧪 テストシナリオ

### シナリオ1: 基本的な最適化
1. ブラウザで http://localhost:3000 を開く
2. 対象月: 2025-10
3. 案数: 3
4. 「既存条件で最適化」をクリック
5. **期待結果**: 3つのシフト案が表示される

### シナリオ2: セル編集と再最適化
1. シナリオ1を実施
2. 任意のセルをクリック
3. シフトを変更（例: 日勤 → 夜勤）
4. **期待結果**: セルがロック（オレンジ枠）され、自動的に再最適化

### シナリオ3: 違反検出
1. シナリオ2で複数セルを編集
2. 制約違反が発生するよう意図的に変更
3. **期待結果**: 違反セルが赤破線で表示、違反リストに詳細

### シナリオ4: エクスポート
1. シナリオ1を実施
2. 「CSV出力」をクリック
3. **期待結果**: assignments.csv がダウンロード
4. 「PDF出力」をクリック
5. **期待結果**: assignments.pdf がダウンロード

---

## 🔍 デバッグ方法

### フロントエンドのログ確認
```bash
# ブラウザの開発者ツールを開く
# Macの場合: Cmd + Option + I
# Windowsの場合: F12

# Consoleタブでエラーを確認
```

### バックエンドのログ確認
```bash
# ターミナルで実行中のログを確認
# バックエンドが起動中のターミナルを見る

# または、curlでAPIを直接テスト
curl -X POST "http://localhost:8000/optimize/default-md?year=2025&month=10&alternatives=1"
```

### APIの詳細ドキュメント
http://localhost:8000/docs にアクセスすると、Swagger UIで全APIをテスト可能

---

## 🛑 サービスの停止方法

### 方法1: Claude Codeで停止
バックグラウンドプロセスを停止:
```bash
lsof -ti:8000 | xargs kill -9  # バックエンド
lsof -ti:3000 | xargs kill -9  # フロントエンド
```

### 方法2: 手動で停止
各サービスが起動中のターミナルで:
```
Ctrl + C
```

---

## 📊 パフォーマンス指標

### バックエンド
- **最適化時間**: 約5-30秒（30人×31日）
- **メモリ使用量**: 約200-500MB
- **CPU使用率**: 最適化中 80-100%

### フロントエンド
- **初回ロード**: 約1-2秒
- **シフト表示**: 即座
- **再最適化**: 5-30秒（バックエンド依存）

---

## 🐛 トラブルシューティング

### 問題1: ポート使用中エラー
**症状**: `EADDRINUSE: address already in use`

**解決**:
```bash
# 使用中のプロセスを終了
lsof -ti:3000 | xargs kill -9  # フロントエンド
lsof -ti:8000 | xargs kill -9  # バックエンド

# 再起動
cd /Users/tom/Desktop/nurse_shift
# バックエンド
cd api && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# フロントエンド（別ターミナル）
cd frontend && export NEXT_PUBLIC_API_BASE="http://localhost:8000" && npm run dev
```

### 問題2: API接続エラー
**症状**: フロントエンドで "NEXT_PUBLIC_API_BASE が設定されていません"

**解決**:
```bash
# 環境変数を設定して再起動
cd /Users/tom/Desktop/nurse_shift/frontend
export NEXT_PUBLIC_API_BASE="http://localhost:8000"
npm run dev
```

### 問題3: Python パッケージエラー
**症状**: `ModuleNotFoundError: No module named 'fastapi'`

**解決**:
```bash
cd /Users/tom/Desktop/nurse_shift/api
source .venv/bin/activate
pip install -r requirements.txt
```

### 問題4: 最適化が "不可解" になる
**症状**: 制約が厳しすぎて解が見つからない

**確認**:
- `shift.md` の制約を確認
- 看護師台帳の人数が十分か確認
- 夜勤可能な看護師が必要人数以上いるか確認

---

## 📝 テストデータ

### サンプルデータの場所
```bash
/Users/tom/Desktop/nurse_shift/samples/
├── nurses.csv    # 看護師台帳サンプル
└── rules.json    # 月次ルールサンプル
```

### カスタムデータ作成
1. `samples/nurses.csv` を参考に看護師台帳を作成
2. `samples/rules.json` を参考に月次ルールを作成
3. APIで直接テスト（現在はファイルアップロード未実装）

---

## 🎯 次のステップ

### 動作確認後
1. ✅ 基本機能の動作確認
2. ✅ UI/UXの確認
3. ✅ レスポンシブ動作確認（ブラウザのデバイスツール）
4. 📦 本番環境へのデプロイ（DEPLOYMENT.md参照）

### 機能拡張
1. データベース導入（Supabase）
2. ユーザー認証
3. シフト履歴管理
4. 通知機能

---

## 💡 ヒント

### 開発効率化
- **ホットリロード**: コード変更時に自動でリロード
- **デバッグ**: ブラウザ開発者ツールでリアルタイムデバッグ
- **API テスト**: Swagger UI で簡単にAPIテスト

### レスポンシブ確認
1. ブラウザ開発者ツールを開く
2. デバイスツールバーを表示（Cmd+Shift+M / Ctrl+Shift+M）
3. デバイスを選択（iPad, iPhone等）
4. タッチ操作をシミュレート

---

**✅ テスト環境準備完了！**

ブラウザで http://localhost:3000 を開いて、シフト自動割当を体験してください。

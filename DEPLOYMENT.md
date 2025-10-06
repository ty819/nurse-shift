# デプロイガイド - 看護師シフト自動割当

## 🚀 クイックデプロイ（30分で完了）

### 前提条件
- GitHubアカウント
- Renderアカウント（無料）
- Vercelアカウント（無料）

---

## ステップ1: GitHubリポジトリの準備

### 1.1 リポジトリ作成
```bash
cd /Users/tom/Desktop/nurse_shift

# Gitの初期化（まだの場合）
git init

# .gitignore の確認
cat > .gitignore << 'EOF'
# Dependencies
**/node_modules/
**/.venv/
**/__pycache__/

# Build outputs
frontend/.next/
frontend/out/
api/.pytest_cache/

# Environment variables
.env
.env.local
.env.*.local

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
*.log
npm-debug.log*
EOF

# 全ファイルをステージング
git add .
git commit -m "Initial commit: Nurse Shift Optimizer"

# GitHubリポジトリを作成後、リモート追加
git remote add origin https://github.com/YOUR_USERNAME/nurse-shift.git
git branch -M main
git push -u origin main
```

---

## ステップ2: バックエンドデプロイ（Render）

### 2.1 Render Dashboard
1. https://dashboard.render.com/ にアクセス
2. "New +" → "Web Service" を選択

### 2.2 リポジトリ接続
1. "Connect a repository" → GitHub認証
2. `nurse-shift` リポジトリを選択

### 2.3 サービス設定
```yaml
Name: nurse-shift-api
Runtime: Docker
Region: Singapore
Branch: main
Root Directory: api
Dockerfile Path: ./Dockerfile
```

**重要**: "Advanced" → "Docker Command" は空欄のまま（Dockerfileの CMD を使用）

### 2.4 環境変数設定
```bash
ALLOWED_ORIGINS=*  # ステップ4で更新
PYTHONPATH=/app
HOST=0.0.0.0
PORT=10000
```

### 2.5 プラン選択
- 開発・テスト: **Free** プラン
- 本番運用: **Starter** プラン（$7/月）

### 2.6 デプロイ実行
1. "Create Web Service" をクリック
2. 自動ビルド開始（5-10分）
3. ビルド完了後、URLをコピー:
   ```
   https://nurse-shift-api.onrender.com
   ```

### 2.7 動作確認
ブラウザで以下にアクセス:
```
https://nurse-shift-api.onrender.com/docs
```
→ FastAPI Swagger UIが表示されればOK

---

## ステップ3: フロントエンドデプロイ（Vercel）

### 3.1 Vercel Dashboard
1. https://vercel.com/dashboard にアクセス
2. "Add New..." → "Project" を選択

### 3.2 リポジトリインポート
1. "Import Git Repository" → GitHub認証
2. `nurse-shift` リポジトリを選択

### 3.3 プロジェクト設定
```yaml
Framework Preset: Next.js
Root Directory: frontend
Build Command: npm run build
Output Directory: .next
Install Command: npm install
Node.js Version: 20.x
```

### 3.4 環境変数設定
```bash
NEXT_PUBLIC_API_BASE=https://nurse-shift-api.onrender.com
```
（ステップ2.6でコピーしたURLを使用）

### 3.5 デプロイ実行
1. "Deploy" をクリック
2. 自動ビルド開始（3-5分）
3. デプロイ完了後、URLをコピー:
   ```
   https://nurse-shift-xxx.vercel.app
   ```

### 3.6 動作確認
ブラウザでアクセス:
```
https://nurse-shift-xxx.vercel.app
```
→ トップページが表示されればOK

---

## ステップ4: CORS設定の更新

### 4.1 Renderに戻る
1. Render Dashboard → `nurse-shift-api` サービス
2. "Environment" タブ
3. `ALLOWED_ORIGINS` を編集:
   ```bash
   ALLOWED_ORIGINS=https://nurse-shift-xxx.vercel.app
   ```
   （ステップ3.5でコピーしたURLを使用）
4. "Save Changes" → 自動再デプロイ

---

## ステップ5: 統合テスト

### 5.1 機能確認チェックリスト

#### 基本動作
- [ ] トップページが表示される
- [ ] 対象月の選択ができる
- [ ] 「既存条件で最適化」ボタンをクリック
- [ ] シフト表が表示される
- [ ] セルをクリックしてシフト変更が可能
- [ ] 複数案が表示される（alternatives > 1の場合）

#### エクスポート機能
- [ ] CSV出力が動作する
- [ ] PDF出力が動作する
- [ ] ダウンロードファイルが正常に開ける

#### レスポンシブ
- [ ] デスクトップで快適に動作
- [ ] iPadで快適に動作（タッチ操作）
- [ ] モバイルで快適に動作

#### エラーハンドリング
- [ ] API接続エラー時に適切なメッセージ表示
- [ ] 不正な入力時にバリデーションエラー表示

### 5.2 トラブルシューティング

#### 問題: フロントエンドからAPIに接続できない
**症状**: "NEXT_PUBLIC_API_BASE が設定されていません" エラー

**解決**:
1. Vercel Dashboard → プロジェクト → Settings → Environment Variables
2. `NEXT_PUBLIC_API_BASE` が正しく設定されているか確認
3. 再デプロイ: Deployments → 最新デプロイ → "Redeploy"

#### 問題: CORS エラー
**症状**: コンソールに "CORS policy: No 'Access-Control-Allow-Origin' header"

**解決**:
1. Render Dashboard → `nurse-shift-api` → Environment
2. `ALLOWED_ORIGINS` がフロントエンドURLと一致しているか確認
3. ワイルドカード `*` は開発用のみ、本番では必ず具体的なURLを指定

#### 問題: Render Free プランでサービスが停止する
**症状**: 初回アクセス時に30秒以上かかる

**原因**: Renderの無料プランは15分間アクセスがないとスリープ

**解決**:
- 本番運用の場合は Starter プラン（$7/月）にアップグレード
- または、定期的にヘルスチェックを実行（外部監視サービス使用）

---

## ステップ6: カスタムドメイン設定（オプション）

### 6.1 Vercel（フロントエンド）
1. Vercel Dashboard → プロジェクト → Settings → Domains
2. カスタムドメインを追加（例: shift.example.com）
3. DNSレコードを設定:
   ```
   Type: CNAME
   Name: shift
   Value: cname.vercel-dns.com
   ```

### 6.2 Render（バックエンド）
1. Render Dashboard → サービス → Settings → Custom Domains
2. カスタムドメインを追加（例: api.example.com）
3. DNSレコードを設定:
   ```
   Type: CNAME
   Name: api
   Value: nurse-shift-api.onrender.com
   ```

### 6.3 環境変数の更新
**Render**:
```bash
ALLOWED_ORIGINS=https://shift.example.com
```

**Vercel**:
```bash
NEXT_PUBLIC_API_BASE=https://api.example.com
```

---

## 📊 コスト見積もり

### 開発・テスト環境
```
Render Free: $0/月
Vercel Hobby: $0/月
合計: $0/月
```

### 本番環境（小規模）
```
Render Starter: $7/月（512MB RAM、0.5 CPU）
Vercel Hobby: $0/月
合計: $7/月
```

### 本番環境（中規模）
```
Render Standard: $25/月（2GB RAM、1 CPU）
Vercel Pro: $20/月（チーム機能、優先ビルド）
合計: $45/月
```

---

## 🔄 継続的デプロイ（CI/CD）

### 自動デプロイ設定済み
- **main** ブランチへのプッシュ → 自動デプロイ
- **プルリクエスト** → プレビューデプロイ（Vercel）

### GitHub Actions（推奨）
将来的にテスト自動実行を追加:
```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Test Backend
        run: |
          cd api
          pip install -r requirements.txt
          pytest
```

---

## 🔒 セキュリティチェックリスト

デプロイ前に確認:
- [ ] 環境変数にシークレットが含まれていない（.env.example参照）
- [ ] ALLOWED_ORIGINS がワイルドカード（*）でない（本番）
- [ ] HTTPS通信が有効（Vercel/Render自動）
- [ ] APIレート制限を検討（将来）
- [ ] 認証・認可を検討（将来）

---

## 📈 次のステップ

### Phase 2: データベース導入
1. Supabase アカウント作成
2. PostgreSQL データベース作成
3. 看護師台帳の永続化
4. シフト履歴の保存

### Phase 3: 認証機能
1. Supabase Auth 設定
2. ユーザーログイン画面
3. 権限管理（管理者/一般）

### Phase 4: 監視・アラート
1. Sentry 導入（エラートラッキング）
2. Uptime Robot（稼働監視）
3. Google Analytics（アクセス解析）

---

## 💡 よくある質問（FAQ）

### Q1: デプロイにどれくらい時間がかかる？
**A**: 初回は約30分（Render 10分 + Vercel 5分 + 設定 15分）

### Q2: 無料プランで本番運用できる？
**A**: 小規模（月間アクセス < 1000）なら可能。ただし、Render Freeはスリープするため、レスポンスが遅い。

### Q3: 独自ドメインは必須？
**A**: いいえ。VercelとRenderの無料サブドメインでも十分。

### Q4: データはどこに保存される？
**A**: 現状はファイルベース（永続化なし）。Phase 2でSupabase導入予定。

### Q5: スケールアップの方法は？
**A**: RenderのプランをStarter → Standardに変更。Vercelは自動スケール。

---

## 🆘 サポート

問題が発生した場合:
1. Render Logs を確認: Dashboard → サービス → Logs
2. Vercel Logs を確認: Dashboard → プロジェクト → Deployments → View Function Logs
3. GitHub Issues で報告

**デバッグコマンド**:
```bash
# ローカルでビルドテスト
cd frontend && npm run build
cd api && docker build -t test .
```

---

**✅ デプロイ完了おめでとうございます！**

次は TECH_STACK.md の「Phase 2: データ永続化」に進んでください。

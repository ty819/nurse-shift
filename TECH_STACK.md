# 看護師シフト自動割当 - 技術スタック & デプロイ戦略

## 📋 現在の技術スタック

### フロントエンド
```json
{
  "framework": "Next.js 14.2.7",
  "runtime": "React 18.3.1",
  "language": "TypeScript",
  "styling": "CSS Modules + CSS Variables",
  "build": "Next.js Static/SSR Hybrid",
  "node": "v24.3.0",
  "npm": "11.4.2"
}
```

**特徴:**
- App Router採用（Next.js 14）
- レスポンシブデザイン（デスクトップ・iPad・モバイル対応）
- CSS Modules によるスコープ化されたスタイル
- タッチフレンドリーUI（最小タッチターゲット: 44px）

### バックエンド
```python
# requirements.txt
fastapi==0.115.0          # 高速APIフレームワーク
uvicorn[standard]==0.30.6  # ASGIサーバー
pydantic==2.8.2           # データバリデーション
ortools==9.10.4067        # 最適化エンジン（CP-SAT）
pandas==2.2.2             # データ処理
reportlab==4.2.2          # PDF生成
python-multipart==0.0.9   # ファイルアップロード
jsonschema==4.23.0        # スキーマ検証
pytest==8.3.2             # テスト
```

**特徴:**
- FastAPI による高速REST API
- OR-Tools (CP-SAT) による制約充足問題の最適化
- Docker コンテナ化済み（Python 3.12-slim）
- ヘルスチェック対応（/docs エンドポイント）

### データストレージ
- **現状**: ファイルベース（No-DB）
- **入力**: CSV（看護師台帳）、JSON（月次ルール）
- **出力**: JSON（シフト表）、PDF、CSV

---

## 🚀 推奨デプロイ戦略

### ✅ **最適解: Vercel (Frontend) + Render (Backend)**

#### なぜこの構成？

1. **フロントエンド: Vercel**
   - Next.jsの開発元が提供（最高の互換性）
   - 自動CDN配信・エッジキャッシング
   - 自動HTTPS・カスタムドメイン
   - GitHub連携で自動デプロイ
   - **無料枠**: Hobby Plan（個人プロジェクト十分）

2. **バックエンド: Render**
   - Dockerネイティブサポート
   - 自動HTTPS・ヘルスチェック
   - 簡単な環境変数管理
   - GitHub連携で自動デプロイ
   - **無料枠**: Free Plan（制限あり、本番はStarter $7/月）

3. **コストパフォーマンス**
   ```
   開発・検証: 無料（両方の無料枠）
   本番運用:   $7/月（Render Starter）+ Vercel無料枠
   ```

---

## 📦 デプロイ手順（推奨構成）

### 1. バックエンド（Render）

**事前準備:**
```bash
# リポジトリをGitHubにプッシュ
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/nurse-shift.git
git push -u origin main
```

**Render設定:**
1. [Render Dashboard](https://dashboard.render.com/) にログイン
2. "New Web Service" をクリック
3. GitHubリポジトリを接続
4. 設定:
   ```yaml
   Name: nurse-shift-api
   Environment: Docker
   Region: Singapore（日本に最も近い）
   Branch: main
   Root Directory: api
   Docker Command: 既存のDockerfile使用
   Plan: Free（開発）/ Starter（本番）
   ```
5. 環境変数:
   ```
   ALLOWED_ORIGINS=https://YOUR-FRONTEND-URL.vercel.app
   PYTHONPATH=/app
   ```
6. "Create Web Service" → 自動ビルド開始
7. デプロイ完了後、URLをメモ: `https://nurse-shift-api.onrender.com`

### 2. フロントエンド（Vercel）

**Vercel設定:**
1. [Vercel Dashboard](https://vercel.com/dashboard) にログイン
2. "Add New Project" → GitHubリポジトリをインポート
3. 設定:
   ```
   Framework Preset: Next.js
   Root Directory: frontend
   Build Command: npm run build
   Output Directory: .next
   Install Command: npm install
   ```
4. 環境変数:
   ```
   NEXT_PUBLIC_API_BASE=https://nurse-shift-api.onrender.com
   ```
5. "Deploy" → 自動ビルド開始
6. デプロイ完了後、URL取得: `https://nurse-shift-xxx.vercel.app`

### 3. CORS設定の更新

**バックエンド（Render）の環境変数を更新:**
```
ALLOWED_ORIGINS=https://nurse-shift-xxx.vercel.app
```

---

## 🔄 代替デプロイオプション

### オプション2: Render フルスタック
**構成**: Frontend (Static) + Backend (Web Service)

**メリット**:
- 一元管理（同じプラットフォーム）
- シンプルな請求
- 同一リージョンで低レイテンシ

**デメリット**:
- フロントエンドのCDN性能がVercelに劣る
- Next.jsのEdge機能が使えない

**コスト**: $7/月（Starter） × 2 = $14/月

### オプション3: AWS フルスタック
**構成**: S3+CloudFront (Frontend) + ECS/Lambda (Backend)

**メリット**:
- 最高のスケーラビリティ
- 豊富なAWSサービス連携

**デメリット**:
- 設定複雑（IAM、VPC、ALB等）
- コスト予測が難しい
- 運用コスト高

**コスト**: 最低 $20-50/月

### オプション4: Google Cloud Run
**構成**: Both in Cloud Run Containers

**メリット**:
- コンテナベース（統一環境）
- オートスケーリング
- 従量課金（使った分だけ）

**デメリット**:
- Next.jsのStatic最適化が活かせない
- 初回起動が遅い（コールドスタート）

**コスト**: 従量課金（低トラフィック: $5-15/月）

---

## 🎯 推奨構成の理由（再確認）

### Vercel + Render を選ぶべき理由:

1. **開発者体験**: 両方ともGit連携で自動デプロイ
2. **パフォーマンス**: Next.jsはVercelで最高性能、バックエンドは地理的に近い
3. **コスト**: 開発は無料、本番は$7/月から
4. **拡張性**: トラフィック増加時は簡単にプラン変更可能
5. **保守性**: シンプルな構成、複雑なインフラ管理不要

### デプロイ後の確認ポイント:
- [ ] フロントエンドがAPIに接続できる（CORS設定）
- [ ] 最適化APIが正常に動作（/optimize/default-md）
- [ ] PDF/CSV出力が正常に動作
- [ ] レスポンシブデザインが全デバイスで動作
- [ ] HTTPS通信が確立されている

---

## 🔧 環境変数の完全リスト

### フロントエンド（Vercel）
```bash
NEXT_PUBLIC_API_BASE=https://nurse-shift-api.onrender.com
```

### バックエンド（Render）
```bash
ALLOWED_ORIGINS=https://nurse-shift-xxx.vercel.app
PYTHONPATH=/app
HOST=0.0.0.0
PORT=10000
```

---

## 📊 パフォーマンス最適化

### すでに実装済み:
- ✅ Next.js Static Generation（ビルド時最適化）
- ✅ CSS Modules（スコープ化、Tree Shaking）
- ✅ Docker Multi-stage Build準備済み
- ✅ レスポンシブ画像・フォント最適化

### 今後の最適化提案:
- [ ] Redis導入（セッション・キャッシュ管理）
- [ ] Database導入（Supabase/PostgreSQL）
  - 看護師台帳の永続化
  - シフト履歴の保存
  - ユーザー認証・権限管理
- [ ] WebSocket（リアルタイム更新）
- [ ] 画像最適化（next/image使用）

---

## 🔒 セキュリティ対策

### 現在の対策:
- ✅ CORS設定（ALLOWED_ORIGINS）
- ✅ HTTPS通信（Vercel/Render自動）
- ✅ 環境変数による設定管理
- ✅ Dockerコンテナ分離

### 本番運用前に追加すべき:
- [ ] レート制限（API呼び出し制限）
- [ ] 認証・認可（JWT/OAuth）
- [ ] CSP（Content Security Policy）
- [ ] APIキー管理
- [ ] 監査ログ

---

## 📈 モニタリング・ログ

### Vercel（標準機能）:
- アクセスログ
- ビルドログ
- パフォーマンス分析

### Render（標準機能）:
- アプリケーションログ
- メトリクス（CPU/メモリ）
- ヘルスチェック

### 追加推奨:
- Sentry（エラートラッキング）
- LogRocket（ユーザーセッション記録）
- Datadog/New Relic（APM）

---

## ⚡ クイックスタート（ローカル開発）

### バックエンド起動:
```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### フロントエンド起動:
```bash
cd frontend
npm install
export NEXT_PUBLIC_API_BASE="http://localhost:8000"
npm run dev
```

ブラウザ: http://localhost:3000

---

## 🎓 次のステップ

1. **Phase 1: デプロイ**（現在）
   - Render + Vercel構成でデプロイ
   - 基本動作確認

2. **Phase 2: データ永続化**
   - Supabase導入（PostgreSQL + 認証）
   - 看護師台帳・シフト履歴の保存

3. **Phase 3: 機能拡張**
   - ユーザー認証・権限管理
   - シフト編集履歴・承認フロー
   - 通知機能（メール/Slack）

4. **Phase 4: スケール対応**
   - Redis キャッシュ
   - CDN最適化
   - パフォーマンス監視

---

## 💡 まとめ

**推奨デプロイ構成**: Vercel (Frontend) + Render (Backend)

**理由**:
- ✅ 開発者体験が最高
- ✅ コストパフォーマンスが優秀
- ✅ スケーラブル
- ✅ 保守が簡単

**コスト**:
- 開発: 無料
- 本番: $7/月〜

**デプロイ時間**: 約30分（両方合わせて）

**次のアクション**:
1. GitHubリポジトリ作成
2. Renderでバックエンドデプロイ
3. Vercelでフロントエンドデプロイ
4. 動作確認
5. カスタムドメイン設定（オプション）

# 看護師シフト自動割当 Web アプリ

**OR-Tools (CP-SAT) による制約充足問題の最適化を使用した看護師シフト自動生成システム**

[![Next.js](https://img.shields.io/badge/Next.js-14.2.7-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🎯 概要

病棟看護師（20〜30名規模）の月間シフトを自動生成するWebアプリケーション。
個々の看護師の勤務条件（夜勤回数、週上限、土日祝制限等）を厳守しながら、
日勤・夜勤の必要人数を充足する最適なシフトを生成します。

### 主な機能
- ✅ **自動最適化**: OR-Toolsによる制約充足問題の解決
- 📊 **複数案生成**: 最大10案の代替シフトを比較
- 🖊️ **手動編集**: セルをロックして再最適化
- 📱 **レスポンシブ**: デスクトップ・iPad・モバイル対応
- 📄 **エクスポート**: PDF・CSV出力
- ⚠️ **違反検出**: リアルタイムで制約違反を表示
- 💡 **補充推奨**: 不足時の候補を自動提示

---

## 🏗️ アーキテクチャ

### フロントエンド
- **Framework**: Next.js 14.2.7 (App Router)
- **Language**: TypeScript
- **Styling**: CSS Modules + CSS Variables
- **State**: React Hooks（useState, useMemo）

### バックエンド
- **Framework**: FastAPI 0.115.0
- **Optimizer**: OR-Tools 9.10.4067 (CP-SAT)
- **Data Processing**: Pandas 2.2.2
- **PDF Export**: ReportLab 4.2.2
- **Runtime**: Python 3.12

### デプロイ
- **Frontend**: Vercel（推奨）
- **Backend**: Render（推奨）
- **Container**: Docker

詳細は [TECH_STACK.md](./TECH_STACK.md) を参照

---

## 🚀 クイックスタート

### 必要環境
- Node.js 20.x 以上
- Python 3.12 以上
- npm 11.x 以上

### ローカル開発

#### 1. リポジトリのクローン
```bash
git clone https://github.com/YOUR_USERNAME/nurse-shift.git
cd nurse-shift
```

#### 2. バックエンドの起動
```bash
cd api
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
→ バックエンドAPI: http://localhost:8000/docs

#### 3. フロントエンドの起動（別ターミナル）
```bash
cd frontend
npm install
export NEXT_PUBLIC_API_BASE="http://localhost:8000"  # Windows: set NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev
```
→ フロントエンド: http://localhost:3000

---

## 📖 使い方

### 基本フロー

1. **対象月の選択**
   - 月選択フォームで対象年月を指定
   - 案数（alternatives）を設定（1〜10）

2. **最適化実行**
   - 「既存条件で最適化」ボタンをクリック
   - `shift.md` の条件に基づいてシフトを自動生成

3. **結果の確認**
   - シフト表が表示される
   - 個人サマリ・日別充足状況を確認
   - 違反・警告を確認

4. **手動調整（必要に応じて）**
   - セルをクリックしてシフトを変更
   - 変更したセルは自動的にロック
   - ロック条件を保持したまま再最適化

5. **エクスポート**
   - 「CSV出力」または「PDF出力」でファイル取得

### 詳細な使い方
詳細は [purpose.md](./purpose.md) と [shift.md](./shift.md) を参照

---

## 🌐 本番デプロイ

### 推奨構成: Vercel (Frontend) + Render (Backend)

#### デプロイ手順（30分で完了）
1. GitHubリポジトリにプッシュ
2. Renderでバックエンドをデプロイ
3. Vercelでフロントエンドをデプロイ
4. 環境変数を設定

詳細な手順は [DEPLOYMENT.md](./DEPLOYMENT.md) を参照

#### コスト
- **開発**: 無料（両方の無料プラン）
- **本番**: $7/月〜（Render Starter + Vercel Hobby）

---

## 📂 プロジェクト構成

```
nurse-shift/
├── frontend/              # Next.jsフロントエンド
│   ├── app/
│   │   ├── page.tsx      # メインページ
│   │   ├── page.module.css
│   │   ├── globals.css
│   │   └── layout.tsx
│   ├── package.json
│   └── vercel.json       # Vercelデプロイ設定
│
├── api/                   # FastAPIバックエンド
│   ├── app/
│   │   ├── main.py       # FastAPIエントリーポイント
│   │   ├── optimizer.py  # OR-Tools最適化ロジック
│   │   ├── validator.py  # 制約検証
│   │   └── exporter.py   # PDF/CSV出力
│   ├── requirements.txt
│   ├── Dockerfile        # Dockerコンテナ定義
│   └── render.yaml       # Renderデプロイ設定
│
├── samples/               # サンプルデータ
│   ├── nurses.csv        # 看護師台帳サンプル
│   └── rules.json        # 月次ルールサンプル
│
├── packages/schemas/      # JSON Schema定義
│
├── TECH_STACK.md         # 技術スタック詳細
├── DEPLOYMENT.md         # デプロイガイド
├── purpose.md            # 要件定義
├── shift.md              # 現場ルール
└── README.md             # このファイル
```

---

## 🧪 テスト

### バックエンドテスト
```bash
cd api
pytest
```

### フロントエンドビルドテスト
```bash
cd frontend
npm run build
```

---

## 🔧 技術スタック詳細

### 最適化エンジン（OR-Tools）
- **アルゴリズム**: CP-SAT（制約充足問題ソルバー）
- **ハード制約**: 必要人数、夜勤回数、週上限、夜勤翌日休み等
- **ソフト制約**: 公平性、連勤制限、希望休等

### UI/UX設計
- **デザインシステム**: CSS Variables による統一カラーパレット
- **レスポンシブ**: モバイルファースト、タッチフレンドリー
- **アクセシビリティ**: キーボード操作、高コントラスト

詳細は [TECH_STACK.md](./TECH_STACK.md) を参照

---

## 📊 制約仕様

### ハード制約（必須）
- 各日・各シフトの必要人数充足
- 夜勤チーム構成（A/B/救急の混成）
- 夜勤翌日の日勤不可
- 個人の夜勤回数範囲
- 週当たり勤務上限
- 土日祝制限
- 組合せ禁止ルール

### ソフト制約（ペナルティ最小化）
- 夜勤・週末の偏り
- 連続夜勤の抑制
- 希望休の尊重

詳細は [shift.md](./shift.md) を参照

---

## 🛠️ トラブルシューティング

### よくある問題

#### Q1: フロントエンドからAPIに接続できない
**A**: 環境変数 `NEXT_PUBLIC_API_BASE` が正しく設定されているか確認

```bash
# frontend/.env.local
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

#### Q2: ビルドエラー "Cannot find module './819.js'"
**A**: `.next` キャッシュをクリア

```bash
cd frontend
rm -rf .next
npm run build
```

#### Q3: 最適化が "不可解" になる
**A**: 制約が厳しすぎる可能性。以下を確認:
- 看護師台帳の人数が十分か
- 夜勤可能な看護師が必要人数以上いるか
- 個別条件が矛盾していないか

---

## 🗺️ ロードマップ

### Phase 1: デプロイ（完了）
- ✅ UI/UXブラッシュアップ
- ✅ レスポンシブ対応
- ✅ デプロイ設定

### Phase 2: データ永続化（次）
- [ ] Supabase導入（PostgreSQL）
- [ ] 看護師台帳の保存
- [ ] シフト履歴の管理

### Phase 3: 認証・権限管理
- [ ] ユーザーログイン
- [ ] 管理者/一般の権限分離
- [ ] シフト承認フロー

### Phase 4: 機能拡張
- [ ] 希望休申請UI
- [ ] Slack/メール通知
- [ ] シフト変更履歴
- [ ] A/Bテスト機能

---

## 📝 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照

---

## 🤝 コントリビューション

プルリクエスト歓迎！以下の手順でお願いします:

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

---

## 📧 サポート

- 問題報告: [GitHub Issues](https://github.com/YOUR_USERNAME/nurse-shift/issues)
- ドキュメント: [Wiki](https://github.com/YOUR_USERNAME/nurse-shift/wiki)
- 技術スタック: [TECH_STACK.md](./TECH_STACK.md)
- デプロイガイド: [DEPLOYMENT.md](./DEPLOYMENT.md)

---

## 🙏 謝辞

- [OR-Tools](https://developers.google.com/optimization) - Google Optimization Tools
- [FastAPI](https://fastapi.tiangolo.com/) - 高速APIフレームワーク
- [Next.js](https://nextjs.org/) - Reactフレームワーク
- [Vercel](https://vercel.com/) - フロントエンドホスティング
- [Render](https://render.com/) - バックエンドホスティング

---

**Made with ❤️ for better nurse scheduling**


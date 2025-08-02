# Civitai API公式ドキュメント

このディレクトリには、Civitai公式WikiからダウンロードしたAPI仕様書および関連ドキュメントを格納しています。

## ファイル構成

### API仕様書
- **`REST-API-Reference.md`** - Civitai REST API v1の完全な仕様書
  - 認証方法（APIキー）
  - 全エンドポイントの詳細仕様
  - リクエスト/レスポンス形式

### 関連ドキュメント
- **`AIR-‐-Uniform-Resource-Names-for-AI.md`** - AIリソース統一命名規則
- **`Civitai-Link-Integration.md`** - Civitai Link統合ガイド  
- **`How-to-use-models.md`** - モデル使用方法ガイド
- **`Image-Reproduction.md`** - 画像再現ガイド
- **`Model-Safety-Checks.md`** - モデルセーフティチェック仕様

## 主要API仕様概要

### 認証
```
Authorization: Bearer {api_key}
```

### 主要エンドポイント
- `GET /api/v1/models` - モデル一覧取得
- `GET /api/v1/models/{modelId}` - 特定モデル情報取得
- `GET /api/v1/model-versions/{versionId}` - バージョン情報取得
- `GET /api/v1/model-versions/by-hash/{hash}` - ハッシュによるバージョン検索
- `GET /api/v1/images` - 画像一覧取得
- `GET /api/v1/creators` - クリエイター情報取得
- `GET /api/v1/tags` - タグ一覧取得

## 更新について
これらのドキュメントは以下のリポジトリから取得されました：
- ソース: https://github.com/civitai/civitai.wiki.git
- 最終更新: 2025年7月14日

最新情報については、上記リポジトリを確認してください。

## 実装時の参考
- ダウンローダー実装時は`REST-API-Reference.md`を主に参照
- セキュリティ考慮事項は`Model-Safety-Checks.md`を参照
- AIR識別子については`AIR-‐-Uniform-Resource-Names-for-AI.md`を参照
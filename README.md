# Civitai Downloader CLI

CivitaiのAIモデルとイメージを高速・安定的に一括ダウンロードするCLIツール

## 🚀 特徴

- **高速並列ダウンロード**: 最大3モデルを同時並列処理、大幅な時間短縮を実現
- **タグベース自動整理**: モデルをCONCEPT、CHARACTER、STYLE、POSEなどのタグで自動分類
- **ベースモデルフィルタリング**: Illustrious、Pony、SDXLなど特定のベースモデルのみをダウンロード
- **ユーザー一括ダウンロード**: 指定ユーザーの全モデル・画像を自動取得
- **スキップ機能**: 既存ファイルをスキップして差分ダウンロード
- **SHA256検証**: ファイル整合性を自動チェック
- **レート制限対応**: Civitai APIの制限を自動的に考慮
- **NSFW対応**: NSFWコンテンツも含めて完全ダウンロード

## 📋 必要要件

- Python 3.10以降
- Civitai APIキー（[取得方法](#apiキーの取得方法)）
- 十分なディスク容量（モデルファイルは数GB以上になる場合があります）

## 💾 インストール

### 基本インストール
```bash
git clone https://github.com/yourusername/civitai_downloader_cli.git
cd civitai_downloader_cli
pip install -e .
```

### 開発環境セットアップ
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .[dev]
```

## 🔧 使い方

### 基本的な使用例

#### 1. 単一ユーザーのモデルをダウンロード
```bash
# テストモードで実行（./test_downloads/に保存）
python -m civitai_dl --user bolero537 --test-mode

# 本番環境にダウンロード
python -m civitai_dl --user bolero537 --token YOUR_API_KEY

# 高速並列モードで実行（推奨）
python -m civitai_dl --user bolero537 --parallel-mode --token YOUR_API_KEY
```

#### 2. 複数ユーザーを一括ダウンロード
```bash
# user.txtファイルから複数ユーザーを順次ダウンロード
python -m civitai_dl --user-list user.txt --parallel-mode --skip-existing
```

#### 3. ベースモデルでフィルタリング
```bash
# IllustriousとPonyモデルのみダウンロード
python -m civitai_dl --user bolero537 --parallel-mode --base-model-filter model_filter_white_list.txt

# Illustriousモデルのみ
python -m civitai_dl --user bolero537 --parallel-mode --base-model-filter model_filter_illustrious_only.txt
```

#### 4. 特定モデルIDを指定してダウンロード
```bash
python -m civitai_dl --model 123456 --parallel-mode
```

### コマンドラインオプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--user, -u` | Civitaiユーザー名 | - |
| `--user-list` | ユーザーリストファイル | - |
| `--model, -m` | 特定のモデルID | - |
| `--token, -t` | Civitai APIトークン | 環境変数から取得 |
| `--output, -o` | 出力ディレクトリ | `H:\Civitai\civitai-models` |
| `--test-mode` | テストモード（`./test_downloads/`に保存） | False |
| `--parallel-mode` | 高速並列処理モード（推奨） | False |
| `--skip-existing` | 既存ファイルをスキップ | False |
| `--base-model-filter` | ベースモデルフィルターファイル | - |
| `--max-images` | ユーザー画像の最大ダウンロード数 | 1000 |
| `--verbose, -v` | 詳細ログ出力 | False |

## 📁 フォルダ構造

ダウンロードされたファイルは以下の構造で整理されます：

```
出力ディレクトリ/
├── models/
│   ├── Illustrious/              # ベースモデル別
│   │   ├── CONCEPT/               # タグカテゴリ別
│   │   │   └── username_modelname_version/
│   │   │       ├── description.md
│   │   │       ├── model.civitai.info
│   │   │       ├── model.safetensors
│   │   │       ├── preview_1.jpeg
│   │   │       └── Gallery/
│   │   │           └── *.jpeg
│   │   ├── CHARACTER/
│   │   ├── STYLE/
│   │   └── POSE/
│   ├── Pony/
│   ├── SDXL 1.0/
│   └── SD 1.5/
└── images/
    └── username/
        ├── images_metadata.json
        └── *.jpeg
```

## 🔐 APIキーの設定

### APIキーの取得方法

1. [Civitai.com](https://civitai.com) にログイン
2. アカウント設定を開く
3. API Keys セクションを探す
4. 新しいAPIキーを生成
5. キーをコピー

### APIキーの設定方法（3つの方法）

#### 方法1: 環境変数（推奨）
```bash
export CIVITAI_API_KEY=your_api_key_here
```

#### 方法2: api_key.mdファイル
```bash
echo "your_api_key_here" > api_key.md
```

#### 方法3: コマンドライン引数
```bash
python -m civitai_dl --user username --token your_api_key_here
```

## 📝 設定ファイルの書き方

### user.txt（ユーザーリスト）
```
https://civitai.com/user/bolero537
https://civitai.com/user/IceCycle123
https://civitai.com/user/Fandingo

# コメント行は#で始める
# URLまたはユーザー名のみでもOK
username1
username2
```

### model_filter_white_list.txt（ベースモデルフィルター）
```
# IllustriousとPonyモデルのみダウンロード
Illustrious
Pony

# 大文字小文字は区別しない
# 部分一致でフィルタリング
```

### models.txt（モデルURLリスト）
```
# 特定のモデルをダウンロードする場合
https://civitai.com/models/123456/model-name
https://civitai.com/models/789012
123456  # モデルIDのみでもOK
```

## ⚡ パフォーマンス設定

### 並列処理モード

- **標準モード**: 安定性重視、順次ダウンロード
- **並列モード** (`--parallel-mode`): 最大3モデル同時ダウンロード、約3倍高速

```bash
# 高速並列モード（推奨）
python -m civitai_dl --user-list user.txt --parallel-mode --skip-existing
```

### メモリ使用量の調整

大規模なダウンロードではメモリ使用量が増加する場合があります。必要に応じて調整してください。

## 🐛 トラブルシューティング

### よくある問題と解決方法

#### 1. "User not found" エラー
- ユーザー名が正しいか確認
- `--user-list`と`--user`を間違えていないか確認

#### 2. APIキーエラー
- APIキーが正しく設定されているか確認
- 環境変数 `CIVITAI_API_KEY` を確認

#### 3. ダウンロードが遅い
- `--parallel-mode` オプションを使用
- インターネット接続を確認

#### 4. ディスク容量不足
- 出力ディレクトリの空き容量を確認
- `--base-model-filter` で必要なモデルのみダウンロード

## 🔧 開発者向け情報

### アーキテクチャ

- **非同期処理**: aiohttpによる高速HTTP通信
- **並列制御**: ThreadPoolExecutorによるマルチスレッド処理
- **適応的並列度調整**: エラー率に応じた自動調整
- **フォールバック機構**: エラー時の自動復旧

### テスト実行

```bash
# 単体テスト
pytest tests/ -v

# カバレッジレポート
pytest tests/ --cov=civitai_dl --cov-report=html

# 静的解析
ruff check .
mypy .
black --check .
```

### 貢献方法

1. このリポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## 📄 ライセンス

MIT License - 詳細は[LICENSE](LICENSE)ファイルを参照

## 🙏 謝辞

- Civitai.com - 素晴らしいAIモデル共有プラットフォームの提供
- コントリビューター - バグ報告と改善提案

## 📮 サポート

問題が発生した場合は、[Issues](https://github.com/yourusername/civitai_downloader_cli/issues)で報告してください。

---

**注意**: このツールを使用する際は、Civitaiの利用規約とレート制限を遵守してください。大量ダウンロードは責任を持って行ってください。
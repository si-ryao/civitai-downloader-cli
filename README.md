# Civitai Downloader CLI

CivitaiのAIモデルとイメージを高速・安定的に一括ダウンロードするCLIツール

## インストール方法

```bash
git clone https://github.com/si-ryao/civitai-downloader-cli.git
cd civitai-downloader-cli
pip install -e .
```

## APIキーの設定方法

### 1. Civitai APIキーを取得
1. [Civitai.com](https://civitai.com) にログイン
2. アカウント設定 → API Keys
3. 新しいAPIキーを生成・コピー

### 2. api_key.mdファイルを作成
```bash
echo "your_api_key_here" > api_key.md
```

## デフォルト出力ディレクトリの設定

### default_output_dir.txtファイルを作成
次のように記載すれば、DドライブのCivitaiModelsフォルダにダウンロードが格納される
```
D:\CivitaiModels
```

**重要**: このファイルがない場合、`./downloads`フォルダに保存されます

## 出力ディレクトリの指定方法

コマンド実行時に出力先を変更できます：

```bash
# 一時的に別のディレクトリに保存
python -m civitai_dl --user username --output "E:\TempDownloads" --parallel-mode

# テストモード（./test_downloads/に保存）
python -m civitai_dl --user username --test-mode --parallel-mode
```

## ベースモデルフィルタの使い方

### フィルターファイルを作成
```bash
# model_filter_my_models.txt
Illustrious
Pony
SDXL
```

### フィルターを適用してダウンロード
```bash
python -m civitai_dl --user username --parallel-mode --base-model-filter model_filter_white_list.txt
```

**提供済みフィルター例**:
- `model_filter_white_list.txt` - Illustrious + Pony。任意に書き換え可能

## 高速並列モードの実行

**必ず`--parallel-mode`オプションを使用してください（約3倍高速）**

```bash
# 基本の高速実行
python -m civitai_dl --user username --parallel-mode

# 既存ファイルをスキップして高速実行
python -m civitai_dl --user username --parallel-mode --skip-existing
```

## ユーザーリスト・モデルリストダウンロード

### ユーザーリスト（user.txt）の書き方
```
# user.txt
https://civitai.com/user/bolero537
https://civitai.com/user/IceCycle123
Fandingo

# コメント行は#で始める
# URLまたはユーザー名のみでもOK
```

### ユーザーリストを使用
```bash
python -m civitai_dl --user-list user.txt --parallel-mode --skip-existing
```

### モデルリスト（models.txt）の書き方
```
# models.txt
https://civitai.com/models/123456/model-name
https://civitai.com/models/789012
123456

# モデルURLまたはIDを指定
```

### モデルリストを使用
```bash
python -m civitai_dl --model-list models.txt --parallel-mode
```

## コマンドラインオプション

| オプション | 説明 |
|-----------|------|
| `--user username` | 特定ユーザーのモデルをダウンロード |
| `--user-list file.txt` | ユーザーリストファイルを使用 |
| `--model 123456` | 特定モデルIDをダウンロード |
| `--model-list file.txt` | モデルリストファイルを使用 |
| `--parallel-mode` | **高速並列処理（推奨）** |
| `--skip-existing` | 既存ファイルをスキップ |
| `--base-model-filter file.txt` | ベースモデルでフィルタリング |
| `--output "path"` | 出力ディレクトリを指定 |
| `--test-mode` | テストモード（./test_downloads/に保存） |
| `--max-images 1000` | ユーザー画像の最大ダウンロード数 |
| `--token your_key` | APIキーを直接指定 |
| `--verbose` | 詳細ログ表示 |

## 使用例

```bash
# 基本的な使用方法
python -m civitai_dl --user bolero537 --parallel-mode

# フィルター + スキップ機能で高速実行
python -m civitai_dl --user-list user.txt --parallel-mode --skip-existing --base-model-filter model_filter_white_list.txt

# 出力先を指定
python -m civitai_dl --user username --parallel-mode --output "D:\MyModels"

# テストモードで動作確認
python -m civitai_dl --user username --test-mode --parallel-mode --verbose
```

## ダウンロードされるファイル構造

```
出力ディレクトリ/
├── models/
│   ├── Illustrious/
│   │   ├── CONCEPT/
│   │   │   └── username_modelname_version/
│   │   │       ├── description.md
│   │   │       ├── model.safetensors
│   │   │       └── Gallery/
│   │   └── CHARACTER/
│   └── Pony/
└── images/
    └── username/
        └── *.jpeg
```

---

**注意**: 大量ダウンロードは責任を持って行い、Civitaiの利用規約を遵守してください。
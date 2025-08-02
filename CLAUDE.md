# CLAUDE.md

このファイルは、このリポジトリでコード作業を行う際のClaude Code (claude.ai/code) へのガイダンスを提供します。

## プロジェクト概要

CivitaiのAIモデルとイメージを大量・高速・安定してダウンロードするCLIツールです。数百〜数千のモデルを効率的に処理し、失敗時の自動再試行、進捗表示、NSFW対応などの機能を提供します。

### アーキテクチャ方針

**高速版**: 非同期I/O（aiohttp）による最大性能を発揮する構成
**シンプル版**: 同期HTTP（requests）+ ThreadPoolによる保守性重視構成

どちらの構成でも共通インターフェースを維持し、用途に応じて選択可能です。

## 開発環境とツールチェーン

### 必須要件
- Python 3.10以降
- Civitai APIキー（環境変数`CIVITAI_API_KEY`でも可）

### 主要依存ライブラリ
```python
# 高速版
aiohttp      # 非同期HTTP通信
tenacity     # 再試行制御
tqdm         # プログレスバー
rich         # コンソール出力
pydantic     # データ検証

# シンプル版
requests     # 同期HTTP通信
tqdm         # プログレスバー  
backoff      # 再試行制御（または手書きループ）
```

### 開発ツール設定
```bash
# 静的解析・フォーマット
pip install ruff mypy black

# テスト関連
pip install pytest pytest-asyncio pytest-httpx responses freezegun

# CI/CD前提のコマンド
ruff check .                # リンティング
mypy .                      # 型チェック
black --check .             # フォーマット確認
pytest tests/ -v --cov=civitai_dl --cov-report=html
```

## コーディング標準とベストプラクティス

### Python基本規約
- **PEP8準拠必須**: `black`による自動フォーマット
- **型ヒント必須**: すべての関数・メソッドに型注釈を付与
- **1ファイル400行制限**: 超過時は機能単位で分割
- **docstring必須**: パブリック関数・クラスにはGoogle Style

```python
async def download_model(
    model_id: int, 
    output_dir: Path, 
    api_client: ApiClient
) -> DownloadResult:
    """指定されたモデルをダウンロードする.
    
    Args:
        model_id: CivitaiモデルID
        output_dir: 保存先ディレクトリ
        api_client: API通信クライアント
        
    Returns:
        ダウンロード結果（成功/失敗情報含む）
        
    Raises:
        ApiError: API通信エラー時
        StorageError: ファイル保存エラー時
    """
```

### 非同期プログラミングパターン
```python
# セマフォによる並列制御（最大2本の同時ダウンロード）
sem_model = asyncio.Semaphore(1)
sem_gallery = asyncio.Semaphore(1)

async def process_models():
    tasks = [
        model_worker(model_queue, sem_model),
        gallery_worker(gallery_queue, sem_gallery),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
```

### エラーハンドリングと再試行ロジック
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=64),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
)
async def fetch_with_retry(url: str) -> dict:
    """指数バックオフによる再試行付きHTTPリクエスト"""
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        return await resp.json()
```

### ファイル命名規則
```
civitai_dl/
├── __init__.py          # パッケージエントリポイント
├── cli.py               # CLI引数解析・メイン処理
├── config.py            # 設定管理（pydantic.BaseSettings）
├── scheduler.py         # タスク生成・キュー管理
├── worker.py            # 非同期ワーカー実装
├── adapters/            # 外部システム境界
│   ├── api_client.py    # Civitai API通信
│   └── storage.py       # ファイルシステム操作
├── domain/              # ビジネスロジック
│   ├── model_entity.py  # データクラス定義
│   └── services.py      # ユースケース実装
└── utils/               # 共通ユーティリティ
    ├── fs.py            # ファイル操作
    └── progress.py      # 進捗表示
```

## アーキテクチャガイドライン

### Clean Architecture適用
```python
# 依存関係の方向: 上位 → 下位へ一方向
CLI → Services → Repositories → External APIs
     ↓         ↓              ↓
   Domain ← Entities ←── Infrastructure
```

### モジュール分割ルール
1. **単一責任原則**: 1クラス1責任を徹底
2. **公開API制限**: `__all__`で公開範囲を明示
3. **内部モジュール**: プライベートは`_`プレフィックス
4. **依存注入**: concrete実装をDIコンテナで注入

```python
# 良い例: 責任が明確
class ModelDownloadService:
    def __init__(self, api_client: ApiClient, storage: Storage):
        self._api_client = api_client
        self._storage = storage
    
    async def download(self, model_id: int) -> DownloadResult:
        """モデルダウンロード処理のみに集中"""
        pass

# 悪い例: 複数の責任が混在
class ModelManager:  # NG: API通信もファイル保存も進捗表示も担当
    pass
```

## パフォーマンス要件

### 並列処理設計
```python
# レートリミット設定
RATE_LIMITS = {
    "model_api": 0.5,    # req/sec
    "image_api": 2.0,    # req/sec
}

# トークンバケット実装例
class RateLimiter:
    def __init__(self, rate: float):
        self._rate = rate
        self._tokens = rate
        self._last_update = time.time()
    
    async def acquire(self):
        """トークン取得（レート制限適用）"""
        await self._wait_for_token()
    
    async def _wait_for_token(self):
        # 実装詳細...
```

### メモリ効率化
```python
# ストリーミング書き込み（大ファイル対応）
async def download_file_stream(url: str, filepath: Path):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            with open(filepath, 'wb') as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)
```

### スケーラビリティ対応
- **ディレクトリ分割**: `model_<id // 1000>/<id>/` の2階層構造
- **重複排除**: SHA256ハッシュによる同一ファイル検出
- **Range Resume**: 途中停止からの再開に対応

## テスト戦略

### テストピラミッド構成
```
     /\     負荷テスト (週次)
    /  \    ----------------
   /    \   結合テスト (日次)  
  /______\  ----------------
  単体テスト (commit毎)
```

### 単体テスト要件
- **カバレッジ85%以上必須**
- **Pure Function優先**: 副作用のない関数を積極的にテスト
- **モッキング戦略**: `pytest-httpx`でHTTP通信をモック

```python
# テスト例
@pytest.mark.asyncio
async def test_download_model_success(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://civitai.com/api/v1/models/123",
        json={"id": 123, "name": "test-model"}
    )
    
    result = await download_model(123, Path("/tmp"), api_client)
    assert result.success is True
    assert result.model_name == "test-model"
```

### CI/CDパイプライン
```yaml
# GitHub Actionsステージ構成
stages:
  - stage0: 静的解析 (ruff, mypy, black) - 1分以内
  - stage1: 単体テスト (pytest) - 5分以内  
  - stage2: 結合テスト (nightly) - 10分以内
  - stage3: 負荷テスト (weekly) - 2時間、Slack通知
```

## セキュリティとエラーハンドリング指針

### APIキー管理
```python
# 環境変数優先、フォールバック対応
api_key = os.getenv("CIVITAI_API_KEY") or config.api_key
if not api_key:
    raise ConfigError("Civitai API key not found")

# HTTPヘッダー設定
headers = {
    "Authorization": f"Bearer {api_key}",
    "User-Agent": f"Civitai-DL/{__version__} (+https://github.com/your-org/civitai-dl)"
}
```

### ファイル検証とセキュリティ
```python
# SHA256検証必須
def verify_file_integrity(filepath: Path, expected_sha256: str) -> bool:
    """ダウンロードファイルの整合性を検証"""
    calculated = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b""):
            calculated.update(chunk)
    return calculated.hexdigest() == expected_sha256

# パス・サニタイゼーション  
def sanitize_filename(name: str) -> str:
    """ファイル名の危険文字を除去"""
    return re.sub(r'[<>:"/\\|?*]', '_', name)[:255]
```

### エラー分類と対応
```python
class CivitaiError(Exception):
    """基底例外クラス"""
    pass

class ApiError(CivitaiError):
    """API通信エラー（再試行対象）"""
    pass

class StorageError(CivitaiError):
    """ストレージエラー（致命的）"""
    pass

class ValidationError(CivitaiError):
    """データ検証エラー（スキップ対象）"""
    pass
```

## ドキュメント要件

### docstring規約（Google Style）
```python
def process_user_models(username: str, output_dir: Path) -> List[DownloadResult]:
    """指定ユーザーの全モデルを処理する.
    
    Args:
        username: Civitaiユーザー名
        output_dir: ダウンロード先ディレクトリ
        
    Returns:
        各モデルのダウンロード結果リスト
        
    Raises:
        ApiError: ユーザー情報取得失敗時
        ValidationError: 無効なユーザー名時
        
    Example:
        >>> results = process_user_models("sample_user", Path("/downloads"))
        >>> successful = [r for r in results if r.success]
        >>> print(f"成功: {len(successful)}件")
    """
```

### README.mdメンテナンス
- **インストール手順**: `pipx install civitai-dl`
- **基本使用例**: 最小限のコマンド例
- **設定オプション**: 主要なCLIフラグ説明
- **トラブルシューティング**: よくある問題と解決策

## 運用・保守ガイドライン

### ロギング戦略
```python
import structlog

# 構造化ログ設定
logger = structlog.get_logger()

# 使用例
await logger.ainfo(
    "model_download_started",
    model_id=123,
    user_id="sample_user",
    file_size_mb=512.5
)
```

### メトリクス収集
```python
# プログレス情報
progress_metrics = {
    "total_models": len(model_queue),
    "completed": completed_count,
    "failed": failed_count,
    "current_throughput_mbps": calculate_throughput(),
    "estimated_remaining_minutes": estimate_remaining_time()
}
```

### デバッグ手法
- **詳細ログ**: `--verbose`フラグで内部状態を出力
- **ドライラン**: `--dry-run`でAPI呼び出しのみシミュレーション  
- **部分実行**: `--limit N`で最初のN件のみ処理

### リリース手順
1. `pyproject.toml`でバージョン更新
2. 全テストスイート実行（stage0-3）
3. GitHubリリース作成・タグ付け
4. PyPI自動デプロイ（GitHub Actions）

## 開発コマンド

```bash
# プロジェクト初期化
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .[dev]

# 品質チェック
ruff check . --fix        # Lint + 自動修正
mypy .                    # 型チェック
black .                   # フォーマット
pytest -v --cov=civitai_dl

# 実行例
python -m civitai_dl --users users.txt --output downloads/ --token YOUR_API_KEY
```

## API統合詳細

### 認証
- `Authorization: Bearer {api_key}`形式
- Civitai User Account Settingsで取得

### 主要エンドポイント
- `GET /api/v1/models` - モデル一覧
- `GET /api/v1/models/{modelId}` - モデル詳細
- `GET /api/v1/model-versions/{versionId}` - バージョン詳細
- `GET /api/v1/images` - 画像一覧（`modelId`/`username`パラメータ）

### 実装考慮事項
- NSFWコンテンツは`nsfw`パラメータで明示的に取得
- ページネーション対応（`metadata.nextPage`）
- レート制限（429）と指数バックオフ
- ファイル整合性検証（SHA256）
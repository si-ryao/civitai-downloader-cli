# Batch Download Guide / バッチダウンロードガイド

## Overview / 概要

The Civitai Downloader CLI now supports batch downloading of multiple users from a text file.  
Civitai Downloader CLIはテキストファイルから複数ユーザーの一括ダウンロードに対応しました。

## Usage / 使い方

### Basic Command / 基本コマンド

```bash
# Download all users listed in user.txt
python -m civitai_dl --user-list user.txt

# With parallel processing mode (recommended)
python -m civitai_dl --user-list user.txt --parallel-mode

# Test mode (downloads to ./test_downloads/)
python -m civitai_dl --user-list user.txt --test-mode

# With verbose output
python -m civitai_dl --user-list user.txt --parallel-mode --verbose
```

### User List File Format / ユーザーリストファイルの形式

The user list file supports two formats:  
ユーザーリストファイルは2つの形式に対応しています：

1. **URL format / URL形式**:
   ```
   https://civitai.com/user/username1
   https://civitai.com/user/username2
   ```

2. **Username only / ユーザー名のみ**:
   ```
   username1
   username2
   ```

3. **Comments / コメント**:
   Lines starting with `#` are ignored  
   `#`で始まる行は無視されます
   ```
   # This is a comment
   https://civitai.com/user/username1
   # https://civitai.com/user/username2  # This user is skipped
   ```

### Example: user.txt

```
https://civitai.com/user/yukaka05570
https://civitai.com/user/81189
https://civitai.com/user/bolero537
# https://civitai.com/user/IceCycle123  # Commented out
# https://civitai.com/user/Fandingo

# 1000over 
# https://civitai.com/user/LittleJelly
# https://civitai.com/user/moai1088
# https://civitai.com/user/nochekaiser881
```

In this example, only the first 3 users will be downloaded.  
この例では、最初の3ユーザーのみがダウンロードされます。

## Features / 機能

### Sequential Processing / 順次処理
- Users are processed one by one to ensure stability  
  安定性確保のため、ユーザーは1人ずつ順番に処理されます

### Error Handling / エラーハンドリング
- If one user fails, the process continues with the next user  
  1ユーザーが失敗しても、次のユーザーの処理を継続します
- Failed users are reported in the final summary  
  失敗したユーザーは最終サマリーで報告されます

### Progress Tracking / 進捗追跡
- Shows current user being processed (e.g., `[3/10]`)  
  現在処理中のユーザーを表示（例：`[3/10]`）
- Displays download statistics for each user  
  各ユーザーのダウンロード統計を表示

### Final Summary / 最終サマリー
- Total successful/failed users  
  成功/失敗したユーザーの合計
- List of successful users  
  成功したユーザーのリスト
- Error details for failed users  
  失敗したユーザーのエラー詳細

## Example Output / 出力例

```
📋 Found 3 users to download
👥 Users: yukaka05570, 81189, bolero537
==================================================

[1/3] 📥 Processing user: yukaka05570
----------------------------------------
✅ Models: 75/75 downloaded
✅ Images: 993/1000 downloaded

[2/3] 📥 Processing user: 81189
----------------------------------------
✅ Models: 12/12 downloaded
✅ Images: 50/50 downloaded

[3/3] 📥 Processing user: bolero537
----------------------------------------
✅ Models: 8/8 downloaded
✅ Images: 150/150 downloaded

==================================================
📊 BATCH DOWNLOAD SUMMARY
==================================================
✅ Successful: 3/3 users
   Users: yukaka05570, 81189, bolero537

✅ Batch download completed!
```

## Tips / ヒント

1. **Use parallel mode for faster downloads**  
   高速ダウンロードのために並列モードを使用
   ```bash
   python -m civitai_dl --user-list user.txt --parallel-mode
   ```

2. **Test with a small list first**  
   最初は小さなリストでテスト
   ```bash
   # Create test_users.txt with 2-3 users
   python -m civitai_dl --user-list test_users.txt --test-mode
   ```

3. **Monitor progress with verbose mode**  
   詳細モードで進捗を監視
   ```bash
   python -m civitai_dl --user-list user.txt --verbose
   ```

4. **Check logs for failed downloads**  
   失敗したダウンロードのログを確認
   - Failed users are listed in the summary  
     失敗したユーザーはサマリーにリストされます
   - Error messages help identify issues  
     エラーメッセージで問題を特定できます
#!/usr/bin/env python3
"""
網域批量導入腳本

用法：
    python import_domains.py domain.txt

說明：
    - 從文本文件批量導入網域到 domains.json
    - 每行一個網域，自動處理 URL 格式
    - 遇重複網域則跳過
    - 初始化 reported=false, polluted=false
    - 時間使用東八區 (UTC+8)
"""
import sys
from pathlib import Path

# 將 app 目錄加入路徑
sys.path.insert(0, str(Path(__file__).parent))

from app.domains import import_from_file


def main():
    if len(sys.argv) < 2:
        print("用法: python import_domains.py <domain.txt>")
        print("範例: python import_domains.py domain.txt")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    if not Path(filepath).exists():
        print(f"錯誤: 文件不存在 - {filepath}")
        sys.exit(1)
    
    print(f"正在從 {filepath} 導入網域...")
    added, skipped = import_from_file(filepath)
    
    print(f"\n導入完成！")
    print(f"  ✓ 新增: {added} 個網域")
    print(f"  ○ 跳過: {skipped} 個（重複或無效）")


if __name__ == "__main__":
    main()

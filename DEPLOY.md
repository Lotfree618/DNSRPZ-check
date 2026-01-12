# 網域台灣 DNS RPZ 檢測 - 部署指南

本文檔介紹如何在 Debian/Ubuntu VPS 上部署該工具（前後端部署在同一台 VPS）。

---

## 目錄結構

```
/opt/dnsrpz/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── schemas.py
│   │   ├── domains.py
│   │   ├── dns_probe.py
│   │   ├── redirect_trace.py
│   │   ├── verdict.py
│   │   └── store.py
│   ├── domains.json        # 網域資料（自動生成）
│   ├── import_domains.py   # 批量導入腳本
│   ├── requirements.txt
│   └── venv/
├── frontend/
│   └── dist/               # 前端靜態文件
└── README.md
```

---

## 1. 環境準備

```bash
# 更新系統
sudo apt update && sudo apt upgrade -y

# 安裝必要軟體
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git

# 創建目錄
sudo mkdir -p /opt/dnsrpz
sudo chown $USER:$USER /opt/dnsrpz
```

---

## 2. 部署後端

```bash
# 進入目錄
cd /opt/dnsrpz

# 上傳代碼（或使用 git clone）
# scp -r ./backend user@server:/opt/dnsrpz/

# 創建虛擬環境
cd backend
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
pip install filelock  # 新增依賴

# 測試運行
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Ctrl+C 停止
deactivate
```

---

## 3. 導入初始網域

準備一個 `domain.txt` 文件，每行一個網域：

```txt
example.com
google.com
https://www.youtube.com/watch?v=xxx  # 支援 URL 格式，自動提取網域
```

執行導入：

```bash
cd /opt/dnsrpz/backend
source venv/bin/activate
python import_domains.py domain.txt
deactivate
```

輸出示例：
```
正在從 domain.txt 導入網域...

導入完成！
  ✓ 新增: 15 個網域
  ○ 跳過: 2 個（重複或無效）
```

---

## 4. 創建 Systemd 服務

創建服務文件 `/etc/systemd/system/dnsrpz.service`：

```ini
[Unit]
Description=DNS RPZ Detection Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/dnsrpz/backend
ExecStart=/opt/dnsrpz/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

設置權限並啟動服務：

```bash
# 設置目錄權限
sudo chown -R www-data:www-data /opt/dnsrpz/backend/domains.json
sudo chown -R www-data:www-data /opt/dnsrpz/backend

# 啟動服務
sudo systemctl daemon-reload
sudo systemctl enable dnsrpz
sudo systemctl start dnsrpz
sudo systemctl status dnsrpz
```

---

## 5. 構建前端

在本地構建（推薦）：

```bash
cd frontend
npm install
npm run build
```

上傳到伺服器：

```bash
# 從本地上傳
scp -r dist user@server:/tmp/dnsrpz-dist

# 在伺服器上
sudo mkdir -p /opt/dnsrpz/frontend
sudo cp -r /tmp/dnsrpz-dist /opt/dnsrpz/frontend/dist
sudo chown -R www-data:www-data /opt/dnsrpz/frontend/dist
```

或者在伺服器構建（需安裝 Node.js）：

```bash
# 安裝 Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 構建
cd /opt/dnsrpz/frontend
npm install
npm run build
```

---

## 6. 配置 Nginx

創建配置文件 `/etc/nginx/sites-available/dnsrpz`：

```nginx
server {
    listen 80;
    server_name dns.example.com;  # 替換為你的網域
    
    # 前端靜態文件
    root /opt/dnsrpz/frontend/dist;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 增加超時時間（批量操作可能需要較長時間）
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

啟用配置：

```bash
sudo ln -s /etc/nginx/sites-available/dnsrpz /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 7. 配置 HTTPS

使用 Let's Encrypt：

```bash
sudo certbot --nginx -d dns.example.com
```

按提示完成配置，certbot 會自動修改 Nginx 配置。

---

## 8. 防火牆配置

```bash
# 允許出站 DNS 查詢
sudo ufw allow out 53/udp
sudo ufw allow out 53/tcp

# 允許出站 HTTP/HTTPS（用於重定向追蹤）
sudo ufw allow out 80/tcp
sudo ufw allow out 443/tcp

# 允許入站 HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

---

## 9. 驗證部署

1. 訪問 `https://dns.example.com`
2. 確認網域列表顯示正確
3. 測試篩選/搜尋/排序功能
4. 點擊網域查看詳情
5. 測試新增/修改/刪除網域
6. 確認每 10 秒自動刷新

---

## 常用命令

```bash
# 查看後端日誌
sudo journalctl -u dnsrpz -f

# 重啟後端
sudo systemctl restart dnsrpz

# 批量導入網域
cd /opt/dnsrpz/backend
source venv/bin/activate
python import_domains.py new_domains.txt
deactivate

# 查看 Nginx 日誌
sudo tail -f /var/log/nginx/access.log

# 備份網域資料
cp /opt/dnsrpz/backend/domains.json ~/domains_backup.json
```

---

## API 端點一覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/health` | 健康檢查 |
| GET | `/api/domains` | 獲取網域列表（含屬性） |
| POST | `/api/domains` | 新增網域 |
| PUT | `/api/domains/{domain}` | 修改網域名稱 |
| DELETE | `/api/domains/{domain}` | 刪除網域 |
| POST | `/api/domains/batch-delete` | 批量刪除 |
| PATCH | `/api/domains/{domain}/note` | 更新備註 |
| PATCH | `/api/domains/{domain}/reported` | 切換已上報狀態 |
| GET | `/api/detail?domain=xxx` | 獲取網域詳情 |
| GET | `/api/check?domain=xxx` | 簡化版檢測（供外部調用） |

---

## Windows 本地開發

```powershell
# 後端
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install filelock
uvicorn app.main:app --reload --port 8000

# 前端（新終端）
cd frontend
npm install
npm run dev
```

訪問 http://localhost:5173

---

## 故障排除

### 1. 網域資料丟失
檢查 `domains.json` 文件權限：
```bash
ls -la /opt/dnsrpz/backend/domains.json
sudo chown www-data:www-data /opt/dnsrpz/backend/domains.json
```

### 2. API 回應 500 錯誤
查看後端日誌：
```bash
sudo journalctl -u dnsrpz -n 100
```

### 3. 前端無法連接 API
檢查 Nginx 配置和後端服務狀態：
```bash
sudo nginx -t
sudo systemctl status dnsrpz
```

### 4. DNS 查詢超時
確保伺服器可以訪問外部 DNS：
```bash
dig @8.8.8.8 google.com
dig @168.95.1.1 google.com
```

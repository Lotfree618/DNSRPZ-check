# 域名台湾DNS RPZ检测 - 部署指南

本文档介绍如何在 Debian VPS 上部署该工具。

---

## 目录结构

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
│   │   ├── verdict.py
│   │   └── store.py
│   ├── requirements.txt
│   └── venv/
├── frontend/
│   └── dist/           # 构建后的静态文件
├── Domains.txt         # 域名列表
└── README.md
```

---

## 1. 环境准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要软件
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# 创建目录
sudo mkdir -p /opt/dnsrpz
sudo chown $USER:$USER /opt/dnsrpz
```

---

## 2. 部署后端

```bash
# 进入目录
cd /opt/dnsrpz

# 复制后端代码
# (将 backend/ 目录上传到服务器)

# 创建虚拟环境
cd backend
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 测试运行
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Ctrl+C 停止
deactivate
```

---

## 3. 创建 Systemd 服务

创建服务文件 `/etc/systemd/system/dnsrpz.service`：

```ini
[Unit]
Description=DNS RPZ Detection Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/dnsrpz/backend
Environment="DOMAINS_FILE=/opt/dnsrpz/Domains.txt"
ExecStart=/opt/dnsrpz/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable dnsrpz
sudo systemctl start dnsrpz
sudo systemctl status dnsrpz
```

---

## 4. 构建前端

在本地或服务器构建：

```bash
cd frontend
npm install
npm run build
```

将 `dist/` 目录复制到服务器：

```bash
# 复制到 /opt/dnsrpz/frontend/dist/
sudo mkdir -p /opt/dnsrpz/frontend
sudo cp -r dist /opt/dnsrpz/frontend/
sudo chown -R www-data:www-data /opt/dnsrpz/frontend/dist
```

---

## 5. 配置 Nginx

创建配置文件 `/etc/nginx/sites-available/dnsrpz`：

```nginx
server {
    listen 80;
    server_name dns.example.com;  # 替换为你的域名
    
    # 前端静态文件
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
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/dnsrpz /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 6. 配置 HTTPS

使用 Let's Encrypt：

```bash
sudo certbot --nginx -d dns.example.com
```

按提示完成配置，certbot 会自动修改 Nginx 配置。

---

## 7. 配置域名列表

编辑 `/opt/dnsrpz/Domains.txt`：

```txt
# 每行一个域名
google.com
youtube.com
github.com
```

修改后无需重启，10 秒内自动生效。

---

## 8. 防火墙配置

确保服务器可以向外发起 DNS 查询：

```bash
# 允许出站 UDP/TCP 53
sudo ufw allow out 53/udp
sudo ufw allow out 53/tcp

# 允许入站 HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

---

## 9. 验证部署

1. 访问 `https://dns.example.com`
2. 检查域名列表是否显示
3. 点击域名查看详情
4. 确认每 10 秒自动刷新

---

## 常用命令

```bash
# 查看后端日志
sudo journalctl -u dnsrpz -f

# 重启后端
sudo systemctl restart dnsrpz

# 修改域名列表
sudo nano /opt/dnsrpz/Domains.txt

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/access.log
```

---

## Windows 本地开发

```powershell
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端（新终端）
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

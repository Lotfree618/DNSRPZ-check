# VPS 部署教程

台湾DNS RPZ检测工具的完整部署指南（Ubuntu/Debian）

---

## 1. 准备工作

### 1.1 服务器要求
- Ubuntu 20.04/22.04 或 Debian 11/12
- 至少 512MB 内存
- 确保 UDP/TCP 53 出站未被阻断

### 1.2 安装基础依赖
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 3 和 pip
sudo apt install python3 python3-pip python3-venv -y

# 安装 Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# 安装 Nginx
sudo apt install nginx -y
```

---

## 2. 上传项目代码

```bash
# 创建项目目录
sudo mkdir -p /var/www/dnsrpz
sudo chown $USER:$USER /var/www/dnsrpz

# 上传代码（从本地执行）
# scp -r backend frontend user@your-vps:/var/www/dnsrpz/
```

或使用 Git：
```bash
cd /var/www/dnsrpz
git clone https://github.com/your-repo/DNSRPZ-check.git .
```

---

## 3. 后端部署

```bash
cd /var/www/dnsrpz/backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 测试运行
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 按 Ctrl+C 停止
```

### 3.1 创建 systemd 服务

```bash
sudo nano /etc/systemd/system/dnsrpz.service
```

写入以下内容：
```ini
[Unit]
Description=DNS RPZ Detection API
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/dnsrpz/backend
Environment="PATH=/var/www/dnsrpz/backend/venv/bin"
ExecStart=/var/www/dnsrpz/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动服务：
```bash
# 修复权限
sudo chown -R www-data:www-data /var/www/dnsrpz

# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable dnsrpz
sudo systemctl start dnsrpz

# 查看状态
sudo systemctl status dnsrpz
```

---

## 4. 前端构建

```bash
cd /var/www/dnsrpz/frontend

# 安装依赖
npm install

# 构建生产版本
npm run build

# 产物在 dist/ 目录
```

---

## 5. Nginx 配置

### 5.1 创建站点配置

```bash
sudo nano /etc/nginx/sites-available/dnsrpz
```

写入以下内容：
```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名

    root /var/www/dnsrpz/frontend/dist;
    index index.html;

    # 前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端API代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 30s;
        proxy_read_timeout 60s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 5.2 启用站点

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/dnsrpz /etc/nginx/sites-enabled/

# 删除默认站点（可选）
sudo rm /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

---

## 6. 配置 HTTPS（推荐）

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 申请证书（自动配置 Nginx）
sudo certbot --nginx -d your-domain.com

# 自动续期测试
sudo certbot renew --dry-run
```

---

## 7. 防火墙配置

```bash
# 如果使用 ufw
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 8. 验证部署

```bash
# 测试后端API
curl http://127.0.0.1:8000/api/resolve?target=example.com

# 测试完整流程
curl https://your-domain.com/api/resolve?target=google.com
```

访问 `https://your-domain.com` 验证前端页面。

---

## 9. 常用维护命令

```bash
# 查看后端日志
sudo journalctl -u dnsrpz -f

# 重启后端
sudo systemctl restart dnsrpz

# 重载 Nginx
sudo systemctl reload nginx

# 更新代码后
cd /var/www/dnsrpz/frontend && npm run build
sudo systemctl restart dnsrpz
```

---

## 故障排查

| 问题 | 检查项 |
|-----|-------|
| 502 Bad Gateway | 后端是否运行：`systemctl status dnsrpz` |
| DNS查询超时 | VPS是否能访问53端口：`dig @8.8.8.8 google.com` |
| 前端白屏 | dist目录是否存在、Nginx root路径是否正确 |
| API 404 | Nginx代理配置是否正确 |

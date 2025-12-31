# 台湾DNS RPZ检测（执行方案）

> 目标：做一个简洁的单页面网页工具（Vue SPA），用户输入域名或 URL 后，前端调用 Python API；后端分别使用 **Google DNS（8.8.8.8）/ Cloudflare DNS（1.1.1.1）** 与指定的台湾 DNS（**HiNet（中华电信）168.95.1.1、TWNIC Quad101 101.101.101.101**）进行 A/AAAA 记录解析，并严格按照规则分类输出结果。前端与后端 **部署在同一台 VPS** 上，并且 **所有提示文案与检测结果均使用简体中文**。

---

## 1. 范围与原则

### 1.1 功能范围（MVP）
1. **输入域名/URL 并查询**（按钮触发，支持回车）
2. 展示各解析器结果（A/AAAA 记录）：
   - Google DNS：8.8.8.8（基准）
   - Cloudflare DNS：1.1.1.1（基准）
   - HiNet（中华电信）：168.95.1.1（台湾）
   - TWNIC Quad101：101.101.101.101（台湾）
3. **对比结论输出**：OK / 异常 / 不确定，并给出“依据”
4. **显示查询历史**：
   - 默认采用浏览器 localStorage 保存最近 30 次查询记录
   - 无账号体系、无服务端用户隔离（保持简单）

### 1.2 判定原则
- 先取“基准解析”（baseline）：8.8.8.8 与 1.1.1.1 返回的 A/AAAA 记录 IP 合并为集合 `baseline_ips`
- 再逐个查询台湾 DNS（仅保留两项：HiNet、Quad101）
- 对每个台湾 DNS 的结果进行分类（使用 A/AAAA 记录）：
  - **超时（timeout）**
  - **被阻断（nxdomain）**
  - **已封锁（命中黑名单 IP）**
  - **正常（返回 IP 是 baseline 的子集）**
  - **差异（可能 CDN）**
- **重要约束：`差异（可能CDN）不影响最终结论为 OK`。**
  - 也就是说：只要未出现“被阻断 / 已封锁”，即便出现“差异（可能CDN）”，最终仍可判为 OK。
  - 若出现“超时/错误”，最终判为“不确定”（需检查网络连通性）。

---

## 2. 总体架构（最简可交付）

```
[Vue SPA (同VPS静态文件)]  --HTTPS-->  [Python FastAPI (同VPS)]
                                         |
                                         |--(UDP/TCP 53)--> 8.8.8.8
                                         |--(UDP/TCP 53)--> 1.1.1.1
                                         |--(UDP/TCP 53)--> 168.95.1.1
                                         `--(UDP/TCP 53)--> 101.101.101.101
```

---

## 3. 后端（Python）详细方案

### 3.1 技术栈
- Web 框架：FastAPI
- 运行：uvicorn
- DNS 解析：dnspython
- 并发：asyncio（并发查询多个 resolver）

### 3.2 依赖清单（requirements.txt）
- fastapi
- uvicorn[standard]
- dnspython
- pydantic

### 3.3 API 设计

#### 3.3.1 `GET /api/resolve?target=...`
- 输入：
  - `target`：用户输入（可为域名或 URL）
- 输出（JSON）：
  - `input`：原始输入（trim 后）
  - `domain`：规范化后的域名（小写、去尾点、提取自 URL 的 hostname）
  - `timestamp`：ISO8601
  - `baseline`：
    - `ips`：基准 IP 集合（8.8.8.8 + 1.1.1.1）
    - `detail`：两条基准解析各自的状态与 IP
  - `tw_resolvers`：台湾 DNS 的解析结果与分类
  - `conclusion`：
    - `status`：`OK` / `异常` / `不确定`
    - `reason`：简体中文理由列表

### 3.4 域名/URL 输入规范化（后端必须做）
后端必须容错处理“域名或 URL”两种输入，并将其归一化为 **hostname**（不含协议、路径、端口、参数）：
1. `strip()` 去空白；拒绝空字符串
2. 若包含 `://` 或包含 `/`、`?`、`#` 等 URL 特征：
   - 使用 URL 解析提取 `hostname`
3. 将域名转小写
4. 去掉尾部 `.`（FQDN 尾点）
5. 允许 IDN：内部查询时用 `idna` 转 punycode（ASCII）
6. 拒绝无效 hostname（空、含空格、长度超限等）

### 3.5 DNS 查询策略（实现细节）
- 查询类型：**A/AAAA 记录**
- 单次超时：默认 3s（可配置）；台湾 DNS 可适当提高到 4s
- UDP 优先；必要时可 TCP fallback（dnspython 支持）
- 并发：一次请求并发 4 个 resolver（2 基准 + 2 台湾）

#### 3.5.1 结果统一化
每个 resolver 返回：
- `status`：`ok` / `nxdomain` / `timeout` / `error`
- `ips`：A/AAAA 记录 IP 列表（成功时）
- `msg`：错误信息（仅 error）

### 3.6 RPZ/污染分类逻辑
#### 3.6.1 基准（baseline）
- 查询 8.8.8.8 与 1.1.1.1，汇总得到 `baseline_ips`
- 若 `baseline_ips` 为空：返回错误（域名可能不存在，或 VPS 无法访问国际 DNS）

#### 3.6.2 黑名单 IP（BLOCK_PAGE_IPS）
若台湾 DNS 返回 IP 命中黑名单之一，则直接判定为 **已封锁**：
- 182.173.0.181（常见反诈警示页）
- 104.18.0.0
- 127.0.0.1
- 0.0.0.0

#### 3.6.3 台湾 DNS 单项分类（逐条输出）
对每个台湾 DNS 的查询结果：
- `timeout` ⇒ **超时**（提示：网络不可达或 UDP 被阻断）
- `nxdomain` ⇒ **被阻断**（在 baseline 有结果前提下，认为是故意屏蔽）
- `ok`：
  - 命中黑名单 IP ⇒ **已封锁**
  - 否则若 `result_ips` 是 `baseline_ips` 的子集 ⇒ **正常**
  - 否则 ⇒ **差异（可能CDN）**
- `error` ⇒ **错误**

### 3.7 最终结论聚合（强调“差异不影响 OK”）
- 若任一台湾 DNS 出现 **已封锁** 或 **被阻断** ⇒ `异常`
- 否则若任一台湾 DNS 出现 **超时** 或 **错误** ⇒ `不确定`
- 否则（仅出现 **正常** 与/或 **差异（可能CDN）**） ⇒ `OK`

### 3.8 FastAPI 工程结构（建议）
```
backend/
  app/
    main.py            # FastAPI 入口
    config.py          # 超时、resolver 列表、黑名单等
    schemas.py         # Pydantic 响应模型
    dns_probe.py       # DNS 查询与结果归一化
    verdict.py         # 分类与结论聚合
  requirements.txt
  README.md
```

---

## 4. 前端（Vue SPA）详细方案

### 4.1 技术栈
- Vue 3 + Vite
- 请求：fetch 或 axios（二选一）

### 4.2 标题与文案（简体中文）
- 网站标题（页面 H1）与浏览器标签页（`document.title`）统一为：**台湾DNS RPZ检测**
- 所有按钮、表头、状态、提示信息均使用简体中文

### 4.3 域名输入框：粘贴 URL 自动格式化为域名
前端输入框支持用户直接粘贴 URL；在以下时机自动归一化并回填输入框（保证用户可见输入为纯域名）：
- `onBlur`（失焦）
- 或 `onPaste`/`onChange`（可选）

格式化规则：
- 输入：`https://gemini.google.com/app/b424aa428783a462`
- 输出回填：`gemini.google.com`

说明：
- 若用户输入已是域名（如 `google.com`），保持不变
- 归一化后仍将原始输入保留在历史记录中（便于排查）

### 4.4 页面结构（单页）
1. 顶部：标题（台湾DNS RPZ检测）+ 简短说明
2. 输入区：
   - 输入框（域名/URL，自动格式化显示域名）
   - “查询”按钮
   - 加载态（禁用按钮/加载提示）
3. 结果区（表格/卡片均可）：
   - **基准区**：8.8.8.8 与 1.1.1.1 的解析状态与 IP 列表、baseline IP 集合
   - **台湾 DNS 区**：HiNet 与 Quad101 的状态（超时/被阻断/已封锁/正常/差异）与 IP 列表
   - **结论区**：醒目 badge（OK / 异常 / 不确定）+ 理由列表（简体中文）
4. 历史区：
   - 最近 30 条：domain、结论、时间
   - 点击可一键再次查询

### 4.5 查询历史（localStorage）
- key：`dnsrpz_history_v1`
- 结构：
```json
[
  {"domain":"example.com","status":"OK","ts":1700000000},
  {"domain":"bad.com","status":"异常","ts":1700000123}
]
```
- 策略：最新插入头部、同域名去重（保留最新）、最多保留 30 条

---

## 5. 部署方案（同一台 VPS）

### 5.1 Nginx + 静态前端 + 反向代理后端
- 前端：`npm run build` 生成静态文件
- 后端：FastAPI 提供 `/api/*`
- Nginx：
  - `/` → 前端静态文件（Vue SPA）
  - `/api/` → 反向代理到 uvicorn

Nginx 典型路由：
- `location /api/ { proxy_pass http://127.0.0.1:8000; }`
- `location / { root /var/www/dist; try_files $uri $uri/ /index.html; }`

### 5.2 进程管理
- systemd 管理 uvicorn：
  - `ExecStart=/path/to/uvicorn app.main:app --host 127.0.0.1 --port 8000`

### 5.3 HTTPS
- Let’s Encrypt（certbot）签发证书
- 强制 HTTPS

---

## 6. 测试清单（上线前必须跑）

1. **网络连通性**
   - VPS 能否出站 UDP/TCP 53 到 8.8.8.8 / 1.1.1.1 / 168.95.1.1 / 101.101.101.101
2. **正常域名**
   - `example.com` 预期最终结论为 OK
3. **URL 输入格式化**
   - 输入 `https://gemini.google.com/app/b424aa428783a462`，前端回填显示 `gemini.google.com`
4. **差异不影响 OK**
   - 选取可能走 CDN 的域名，出现“差异（可能CDN）”时，最终仍应为 OK（前提：无被阻断/已封锁）
5. **超时分支**
   - 在受限网络环境下验证“超时”展示与最终“不确定”聚合逻辑
6. **历史记录**
   - 刷新页面历史仍在；超过 30 条后裁剪

---

## 7. 里程碑拆解（可按 1~2 天完成的节奏）

### M1：后端 MVP（0.5~1 天）
- FastAPI `/api/resolve`
- dnspython 并发查询（A/AAAA 记录）
- 分类逻辑与结论聚合（差异不影响 OK）

### M2：前端 MVP（0.5~1 天）
- Vue 单页输入 + 结果展示（简体中文）
- URL 输入自动格式化为域名
- localStorage 历史

### M3：VPS 部署上线（0.5 天）
- Nginx 托管前端静态文件
- Nginx 反向代理 `/api/` 到 uvicorn
- HTTPS + systemd

# DNS RPZ 污染监测工具（简版）执行方案

> 目标：做一个简洁的单页面网页工具（Vue SPA），用户输入域名后，前端调用 Python API；后端分别使用 **8.8.8.8 / 1.1.1.1** 与指定的台湾 DNS（**中华电信 168.95.1.1、台湾大哥大 211.78.130.2、远传电信 139.175.55.244、TWNIC 101.101.101.101**）进行解析，对比并输出“是否疑似 RPZ/污染/拦截”的结论；前端显示查询历史。

---

## 1. 范围与原则

### 1.1 功能范围（MVP）
1. **输入域名并查询**（按钮触发，支持回车）
2. 展示各解析器结果：
   - Google DNS：8.8.8.8
   - Cloudflare DNS：1.1.1.1
   - 中华电信：168.95.1.1
   - 台湾大哥大：211.78.130.2
   - 远传电信：139.175.55.244
   - TWNIC Quad101：101.101.101.101
3. **对比结论输出**：是否疑似 RPZ/污染；同时说明“依据”
4. **显示查询历史**：
   - 默认采用 **浏览器 localStorage** 保存最近 30 次 查询记录
   - 无账号体系、无服务端用户隔离（尽量简单）

---

## 2. 总体架构（最简可交付）

```
[Vue SPA]  --HTTPS-->  [Python FastAPI]
                         |
                         |--(UDP/TCP 53)--> 8.8.8.8
                         |--(UDP/TCP 53)--> 1.1.1.1
                         |--(UDP/TCP 53)--> 168.95.1.1
                         |--(UDP/TCP 53)--> 211.78.130.2
                         |--(UDP/TCP 53)--> 139.175.55.244
                         `--(UDP/TCP 53)--> 101.101.101.101
```

### 2.1 关键注意点（部署前必检查）
- VPS 必须允许 **出站 UDP 53**（以及可选 TCP 53）。  
  若云厂商默认封 UDP 53，需要：
  - 在安全组/防火墙放行出站 53
  - 后端对 **8.8.8.8/1.1.1.1**走 DoH 作为基准

---

## 3. 后端（Python）详细方案

### 3.1 技术栈
- Web 框架：**FastAPI**
- 运行：**uvicorn**
- DNS 解析：**dnspython**
- 并发：**asyncio**（并发查询多个 resolver）
- （可选）输入校验：`idna`（域名 punycode/IDN）

### 3.2 依赖清单（requirements.txt）
建议版本范围（可按实际锁定）：

- fastapi
- uvicorn[standard]
- dnspython
- pydantic
- idna

### 3.3 API 设计

#### 3.3.1 `GET /api/resolve?domain=example.com`
- 输入：
  - `domain`：待检测域名
- 输出（JSON）：
  - `domain`：规范化后的域名（小写、去尾点）
  - `timestamp`：ISO8601
  - `baseline`：基准一致性信息
  - `resolvers`：每个 resolver 的解析结果
  - `comparison`：差异摘要
  - `conclusion`：结论（OK/可能污染/不确定）+ 理由列表

**建议响应结构：**
```json
{
  "domain": "example.com",
  "timestamp": "2025-12-30T12:34:56Z",
  "baseline": {
    "agreed": true,
    "types_checked": ["A", "AAAA"],
    "reference": {
      "A": ["93.184.216.34"],
      "AAAA": []
    }
  },
  "resolvers": {
    "google": {
      "ip": "8.8.8.8",
      "A": {"status": "NOERROR", "answers": ["93.184.216.34"], "ttl": 300},
      "AAAA": {"status": "NOERROR", "answers": [], "ttl": null},
      "elapsed_ms": 45
    },
    "cloudflare": { "...": "..." },
    "hinet": { "...": "..." },
    "twm": { "...": "..." },
    "fet": { "...": "..." },
    "quad101": { "...": "..." }
  },
  "comparison": {
    "mismatches": [
      {"resolver": "hinet", "type": "A", "reason": "NXDOMAIN but baseline NOERROR"},
      {"resolver": "fet", "type": "A", "reason": "Different A answers from baseline"}
    ]
  },
  "conclusion": {
    "status": "SUSPECTED_RPZ",
    "reasons": [
      "Baseline一致（Google/Cloudflare结果一致）",
      "中华电信返回 NXDOMAIN，但基准返回 A 记录",
      "远传返回 0.0.0.0，疑似拦截/重定向"
    ]
  }
}
```

### 3.4 域名输入校验与规范化（后端必须做）
1. `strip()` 去空白；拒绝空字符串
2. 转小写
3. 去掉尾部 `.`（FQDN 尾点）
4. 允许 IDN：用 `idna.encode()` 转 punycode（内部查询用 ASCII）
5. 拒绝：
   - 含空格、协议头（`http://`）
   - 含路径（`/`）、端口（`:`）等
6. 限制长度：整域名 <= 253；每 label <= 63

### 3.5 DNS 查询策略（实现细节）
- 查询类型：**A + AAAA**（MVP 足够）
- 超时：单次 1.5s（可配），重试 1 次（可配）
- UDP 优先；失败可 **TCP fallback**（dnspython 支持）
- 并发：一次请求并发 6 个 resolver * 2 种 type

#### 3.5.1 结果统一化
每个 (resolver, qtype) 返回：
- `status`：NOERROR / NXDOMAIN / SERVFAIL / TIMEOUT / OTHER
- `answers`：IP 列表（A/AAAA）或空
- `ttl`：取最小 TTL（若多个 RR）
- `cname_chain`：（可选）如果发现 CNAME，记录链路用于展示解释

### 3.6 “RPZ/污染”判定逻辑（简化且可解释）
定义 **基准（baseline）**：
- 同时查询 8.8.8.8 与 1.1.1.1
- 若二者在 A/AAAA 上“足够一致”（完全相同或一方空、一方空），认为 **baseline.agreed = true**
- 若不一致，标记 **baseline.agreed = false**，最终结论多为 **UNCERTAIN**，并提示“基准不一致，可能存在地理/负载差异或解析策略差异”。

对每个台湾 resolver（hinet/twm/fet/quad101）进行对比：
- **规则 R1：NXDOMAIN/SERVFAIL/Timeout vs baseline NOERROR**
  - baseline 有 A/AAAA，但 ISP 返回 NXDOMAIN/SERVFAIL ⇒ **强疑似拦截/污染**
- **规则 R2：返回“疑似拦截 IP”**
  - 若 ISP 返回任一答案落在：
    - 0.0.0.0/8
    - 127.0.0.0/8
    - 私网：10/8、172.16/12、192.168/16
    - 100.64/10（CGNAT，视情况）
  ⇒ 标记 **SUSPECTED_RPZ**
- **规则 R3：答案集合与 baseline 明显不同**
  - baseline 与 ISP 的 A/AAAA 不相交（intersection 为空）
  - 且 baseline.agreed 为 true
  ⇒ 标记 **POSSIBLE_INTERFERENCE**（可能污染/劫持/重定向/区域差异）
- **规则 R4：无法判断**
  - baseline 不一致或 ISP 超时
  ⇒ **UNCERTAIN**

最终结论聚合策略：
- 任何 resolver 命中 R1/R2 ⇒ `SUSPECTED_RPZ`
- 否则若 ≥2 个台湾 resolver 与 baseline 明显不一致（R3） ⇒ `POSSIBLE_INTERFERENCE`
- 否则 ⇒ `OK`（未观察到异常）

> 备注：该判定是“启发式”，重点是“可解释”和“降低误报”。后续可加入更强证据（例如已知拦截页 IP/域名特征库、权威对照、HTTPS 探测等）。

### 3.7 FastAPI 工程结构（建议）
```
backend/
  app/
    main.py            # FastAPI 入口
    config.py          # 超时、resolver 列表等
    schemas.py         # Pydantic 响应模型
    dns_probe.py       # DNS 并发查询与结果归一化
    verdict.py         # 判定逻辑
  requirements.txt
  README.md
```


---

## 4. 前端（Vue SPA）详细方案

### 4.1 技术栈
- Vue 3 + Vite
- UI：建议用 **原生 CSS + 少量 utility**（或轻量组件库）以保持简洁
- 请求：fetch 或 axios（二选一）

### 4.2 页面结构（单页）
1. 顶部：标题 + 简短说明
2. 输入区：
   - 输入框（domain）
   - “查询”按钮
   - 加载态（spinner/禁用按钮）
3. 结果区（响应式卡片/表格二选一）：
   - 基准区：8.8.8.8 与 1.1.1.1 结果
   - 台湾 DNS 区：四个 resolver 的 A/AAAA 结果与状态
   - 结论区：一个醒目 badge（OK / 疑似污染 / 不确定）+ 理由列表
4. 历史区：
   - 列表显示最近 30 条：domain、结论、时间
   - 点击历史项可一键再次查询

### 4.3 UI/响应式实现要点
- PC：结果用表格更直观；Mobile：切换为卡片列表（CSS media query）
- 统一展示字段：
  - `status`（NOERROR/NXDOMAIN/TIMEOUT）
  - `A`、`AAAA` answers（多值换行或 chip）
  - 耗时（ms）
- 高亮差异：
  - 与 baseline 不一致时，标红/标黄（避免强烈视觉噪音）

### 4.4 查询历史（默认用 localStorage）
- key：`dnsrpz_history_v1`
- 结构：
```json
[
  {"domain":"example.com","status":"OK","ts":1700000000},
  {"domain":"bad.com","status":"SUSPECTED_RPZ","ts":1700000123}
]
```
- 写入策略：最新插入头部、去重（同域名保留最新）、最多保留 30 条

---

## 5. 部署方案（最简）

### 5.1 方案 A：同一台 VPS 上部署前后端（推荐最简单）
- 前端：`npm run build` 生成静态文件
- 后端：FastAPI 提供 `/api/*`
- Nginx：
  - `/` → 前端静态文件
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
   - VPS 能否出站 UDP 53 到 8.8.8.8/1.1.1.1/台湾 resolver
2. **正常域名**
   - `example.com` 预期 OK
3. **无 AAAA 的域**
   - 确认 AAAA 显示为空而不是报错
4. **超时/不可达**
   - 人为填写不可达 resolver（仅测试环境）验证 TIMEOUT 分支
5. **前端适配**
   - iPhone/Android/桌面浏览器显示正常
6. **历史记录**
   - 刷新页面历史仍在；超过 30 条后裁剪

---

## 7. 里程碑拆解（可按 1~2 天完成的节奏）

### M1：后端 MVP（0.5~1 天）
- FastAPI `/api/resolve`
- dnspython 并发查询 A/AAAA
- 判定逻辑 + JSON 输出

### M2：前端 MVP（0.5~1 天）
- Vue 单页输入 + 展示结果
- localStorage 历史
- 响应式布局

### M3：部署上线（0.5 天）
- Cloudflare Pages静态部署
- HTTPS + systemd

---

# SkillPay 支付网关 — 独立 Flask 应用

## 项目结构

```
skillpay_app/
├── app.py                 # Flask 主程序（所有路由 + 数据库 + 支付逻辑）
├── requirements.txt       # Python 依赖
├── instance/              # SQLite 数据库目录（启动后自动生成 auth_access.db）
├── templates/
│   ├── support.html       # 用户支付页面（24h 通行证）
│   └── auth_stats.html    # 管理员授权统计面板
└── 使用说明.md             # 本文件
```

## 快速启动

```bash
cd skillpay_app
pip install -r requirements.txt
python app.py
```

默认监听 `http://0.0.0.0:5009`。

## 路由说明

| 路由 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 重定向到 `/support` |
| `/support` | GET | 用户支付页面（UI） |
| `/api/activate-key` | POST | 核心 API：检查授权 → 尝试扣费 → 返回支付链接 |
| `/admin/supports` | GET | 管理员面板：查看所有授权 IP 及状态 |

## 支付流程

```
用户访问 /support
  → 页面加载时自动 POST /api/activate-key 检查当前 IP 是否已授权
  → 若已授权 → 直接显示成功页
  → 若未授权 → 用户点击 "Unlock Now via SkillPay"
    → POST /api/activate-key
      → 后端尝试从 SkillPay 扣费（1 USDT）
        → 扣费成功 → 写入 IP 授权（24h）→ 返回 200
        → 扣费失败（余额不足）→ 生成支付链接 → 返回 402 + payment_url
      → 前端打开支付链接新窗口 + 每 4 秒轮询 /api/activate-key
      → 用户扫码支付后 → 轮询命中授权 → 显示成功
```

## 数据库

- **文件**: `instance/auth_access.db`
- **表**: `ip_auth`

| 字段 | 类型 | 说明 |
|------|------|------|
| `ip` | TEXT PRIMARY KEY | 客户端 IP（作为授权唯一标识） |
| `is_active` | INTEGER | 是否激活（0/1） |
| `expires_at` | DATETIME | 授权过期时间 |

## 配置说明

在 `app.py` 顶部可修改：

```python
BILLING_API_URL = 'https://skillpay.me'          # SkillPay 网关地址
BILLING_API_KEY = 'sk_...'                        # 你的 API Key
SKILL_ID = 'a4f43f51-...'                         # 商品 ID
PRICE_USDT = 1.0                                  # 价格（USDT）
```

## 与原项目的区别

- **独立运行**：不依赖原项目的 `config.py`、`decorators.py`、`stocks.db` 等
- **纯支付功能**：仅含 SkillPay 支付 + IP 授权逻辑
- 适合于个人开发这个境外收款

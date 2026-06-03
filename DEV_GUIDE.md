# xmotp 厦门高端办公空间房源管理平台 — 开发手册

## 1. 项目概述

xmotp.com 是龙溪企服内部的**房源管理后台**，厦门 Only Top Person 品牌。

- **定位**：内部员工使用，管理全厦门在租写字楼/厂房房源数据
- **用户**：龙溪企服的招商经理，单一管理员账号
- **数据来源**：招商虾 Agent 每天扫描 58/安居客等平台、业主直租、同行推荐
- **部署位置**：阿里云 ECS 47.94.201.215（华北2北京，CentOS 7.9，2核2G）

## 2. 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Python 3.6 + Flask 2.x | CentOS 7 自带 Python 3.6，注意别用 3.8+ 语法 |
| 数据库 | SQLite | 单文件 xmotp.db，不需要额外安装 |
| WSGI | gunicorn 21.x | 2 worker，监听 127.0.0.1:5100 |
| 前端 | Jinja2 模板 + 原生 CSS | 无 JS 框架，纯服务端渲染 |
| 反向代理 | Nginx 1.20 | xmotp.com → proxy_pass 127.0.0.1:5100 |
| 运维 | systemd | 服务名 xmotp，开机自启 |

## 3. 项目结构

```
xmotp-platform/
├── app.py              # Flask 主应用（全部路由 + 数据库操作）
├── requirements.txt    # flask + gunicorn
├── .gitignore          # 排除 __pycache__ *.db
├── static/
│   └── style.css       # 全局样式（后台风格，暗色顶栏）
├── templates/
│   ├── base.html       # 基础布局（顶栏 + 容器）
│   ├── login.html      # 登录页
│   ├── index.html      # 房源列表（统计卡片 + 筛选栏 + 表格 + 分页）
│   ├── form.html       # 添加/编辑房源表单
│   ├── detail.html     # 房源详情
│   └── import.html     # CSV 批量导入页
└── xmotp.db            # SQLite 数据库（本地生成，不上传 Git）
```

## 4. 数据库结构

### users 表（用户）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| username | TEXT UNIQUE | admin |
| password_hash | TEXT | SHA256(密码) |
| display_name | TEXT | 显示名 |
| created_at | DATETIME | 创建时间 |

### listings 表（房源）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| district | TEXT | 区域：思明区/湖里区/集美区/海沧区/同安区/翔安区 |
| building_name | TEXT | 楼盘名（必填） |
| area_m2 | REAL | 面积(㎡) |
| rent_per_day | REAL | 日租金(元/㎡/天) |
| total_rent_month | REAL | 月租金(元) |
| floor_info | TEXT | 楼层信息 |
| decoration | TEXT | 装修：毛坯/简装/精装/豪华 |
| property_fee | REAL | 物业费(元/㎡/月) |
| parking | TEXT | 停车位信息 |
| lease_expiry | TEXT | 合同到期日 |
| source | TEXT | 来源：58同城/安居客/业主直租/朋友圈/同行推荐/客户转介/其他 |
| contact_name | TEXT | 联系人 |
| contact_phone | TEXT | 联系电话 |
| notes | TEXT | 备注 |
| status | TEXT | 状态：在租/已成交/已下架 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

## 5. 路由表

| 路由 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/login` | GET/POST | 否 | 登录页 |
| `/logout` | GET | 否 | 退出 |
| `/` | GET | 是 | 房源列表（带筛选、排序、分页） |
| `/listing/new` | GET/POST | 是 | 添加房源 |
| `/listing/<id>/edit` | GET/POST | 是 | 编辑房源 |
| `/listing/<id>/delete` | POST | 是 | 下架房源（软删除，改状态为"已下架"） |
| `/listing/<id>/detail` | GET | 是 | 房源详情 |
| `/export` | GET | 是 | 导出在租房源为 CSV |
| `/import` | GET/POST | 是 | 批量导入 CSV/Excel |
| `/import/template` | GET | 是 | 下载 CSV 导入模板 |

### index 筛选参数

| 参数 | 说明 |
|------|------|
| `district` | 区域精确匹配 |
| `status` | 在租/已成交/已下架/全部 |
| `keyword` | 模糊搜：楼盘名/联系人/电话/备注 |
| `area_min` / `area_max` | 面积范围 |
| `rent_min` / `rent_max` | 日租金范围 |
| `days` | 时间范围：1/3/7/30（最近N天新增） |
| `sort` | 排序：updated/created/area/rent |
| `page` | 分页，每页20条 |

## 6. 导入逻辑（重要）

- 支持 CSV（UTF-8/GBK 自动识别）和 Excel(.xlsx)
- 去重规则：**同区域 + 同楼盘名 + 同面积** → 更新现有数据，不新增
- 楼盘名为空的行跳过
- 导入后状态自动设为"在租"

## 7. 部署信息

| 项目 | 值 |
|------|-----|
| 服务器 IP | 47.94.201.215 |
| SSH | root / Huage2026xx |
| 项目路径 | /var/www/xmotp/ |
| systemd 服务 | xmotp（`systemctl restart xmotp`） |
| 端口 | 127.0.0.1:5100 |
| Nginx conf | /etc/nginx/conf.d/xmotp.conf |
| 数据库 | /var/www/xmotp/xmotp.db |

### 更新部署命令

```bash
# 本地打包
cd xmotp-platform
tar czf /tmp/xmotp_v3.tar.gz --exclude=__pycache__ --exclude=*.db --exclude=.git .

# 上传
sshpass -p 'Huage2026xx' scp /tmp/xmotp_v3.tar.gz root@47.94.201.215:/tmp/

# 服务器解压 + 重启
sshpass -p 'Huage2026xx' ssh root@47.94.201.215 '
  tar xzf /tmp/xmotp_v3.tar.gz -C /var/www/xmotp/
  systemctl restart xmotp
  systemctl is-active xmotp
'
```

## 8. 默认账号

| 用户名 | 密码 | 备注 |
|--------|------|------|
| admin | admin123 | SHA256 存储，改密码需重算 hash |

## 9. 开发注意事项

1. **Python 3.6 兼容** — CentOS 7 只有 3.6，不能用 f-string（3.6 支持但受限）、海象运算符、match-case 等
2. **SQLite 注意** — 多 worker 模式下 WAL 模式已开启，并发写没问题
3. **不需要 ORM** — 直接写 SQL，保持简单
4. **不加 JS 框架** — 目前纯服务端渲染够用，除非要加前端交互
5. **域名未备案** — xmotp.com 暂时不能绑定国内节点，备案下来前通过 IP+Host 头访问
6. **Git 提交** — 不要提交 xmotp.db、__pycache__/
7. **与 longc-es 共存** — 同一台服务器，不同 Nginx server_name 区分，互不影响

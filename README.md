# ShadeCanopy-01 · 分区气候日志、轮灌计划与遮阳行程

温室「分区气候日志、轮灌计划与遮阳帘行程」全栈种子项目（非考勤 OA、非库存）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python Django 5 · Django REST Framework · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端容器反代 `/api` → Django） |

## 路径与端口

- **项目路径**：`D:\work\document\bytecode\claudeCodePro\ShadeCanopy\ShadeCanopy-01\`
- **前端**：http://localhost:3500
- **后端 API**：http://localhost:8500（也可经前端同源 `/api` 访问）
- **PostgreSQL**：localhost:5435

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | admin（管理员，可进 Django Admin） |
| `grower` | `123456` | grower（种植员） |

启动时 `entrypoint.sh` 会执行 `migrate` + `seed_data` 自动写入账号与示例业务数据。

## 快速启动

```bash
cd D:\work\document\bytecode\claudeCodePro\ShadeCanopy\ShadeCanopy-01
docker compose up --build
```

浏览器打开 http://localhost:3500 ，使用 `grower` / `123456` 登录。

停止：

```bash
docker compose down
```

## 业务模块

1. **Auth**：JWT `POST /api/auth/token/`，当前用户 `GET /api/auth/me/`
2. **Greenhouse**：name / location / areaM2 / notes
3. **Zone**：greenhouseId / zoneCode / cropName / status(`idle|growing|fallow`)；同温室 zoneCode 唯一；列表每行附带 `lastShadeAt`（该区最新遮阳行程的操作时刻，无行程为 `null`）
4. **ClimateLog**：zoneId / recordedAt / tempC / humidityPct / parUmol / co2Ppm；**humidityPct ∈ [20, 100]**
5. **IrrigationCycle**：zoneId / startAt / durationMin / waterLiters / status(`scheduled|running|done|skipped`)
6. **ShadeTravel（遮阳行程）**：zoneId / direction(`open|close`) / extent(1～100 整数) / operatedAt / operatorName / note
7. **Dashboard**：温室数、growing 分区数、近 24h 气候日志数、今日 scheduled 轮灌数 → `GET /api/dashboard/`

## 遮阳行程规则

- 行程挂在分区上，`direction` 取 `open`（拉开）或 `close`（收拢），`extent` 为 1～100 的整数幅度。
- **空闲分区（idle）禁止登记**（400）；**休耕分区（fallow）允许登记，但 `note` 备注必填**（400）。
- **同分区在 `operatedAt` 前后 15 分钟内（含边界）不得有第二条行程**，冲突返回 **409**，响应体带上已有行程编号：

  ```json
  {
    "detail": "与行程 #12 的操作时刻间隔不足 15 分钟",
    "conflictTravelId": 12,
    "conflictOperatedAt": "2026-09-20T12:30:00+08:00"
  }
  ```

- **与气候采样联动**：方向为 `open` 且 `extent > 60`（即 ≥ 61）时，创建行程成功的**同一数据库事务**内必须再写一条 ClimateLog；任一失败整体回滚（只落行程不写气候视为未完成）。联动气候记录的默认值（常量定义在 `backend/core/models.py`）：

  | 字段 | 默认值 | 说明 |
  | --- | --- | --- |
  | `recordedAt` | = 行程 `operatedAt` | 采样时刻等于操作时刻 |
  | `parUmol` | **120** | 光合有效辐射，小于 200 的正数（`SHADE_LINKED_CLIMATE_PAR`） |
  | `tempC` | 26.00 | `SHADE_LINKED_CLIMATE_TEMP_C` |
  | `humidityPct` | 60.00 | `SHADE_LINKED_CLIMATE_HUMIDITY_PCT` |
  | `co2Ppm` | 600.00 | `SHADE_LINKED_CLIMATE_CO2_PPM` |

  `close` 任意幅度、或 `open` 且幅度 ≤ 60，均不联动气候记录。
- 行程只支持新建 / 查询 / 删除，不提供编辑接口，保证「操作时刻不可事后篡改」。
- 前端侧栏「遮阳行程」入口（`/shade-travels`）可登记、按分区/方向筛选、查看冲突编号；分区管理列表每行展示「最近帘程时刻」。

## API 一览

| 方法 | 路径 |
| --- | --- |
| POST | `/api/auth/token/` |
| POST | `/api/auth/token/refresh/` |
| GET | `/api/auth/me/` |
| CRUD | `/api/greenhouses/` |
| CRUD | `/api/zones/?greenhouseId=&status=` |
| CRUD | `/api/climate-logs/?zoneId=` |
| CRUD | `/api/irrigation-cycles/?zoneId=&status=` |
| GET/POST/DELETE | `/api/shade-travels/?zoneId=&direction=`（冲突 → 409 + `conflictTravelId`） |
| GET | `/api/dashboard/` |

字段对外使用 camelCase（如 `areaM2`、`zoneCode`、`humidityPct`、`operatedAt`）。

### 登记行程示例

```bash
TOKEN=$(curl -s localhost:8500/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"grower","password":"123456"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access"])')

curl -i localhost:8500/api/shade-travels/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"zoneId":1,"direction":"open","extent":80,"operatedAt":"2026-09-20T12:30:00+08:00","operatorName":"张师傅","note":"午间强光"}'
```

## 种子数据中的遮阳行程样例

执行 `seed_data` 后（操作时刻均相对启动时间计算）：

| 分区 | 状态 | 行程 | 联动气候 | 用途 |
| --- | --- | --- | --- | --- |
| A-01 | 在种 | 拉开 80%，约 **10 分钟前** | 是（PAR=120） | 可成功的拉开行程；同时是 **15 分钟冲突样例**——启动后立即对 A-01 以当前时刻再登记任意行程，会返回 409 并指向该行程编号 |
| A-02 | 在种 | 收拢 50%，约 2 小时前 | 否 | 收拢不联动 |
| B-02 | 休耕 | 拉开 70%，约 90 分钟前（带备注） | 是（PAR=120） | 休耕分区备注必填 |
| A-03 | 空闲 | — | — | 对其登记行程返回 400，用于验证空闲禁登 |

## 本地开发（可选）

**后端**（需本机 Postgres 或已启动 compose 中的 db）：

```bash
cd backend
pip install -r requirements.txt
set POSTGRES_HOST=127.0.0.1
set POSTGRES_PORT=5435
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:8500
```

**前端**：

```bash
cd frontend
npm install
npm run dev
```

Vite 已将 `/api` 代理到 `http://127.0.0.1:8500`。

## 目录结构

```
ShadeCanopy-01/
├── docker-compose.yml
├── README.md
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh      # migrate + seed + gunicorn
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/            # settings / urls
│   ├── accounts/          # 自定义 User + role
│   └── core/              # 温室/分区/气候/轮灌/遮阳行程 + seed_data
└── frontend/
    ├── Dockerfile
    ├── nginx.conf         # 静态资源 + /api 反代
    ├── package.json
    └── src/               # Vue 页面（叶绿/土色主题）
```

## 配色说明

前端采用叶绿（`#3d6b3a`）与土色（`#8b6b45`）主色，米色底与侧栏深绿渐变，贴近温室场景。

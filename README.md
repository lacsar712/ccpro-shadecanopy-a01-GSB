# ShadeCanopy-01 · 分区气候日志、轮灌计划与遮阳行程

温室「分区气候日志、轮灌计划与遮阳行程」全栈种子项目（非考勤 OA、非库存）。

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

种子中的遮阳行程：分区 A-01 有一条拉开 80% 的成功行程（操作时刻约 40 分钟前，已联动一条 PAR=120 的气候记录），A-02 有一条收拢行程，休耕分区 B-02 有一条带备注的拉开行程；另有一条与 A-01 成功行程相隔 10 分钟的**冲突样例**，种子执行时会按 15 分钟规则拒绝并在日志打印已有行程编号（`conflictTravelId`），该样例不入库。

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
3. **Zone**：greenhouseId / zoneCode / cropName / status(`idle|growing|fallow`)；同温室 zoneCode 唯一；列表附带 `lastShadeAt`（该区最新遮阳行程的操作时刻，无行程为 `null`）
4. **ClimateLog**：zoneId / recordedAt / tempC / humidityPct / parUmol / co2Ppm；**humidityPct ∈ [20, 100]**
5. **IrrigationCycle**：zoneId / startAt / durationMin / waterLiters / status(`scheduled|running|done|skipped`)
6. **ShadeTravel（遮阳行程）**：见下节
7. **Dashboard**：温室数、growing 分区数、近 24h 气候日志数、今日 scheduled 轮灌数 → `GET /api/dashboard/`

## 遮阳行程（ShadeTravel）

行程挂在分区上，记录遮阳帘拉开或收拢的幅度，并与气候采样联动。

**字段**（对外 camelCase）：

| 字段 | 说明 |
| --- | --- |
| `zoneId` | 所属分区 |
| `direction` | 方向：`open` 拉开 / `close` 收拢 |
| `extent` | 幅度，**1～100 的整数** |
| `operatedAt` | 操作时刻 |
| `operatorName` | 操作人姓名 |
| `notes` | 备注（休耕分区必填，其余选填） |

**业务规则**：

- **15 分钟互斥**：同一分区在 `operatedAt` 前后 15 分钟（含边界）内不得存在第二条行程。冲突返回 **HTTP 409**：
  ```json
  { "detail": "同分区操作时刻前后 15 分钟内已存在行程", "conflictTravelId": 12 }
  ```
  `conflictTravelId` 即窗口内已有行程的编号。
- **空闲分区禁止登记**（`status=idle` 返回 400）；**休耕分区允许，但 `notes` 必填**。
- **气候联动**：当 `direction=open` 且 `extent > 60` 时，创建行程的**同一数据库事务**内再写一条 `ClimateLog`，二者同时成功或同时回滚（只落行程不写气候视为未完成）。联动气候记录：
  - `recordedAt = operatedAt`（采样时刻等于操作时刻）
  - `parUmol`（光合有效辐射）= **120.00**（小于 200 的正数，系统默认值）
  - 其余默认值：`tempC=25.00`、`humidityPct=60.00`、`co2Ppm=450.00`

  以上默认值集中定义在后端 `core/services.py`（`SHADE_LINKED_*` 常量），调整时改此处即可。

行程接口仅开放新建（POST）、查询（GET 列表/详情）与删除（DELETE），不提供 PUT/PATCH。

## API 一览

| 方法 | 路径 |
| --- | --- |
| POST | `/api/auth/token/` |
| POST | `/api/auth/token/refresh/` |
| GET | `/api/auth/me/` |
| CRUD | `/api/greenhouses/` |
| CRUD | `/api/zones/?greenhouseId=&status=`（含 `lastShadeAt`） |
| CRUD | `/api/climate-logs/?zoneId=` |
| CRUD | `/api/irrigation-cycles/?zoneId=&status=` |
| GET/POST/DELETE | `/api/shade-travels/?zoneId=&direction=`（冲突 409 + `conflictTravelId`） |
| GET | `/api/dashboard/` |

字段对外使用 camelCase（如 `areaM2`、`zoneCode`、`humidityPct`）。

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
│   └── core/              # 温室/分区/气候/轮灌/遮阳行程 + services + seed_data
│       ├── models.py      # 含 ShadeTravel
│       └── services.py    # register_shade_travel：15 分钟冲突 + 同事务气候联动
└── frontend/
    ├── Dockerfile
    ├── nginx.conf         # 静态资源 + /api 反代
    ├── package.json
    └── src/               # Vue 页面（叶绿/土色主题）
```

## 配色说明

前端采用叶绿（`#3d6b3a`）与土色（`#8b6b45`）主色，米色底与侧栏深绿渐变，贴近温室场景。

"""遮阳行程领域服务：登记行程的事务、冲突判定与气候联动。

视图与种子数据都走 ``register_shade_travel``，保证两条路径规则一致：
同分区操作时刻前后 15 分钟互斥；拉开且幅度 > 60 时同事务补写一条气候记录。
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction

from .models import ClimateLog, ShadeTravel, Zone

#: 同分区两条行程的最小间隔（前后 15 分钟，含边界）
SHADE_CONFLICT_WINDOW = timedelta(minutes=15)

#: 拉开幅度超过该值时联动写入气候记录
SHADE_LINK_EXTENT_THRESHOLD = 60

# 联动气候记录默认值（README「遮阳行程」章节同步说明）
SHADE_LINKED_PAR_UMOL = Decimal("120.00")
SHADE_LINKED_TEMP_C = Decimal("25.00")
SHADE_LINKED_HUMIDITY_PCT = Decimal("60.00")
SHADE_LINKED_CO2_PPM = Decimal("450.00")


class ShadeTravelConflict(Exception):
    """同分区在 15 分钟窗口内已存在行程。"""

    def __init__(self, conflict_travel_id):
        self.conflict_travel_id = conflict_travel_id
        super().__init__(f"同分区操作时刻前后 15 分钟内已存在行程 #{conflict_travel_id}")


def register_shade_travel(*, zone, direction, extent, operated_at, operator_name, notes=""):
    """在同一事务内落行程，并按规则联动气候记录。

    任一步失败整体回滚——只落行程不写气候视为未完成。
    """
    with transaction.atomic():
        # 锁住分区行，把并发的第二条行程挡在窗口检查之外
        Zone.objects.select_for_update().get(pk=zone.pk)

        conflict = (
            ShadeTravel.objects.filter(
                zone_id=zone.pk,
                operated_at__gte=operated_at - SHADE_CONFLICT_WINDOW,
                operated_at__lte=operated_at + SHADE_CONFLICT_WINDOW,
            )
            .order_by("operated_at", "id")
            .first()
        )
        if conflict is not None:
            raise ShadeTravelConflict(conflict.id)

        travel = ShadeTravel.objects.create(
            zone=zone,
            direction=direction,
            extent=extent,
            operated_at=operated_at,
            operator_name=operator_name,
            notes=notes,
        )

        if direction == ShadeTravel.DIRECTION_OPEN and extent > SHADE_LINK_EXTENT_THRESHOLD:
            ClimateLog.objects.create(
                zone=zone,
                recorded_at=operated_at,
                temp_c=SHADE_LINKED_TEMP_C,
                humidity_pct=SHADE_LINKED_HUMIDITY_PCT,
                par_umol=SHADE_LINKED_PAR_UMOL,
                co2_ppm=SHADE_LINKED_CO2_PPM,
            )

        return travel

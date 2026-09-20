from datetime import timedelta
from decimal import Decimal

from django.db import connection, transaction
from rest_framework import serializers

from .models import (
    SHADE_LINKED_CLIMATE_CO2_PPM,
    SHADE_LINKED_CLIMATE_HUMIDITY_PCT,
    SHADE_LINKED_CLIMATE_PAR,
    SHADE_LINKED_CLIMATE_TEMP_C,
    SHADE_TRAVEL_GAP_MINUTES,
    ClimateLog,
    ShadeTravel,
    Zone,
)


class ShadeTravelConflict(Exception):
    """同分区操作时刻前后 15 分钟内已存在行程。"""

    def __init__(self, travel):
        self.travel = travel
        super().__init__(f"与行程 #{travel.id} 的操作时刻间隔不足 {SHADE_TRAVEL_GAP_MINUTES} 分钟")


def create_shade_travel(*, zone, direction, extent, operated_at, operator_name, note):
    """登记一条遮阳行程。

    - 空闲分区禁止登记；休耕分区允许但备注必填；
    - 同分区操作时刻前后 15 分钟（含边界）内不得有第二条行程，否则抛
      ShadeTravelConflict（携带已有行程）；
    - 方向为拉开且幅度 > 60 时，与行程在同一事务内写一条气候记录，
      采样时刻等于操作时刻，PAR 取默认正数（< 200）。
    """
    note = (note or "").strip()
    if zone.status == Zone.STATUS_IDLE:
        raise serializers.ValidationError({"zoneId": "空闲分区禁止登记遮阳行程"})
    if zone.status == Zone.STATUS_FALLOW and not note:
        raise serializers.ValidationError({"note": "休耕分区登记遮阳行程时备注必填"})

    with transaction.atomic():
        # 锁住分区行，避免两个并发行程同时通过冲突检查。
        # SQLite 不支持 SELECT FOR UPDATE（仅本地检查用），降级为普通读取。
        try:
            locked_zone = Zone.objects.select_for_update().get(pk=zone.pk)
        except connection.features.not_supported_error_cls:
            locked_zone = zone
        window = timedelta(minutes=SHADE_TRAVEL_GAP_MINUTES)
        conflict = (
            ShadeTravel.objects.filter(
                zone=locked_zone,
                operated_at__gte=operated_at - window,
                operated_at__lte=operated_at + window,
            )
            .order_by("operated_at")
            .first()
        )
        if conflict is not None:
            raise ShadeTravelConflict(conflict)

        travel = ShadeTravel.objects.create(
            zone=locked_zone,
            direction=direction,
            extent=extent,
            operated_at=operated_at,
            operator_name=operator_name,
            note=note,
        )

        if direction == ShadeTravel.DIRECTION_OPEN and extent > 60:
            ClimateLog.objects.create(
                zone=locked_zone,
                recorded_at=operated_at,
                temp_c=Decimal(SHADE_LINKED_CLIMATE_TEMP_C),
                humidity_pct=Decimal(SHADE_LINKED_CLIMATE_HUMIDITY_PCT),
                par_umol=Decimal(SHADE_LINKED_CLIMATE_PAR),
                co2_ppm=Decimal(SHADE_LINKED_CLIMATE_CO2_PPM),
            )

        return travel

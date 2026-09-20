from datetime import timedelta

from django.db.models import Count, Max
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClimateLog, Greenhouse, IrrigationCycle, ShadeTravel, Zone
from .serializers import (
    ClimateLogSerializer,
    GreenhouseSerializer,
    IrrigationCycleSerializer,
    ShadeTravelSerializer,
    ZoneSerializer,
)
from .services import ShadeTravelConflict, register_shade_travel


class GreenhouseViewSet(viewsets.ModelViewSet):
    queryset = Greenhouse.objects.annotate(zone_count=Count("zones")).all()
    serializer_class = GreenhouseSerializer


class ZoneViewSet(viewsets.ModelViewSet):
    serializer_class = ZoneSerializer

    def get_queryset(self):
        qs = Zone.objects.select_related("greenhouse").annotate(
            last_shade_at=Max("shade_travels__operated_at")
        ).order_by("greenhouse_id", "zone_code")
        greenhouse_id = self.request.query_params.get("greenhouseId")
        status_param = self.request.query_params.get("status")
        if greenhouse_id:
            qs = qs.filter(greenhouse_id=greenhouse_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class ClimateLogViewSet(viewsets.ModelViewSet):
    serializer_class = ClimateLogSerializer

    def get_queryset(self):
        qs = ClimateLog.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        return qs


class IrrigationCycleViewSet(viewsets.ModelViewSet):
    serializer_class = IrrigationCycleSerializer

    def get_queryset(self):
        qs = IrrigationCycle.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        status_param = self.request.query_params.get("status")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class ShadeTravelViewSet(viewsets.ModelViewSet):
    serializer_class = ShadeTravelSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = ShadeTravel.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        direction = self.request.query_params.get("direction")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        if direction:
            qs = qs.filter(direction=direction)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            travel = register_shade_travel(
                zone=data["zone"],
                direction=data["direction"],
                extent=data["extent"],
                operated_at=data["operated_at"],
                operator_name=data["operator_name"],
                notes=data.get("notes", ""),
            )
        except ShadeTravelConflict as exc:
            return Response(
                {
                    "detail": "同分区操作时刻前后 15 分钟内已存在行程",
                    "conflictTravelId": exc.conflict_travel_id,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            self.get_serializer(travel).data, status=status.HTTP_201_CREATED
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    data = {
        "greenhouseCount": Greenhouse.objects.count(),
        "growingZoneCount": Zone.objects.filter(status=Zone.STATUS_GROWING).count(),
        "climateLogLast24h": ClimateLog.objects.filter(
            recorded_at__gte=since_24h
        ).count(),
        "irrigationScheduledToday": IrrigationCycle.objects.filter(
            status=IrrigationCycle.STATUS_SCHEDULED,
            start_at__gte=today_start,
            start_at__lt=today_end,
        ).count(),
    }
    return Response(data)

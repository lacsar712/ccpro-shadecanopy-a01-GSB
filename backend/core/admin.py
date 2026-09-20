from django.contrib import admin

from .models import ClimateLog, Greenhouse, IrrigationCycle, ShadeTravel, Zone


@admin.register(Greenhouse)
class GreenhouseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "location", "area_m2")
    search_fields = ("name", "location")


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("id", "greenhouse", "zone_code", "crop_name", "status")
    list_filter = ("status", "greenhouse")
    search_fields = ("zone_code", "crop_name")


@admin.register(ClimateLog)
class ClimateLogAdmin(admin.ModelAdmin):
    list_display = ("id", "zone", "recorded_at", "temp_c", "humidity_pct", "par_umol", "co2_ppm")
    list_filter = ("zone",)


@admin.register(IrrigationCycle)
class IrrigationCycleAdmin(admin.ModelAdmin):
    list_display = ("id", "zone", "start_at", "duration_min", "water_liters", "status")
    list_filter = ("status", "zone")


@admin.register(ShadeTravel)
class ShadeTravelAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "zone",
        "direction",
        "extent",
        "operated_at",
        "operator_name",
        "note",
    )
    list_filter = ("direction", "zone__greenhouse")
    search_fields = ("operator_name", "note")
    date_hierarchy = "operated_at"

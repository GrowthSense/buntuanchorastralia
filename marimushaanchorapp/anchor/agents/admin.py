from django.contrib import admin
from .models import Agent, CashPayout

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "hours", "active")
    list_filter = ("active",)

@admin.register(CashPayout)
class CashPayoutAdmin(admin.ModelAdmin):
    list_display = ("transaction", "agent", "pickup_code", "ready", "paid_out_at")
    list_filter = ("ready", "paid_out_at", "agent")
    search_fields = ("pickup_code",)

from rest_framework import serializers
from .models import Agent, CashPayout

class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ["id", "public_id", "name", "location", "hours", "active"]


class CashPayoutListSerializer(serializers.ModelSerializer):
    amount_out = serializers.SerializerMethodField()
    asset_code = serializers.SerializerMethodField()
    agent_name = serializers.CharField(source="agent.name", read_only=True)
    agent_location = serializers.CharField(source="agent.location", read_only=True)
    transaction_id = serializers.CharField(source="transaction.id", read_only=True)
    payout_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = CashPayout
        fields = [
            "payout_id", "transaction_id", "pickup_code", "expires_at", "ready",
            "agent_name", "agent_location", "amount_out", "asset_code",
        ]

    def get_amount_out(self, obj):
        return str(getattr(obj.transaction, "amount_out", ""))

    def get_asset_code(self, obj):
        asset = getattr(obj.transaction, "asset", None)
        return getattr(asset, "code", "") if asset else ""

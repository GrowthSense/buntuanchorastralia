# marimushaanchorapp/anchor/agents/views.py

from uuid import UUID

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model

from rest_framework import viewsets, permissions, exceptions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication,
    BasicAuthentication,
)

from .models import Agent, CashPayout
from .serializers import AgentSerializer, CashPayoutListSerializer


# ───────────────────────────────────────────────────────────────────────────────
# Service-to-Service Auth (Nest → Django)
# ───────────────────────────────────────────────────────────────────────────────
class ServiceTokenAuth(BaseAuthentication):
    """
    Accepts: Authorization: Bearer <PYTHON_SERVICE_TOKEN>
    Put this first in authentication_classes to bypass CSRF for POSTs from Nest.
    Returns a concrete 'nest_service' user so DRF's IsAuthenticated passes.
    """
    keyword = "Bearer"

    def authenticate(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith(self.keyword + " "):
            return None  # fall through to Session/Basic if present

        token = auth[len(self.keyword) + 1:].strip()
        expected = getattr(settings, "PYTHON_SERVICE_TOKEN", None)
        if not expected or token != expected:
            raise exceptions.AuthenticationFailed("Invalid service token")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="nest_service",
            defaults={"is_active": True, "is_staff": True},
        )
        if created:
            try:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            except Exception:
                pass

        return (user, None)


# ───────────────────────────────────────────────────────────────────────────────
# Permissions
# ───────────────────────────────────────────────────────────────────────────────
class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)


# ───────────────────────────────────────────────────────────────────────────────
# Agent CRUD (DRF ViewSet)
# ───────────────────────────────────────────────────────────────────────────────
class AgentViewSet(viewsets.ModelViewSet):
    """
    Endpoints:
      GET    /api/agents/               list
      POST   /api/agents/               create   (staff)
      GET    /api/agents/{id}/          retrieve
      PUT    /api/agents/{id}/          update   (staff)
      PATCH  /api/agents/{id}/          partial  (staff)
      DELETE /api/agents/{id}/          delete   (staff)
      POST   /api/agents/{id}/activate/     (staff)
      POST   /api/agents/{id}/deactivate/   (staff)
    """
    queryset = Agent.objects.all().order_by("id")
    serializer_class = AgentSerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def activate(self, request, pk=None):
        a = self.get_object()
        a.active = True
        a.save(update_fields=["active"])
        return Response({"ok": True, "active": a.active})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def deactivate(self, request, pk=None):
        a = self.get_object()
        a.active = False
        a.save(update_fields=["active"])
        return Response({"ok": True, "active": a.active})


# ───────────────────────────────────────────────────────────────────────────────
# Payouts: Ready / Lookup / Complete
# ───────────────────────────────────────────────────────────────────────────────
class ReadyPayoutsView(APIView):
    """
    GET /api/payouts/ready/?agent_id=<int pk or uuid public_id>
    Returns payouts with ready=True and not yet paid.
    Falls back to X-Actor-Id header when agent_id is missing.

    NOTE: We *do not* OR int and UUID filters together to avoid coercion errors.
    """
    authentication_classes = [ServiceTokenAuth, SessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        raw_id = request.query_params.get("agent_id") or request.META.get("HTTP_X_ACTOR_ID")

        qs = (
            CashPayout.objects
            .select_related("agent", "transaction")
            .filter(ready=True, paid_out_at__isnull=True)
        )

        if raw_id:
            applied = False

            # Try integer FK (Agent.id)
            try:
                int_id = int(str(raw_id))
                qs = qs.filter(agent_id=int_id)
                applied = True
            except (TypeError, ValueError):
                pass

            # Try UUID (Agent.public_id)
            if not applied:
                try:
                    UUID(str(raw_id))  # validate UUID format first
                    qs = qs.filter(agent__public_id=str(raw_id))
                    applied = True
                except ValueError:
                    pass

            if not applied:
                return Response(
                    {"detail": "agent_id must be an integer id or a valid UUID public_id"},
                    status=400,
                )

        data = CashPayoutListSerializer(qs, many=True).data
        return Response({"payouts": data})


class LookupPayoutView(APIView):
    """
    POST /api/payouts/lookup/
    body: { "pickup_code": "AB12CD34" }
    """
    authentication_classes = [ServiceTokenAuth, SessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get("pickup_code")
        if not code:
            return Response({"detail": "pickup_code is required"}, status=400)

        cp = get_object_or_404(
            CashPayout.objects.select_related("agent", "transaction"),
            pickup_code=code,
            paid_out_at__isnull=True,
        )
        return Response(CashPayoutListSerializer(cp).data)


class CompletePayoutView(APIView):
    """
    POST /api/payouts/complete/
    body: { "anchor_tx_id": "<uuid>", "pickup_code": "AB12CD34" }

    Marks payout completed and updates the related transaction.
    Uses cache-based idempotency via Idempotency-Key header (best-effort).
    """
    authentication_classes = [ServiceTokenAuth, SessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        anchor_tx_id = request.data.get("anchor_tx_id")
        pickup_code = request.data.get("pickup_code")
        if not anchor_tx_id or not pickup_code:
            return Response({"detail": "anchor_tx_id and pickup_code are required"}, status=400)

        # ---- Idempotency (cache-based) ----
        idem = request.META.get("HTTP_IDEMPOTENCY_KEY")
        if not idem:
            return Response({"detail": "Idempotency-Key header required"}, status=400)
        cache_key = f"idem:complete:{idem}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # ---- Core validations ----
        cp = get_object_or_404(
            CashPayout.objects.select_related("transaction"),
            transaction_id=anchor_tx_id,
        )
        if cp.pickup_code != pickup_code:
            return Response({"detail": "Invalid pickup code"}, status=400)
        if cp.expires_at and timezone.now() > cp.expires_at:
            return Response({"detail": "Pickup code expired"}, status=410)
        if not cp.ready:
            return Response({"detail": "Payout not ready"}, status=409)
        if cp.paid_out_at:
            payload = {"ok": True, "completed_at": cp.paid_out_at.isoformat()}
            cache.set(cache_key, payload, timeout=60 * 60)
            return Response(payload)

        # ---- Complete payout ----
        now = timezone.now()
        cp.paid_out_at = now

        # Auth user here is the service user (nest_service).
        # If you also want to record the human agent, pass X-Actor-Id and resolve Agent here.
        if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False):
            cp.paid_out_by = request.user
            cp.save(update_fields=["paid_out_at", "paid_out_by"])
        else:
            cp.save(update_fields=["paid_out_at"])

        cp.transaction.status = "completed"
        cp.transaction.completed_at = now
        cp.transaction.save(update_fields=["status", "completed_at"])

        payload = {"ok": True, "completed_at": now.isoformat()}
        cache.set(cache_key, payload, timeout=60 * 60)
        return Response(payload)

class AllPayoutsView(APIView):
    """
    GET /api/payouts/all/?agent_id=<int pk or uuid public_id>
    Returns *all* payouts (ready or not, paid or unpaid) for an agent.
    Falls back to X-Actor-Id header if agent_id not provided.
    """
    authentication_classes = [ServiceTokenAuth, SessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        raw_id = request.query_params.get("agent_id") or request.META.get("HTTP_X_ACTOR_ID")

        qs = CashPayout.objects.select_related("agent", "transaction").all()

        if raw_id:
            from uuid import UUID
            applied = False

            # Try int Agent.id
            try:
                int_id = int(str(raw_id))
                qs = qs.filter(agent_id=int_id)
                applied = True
            except (TypeError, ValueError):
                pass

            # Try UUID Agent.public_id
            if not applied:
                try:
                    UUID(str(raw_id))
                    qs = qs.filter(agent__public_id=str(raw_id))
                    applied = True
                except ValueError:
                    pass

            if not applied:
                return Response(
                    {"detail": "agent_id must be an integer id or a valid UUID public_id"},
                    status=400,
                )

        data = CashPayoutListSerializer(qs, many=True).data
        return Response({"payouts": data})

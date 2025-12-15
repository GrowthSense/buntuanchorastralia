# marimushaanchorapp/anchor/agents/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AgentViewSet, ReadyPayoutsView, LookupPayoutView, CompletePayoutView, AllPayoutsView

app_name = "agents"

router = DefaultRouter()
router.register(r'agents', AgentViewSet, basename='agent')

urlpatterns = [
    # Health to prove this file is loaded at /api/health/
    path('health/', ReadyPayoutsView.as_view(), name='health'),

    # Payouts endpoints (final URLs: /api/payouts/...)
    path('payouts/ready/', ReadyPayoutsView.as_view(), name='payouts-ready'),
    path('payouts/lookup/', LookupPayoutView.as_view(), name='payouts-lookup'),
    path('payouts/complete/', CompletePayoutView.as_view(), name='payouts-complete'),
    path('payouts/all/', AllPayoutsView.as_view(), name='payouts-all'),
]

urlpatterns += router.urls

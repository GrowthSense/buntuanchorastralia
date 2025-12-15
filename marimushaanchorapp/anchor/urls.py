# marimushaanchorapp/anchor/urls.py
import polaris.urls
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponseRedirect
from .views import (
    internal_transaction_list, get_transaction,
    approve_transaction, approve_transaction_withdrawal,
    reject_transaction, get_customer_kyc, approve_kyc, reject_kyc,
    get_all_customers, agents_collection, agent_detail, sep1_stellar_toml, kyc_webhook, wallet_transfer_webhook, agent_cash_deposit, approve_cash_payout, list_pending_cash_payouts, mark_cash_payout_ready
)
from .sep6_info import sep6_info

print(">> anchor.urls loaded (mounting Polaris first)")

urlpatterns = [
    # Mount Polaris FIRST at root to handle SEP endpoints
    path("", include(polaris.urls)),  # This handles /auth, /transactions, etc.
    
    # Admin
    path('admin/', admin.site.urls),

    # Your API routes
    path('api/', include('marimushaanchorapp.anchor.agents.urls', namespace='agents')),

    # Stellar.toml - FIXED path (remove the duplicate)
    path('.well-known/stellar.toml', sep1_stellar_toml),  # Create this view (see below)

    # SEP-6 info
    path('sep6/info', sep6_info),

    # Internal routes
    path('internal/transactions', internal_transaction_list),
    path('internal/transaction/<str:transaction_id>/', get_transaction),
    path('internal/transaction/<str:transaction_id>/approve/', approve_transaction),
    path("wallet-transfer-webhook/", wallet_transfer_webhook, name="wallet_transfer_webhook"),
    path('internal/transaction/<str:transaction_id>/approve-withdrawal/', approve_transaction_withdrawal),
    path('internal/transaction/<str:transaction_id>/reject/', reject_transaction),
    path('internal/customer/<str:stellar_account>/', get_customer_kyc),
    path('internal/customers/', get_all_customers),
    path('internal/kyc/<str:stellar_account>/approve/', approve_kyc),
    path('internal/kyc/<str:stellar_account>/reject/', reject_kyc),
    path('internal/agents/', agents_collection),
    path('internal/agents/<uuid:agent_id>/', agent_detail),
    path('webhook/kyc/', kyc_webhook, name='kyc_webhook'),
    path('internal/agents/deposits/', agent_cash_deposit, name='agent_cash_deposit'),
    path('internal/withdrawals/cash/approve/', approve_cash_payout, name='approve_cash_payout'),
    path('internal/cash-payouts/pending', list_pending_cash_payouts),
    path('internal/cash-payout/change/status', mark_cash_payout_ready )
]
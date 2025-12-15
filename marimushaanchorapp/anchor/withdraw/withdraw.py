# anchor/withdraw/withdraw.py

from typing import Dict, List, Optional
from decimal import Decimal
from datetime import timedelta
import secrets

from django.conf import settings
from django.utils import timezone

from stellar_sdk import Keypair  # for deriving the anchor receive account

from polaris.integrations import WithdrawalIntegration
from polaris.sep10.token import SEP10Token
from polaris.models import Transaction
from rest_framework.request import Request

from marimushaanchorapp.anchor.users import user_for_account
from marimushaanchorapp.anchor.rails import calculate_fee, memo_for_transaction

# ⬇️ your cash-out models
from marimushaanchorapp.anchor.agents.models import Agent, CashPayout

import requests


def _pickup_code(n: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _anchor_receive_account() -> str:
    """
    The account your wallet should pay for SEP-6 withdraw.
    We derive it from STELLAR_SECRET_KEY (distribution hot wallet).
    """
    seed = getattr(settings, "STELLAR_SECRET_KEY", None)
    if not seed:
        raise RuntimeError("STELLAR_SECRET_KEY is not configured")
    return Keypair.from_secret(seed).public_key


class AnchorWithdraw(WithdrawalIntegration):
    def process_sep6_request(
        self,
        token: SEP10Token,
        request: Request,
        params: Dict,
        transaction: Transaction,
        *args: List,
        **kwargs: Dict
    ) -> Dict:
        """
        Called when the wallet hits /sep6/withdraw.
        We:
          - run KYC checks
          - compute amount_out & fees
          - return account_id + memo + memo_type
          - for cash: create CashPayout
          - for bank: just record to_address (optional) and return instructions
        """
        # Read type early so KYC checks can be context-aware
        withdrawal_type = (params.get("type") or "").strip()

        # This will resolve using SEP-10 account (muxed or normal)
        user = user_for_account(token.muxed_account or token.account)

        # ── Step 1: KYC checks (cash does NOT require bank details)
        if not user or not user.kyc_approved:
            if user and getattr(user, "kyc_rejected", False):
                return {"type": "customer_info_status", "status": "denied"}

            required_fields = [
                "first_name",
                "last_name",
                "email_address",
                "address",
            ]
            # Only require bank fields when sending to bank
            if withdrawal_type in ("bank_account", "bank_transfer"):
                required_fields += ["bank_account_number", "bank_number"]

            missing_fields = [
                f for f in required_fields
                if not getattr(user, f, None)
            ]

            if not missing_fields:
                return {"type": "customer_info_status", "status": "pending"}
            else:
                return {
                    "type": "non_interactive_customer_info_needed",
                    "fields": missing_fields,
                }

        # ── Step 2: Fee & amount_out
        transaction.amount_fee = calculate_fee(transaction)
        transaction.amount_out = round(
            transaction.amount_in - Decimal(transaction.amount_fee),
            transaction.asset.significant_decimals
        )
        transaction.save()

        # ── Step 3: Prepare response common bits
        account_id = _anchor_receive_account()              # where wallet sends funds
        memo = memo_for_transaction(transaction)            # wallet must use this memo
        memo_type = "text"                                  # change to "hash"/"id" if you implement that

        # ── Step 4: Branch by type

        # 4A) CASH WITHDRAWAL
        if withdrawal_type == "cash":
            # Create or fetch a CashPayout row tied to this Polaris transaction
            payout, _ = CashPayout.objects.get_or_create(
                transaction=transaction,
                defaults={
                    "pickup_code": _pickup_code(8),
                    "expires_at": timezone.now() + timedelta(hours=24),
                    "ready": False,
                }
            )

            # Return TOP-LEVEL fields that the wallet uses
            return {
                "id": str(transaction.id),
                "account_id": account_id,
                "memo": memo,
                "memo_type": memo_type,
                "how": "Send the payment with the memo provided. Then go to the selected cash-out agent with your ID and pickup code.",
                "extra_info": {
                    "pickup_code": payout.pickup_code,
                    "expected_time": "Same day",
                    "expires_at": payout.expires_at.isoformat(),
                },
            }

        # 4B) BANK / INTERNAL ACCOUNT WITHDRAWAL
        elif withdrawal_type in ("bank_account", "bank_transfer"):
            # For SEP-6, the client may send dest/dest_extra, but we also
            # have bank_account_number & bank_number on the user model.
            bank_account_number: Optional[str] = (
                params.get("bank_account_number")
                or getattr(user, "bank_account_number", None)
            )
            bank_number: Optional[str] = (
                params.get("bank_number")
                or getattr(user, "bank_number", None)
            )

            if not bank_account_number or not bank_number:
                return {"error": "Missing bank account details for withdrawal"}

            # OPTIONAL: store IBAN/bank account in the standard Transaction field
            # so we can see it in the DB / admin:
            transaction.to_address = bank_account_number
            transaction.save(update_fields=["amount_fee", "amount_out", "to_address"])

            return {
                "id": str(transaction.id),
                "account_id": account_id,
                "memo": memo,
                "memo_type": memo_type,
                "how": (
                    "Send the payment with the memo provided. "
                    f"We will disburse to your bank/internal account ending {bank_account_number[-4:]}."
                ),
                "extra_info": {
                    "bank_account_number": bank_account_number,
                    "bank_number": bank_number,
                    "expected_time": "1-2 business days",
                },
            }

        else:
            return {"error": f"Unsupported withdrawal type: {withdrawal_type}"}

    # ─────────────────────────────────────────────────────────────
    # Called by Polaris AFTER it detects the user's Stellar payment
    # to the anchor receive account (via watch_transactions).
    #
    # Here we:
    #   - resolve the user again from transaction.stellar_account
    #   - get their internal ledger account (bank_account_number)
    #   - POST to your Nest /transfers endpoint:
    #       fromAccountNumber = anchor ledger account
    #       toAccountNumber   = user ledger account
    #       currency          = "USD" for MUSD
    #       amount            = transaction.amount_out
    # ─────────────────────────────────────────────────────────────
    def process_withdrawal(
        self,
        response: Dict,
        transaction: Transaction,
        *args: List,
        **kwargs: Dict
    ) -> None:
        """
        Execute the off-chain payout once the on-chain payment is confirmed.
        Polaris will call this for withdrawal transactions in pending_anchor, etc.
        If this returns without raising, Polaris will mark the transaction as completed.
        If you raise, Polaris sets status=error.
        """
        # 1) Detect whether this is a CASH or BANK payout.
        #    If there's an associated CashPayout, treat as cash and skip bank logic.
        if CashPayout.objects.filter(transaction=transaction).exists():
            # TODO: if you want, implement agent settlement here.
            return

        # 2) Resolve the user based on the stellar account in the transaction
        if not transaction.stellar_account:
            raise RuntimeError("Transaction is missing stellar_account")

        user = user_for_account(transaction.stellar_account)
        if not user:
            raise RuntimeError("Could not resolve user for transaction")

        bank_account_number = getattr(user, "bank_account_number", None)
        bank_number = getattr(user, "bank_number", None)

        if not bank_account_number or not bank_number:
            raise RuntimeError("User missing bank_account_number or bank_number")

        # 3) Config from settings: destination endpoint + anchor internal ledger account
        transfer_url = getattr(settings, "BANKING_TRANSFER_URL", None)
        anchor_account = getattr(settings, "ANCHOR_BANK_ACCOUNT_NUMBER", None)

        if not transfer_url or not anchor_account:
            raise RuntimeError(
                "Missing BANKING_TRANSFER_URL or ANCHOR_BANK_ACCOUNT_NUMBER in settings"
            )

        # 4) How much to send (net of fees)
        amount_out = transaction.amount_out  # Decimal
        asset_code = transaction.asset.code  # e.g. "TALE"

        # You decided: for MUSD on-chain, internal ledger currency is USD.
        currency = "USD" if asset_code == "TALE" else asset_code

        payload = {
            "fromAccountNumber": anchor_account,
            "toAccountNumber": bank_account_number,   # user's internal ledger account
            "amount": str(amount_out),                # decimal string, ex: "1.97"
            "currency": currency,
            "description": f"anchor_withdraw:{transaction.id}",
        }

        try:
            resp = requests.post(transfer_url, json=payload, timeout=10)
        except requests.RequestException as e:
            raise RuntimeError(f"Bank transfer request failed: {e}") from e

        if resp.status_code >= 300:
            # Polaris will mark this withdrawal as error and store the message
            raise RuntimeError(
                f"Bank transfer failed: {resp.status_code} {resp.text}"
            )

        # Success: just return. Polaris will move status to 'completed'.
        return

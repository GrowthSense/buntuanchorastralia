# marimushaanchorapp/anchor/rails.py

import os
import requests
from polaris.integrations import RailsIntegration
from polaris.models import Transaction
from django.conf import settings


# ------------------------------------------------------------------------------
#  FEES
# ------------------------------------------------------------------------------

def calculate_fee(transaction: Transaction) -> float:
    """
    Calculate the fee for deposit/withdraw.
    Example: fixed 1.5% fee.
    """
    fee_rate = 0.015  # 1.5%
    fee = float(transaction.amount_in) * fee_rate
    return round(fee, 2)


# ------------------------------------------------------------------------------
#  MEMO GENERATOR
# ------------------------------------------------------------------------------

def memo_for_transaction(transaction: Transaction) -> str:
    """
    Generate the memo shown to the wallet.
    Polaris stores this memo to match incoming payments.
    """
    return f"MEMO-{transaction.id}"

def notify_wallet_backend(payload: dict):
    try:
        requests.post(
            f"{settings.WALLET_BACKEND_URL}/transaction/anchor/transaction-status",
            json=payload,
            timeout=5
        )
    except Exception as e:
        print("Failed to notify wallet backend:", e)



# ------------------------------------------------------------------------------
#  RAILS INTEGRATION (OUTGOING PAYOUTS)
# ------------------------------------------------------------------------------

class AnchorRails(RailsIntegration):

    def execute_outgoing_transaction(self, transaction: Transaction):
        print("\n🔥 [RAILS] Executing outgoing transaction:", transaction.id)

        if transaction.status != Transaction.STATUS.pending_anchor:
            print(f"⚠️ [RAILS] Transaction {transaction.id} is not pending_anchor. Skipping.")
            return

        fiat_amount = str(transaction.amount_out)

        destination_bank_account = transaction.to_address
        if not destination_bank_account:
            raise RuntimeError(
                f"[RAILS] Missing banking dest for {transaction.id}. No to_address found."
            )

        anchor_treasury_account = os.getenv("ANCHOR_BANK_ACCOUNT_NUMBER")
        if not anchor_treasury_account:
            raise RuntimeError("ANCHOR_BANK_ACCOUNT_NUMBER must be set in environment")

        payout_url = os.getenv(
            "BANKING_TRANSFER_URL",
            "http://192.168.100.32:7013/transfers",
        )

        payout_payload = {
            "fromAccountNumber": anchor_treasury_account,
            "toAccountNumber": destination_bank_account,
            "amount": fiat_amount,
            "currency": "USD",
            "description": f"anchor_tx:{transaction.id}",
        }

        print("👉 [RAILS] Sending payout:")
        print("    URL:", payout_url)
        print("    Payload:", payout_payload)

        # -------------------------------------------------------------
        # TRY BANK PAYOUT
        # -------------------------------------------------------------
        try:
            response = requests.post(payout_url, json=payout_payload, timeout=10)
        except Exception as e:
            print("❌ [RAILS] Bank request failed:", str(e))

            # ❗ Immediately notify wallet backend of FAILURE
            notify_wallet_backend({
                "transactionId": str(transaction.id),
                "status": "failed",
                "stage": "bank_payout",
                "error": str(e),
            })

            raise RuntimeError(f"[RAILS] Bank request failed: {str(e)}")

        if response.status_code not in (200, 201):
            print("❌ [RAILS] Payout failed:", response.text)

            # ❗ Notify wallet backend — FAILURE
            notify_wallet_backend({
                "transactionId": str(transaction.id),
                "status": "failed",
                "stage": "bank_payout",
                "error": response.text,
            })

            raise RuntimeError(
                f"Payout failed ({response.status_code}): {response.text}"
            )

        print("✅ [RAILS] Bank payout successful for:", transaction.id)

        # -------------------------------------------------------------
        # SUCCESS → Mark completed
        # -------------------------------------------------------------
        transaction.status = Transaction.STATUS.completed
        transaction.save()

        print(f"🎉 [RAILS] Transaction {transaction.id} marked COMPLETED")

        # -------------------------------------------------------------
        # Callback to wallet backend — SUCCESS
        # -------------------------------------------------------------
        notify_wallet_backend({
            "transactionId": str(transaction.id),
            "status": "completed",
            "bankResponse": response.json() if response.text else None,
            "message": "Withdrawal payout completed successfully",
        })

        print("📡 [RAILS] Wallet backend notified of SUCCESS\n")

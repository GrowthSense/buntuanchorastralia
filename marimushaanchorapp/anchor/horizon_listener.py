import threading
from django.conf import settings
from django.utils import timezone
from stellar_sdk import Server, Keypair
from polaris.models import Transaction
from marimushaanchorapp.anchor.agents.models import CashPayout

def _pub():
    return Keypair.from_secret(settings.STELLAR_SECRET_KEY).public_key

def start_cash_stream():
    server = Server(getattr(settings, "HORIZON_URI", "https://horizon.stellar.org"))
    account = _pub()

    def handle(p):
        try:
            if p.get("to") != account or p.get("type") != "payment":
                return
            tx_hash = p.get("transaction_hash")
            if not tx_hash:
                return
            detail = server.transactions().transaction(tx_hash).call()
            memo = detail.get("memo")
            if not memo:
                return

            tx = (Transaction.objects
                  .select_related("cash_payout")
                  .filter(memo=memo, kind=Transaction.KIND.withdrawal)
                  .first())
            if not tx or not hasattr(tx, "cash_payout"):
                return

            cp = tx.cash_payout
            if cp.ready or cp.paid_out_at:
                return

            tx.status = "pending_anchor"
            tx.stellar_transaction_id = tx_hash
            tx.save(update_fields=["status", "stellar_transaction_id"])

            cp.ready = True
            cp.save(update_fields=["ready"])
        except Exception as e:
            print("[HORIZON] handler error:", e)

    def run():
        try:
            print("[HORIZON] starting payments stream…")
            for p in server.payments().for_account(account).cursor("now").stream():
                handle(p)
        except Exception as e:
            print("[HORIZON] stream crashed:", e)

    threading.Thread(target=run, daemon=True).start()

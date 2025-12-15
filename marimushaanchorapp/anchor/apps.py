# marimushaanchorapp/anchor/apps.py
import os
from django.apps import AppConfig

class AnchorConfig(AppConfig):
    name = 'marimushaanchorapp.anchor'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        print("[ANCHOR INIT] Registering integrations...")

        # Ensure Django sees the models inside the agents subpackage
        # (so makemigrations/migrate pick them up)
        from .agents import models as _agents_models  # noqa: F401

        # Polaris integrations
        from polaris.integrations import register_integrations
        from .deposit.deposit import AnchorDeposit
        from .withdraw.withdraw import AnchorWithdraw
        from .customer.customers import AnchorCustomer
        from .rails import AnchorRails

        register_integrations(
            deposit=AnchorDeposit(),
            withdrawal=AnchorWithdraw(),
            customer=AnchorCustomer(),
            rails=AnchorRails(),
        )

        # Start the Horizon payments stream ONE time (avoid double-run with reloader)
        # RUN_MAIN is set to "true" only in the actual serving process of runserver.
        if os.environ.get("RUN_MAIN") == "true":
            try:
                from .horizon_listener import start_cash_stream
                start_cash_stream()
                print("[ANCHOR INIT] Horizon listener started.")
            except Exception as e:
                print(f"[ANCHOR INIT] Horizon listener failed: {e}")

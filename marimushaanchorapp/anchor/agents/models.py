import uuid
from django.db import models
from django.conf import settings


class Agent(models.Model):
    """
    Optional: internal representation of an agent on the anchor side.
    You can keep this if you still want to manage / view agents in Django,
    but it is NO LONGER referenced by CashPayout.
    """
    # keep implicit integer PK 'id'
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=255)
    hours = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} — {self.location}"


class CashPayout(models.Model):
    """
    Represents a cash withdrawal payout tied to a single Polaris Transaction.

    We NO LONGER store an Agent FK here because agents live in the Nest app.
    Nest identifies the payout by pickup_code, and calls an anchor
    "approve payout" endpoint when the cash is disbursed.
    """
    # keep implicit integer PK 'id'
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    # Polaris base transaction (or your AnchorTransaction, which inherits it)
    transaction = models.OneToOneField(
        "polaris.Transaction",
        on_delete=models.CASCADE,
        related_name="cash_payout",
    )

    # 🔑 Code the user gives to the agent (managed in Nest)
    pickup_code = models.CharField(max_length=16, unique=True)

    # When this code expires (e.g. 24h)
    expires_at = models.DateTimeField()

    # False = created / pending; True = payout has been disbursed
    ready = models.BooleanField(default=False)

    # When cash was actually handed out
    paid_out_at = models.DateTimeField(null=True, blank=True)

    # Optional: who in ANCHOR system marked it as paid out
    paid_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        indexes = [
            models.Index(fields=["ready", "paid_out_at"]),
            models.Index(fields=["pickup_code"]),
        ]

    def __str__(self):
        return f"CashPayout(tx={self.transaction.id}, code={self.pickup_code})"

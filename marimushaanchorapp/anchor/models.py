from django.db import models
from django.utils import timezone
from polaris.models import Transaction


class AnchorUser(models.Model):
    stellar_account = models.CharField(max_length=56, unique=True)
    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    email_address = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    bank_account_number = models.CharField(max_length=100, null=True, blank=True)
    bank_number = models.CharField(max_length=100, null=True, blank=True)
    kyc_approved = models.BooleanField(default=False)
    kyc_rejected = models.BooleanField(default=False)
    
    # Add these new fields for webhook support
    kyc_processed_at = models.DateTimeField(null=True, blank=True)
    external_reference_id = models.CharField(max_length=100, blank=True)  # ID from external KYC service
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.stellar_account}"
    
    @property
    def kyc_status(self):
        if self.kyc_approved:
            return "APPROVED"
        elif self.kyc_rejected:
            return "REJECTED"
        else:
            return "PENDING"
        
# marimushaanchorapp/anchor/models.py (example)
from django.db import models
from polaris.models import Transaction

class AnchorTransaction(Transaction):
    FUNDING_METHOD_CHOICES = (
        ("bank", "Bank Transfer"),
        ("wallet", "Wallet Transfer"),
        ("cash", "Cash Agent"),
    )

    funding_method = models.CharField(
        max_length=16,
        choices=FUNDING_METHOD_CHOICES,
        default="bank",
    )

    # 🔹 this will hold the agent id coming from Nest (string)
    external_agent_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Agent identifier from BuntuPay/Nest system",
    )

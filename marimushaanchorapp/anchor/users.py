from marimushaanchorapp.anchor.models import AnchorUser
from typing import Dict, Optional 
from django.db import transaction,IntegrityError

def user_for_account(account: str, memo=None, memo_type=None):
    try:
        # First, try to get user if already created
        return AnchorUser.objects.get(stellar_account=account)
    except AnchorUser.DoesNotExist:
        # If not found, safely try to create
        try:
            with transaction.atomic():
                user = AnchorUser(stellar_account=account)
                user.save()  # Save the object
                print(f"[USER CREATE] Created new user for: {account}")
                return user  # ✅ Return the saved object

        except IntegrityError:
            # Someone else might have created it in the meantime
            print(f"[USER RETRY] Account {account} just created by another request. Retrying get...")
            return AnchorUser.objects.get(stellar_account=account)
def fields_for_type(type: str) -> Dict:
    print(f"Requested KYC type: {type}")
    return {
         "first_name": {
            "description": "First name",
            "type": "string"
        },
        "last_name": {
            "description": "Last name",
            "type": "string"
        },
        "email_address": {
            "description": "Email address",
            "type": "string"
        },
    }

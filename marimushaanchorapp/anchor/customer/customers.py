from typing import Dict, List
from polaris.integrations import CustomerIntegration
from polaris.sep10.token import SEP10Token
from polaris.models import Transaction
from rest_framework.request import Request
from ..users import user_for_account, fields_for_type

class AnchorCustomer(CustomerIntegration):
    def get(
        self,
        token: SEP10Token,
        request: Request,
        params: Dict,
        *args: List,
        **kwargs: Dict
    ) -> Dict:
        # Identify the user based on their account/memo
        user = user_for_account(
            token.muxed_account or token.account,
            token.memo or params.get("memo"),
            "id" if token.memo else params.get("memo_type")
        )

        # Load the required KYC fields based on type
        fields = fields_for_type(params.get("type"))

        # If no user found, return all fields as needed
        if not user:
            return {
                "status": "NEEDS_INFO",
                "fields": fields
            }

        # Separate missing and provided fields
        missing_fields = dict([
            (f, v) for f, v in fields.items()
            if not getattr(user, f, False)
        ])
        provided_fields = dict([
            (f, v) for f, v in fields.items()
            if getattr(user, f, False)
        ])

        # If some KYC fields are missing, return NEEDS_INFO
        if missing_fields:
            return {
                "id": str(user.id),
                "status": "NEEDS_INFO",
                "fields": missing_fields,
                "provided_fields": provided_fields
            }

        if user.kyc_rejected:
            return {
                "id": str(user.id),
                "status": "DENIED",
                "provided_fields": provided_fields
            }

        if user.kyc_approved:
            return {
                "id": str(user.id),
                "status": "ACCEPTED",
                "provided_fields": provided_fields
            }

        return {
            "id": str(user.id),
            "status": "PROCESSING",
            "provided_fields": provided_fields
        }

    
    def put(
        self,
        token: SEP10Token,
        request: Request,
        params: Dict,
        *args: List,
        **kwargs: Dict
    ):
        account = token.muxed_account or token.account
        memo = token.memo or params.get("memo")
        memo_type = "id" if token.memo else params.get("memo_type")

        print(f"[KYC UPDATE] Received update for account: {account}")
        print(f"[KYC UPDATE] Params received: {params}")

        # Retrieve user object
        user = user_for_account(account, memo, memo_type)

        print(f"[KYC UPDATE] User before update: account={user.stellar_account}, "
      f"first_name={user.first_name}, last_name={user.last_name}, "
      f"email_address={user.email_address},"
      f"bank_account_number={user.bank_account_number}, bank_number={user.bank_number}")
        # Update user's fields dynamically based on params
        excluded_fields = [ "stellar_account"]
        updated_fields = []

        for key, value in params.items():
            if key not in excluded_fields and hasattr(user, key) and value is not None:
                setattr(user, key, value)
                updated_fields.append((key, value))
            print(f"[KYC UPDATE] Fields updated for {user.stellar_account}: {updated_fields}")
            user.save()  # Save updates
            print(f"[KYC UPDATE] Successfully updated fields: {updated_fields} for user: {user.stellar_account}")
        return str(user.id)  # No return is required
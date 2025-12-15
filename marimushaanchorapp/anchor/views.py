from django.http import JsonResponse
from polaris.models import Transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.utils import timezone
from stellar_sdk import Server, Keypair, TransactionBuilder, Asset, Network
from django.conf import settings
import requests
import toml
import json
import hashlib
import hmac
from django.http import JsonResponse, HttpRequest, HttpResponse
from marimushaanchorapp.anchor.models import AnchorUser
from marimushaanchorapp.anchor.agents.models import Agent, CashPayout
#from marimushaanchorapp.anchor.models import AnchorTransaction as Transaction
from uuid import UUID
import os
import logging
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
import traceback
from decimal import Decimal
from .rails import calculate_fee
from stellar_sdk.exceptions import BadRequestError

logger = logging.getLogger(__name__)

# ===== IMPLEMENT THE MISSING HELPER FUNCTIONS =====

# def send_approval_email(user_email, stellar_account):
#     """
#     Send email notification for KYC approval
#     """
#     try:
#         subject = "Your KYC Verification Has Been Approved"
#         message = f"""
#         Dear User,
        
#         Your KYC verification for Stellar account {stellar_account} has been approved.
#         You can now use all features of our anchor services.
        
#         Thank you,
#         The Anchor Team
#         """
#         send_mail(
#             subject,
#             message,
#             settings.DEFAULT_FROM_EMAIL,
#             [user_email],
#             fail_silently=False,
#         )
#         logger.info(f"Approval email sent to {user_email}")
#     except Exception as e:
#         logger.error(f"Failed to send approval email: {str(e)}")

# def send_rejection_email(user_email, rejection_reason):
#     """
#     Send email notification for KYC rejection
#     """
#     try:
#         subject = "Update on Your KYC Verification"
#         message = f"""
#         Dear User,
        
#         Your KYC verification could not be completed at this time.
        
#         Reason: {rejection_reason}
        
#         Please contact support if you have any questions.
        
#         Thank you,
#         The Anchor Team
#         """
#         send_mail(
#             subject,
#             message,
#             settings.DEFAULT_FROM_EMAIL,
#             [user_email],
#             fail_silently=False,
#         )
#         logger.info(f"Rejection email sent to {user_email}")
#     except Exception as e:
#         logger.error(f"Failed to send rejection email: {str(e)}")

def establish_trustline(stellar_account):
    """
    Establish a trustline for the user's Stellar account if needed
    """
    try:
        # This would typically involve:
        # 1. Checking if the user already has a trustline for your asset
        # 2. If not, you might need to guide them to create one
        # 3. Or use a sponsored transaction to create it for them
        
        server = Server(settings.HORIZON_URI)
        account = server.accounts().account_id(stellar_account).call()
        
        # Check if trustline exists for your asset
        asset = load_asset_from_remote_toml()
        trustline_exists = any(
            balance.get('asset_code') == asset.code and 
            balance.get('asset_issuer') == asset.issuer
            for balance in account['balances']
        )
        
        if not trustline_exists:
            logger.info(f"Trustline needed for {stellar_account}")
            # You could trigger a process to help user establish trustline
            # or use sponsored transactions
            
        logger.info(f"Trustline check completed for {stellar_account}")
        
    except Exception as e:
        logger.error(f"Error checking trustline for {stellar_account}: {str(e)}")

def process_pending_transactions(user):
    """
    Process any pending transactions for the user after KYC approval
    """
    try:
        pending_transactions = Transaction.objects.filter(
            stellar_account=user.stellar_account,
            status__in=["pending_anchor", "pending_user_transfer_start"]
        )
        
        for tx in pending_transactions:
            try:
                # Auto-approve pending deposit transactions
                if tx.kind == 'deposit':
                    response = send_stellar_payment(tx)
                    logger.info(f"Auto-approved transaction {tx.id} for {user.stellar_account}")
                
                # For withdrawal transactions, you might need different logic
                elif tx.kind == 'withdrawal':
                    tx.status = "pending_user_transfer_complete"
                    tx.save()
                    logger.info(f"Marked withdrawal transaction {tx.id} as ready for processing")
                    
            except Exception as e:
                logger.error(f"Error processing transaction {tx.id}: {str(e)}")
                
        logger.info(f"Processed {pending_transactions.count()} pending transactions for {user.stellar_account}")
        
    except Exception as e:
        logger.error(f"Error in process_pending_transactions: {str(e)}")

def log_kyc_rejection(user, rejection_reason):
    """
    Log KYC rejection for compliance purposes
    """
    try:
        # Log to your compliance system or database
        logger.warning(
            f"KYC_REJECTED - Account: {user.stellar_account}, "
            f"Reason: {rejection_reason}, "
            f"Time: {timezone.now()}"
        )
        
        # You could also save to a separate compliance model
        # ComplianceLog.objects.create(
        #     user=user,
        #     action='KYC_REJECTED',
        #     reason=rejection_reason,
        #     timestamp=timezone.now()
        # )
        
    except Exception as e:
        logger.error(f"Error logging KYC rejection: {str(e)}")

def internal_transaction_list(request):
    transactions = Transaction.objects.all().order_by('-started_at')[:50]
    data = []
    for tx in transactions:
        data.append({
            "id": str(tx.id),
            "account": tx.stellar_account,
            "kind": tx.kind,
            "status": tx.status,
            "asset": tx.asset.code,
            "amount_in": str(tx.amount_in),
            "amount_out": str(tx.amount_out),
            "memo": tx.memo,
            "started_at": tx.started_at.isoformat()
        })
    return JsonResponse({"transactions": data})

def load_asset_from_remote_toml(url="https://buntuswitch.com/.well-known/stellar.toml"):
    response = requests.get(url)
    response.raise_for_status()
    config = toml.loads(response.text)
    asset_code = config["CURRENCIES"][0]["code"]
    issuer = config["CURRENCIES"][0]["issuer"]
    return Asset(asset_code, issuer)

def sep1_stellar_toml(request):
    """Serve the stellar.toml file for SEP-1"""
    stellar_toml_content = f'''# BuntuSwitch Stellar.toml - Testnet
VERSION="2.0.0"

NETWORK_PASSPHRASE="Test SDF Network ; September 2015"

# Transfer server endpoints
TRANSFER_SERVER="{os.getenv('POLARIS_HOST_URL', 'http://localhost:8001')}"
TRANSFER_SERVER_SEP0024="{os.getenv('POLARIS_HOST_URL', 'http://localhost:8001')}"
KYC_SERVER="{os.getenv('POLARIS_HOST_URL', 'http://localhost:8001')}"
WEB_AUTH_ENDPOINT="{os.getenv('POLARIS_HOST_URL', 'http://localhost:8001')}/auth"

# Signing key
SIGNING_KEY="{os.getenv('STELLAR_PUBLIC_KEY', 'GDYOUR_PUBLIC_KEY_HERE')}"

[DOCUMENTATION]
ORG_NAME="BuntuSwitch - Testnet"
ORG_URL="https://www.buntuswitch.com"
ORG_DESCRIPTION="BuntuSwitch Testnet Anchor"

# TALE on Stellar Testnet
[[CURRENCIES]]
code="TALE"
issuer="GD346WA7CNC2FF2P3TRFMPSD7PDK6WAKV5Q63H4DTSS6PYDGS447S6NG"
display_decimals=2
name="TALE"
desc="TALE stablecoin on Stellar Testnet"
status="test"
is_asset_anchored=true
anchor_asset_type="fiat"
anchor_asset="AUD"
'''
    
    return HttpResponse(stellar_toml_content, content_type='text/plain')


def send_stellar_payment(tx):
    server = Server("https://horizon-testnet.stellar.org")  # Use mainnet in production
    secret_key = settings.STELLAR_SECRET_KEY
    if not secret_key:
        raise ValueError("Secret key not found in settings.")
    if not tx.stellar_account:
        raise ValueError("Transaction does not have a stellar account.")

    source_keypair = Keypair.from_secret(secret_key)  # your sending wallet
    source_account = server.load_account(source_keypair.public_key)

    #asset = sep1_stellar_toml()  # your asset code and issuer
    asset=Asset("TALE", "GD346WA7CNC2FF2P3TRFMPSD7PDK6WAKV5Q63H4DTSS6PYDGS447S6NG")

    print("STELLAR PAYMENT DEST:", tx.stellar_account)
    print("STELLAR PAYMENT ASSET:", asset.code, asset.issuer)
    print("STELLAR NETWORK:", server.horizon_url)  # testnet vs mainnet

    tx_builder = TransactionBuilder(
        source_account=source_account,
        network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
        base_fee=100
    ).append_payment_op(
        destination=tx.stellar_account,
        amount=str(tx.amount_out),
        asset=asset
    ).set_timeout(60)

    transaction = tx_builder.build()
    transaction.sign(source_keypair)
    response = server.submit_transaction(transaction)

    # update polaris transaction
    tx.stellar_transaction_id = response["hash"]
    tx.status = "completed"
    tx.save()

    return response


def get_transaction(request, transaction_id):
    try:
        tx = Transaction.objects.get(id=transaction_id)
        data = {
            "id": tx.id,
            "status": tx.status,
            "kind": tx.kind,
            "amount_in": tx.amount_in,
            "stellar_transaction_id": tx.stellar_transaction_id,
            "external_transaction_id": tx.external_transaction_id,
            "started_at": tx.started_at,
            "more_info_url": tx.more_info_url,
            # add more fields as needed
        }
        return JsonResponse({"transaction": data})
    except Transaction.DoesNotExist:
        return JsonResponse({"error": "Transaction not found"}, status=404)

@csrf_exempt
def approve_transaction(request, transaction_id):
    try:
        tx = Transaction.objects.get(id=transaction_id)

        if tx.status not in ["pending_anchor", "pending_user_transfer_start"]:
            return JsonResponse({"error": "Transaction not in a valid state for approval"}, status=400)

        # 🔥 Send tokens to the user
        response = send_stellar_payment(tx)

        return JsonResponse({
            "success": True,
            "message": "Transaction approved and funds sent",
            "stellar_transaction_id": response["hash"]
        })

    except Transaction.DoesNotExist:
        return JsonResponse({"error": "Transaction not found"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
def approve_transaction_withdrawal(request, transaction_id):
    try:
        tx = Transaction.objects.get(id=transaction_id)

        if tx.status not in ["pending_anchor", "pending_user_transfer_start"]:
            return JsonResponse({"error": "Transaction not in a valid state for approval"}, status=400)

        # ✅ 1. Here you would initiate your local payout logic
        # For example, trigger a bank payout, send an SMS, or log for manual processing

        # ✅ 2. Mark as completed
        tx.status = "completed"
        tx.completed_at = timezone.now()
        tx.save()

        return JsonResponse({
            "success": True,
            "message": "Transaction approved and marked as complete"
        })

    except Transaction.DoesNotExist:
        return JsonResponse({"error": "Transaction not found"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def reject_transaction(request, transaction_id):
    try:
        tx = Transaction.objects.get(id=transaction_id)
        tx.status = "error"
        tx.save()
        return JsonResponse({"success": True, "message": "Transaction rejected."})
    except Transaction.DoesNotExist:
        return JsonResponse({"error": "Transaction not found"}, status=404)

def get_customer_kyc(request, stellar_account):
    customer = AnchorUser.objects.get(stellar_account=stellar_account)
    return JsonResponse({
    "stellar_account": customer.stellar_account,
    "first_name": customer.first_name,
    "last_name": customer.last_name,
    "email_address": customer.email_address,
    "address": customer.address,
    "bank_account_number": customer.bank_account_number,
    "bank_number": customer.bank_number,
    "kyc_status": "APPROVED" if customer.kyc_approved else ("REJECTED" if customer.kyc_rejected else "PENDING"),
})

def get_all_customers(request):
    users = AnchorUser.objects.all()
    data = []
    for user in users:
        data.append({
            "stellar_account": user.stellar_account,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email_address": user.email_address,
            "address": user.address,
            "bank_account_number": user.bank_account_number,
            "bank_number": user.bank_number,
            "kyc_status": "APPROVED" if user.kyc_approved else ("REJECTED" if user.kyc_rejected else "PENDING"),
        })
    return JsonResponse({"customers": data})



@csrf_exempt
def approve_kyc(request, stellar_account):
    try:
        user = AnchorUser.objects.get(stellar_account=stellar_account)
        user.kyc_approved = True
        user.kyc_rejected = False
        user.save()
        return JsonResponse({"message": f"KYC approved for {stellar_account}"})
    except AnchorUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

@csrf_exempt
def reject_kyc(request, stellar_account):
    try:
        user = AnchorUser.objects.get(stellar_account=stellar_account)
        user.kyc_approved = False
        user.kyc_rejected = True
        user.save()
        return JsonResponse({"message": f"KYC rejected for {stellar_account}"})
    except AnchorUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

def _parse_body(request: HttpRequest):
    """
    Accept JSON or x-www-form-urlencoded. Returns (payload_dict, error_response_or_None)
    """
    try:
        if request.META.get("CONTENT_TYPE", "").startswith("application/json"):
            raw = request.body.decode("utf-8") or "{}"
            return json.loads(raw), None
        # Fallback to form data
        return request.POST.dict(), None
    except json.JSONDecodeError as e:
        return None, JsonResponse({"error": "Invalid JSON body", "detail": str(e)}, status=400)

@csrf_exempt
def agents_collection(request: HttpRequest):
    """
    GET  /internal/agents/                     -> list all agents
    POST /internal/agents/ (JSON or form)      -> create an agent
        body: { "name": "...", "location": "...", "hours": "08:00-17:00", "active": true }
    """
    if request.method == "GET":
        agents = Agent.objects.all().order_by("id")
        return JsonResponse({"agents": [
            {"id": a.id, "name": a.name, "location": a.location, "hours": a.hours, "active": a.active}
            for a in agents
        ]})

    if request.method == "POST":
        payload, err = _parse_body(request)
        if err:
            return err
        name = (payload.get("name") or "").strip()
        location = (payload.get("location") or "").strip()
        hours = (payload.get("hours") or "").strip()
        active = payload.get("active", True)
        if isinstance(active, str):
            active = active.lower() in ("1", "true", "yes", "on")

        if not name or not location:
            return JsonResponse({"error": "name and location are required"}, status=400)

        agent = Agent.objects.create(name=name, location=location, hours=hours, active=bool(active))
        return JsonResponse(
            {"id": agent.id, "name": agent.name, "location": agent.location, "hours": agent.hours, "active": agent.active},
            status=201
        )

    return JsonResponse({"error": "Method not allowed"}, status=405)

def agent_detail(request: HttpRequest, agent_id: UUID):
    """
    GET /internal/agents/<id>/                 -> fetch one agent
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    a = get_object_or_404(Agent, id=agent_id)
    return JsonResponse({"id": a.id, "name": a.name, "location": a.location, "hours": a.hours, "active": a.active})

@csrf_exempt
def agent_update_delete(request: HttpRequest, agent_id: UUID):
    """
    PATCH/PUT /internal/agents/<id>/           -> update an agent (partial or full)
    DELETE     /internal/agents/<id>/          -> delete
    """
    a = get_object_or_404(Agent, id=agent_id)

    if request.method in ("PATCH", "PUT"):
        payload, err = _parse_body(request)
        if err:
            return err
        for field in ("name", "location", "hours"):
            if field in payload and payload[field] is not None:
                setattr(a, field, str(payload[field]).strip())
        if "active" in payload:
            val = payload["active"]
            if isinstance(val, str):
                val = val.lower() in ("1", "true", "yes", "on")
            a.active = bool(val)
        a.save()
        return JsonResponse({"id": a.id, "name": a.name, "location": a.location, "hours": a.hours, "active": a.active})

    if request.method == "DELETE":
        a.delete()
        return JsonResponse({"ok": True})

    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
@require_http_methods(["POST"])
def kyc_webhook(request):
    """
    Webhook endpoint to receive KYC status updates from external service
    """
    # 1. Verify webhook signature (crucial for security)
    if not verify_webhook_signature(request):
        return JsonResponse({"error": "Invalid signature"}, status=401)
    
    try:
        # 2. Parse the webhook payload
        payload = json.loads(request.body)
        logger.info(f"Received KYC webhook: {payload}")
        
        # 3. Extract essential data
        stellar_account = payload.get('stellar_account')
        kyc_status = payload.get('status')  # 'approved', 'rejected', 'pending'
        kyc_details = payload.get('details', {})
        external_reference_id = payload.get('reference_id')
        
        if not stellar_account or not kyc_status:
            return JsonResponse({"error": "Missing required fields"}, status=400)
        
        # 4. Find user and update status
        user = AnchorUser.objects.get(stellar_account=stellar_account)
        
        if kyc_status == 'approved':
            user.kyc_approved = True
            user.kyc_rejected = False
            user.kyc_processed_at = timezone.now()
            user.external_reference_id = external_reference_id
            user.save()
            
            # Trigger any post-approval actions
            handle_kyc_approval(user, kyc_details)
            
            logger.info(f"KYC approved via webhook for {stellar_account}")
            
        elif kyc_status == 'rejected':
            user.kyc_approved = False
            user.kyc_rejected = True
            user.kyc_processed_at = timezone.now()
            user.external_reference_id = external_reference_id
            user.rejection_reason = kyc_details.get('reason', '')
            user.save()
            
            # Trigger any post-rejection actions
            handle_kyc_rejection(user, kyc_details)
            
            logger.info(f"KYC rejected via webhook for {stellar_account}")
        
        elif kyc_status == 'pending':
            # KYC is under review
            user.kyc_approved = False
            user.kyc_rejected = False
            user.save()
            logger.info(f"KYC pending via webhook for {stellar_account}")
        
        else:
            return JsonResponse({"error": f"Unknown status: {kyc_status}"}, status=400)
        
        return JsonResponse({
            "message": f"KYC status updated to {kyc_status} for {stellar_account}",
            "status": kyc_status
        })
        
    except AnchorUser.DoesNotExist:
        logger.error(f"User not found for KYC webhook: {stellar_account}")
        return JsonResponse({"error": "User not found"}, status=404)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in KYC webhook payload")
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        
    except Exception as e:
        logger.error(f"Error processing KYC webhook: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)

def verify_webhook_signature(request):
    """
    Verify the webhook signature - handles different JSON formatting
    """
    signature = request.headers.get('X-Webhook-Signature')
    if not signature:
        return False
    
    webhook_secret = settings.KYC_WEBHOOK_SECRET
    
    try:
        # Parse and re-serialize to normalize JSON formatting
        payload_data = json.loads(request.body)
        normalized_body = json.dumps(payload_data, separators=(',', ':'))
        
        expected_signature = hmac.new(
            webhook_secret.encode(),
            normalized_body.encode('utf-8'),  # Use normalized JSON
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
        
    except json.JSONDecodeError:
        # Fallback to raw body if not valid JSON
        expected_signature = hmac.new(
            webhook_secret.encode(),
            request.body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    
def handle_kyc_approval(user, kyc_details):
    """
    Handle post-approval actions
    """
    try:
        # Example actions:
        # 1. Notify user via email
        #send_approval_email(user.email_address, user.stellar_account)
        
        # 2. Create Stellar trustline if needed
        establish_trustline(user.stellar_account)
        
        # 3. Process pending transactions for this user
        process_pending_transactions(user)
        
        # 4. Update analytics/monitoring
        logger.info(f"Post-approval actions completed for {user.stellar_account}")
        
    except Exception as e:
        logger.error(f"Error in post-approval actions: {str(e)}")

def handle_kyc_rejection(user, kyc_details):
    """
    Handle post-rejection actions
    """
    try:
        # Example actions:
        rejection_reason = kyc_details.get('reason', 'KYC verification failed')
        
        # 1. Notify user
        #send_rejection_email(user.email_address, rejection_reason)
        
        # 2. Log the rejection for compliance
        log_kyc_rejection(user, rejection_reason)
        
        logger.info(f"Post-rejection actions completed for {user.stellar_account}")
        
    except Exception as e:
        logger.error(f"Error in post-rejection actions: {str(e)}")
        

def refund_bank_account(tx, customer):
    print("=== REFUNDING USER BANK ACCOUNT ===")

    # lookup user using stellar account in the transaction
    try:
        customer = AnchorUser.objects.get(stellar_account=tx.stellar_account)
    except AnchorUser.DoesNotExist:
        print("ERROR: No AnchorUser found for stellar account:", tx.stellar_account)
        return

    print("REFUND CUSTOMER RECORD:", customer.__dict__)

    user_bank_account = customer.bank_account_number
    user_bank_routing = customer.bank_number

    if not user_bank_account:
        print("ERROR: User has no bank account number stored")
        return

    refund_payload = {
        "fromAccountNumber": settings.ANCHOR_BANK_ACCOUNT_NUMBER,
        "toAccountNumber": user_bank_account,
        "amount": str(tx.amount_in),   # refund what the user deposited
        "currency": "USD",
        "description": f"refund_tx:{tx.id}"
    }

    print("REFUND PAYLOAD:", refund_payload)

    try:
        r = requests.post(
            f"{settings.BANKING_TRANSFER_URL}/refund",
            json=refund_payload,
            timeout=8
        )
        print("REFUND RESPONSE:", r.status_code, r.text)
    except Exception as e:
        print("Failed to send refund:", e)


def notify_wallet_backend(payload: dict):
    try:
        requests.post(
            f"{settings.WALLET_BACKEND_URL}/transaction/anchor/transaction-status",
            json=payload,
            timeout=5
        )
    except Exception as e:
        print("Failed to notify wallet backend:", e)

def human_readable_stellar_failure(result_codes):
    """
    Converts harsh Horizon error codes into friendly human-readable messages.
    """
    if not result_codes:
        return "An unknown error occurred on the Stellar network."

    # Underfunded error = Anchor did not have enough tokens
    if "operations" in result_codes and "op_underfunded" in result_codes["operations"]:
        return (
            "The anchor service temporarily had insufficient liquidity to complete your payout. "
            "Your funds have been refunded safely."
        )

    # General transaction failure
    if result_codes.get("transaction") == "tx_failed":
        return (
            "The payment could not be completed due to a Stellar network processing error. "
            "No funds were lost."
        )

    # Fallback for unknown error codes
    return (
        "The transaction failed due to a network error. No funds were deducted from your account."
    )


@csrf_exempt
def wallet_transfer_webhook(request):
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid method"}, status=405)

        raw_body = request.body.decode("utf-8")
        print("WEBHOOK RAW BODY:", raw_body)

        payload = json.loads(raw_body)

        status = payload.get("status")
        description = payload.get("description")
        direction = payload.get("direction")

        print("WEBHOOK PARSED PAYLOAD:", payload)
        print("WEBHOOK DIRECTION:", direction)

        if not status or not description:
            return JsonResponse({"error": "Missing status or description"}, status=400)

        if not description.startswith("anchor_tx:"):
            return JsonResponse({"error": "Invalid description format"}, status=400)

        transaction_id = description.split("anchor_tx:")[1]
        print("WEBHOOK TRANSACTION ID:", transaction_id)

        try:
            tx = Transaction.objects.get(id=transaction_id)
        except Transaction.DoesNotExist:
            return JsonResponse({"error": "Transaction not found"}, status=404)

        print("WEBHOOK TX BEFORE:", tx.status)

        if tx.status not in ["pending_anchor", "pending_user_transfer_start"]:
            return JsonResponse({"error": "Transaction not in valid state"}, status=400)

        # ============================================================
        # 1️⃣ USER → ANCHOR (no Stellar payment needed)
        # ============================================================
        if direction == "USER_TO_ANCHOR":
            print("USER_TO_ANCHOR: bank transfer acknowledged")

            tx.status = "bank_transfer_completed"
            tx.save(update_fields=["status"])

            return JsonResponse({
                "success": True,
                "message": "User→Anchor transfer acknowledged"
            })

        # ============================================================
        # 2️⃣ ANCHOR → USER (send Stellar payment)
        # ============================================================
        if direction == "ANCHOR_TO_USER":
            print("ANCHOR_TO_USER: attempting Stellar payout")

            try:
                response = send_stellar_payment(tx)

                tx.status = "completed"
                tx.stellar_transaction_hash = response["hash"]
                tx.save(update_fields=["status", "stellar_transaction_id"])
                
                # 🔥 Notify wallet backend
                notify_wallet_backend({
                    "transactionId": str(tx.id),
                    "status": "completed",
                    "stellar_hash": response["hash"],
                    "message": "Stellar payment completed successfully"
                })

                return JsonResponse({
                    "success": True,
                    "message": "Funds sent",
                    "stellar_transaction_id": response["hash"],
                })

            except BadRequestError as e:
                # e.args[0] contains the Response object
                http_response = e.args[0]
                error_json = http_response.json()

                print("STELLAR ERROR:", error_json)

                result_codes = (
                    error_json.get("extras", {})
                              .get("result_codes", {})
                )

                print("RESULT CODES:", result_codes)

                # ----------------------------------------------------
                # Underfunded error (distributor has no funds)
                # ----------------------------------------------------
                if "operations" in result_codes and "op_underfunded" in result_codes["operations"]:
                    print("ANCHOR UNDERFUNDED → issuing refund")

                    tx.status = "failed"
                    tx.status_message = "ANCHOR_UNDERFUNDED"
                    tx.save(update_fields=["status", "status_message"])
                    # Load customer to get bank account number
                    # customer = Customer.objects.filter(
                    #     account=tx.stellar_account
                    # ).first()
                     # Human-readable safe message for the wallet app
                    readable_message = human_readable_stellar_failure(result_codes)

                    
                    notify_wallet_backend({
                        "transactionId": str(tx.id),
                        "status": "failed",
                        "reason": "ANCHOR_UNDERFUNDED",
                        "userMessage": readable_message,
                    })
                    
                    customer = AnchorUser.objects.get(stellar_account=tx.stellar_account)

                    print("REFUND CUSTOMER:", customer.__dict__ if customer else None)

                    refund_bank_account(tx, customer)

                    # notify_wallet_backend({
                    #     "transactionId": str(tx.id),
                    #     "status": "failed",
                    #     "reason": "ANCHOR_UNDERFUNDED",
                    # })

                    return JsonResponse({
                        "success": False,
                        "message": "Anchor distributor underfunded. Refunded.",
                        "error": "op_underfunded",
                    }, status=200)

                raise

        # ============================================================
        # 3️⃣ UNKNOWN → fallback to legacy payout
        # ============================================================
        print("UNKNOWN direction → legacy payout")

        response = send_stellar_payment(tx)

        tx.status = "completed"
        tx.stellar_transaction_hash = response["hash"]
        tx.save(update_fields=["status", "stellar_transaction_hash"])

        return JsonResponse({
            "success": True,
            "message": "Legacy payout completed",
            "stellar_transaction_id": response["hash"],
        })

    except Exception as e:
        print("WEBHOOK ERROR:")
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
def agent_cash_deposit(request: HttpRequest):
    try:
        payload, err = _parse_body(request)
        if err:
            return err

        external_agent_id = (payload.get("agent_id") or "").strip()
        currency = (payload.get("currency") or "").strip()
        amount_str = (payload.get("amount") or "").strip()
        user_email = (payload.get("user_email") or "").strip()

        if not external_agent_id or not currency or not amount_str or not user_email:
            return JsonResponse(
                {"error": "agent_id, currency, amount and user_email are required"},
                status=400,
            )

        # validate amount
        from decimal import Decimal, InvalidOperation
        try:
            amount_in = Decimal(amount_str)
            if amount_in <= 0:
                raise InvalidOperation()
        except Exception:
            return JsonResponse({"error": "Invalid amount"}, status=400)

        # lookup AnchorUser by email, allow duplicates safely
        qs = AnchorUser.objects.filter(
            email_address=user_email,
        ).order_by('-updated_at')  # pick the newest

        user = qs.first()
        if not user:
            return JsonResponse(
                {"error": "User with this email not found in anchor"},
                status=404,
            )

        if not user.kyc_approved:
            return JsonResponse({"error": "User KYC is not approved"}, status=400)

        if not user.stellar_account:
            return JsonResponse(
                {"error": "User does not have a Stellar account linked"},
                status=400,
            )

        # get Polaris asset model
        from polaris.models import Asset as PolarisAsset
        try:
            asset_model = PolarisAsset.objects.get(code=currency)
        except PolarisAsset.DoesNotExist:
            return JsonResponse(
                {"error": f"Unsupported currency/asset: {currency}"},
                status=400,
            )

        # create Transaction (using AnchorTransaction)
        tx = Transaction.objects.create(
            asset=asset_model,
            kind="deposit",
            status="pending_anchor",
            amount_in=amount_in,
            amount_fee=Decimal("0"),
            amount_out=Decimal("0"),
            stellar_account=user.stellar_account,
        )

        # attach metadata
        tx.funding_method = "cash"
        tx.external_agent_id = external_agent_id
        tx.save()

        # fee & amount_out
        fee = calculate_fee(tx)
        fee = Decimal(str(fee))
        tx.amount_fee = fee
        tx.amount_out = amount_in - fee

        if tx.amount_out <= 0:
            tx.status = "error"
            tx.save()
            return JsonResponse(
                {"error": "Amount is too small after fees"},
                status=400,
            )

        tx.save()

        # send tokens on Stellar
        response = send_stellar_payment(tx)

        return JsonResponse(
            {
                "success": True,
                "message": "Cash deposit created and credited to user",
                "transaction": {
                    "id": str(tx.id),
                    "status": tx.status,
                    "kind": tx.kind,
                    "funding_method": getattr(tx, "funding_method", "cash"),
                    "asset": tx.asset.code,
                    "amount_in": str(tx.amount_in),
                    "amount_fee": str(tx.amount_fee),
                    "amount_out": str(tx.amount_out),
                    "stellar_account": tx.stellar_account,
                    "stellar_transaction_id": tx.stellar_transaction_id,
                    "external_agent_id": tx.external_agent_id,
                },
                "raw_horizon_response": response,
            },
            status=201,
        )

    except Exception as e:
        logger.error(f"Error in agent_cash_deposit: {str(e)}")
        traceback.print_exc()
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_POST
def approve_cash_payout(request: HttpRequest):
    try:
        payload, err = _parse_body(request)
        if err:
            return err

        pickup_code = (payload.get("pickup_code") or "").strip()

        if not pickup_code:
            return JsonResponse({"error": "pickup_code is required"}, status=400)

        payout = (
            CashPayout.objects
            .select_related("transaction")
            .filter(pickup_code=pickup_code, ready=False)
            .first()
        )

        if not payout:
            return JsonResponse({"error": "Invalid or already-used pickup code"}, status=404)

        tx = payout.transaction

        if tx.status != "pending_anchor":
            return JsonResponse({"error": "Transaction not ready for cash payout"}, status=400)

        # Mark as disbursed
        payout.ready = True
        payout.disbursed_at = timezone.now()
        payout.save()

        # Complete the transaction
        tx.status = "completed"
        tx.completed_at = timezone.now()
        tx.save()
        
        # 🔥 Notify wallet backend
        notify_wallet_backend({
            "transactionId": str(tx.id),
            "status": "completed",
            # "stellar_hash": payout.hash,
            "message": "Stellar payment completed successfully"
        })

        return JsonResponse({
            "success": True,
            "message": "Cash payout completed successfully",
            "transaction_id": str(tx.id)
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": "Internal error"}, status=500)
    
@csrf_exempt
@require_GET
def list_pending_cash_payouts(request: HttpRequest):
    """
    GET /internal/cash-payouts/pending

    Returns all cash withdrawal transactions that still need a cash payout:
      - CashPayout.ready = False
      - CashPayout.expires_at > now
      - Transaction.status not in ('completed', 'error')
    """
    now = timezone.now()

    payouts = (
        CashPayout.objects
        .select_related("transaction")
        .filter(ready=False, expires_at__gt=now)
        .exclude(transaction__status__in=["completed", "error"])
        .order_by("expires_at")
    )

    results = []
    for p in payouts:
        tx = p.transaction
        results.append({
            "pickup_code": p.pickup_code,
            "expires_at": p.expires_at.isoformat(),
            "transaction_id": str(tx.id),
            "status": tx.status,
            "kind": tx.kind,
            "asset": tx.asset.code if tx.asset else None,
            "amount_in": str(tx.amount_in) if tx.amount_in is not None else None,
            "amount_out": str(tx.amount_out) if tx.amount_out is not None else None,
            "stellar_account": tx.stellar_account,
            "memo": tx.memo,
        })

    return JsonResponse({"payouts": results})

@csrf_exempt
def mark_cash_payout_ready(request):
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        try:
            payload = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        pickup_code = (payload.get("pickup_code") or "").strip()

        if not pickup_code:
            return JsonResponse({"error": "pickup_code is required"}, status=400)

        payout = (
            CashPayout.objects
            .select_related("transaction")
            .filter(pickup_code=pickup_code)
            .first()
        )

        if not payout:
            return JsonResponse({"error": "Pickup code not found"}, status=404)

        tx = payout.transaction

        # Old status
        old_status = tx.status

        # Only allow progression from pending_user_transfer_start
        if tx.status != "pending_user_transfer_start":
            return JsonResponse({
                "error": f"Cannot mark payout ready from status '{tx.status}'"
            }, status=400)

        # Update to pending_anchor
        tx.status = "pending_anchor"
        tx.updated_at = timezone.now()
        tx.save()

        return JsonResponse({
            "success": True,
            "message": "Transaction status updated to pending_anchor",
            "old_status": old_status,
            "new_status": tx.status,
            "transaction_id": str(tx.id)
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": "Internal error"}, status=500)

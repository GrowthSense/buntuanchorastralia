# marimushaanchorapp/anchor/sep6_info.py
from django.http import JsonResponse
from marimushaanchorapp.anchor.agents.models import Agent

def sep6_info(request):
    # Build agent choices for the wallet UI
    agents = Agent.objects.filter(active=True)
    agent_choices = [
        {
            "value": str(getattr(a, "public_id", a.id)),
            "description": f"{a.name} — {a.location} ({a.hours})".strip()
        }
        for a in agents
    ]

    payload = {
        "deposit": {},  # add deposit fields if you need them
        "withdraw": {
            "types": {
                "cash": {
                    "fields": {
                        "agent_id": {
                            "description": "Cash-out agent to pick up funds",
                            "choices": agent_choices
                        }
                    }
                },
                "bank_account": {
                    "fields": {
                        "dest": {"description": "Bank account number"},
                        "dest_extra": {"description": "Routing/branch number"}
                    }
                }
            }
        }
    }
    return JsonResponse(payload)

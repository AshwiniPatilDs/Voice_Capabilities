import json
from typing import Any, Dict, List, Optional, Sequence

LOCAL_CUSTOMER_DATABASE: Dict[str, Dict[str, Any]] = {
    "PRL-1001": {
        "policy_no": "PRL-1001",
        "customer_id": "CUST-1001",
        "application_no": "APP-5001",
        "plan_name": "Pramerica Life Protect",
        "policy_holder_name": "Amit Sharma",
        "dob": "15-06-1988",
        "insured_person_name": "Amit Sharma",
        "customer_city_correspondance": "Mumbai",
        "customer_state_correspondance": "Maharashtra",
        "branch_name": "Andheri Branch",
        "mis_group": "Retail Life",
        "zonal_head": "Ravi Mehta",
        "supervisor": "Naina Deshpande",
        "cro_name": "Sanjay Kulkarni",
        "collectible_premium": "₹5000/month",
        "date_of_issue": "01-01-2024",
        "next_due_date": "01-08-2026",
        "contact_no": "9876543210",
        "email": "amit.sharma@example.com",
        "policy_status": "Active",
        "premium_mode": "Annual",
        "nominee_name": "Pooja Sharma",
        "customer_address": "Flat 12, Lake View Apartments, Mumbai",
    },
    "PRL-1002": {
        "policy_no": "PRL-1002",
        "customer_id": "CUST-1002",
        "application_no": "APP-5002",
        "plan_name": "Pramerica Smart Secure",
        "policy_holder_name": "Priya Nair",
        "dob": "22-09-1992",
        "insured_person_name": "Priya Nair",
        "customer_city_correspondance": "Bengaluru",
        "customer_state_correspondance": "Karnataka",
        "branch_name": "Koramangala Branch",
        "mis_group": "Retail Life",
        "zonal_head": "Asha Nair",
        "supervisor": "Kiran Rao",
        "cro_name": "Meera Joshi",
        "collectible_premium": "₹4200/month",
        "date_of_issue": "15-03-2024",
        "next_due_date": "15-09-2026",
        "contact_no": "9123456780",
        "email": "priya.nair@example.com",
        "policy_status": "Active",
        "premium_mode": "Half-Yearly",
        "nominee_name": "Arun Nair",
        "customer_address": "House 45, 2nd Cross, Bengaluru",
    },
}

SUPPORTED_LOOKUP_KEYS = (
    "policy_no",
    "customer_id",
    "application_no",
    "plan_name",
    "policy_holder_name",
    "dob",
    "insured_person_name",
    "customer_city_correspondance",
    "customer_state_correspondance",
    "branch_name",
    "mis_group",
    "zonal_head",
    "supervisor",
    "cro_name",
    "collectible_premium",
    "date_of_issue",
    "next_due_date",
    "contact_no",
    "email",
    "policy_status",
    "premium_mode",
    "nominee_name",
    "customer_address",
)

SUPPORTED_LOOKUP_SET = set(SUPPORTED_LOOKUP_KEYS)


def normalize_lookup_key(key: str) -> str:
    normalized = key.strip().lower().replace("-", "_").replace(" ", "_").replace(".", "")
    synonyms = {
        "customer_name": "policy_holder_name",
        "name": "policy_holder_name",
        "policy": "policy_no",
        "policy_number": "policy_no",
        "policyno": "policy_no",
        "contact": "contact_no",
        "phone": "contact_no",
        "contact_number": "contact_no",
        "contactno": "contact_no",
        "emailid": "email",
        "mail": "email",
        "plan": "plan_name",
        "premium": "collectible_premium",
        "nextduedate": "next_due_date",
        "dateofissue": "date_of_issue",
        "zonalhead": "zonal_head",
        "crosname": "cro_name",
    }
    return synonyms.get(normalized, normalized)


def lookup_customer_details(key: str, value: str) -> Optional[Dict[str, Any]]:
    normalized_key = normalize_lookup_key(key)
    if normalized_key not in SUPPORTED_LOOKUP_SET:
        raise ValueError(f"Unsupported lookup key: {key}")

    lookup_value = value.strip().lower()
    for record in LOCAL_CUSTOMER_DATABASE.values():
        field_value = record.get(normalized_key)
        if isinstance(field_value, str) and field_value.lower() == lookup_value:
            return record
    return None


def format_local_customer_db_for_prompt() -> str:
    """Convert the local customer database into a text block suitable for a prompt."""
    return json.dumps(LOCAL_CUSTOMER_DATABASE, indent=2, ensure_ascii=False)


# from pathlib import Path

# SYSTEM_PROMPT_FILE = Path(
#     r"C:\Users\ashwi\OneDrive\Desktop\voice_ai_barge\prompts\system_prompt.txt"
# )


# def build_customer_lookup_system_message() -> str:
#     """
#     Loads the entire system prompt from a single text file and injects
#     the local customer database.
#     """
#     prompt = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")

#     prompt = prompt.replace(
#         "{LOCAL_CUSTOMER_DATABASE}",
#         format_local_customer_db_for_prompt(),
#     )

#     return prompt


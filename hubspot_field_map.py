"""
Maps HubSpot Deal (Financial Assistance) property internal names to the
header strings csv_to_word_forms.py already expects from a CSV row.

PLACEHOLDERS — every "REPLACE_WITH_..." value below must be replaced with
real internal names/option values found by running
hubspot_discover_properties.py against the real HubSpot account. Do not
commit this file until tests/test_hubspot_field_map.py passes.
"""
from __future__ import annotations

HUBSPOT_TO_ENGINE_HEADER: dict[str, str] = {
    "REPLACE_WITH_client_name_internal_name": "Client Name",
    "REPLACE_WITH_payment_date_internal_name": "Payment Date (Today's Date)",
    "REPLACE_WITH_program_internal_name": "Program (Sync)",
    "REPLACE_WITH_check_type_internal_name": "Check Type",
    "REPLACE_WITH_type_of_assistance_internal_name": "Type of Rental Assistance",
    "REPLACE_WITH_stepped_down_internal_name": "Has the client been Stepped down?",
    "REPLACE_WITH_monthly_rent_amount_internal_name": "Monthly Rent Amount",
    "REPLACE_WITH_ubh_amount_internal_name": "UBH Amount",
    "REPLACE_WITH_client_rent_amount_internal_name": "Client Rent Amount",
    "REPLACE_WITH_check_payable_to_internal_name": "Check Payable to (Sync)",
    "REPLACE_WITH_landlord_address_internal_name": "Landlord Address Sync",
    "REPLACE_WITH_household_size_internal_name": "Household Size Sync",
    "REPLACE_WITH_bedroom_internal_name": "Bedroom Sync",
    "REPLACE_WITH_over_fmr_internal_name": "Over FMR?",
    "REPLACE_WITH_payment_month_internal_name": "Payment Month - Calc",
    "REPLACE_WITH_payment_year_internal_name": "Payment Year - Calc",
}

# Same internal name as HUBSPOT_TO_ENGINE_HEADER's "Check Type" entry above.
FILTER_CHECK_TYPE_PROPERTY = "REPLACE_WITH_check_type_internal_name"
FILTER_CHECK_TYPE_VALUE = "REPLACE_WITH_monthly_rent_option_value"

FILTER_PAID_STATUS_PROPERTY = "REPLACE_WITH_paid_status_internal_name"
FILTER_PAID_STATUS_VALUE = "REPLACE_WITH_pending_approval_option_value"

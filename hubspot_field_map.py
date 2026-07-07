"""
Maps HubSpot Deal (Financial Assistance) property internal names to the
header strings csv_to_word_forms.py already expects from a CSV row.

Internal names below were found by running hubspot_discover_properties.py
against the real HubSpot account on 2026-07-06. Re-run that script and
update this file if HubSpot properties are ever renamed or recreated.

Notes from discovery:
- HubSpot's internal name for "Type of Assistance" is 'type_of_rental_assitance'
  (typo is HubSpot's, and matches the engine's tolerated header).
- "UBH Amount" is 'ubh_amount_calc'; plain 'ubh_amount' is the Historical one.
- 'over_fmr' stores 'true'/'false' internally while the UI shows Yes/No —
  translated via ENGINE_VALUE_TRANSLATIONS so forms print Yes/No.
"""
from __future__ import annotations

HUBSPOT_TO_ENGINE_HEADER: dict[str, str] = {
    "client_name": "Client Name",
    "payment_date": "Payment Date (Today's Date)",
    "program_sync": "Program (Sync)",
    "check_type": "Check Type",
    "type_of_rental_assitance": "Type of Rental Assistance",
    "has_the_client_been_stepped_down": "Has the client been Stepped down?",
    "monthly_rent_amount": "Monthly Rent Amount",
    "ubh_amount_calc": "UBH Amount",
    "client_rent_amount": "Client Rent Amount",
    "check_payable_to_sync": "Check Payable to (Sync)",
    "lla_sync": "Landlord Address Sync",
    "hhsize_sync": "Household Size Sync",
    "bedroom": "Bedroom Sync",
    "over_fmr": "Over FMR?",
    "mw": "Payment Month - Calc",
    "y": "Payment Year - Calc",
}

# HubSpot returns internal option values, which for some properties differ
# from the display labels the old CSV export carried. Keyed by engine header.
ENGINE_VALUE_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Over FMR?": {"true": "Yes", "false": "No"},
}

# Same internal name as HUBSPOT_TO_ENGINE_HEADER's "Check Type" entry above.
FILTER_CHECK_TYPE_PROPERTY = "check_type"
FILTER_CHECK_TYPE_VALUE = "Monthly Rent"

FILTER_PAID_STATUS_PROPERTY = "paid_status"
FILTER_PAID_STATUS_VALUE = "Pending Approval"

FILTER_TYPE_OF_ASSISTANCE_PROPERTY = "type_of_rental_assitance"
FILTER_TYPE_OF_ASSISTANCE_VALUE = "Rent"

# HubSpot Deal create date — day-of-month for the monthly batch (records created
# on the 13th; job is intended to run on the 20th of the same month).
FILTER_CREATE_DATE_DAY = 13
HUBSPOT_CREATEDATE_PROPERTY = "createdate"

# "Month (Month the Assistance is being paid for)" — used in the PandaDoc
# document name, not on the Word form.
ASSISTANCE_PAYMENT_MONTH_PROPERTY = "m_p"

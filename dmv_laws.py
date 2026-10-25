# dmv_laws.py

JURISDICTION_LAWS = {
    "Virginia (VRLTA)": {
        "jurisdiction": "Virginia",
        "statute": "Virginia Code § 55.1-1226 (VRLTA)",
        "return_window": "45 days",
        "official_link": "https://law.lis.virginia.gov/vacode/title55.1/chapter12/section55.1-1226/",
        "key_rule": "Landlords must provide an itemized list of deductions and final payment within 45 days. Deductions cannot be made for ordinary wear and tear."
    },
    "Maryland Security Deposit Law": {
        "jurisdiction": "Maryland",
        "statute": "Maryland Code, Real Property § 8-203",
        "return_window": "45 days",
        "official_link": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=grp&section=8-203",
        "key_rule": "Landlords must return the deposit plus accrued interest within 45 days. Unreasonable or non-itemized withholdings may subject the landlord to up to 3x damages."
    },
    "District of Columbia (DC Tenant Bill of Rights)": {
        "jurisdiction": "Washington, D.C.",
        "statute": "D.C. Code § 42-3502.17 & D.C. Municipal Regulations (14 DCMR § 309)",
        "return_window": "45 days",
        "official_link": "https://code.dccouncil.gov/us/dc/council/code/sections/42-3502.17",
        "key_rule": "Housing providers must return deposits or provide formal written notice of intent to withhold within 45 days, accompanied by detailed repair estimates."
    }
}

def get_law_details(jurisdiction_name):
    # Safe fallback prevents app crashes if key isn't found
    return JURISDICTION_LAWS.get(jurisdiction_name, JURISDICTION_LAWS["Virginia (VRLTA)"])


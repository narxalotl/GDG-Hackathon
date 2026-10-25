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
    def get_law_details(jurisdiction_name):
    # Flexible matching based on selected string
        name_str = str(jurisdiction_name).upper()
        
        def get_law_details(jurisdiction_name):
            name_str = str(jurisdiction_name).upper()        
            if "MARYLAND" in name_str or "MD" in name_str:
                return JURISDICTION_LAWS["MD"]
            elif "COLUMBIA" in name_str or "DC" in name_str or "DISTRICT" in name_str:
                return JURISDICTION_LAWS["DC"]
            else:
                return JURISDICTION_LAWS["VA"]


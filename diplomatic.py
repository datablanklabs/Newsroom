"""
Diplomatic pack: U.S. State Department cables (Cablegate, the 1970s "Kissinger cables", FOIA'd
telegrams) and diplomatic correspondence in general.

The metadata parser reads the cable header — SUBJECT, TAGS, "FM AMEMBASSY ..." and the signer —
so every cable gets a real title, its originating post, and its TAGS subject codes as topics
(PREL, PGOV, PHUM ...) and country codes as places.
"""
import re

DESCRIPTION = "Diplomatic cables: State Department TAGS topics, posts, cable headers"
REQUIRES = ["government"]

# State Department TAGS subject codes (Traffic Analysis by Geography and Subject).
TAG_TOPICS = {
    "PREL": "External political relations", "PGOV": "Internal government affairs", "PHUM": "Human rights",
    "PINR": "Intelligence", "PTER": "Terrorism", "PINS": "National security", "PARM": "Arms control",
    "MARR": "Military and defense arrangements", "MOPS": "Military operations", "MASS": "Military assistance and sales",
    "ECON": "Economic conditions", "EFIN": "Financial and monetary affairs", "ETRD": "Foreign trade",
    "EINV": "Foreign investment", "ENRG": "Energy", "EPET": "Petroleum", "EAID": "Foreign economic assistance",
    "EAGR": "Agriculture", "ELAB": "Labor", "ECPS": "Communications and postal systems",
    "ETTC": "Trade and technology controls", "KCRM": "Criminal activity", "SNAR": "Narcotics", "KJUS": "Justice",
    "KDEM": "Democratization", "KPAO": "Public affairs", "KCOR": "Corruption", "KNNP": "Nuclear nonproliferation",
    "KTFN": "Terrorist financing", "SMIG": "Migration", "PREF": "Refugees", "SOCI": "Social conditions",
    "CASC": "Assistance to U.S. citizens", "CVIS": "Visas", "ASEC": "Security", "AMGT": "Embassy management",
    "OVIP": "VIP visits", "OEXC": "Educational and cultural exchange", "SENV": "Environment",
    "KPKO": "Peacekeeping", "KWMN": "Women's issues", "KIRF": "Religious freedom", "KTIP": "Trafficking in persons",
    "KISL": "Islam", "KMDR": "Media reaction", "PBTS": "Boundaries and territorial sovereignty", "EFIS": "Fisheries",
    "ELTN": "Transportation", "EIND": "Industry", "EWWT": "Maritime and waterways", "KPAL": "Palestinian affairs",
    "KWBG": "West Bank and Gaza", "KIPR": "Intellectual property", "KFRD": "Fraud", "AORC": "International organizations",
    "TSPA": "Space", "TBIO": "Biotechnology", "KHIV": "HIV/AIDS", "KFLU": "Influenza", "KSCA": "Science",
}

# FIPS 10-4 country codes used in TAGS lines -> canonical place names in the core pack.
FIPS = {
    "AF": "Afghanistan", "AG": "Algeria", "AJ": "Azerbaijan", "AL": "Albania", "AM": "Armenia", "AO": "Angola",
    "AR": "Argentina", "AS": "Australia", "AU": "Austria", "BA": "Bahrain", "BE": "Belgium", "BG": "Bangladesh",
    "BK": "Bosnia", "BL": "Bolivia", "BM": "Burma", "BO": "Belarus", "BR": "Brazil", "BU": "Bulgaria", "CA": "Canada",
    "CB": "Cambodia", "CD": "Chad", "CE": "Sri Lanka", "CG": "Democratic Republic of the Congo",
    "CF": "Republic of the Congo", "CH": "China", "CI": "Chile", "CO": "Colombia", "CS": "Costa Rica", "CU": "Cuba",
    "CY": "Cyprus", "DA": "Denmark", "DJ": "Djibouti", "EC": "Ecuador", "EG": "Egypt", "EI": "Ireland", "EN": "Estonia",
    "ER": "Eritrea", "ES": "El Salvador", "ET": "Ethiopia", "EZ": "Czech Republic", "FI": "Finland", "FR": "France",
    "GG": "Georgia (country)", "GH": "Ghana", "GM": "Germany", "GR": "Greece", "GT": "Guatemala", "GZ": "Palestinian territories",
    "HA": "Haiti", "HK": "Hong Kong", "HO": "Honduras", "HR": "Croatia", "HU": "Hungary", "IC": "Iceland", "ID": "Indonesia",
    "IN": "India", "IR": "Iran", "IS": "Israel", "IT": "Italy", "IZ": "Iraq", "JA": "Japan", "JO": "Jordan", "KE": "Kenya",
    "KG": "Kyrgyzstan", "KN": "North Korea", "KS": "South Korea", "KU": "Kuwait", "KV": "Kosovo", "KZ": "Kazakhstan",
    "LA": "Laos", "LE": "Lebanon", "LG": "Latvia", "LH": "Lithuania", "LY": "Libya", "MG": "Mongolia", "ML": "Mali",
    "MO": "Morocco", "MU": "Oman", "MX": "Mexico", "MY": "Malaysia", "NG": "Niger", "NI": "Nigeria", "NL": "Netherlands",
    "NO": "Norway", "NP": "Nepal", "NU": "Nicaragua", "NZ": "New Zealand", "PE": "Peru", "PK": "Pakistan", "PL": "Poland",
    "PM": "Panama", "PO": "Portugal", "QA": "Qatar", "RO": "Romania", "RP": "Philippines", "RS": "Russia",
    "SA": "Saudi Arabia", "SF": "South Africa", "SG": "Senegal", "SN": "Singapore", "SO": "Somalia", "SP": "Spain",
    "SU": "Sudan", "SW": "Sweden", "SY": "Syria", "SZ": "Switzerland", "TH": "Thailand", "TS": "Tunisia", "TU": "Turkey",
    "TW": "Taiwan", "TX": "Turkmenistan", "TZ": "Tanzania", "AE": "United Arab Emirates", "UG": "Uganda",
    "UK": "United Kingdom", "UP": "Ukraine", "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan",
    "VE": "Venezuela", "VM": "Vietnam", "WE": "Palestinian territories", "YM": "Yemen", "ZA": "Zambia", "ZI": "Zimbabwe",
}
ORG_TAGS = {"EUN": ("organization", "European Union"), "NATO": ("organization", "NATO"), "UNSC": ("organization", "United Nations"),
            "UNGA": ("organization", "United Nations"), "IAEA": ("organization", "IAEA"), "OPEC": ("organization", "OPEC"),
            "WTO": ("organization", "WTO"), "OSCE": ("organization", "OSCE"), "AU": ("organization", "African Union")}

# Routing lines would link every addressee post to every cable (like REL TO banners).
STRIP_PATTERNS = [
    r"(?m)^\s*E\.?\s?O\.?\s?\d{5}:?[^\n]*",            # E.O. 12958: DECL: ...
    r"(?m)^\s*TAGS:?[^\n]*",
    r"(?m)^\s*(?:INFO|TO|FM|FROM)\s+(?:AMEMBASSY|AMCONSUL|USMISSION|SECSTATE|SECDEF|CIA|DIA|JOINT STAFF|USCINC|CDR|RUE)[^\n]*",
    r"(?m)^\s*(?:AMEMBASSY|AMCONSUL|USMISSION|AMCONSULATE)\s[^\n]*",
    r"(?m)^\s*(?:CLASSIFIED BY|REASON):?[^\n]*",
]

_SUBJECT = re.compile(r"(?m)^\s*SUBJ(?:ECT)?\s*:\s*(.+(?:\n(?!\s*\n)(?!\s*(?:REF|CLASSIFIED|TAGS|E\.O\.)\b).+){0,2})")
_TAGS = re.compile(r"(?m)^\s*TAGS:?\s*([A-Z0-9 ,/\-]+)$")
_FROM = re.compile(r"(?m)^\s*FM\s+(AMEMBASSY|AMCONSUL|USMISSION|SECSTATE|AMCONSULATE)\s+([A-Z .'\-]+?)(?:\s+(?:WASHDC|\d))?\s*$")
_SIGNER = re.compile(r"\n\s*([A-Z][A-Z'\-]{2,20}(?: [A-Z][A-Z'\-]{1,20})?)\s*$")


ACRONYMS = {"US", "USG", "UN", "UNSC", "UNGA", "EU", "UK", "AU", "NATO", "IMF", "WTO", "NGO", "NGOS", "PRC", "ROK", "DPRK", "GOI",
            "GOK", "GOZ", "GOE", "MFA", "MOD", "MOI", "FM", "PM", "DCM", "CODEL", "SECDEF", "SECSTATE", "VP", "OAS", "ASEAN",
            "OPEC", "IAEA", "HIV", "AIDS", "FTA", "GDP", "ICC", "ICTY", "ANC", "PLO", "PA", "IDF", "PKK", "FARC", "UNHCR",
            "USAID", "MCC", "DOD", "DOJ", "DHS", "FBI", "CIA", "OSCE", "G8", "G20", "WMD", "TIP", "SOFA", "ZANU-PF", "MDC"}


SHORT_WORDS = set("""a an the and or but nor for so yet of on in at to by up off out via per as is are was were be been has had
have do does did its it his her him he she we us our you your they them their who why how what when all any can may might
must will would should could now new old own say says said see set two one six ten not no yes more most less than then
over into onto from with amid upon why vs""".split())


def _is_word(w):
    from lib.text import DICT_LOWER
    return w in SHORT_WORDS or w in DICT_LOWER or (w.endswith("s") and w[:-1] in DICT_LOWER)


def _smart_title(s):
    """'ZIMBABWE RULING PARTY CRANKS UP INTIMIDATION' -> 'Zimbabwe Ruling Party Cranks Up Intimidation'
    (acronyms and short non-words such as 'GOZ' or 'MDC' stay in capitals)."""
    s = re.sub(r"\s+", " ", s).strip(" .")
    if not s.isupper():
        return s[:200]
    words = []
    for w in s.split():
        core = w.strip("(),.:;'\"")
        keep = (core in ACRONYMS or any(c.isdigit() for c in core) or re.fullmatch(r"(?:[A-Z]\.)+[A-Z]?\.?", core)
                or (len(core) <= 4 and core.isalpha() and not _is_word(core.lower())))
        if keep:
            words.append(w)
        else:
            words.append("-".join(p[:1] + p[1:].lower() for p in w.split("-")))
    return " ".join(words)[:200]


def cable_header(d, text, meta, corpus):
    head = text[:5000]
    if d.get("kind") != "cable" and not ("TAGS" in head and ("SUBJECT" in head or "SUBJ:" in head)):
        return
    m = _SUBJECT.search(head)
    if m:
        subj = _smart_title(m.group(1))
        meta["fields"]["Subject"] = subj
        if not meta.get("title") or meta["title"] == meta["fields"].get("ref") or re.fullmatch(r"\d{2}[A-Z]+\d+", meta.get("title", "")):
            meta["title"] = subj
    m = _TAGS.search(head)
    if m:
        codes = [c for c in re.split(r"[\s,/]+", m.group(1).strip()) if c]
        meta["fields"]["TAGS"] = ", ".join(codes)
        for c in codes:
            if c in TAG_TOPICS:
                meta["entities"].append({"type": "idea", "name": f"{c} — {TAG_TOPICS[c]}", "source": "metadata",
                                         "description": "State Department TAGS subject code."})
            elif c in FIPS:
                meta["entities"].append({"type": "place", "name": FIPS[c], "source": "metadata"})
            elif c in ORG_TAGS:
                t, n = ORG_TAGS[c]
                meta["entities"].append({"type": t, "name": n, "source": "metadata"})
    if not meta.get("origin"):
        m = _FROM.search(head)
        if m:
            post = m.group(2).strip().title()
            meta["origin"] = "Department of State" if m.group(1) == "SECSTATE" else f"{'Consulate' if 'CONSUL' in m.group(1) else 'Embassy'} {post}"
    if not meta.get("author"):
        m = _SIGNER.search(text[-400:])
        if m and m.group(1) not in {"END", "UNCLASSIFIED", "CONFIDENTIAL", "SECRET", "NNNN", "BT", "LIMITED OFFICIAL USE"}:
            meta["author"] = m.group(1).title()


METADATA = [cable_header]

AGENCY = [
    ("U.S. Mission to the UN", ["USUN", "U.S. Mission to the United Nations", "USMISSION USUN"], "U.S. Mission to the United Nations, New York."),
    ("Bureau of Intelligence and Research", ["Bureau of Intelligence and Research", "INR"], "The State Department's intelligence bureau."),
    ("Diplomatic Security Service", ["Diplomatic Security Service", "Bureau of Diplomatic Security"], "State Department security and law-enforcement arm."),
    ("Peace Corps", ["Peace Corps"], "U.S. volunteer program abroad."),
    ("Millennium Challenge Corporation", ["Millennium Challenge Corporation", "MCC"], "U.S. foreign aid agency."),
]

ENTITIES = {"agency": AGENCY}

IDEAS = [
    ("Visas & consular affairs", [r"(?i:\bvisas?\b)", r"(?i:\bconsular\b)", r"(?i:\bpassports?\b)", r"(?i:\bAmerican citizens? services\b)"],
     "Visas, passports and help for citizens abroad."),
    ("Trade negotiations", [r"(?i:\btrade (?:agreement|negotiation|talks|deal))", r"(?i:\bfree trade\b)", r"(?i:\btariffs?\b)", r"(?i:\bmarket access\b)", r"(?i:\bintellectual property\b)"],
     "Trade agreements, tariffs and market access."),
    ("Military cooperation & basing", [r"(?i:\bbasing\b)", r"(?i:\bmilitary (?:assistance|cooperation|aid|sales)\b)", r"(?i:\bstatus of forces\b)", r"\bSOFA\b", r"(?i:\bjoint exercises?\b)", r"(?i:\bforeign military (?:sales|financing)\b)"],
     "Bases, military aid, arms sales and status-of-forces agreements."),
    ("Foreign aid & development", [r"\bUSAID\b", r"(?i:\bforeign assistance\b)", r"(?i:\bdevelopment (?:aid|assistance)\b)", r"(?i:\bhumanitarian (?:aid|assistance)\b)", r"(?i:\bdonors?\b)"],
     "Development and humanitarian assistance."),
    ("Demarches & UN votes", [r"(?i:\bd[eé]marche)", r"(?i:\bUN(?:GA|SC)? vote)", r"(?i:\bresolution\b)", r"(?i:\bGeneral Assembly\b)", r"(?i:\btalking points\b)"],
     "Diplomatic demarches, lobbying for votes and UN resolutions."),
]

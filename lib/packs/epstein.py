"""
Epstein pack: places, institutions and legal milestones of the Jeffrey Epstein and Ghislaine Maxwell
cases, for the DOJ Epstein Library and related court records.

Deliberately no list of "associates": appearing in these files (address books, flight logs, emails)
does not imply wrongdoing, and a curated list would suggest otherwise. Names come from the documents
through NER, with their context on every page.
"""

DESCRIPTION = "Epstein/Maxwell cases: properties, institutions, prosecutions (no associate list by design)"
REQUIRES = ["core", "government"]

PERSON = [
    ("Jeffrey Epstein", ["Epstein", "Jeffrey Epstein", "Jeffrey E. Epstein", "JE"], "Financier; convicted in Florida in 2008 of soliciting a minor; charged with federal sex trafficking in 2019; died in federal custody in August 2019."),
    ("Ghislaine Maxwell", ["Ghislaine Maxwell", "G. Maxwell", "Ms. Maxwell"], "Epstein's associate; convicted in 2021 of sex trafficking and related charges."),
    ("Alexander Acosta", ["Alexander Acosta", "Alex Acosta", "R. Alexander Acosta"], "U.S. Attorney for the Southern District of Florida who approved Epstein's 2008 non-prosecution agreement; Labor Secretary 2017–2019."),
]

PLACE = [
    ("Little St. James", ["Little St. James", "Little Saint James", "LSJ"], "Epstein's private island in the U.S. Virgin Islands."),
    ("Great St. James", ["Great St. James", "Great Saint James"], "Neighbouring island Epstein bought in 2016."),
    ("Zorro Ranch", ["Zorro Ranch"], "Epstein's ranch near Stanley, New Mexico."),
    ("Palm Beach", ["Palm Beach"], "Florida town where Epstein had a house and where the first police investigation began (2005)."),
    ("U.S. Virgin Islands", ["U.S. Virgin Islands", "USVI", "St. Thomas", "Saint Thomas"], "U.S. territory; its government sued Epstein's estate."),
    ("Metropolitan Correctional Center", ["Metropolitan Correctional Center", "MCC New York", "MCC Manhattan"], "Federal jail in Manhattan where Epstein died in August 2019."),
    ("Teterboro Airport", ["Teterboro", "Teterboro Airport"], "New Jersey airport used by Epstein's private jets."),
]

AGENCY = [
    ("SDNY", ["Southern District of New York", "SDNY", "U.S. Attorney's Office for the Southern District of New York"], "Federal prosecutors who charged Epstein (2019) and Maxwell (2020)."),
    ("Southern District of Florida", ["Southern District of Florida", "SDFL", "USAO-SDFL"], "Federal prosecutors who negotiated the 2008 non-prosecution agreement."),
    ("Palm Beach Police Department", ["Palm Beach Police Department", "Palm Beach Police", "PBPD"], "Police department that opened the 2005 investigation."),
    ("Bureau of Prisons", ["Bureau of Prisons", "Federal Bureau of Prisons", "BOP"], "Federal prison agency responsible for MCC New York."),
]

PROGRAM = [
    ("2008 non-prosecution agreement", ["non-prosecution agreement", "NPA"], "Deal under which Epstein pleaded guilty to state charges and federal prosecution was dropped."),
    ("Epstein Files Transparency Act", ["Epstein Files Transparency Act", "EFTA"], "2025 law requiring the Justice Department to release its Epstein files."),
]

ENTITIES = {"person": PERSON, "place": PLACE, "agency": AGENCY, "program": PROGRAM}

IDEAS = [
    ("Sexual abuse & trafficking", [r"(?i:\bsex(?:ual)? (?:abuse|assault|trafficking)\b)", r"(?i:\btrafficking\b)", r"(?i:\bminors?\b)", r"(?i:\bunderage\b)", r"(?i:\bvictims?\b)"],
     "Sexual abuse, trafficking and victims."),
    ("Travel & flight logs", [r"(?i:\bflight logs?\b)", r"(?i:\bmanifests?\b)", r"(?i:\btail number\b)", r"(?i:\bBoeing 727\b)", r"(?i:\bGulfstream\b)", r"(?i:\bpassengers?\b)"],
     "Flights, manifests and travel."),
    ("Money & payments", [r"(?i:\bwire transfers?\b)", r"(?i:\bpayments?\b)", r"(?i:\bbank (?:account|statement)s?\b)", r"(?i:\btrust\b)", r"(?i:\bfoundation\b)"],
     "Payments, accounts, trusts and foundations."),
    ("Investigations & prosecutions", [r"(?i:\bgrand jury\b)", r"(?i:\bsubpoena)", r"(?i:\bindictment\b)", r"(?i:\bplea\b)", r"(?i:\bFBI\b)", r"(?i:\binterview(?:ed)?\b)"],
     "Grand juries, subpoenas, interviews and charges."),
    ("Custody & death in jail", [r"(?i:\bsuicide watch\b)", r"(?i:\bautopsy\b)", r"(?i:\bcorrectional officers?\b)", r"(?i:\bcell\b)", r"(?i:\bcustody\b)"],
     "Detention and the death at MCC New York."),
]

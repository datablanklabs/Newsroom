"""
Markings pack: the classification and declassification conventions of U.S./UK/Five Eyes government
documents — banner and portion markings stripped before entity matching, classification levels,
court captions, the generic U.S.-government origin rule and the "Declassify On − 25 years" date
estimate. Required by the government, sigint and diplomatic packs.
"""
import re

DESCRIPTION = "Classification markings, court captions and declassification dates (rules only, no entities)"

# Boilerplate removed before entity matching, so classification banners such as
# "REL TO USA, AUS, CAN, GBR, NZL" don't link every country to every document.
STRIP_PATTERNS = [
    r"(?i)DYNAMIC PAGE\s*--\s*HIGHEST POSSIBLE CLASSIFICATION IS",
    r"(?i)\bREL(?:EASABLE)?\s+TO:?\s+(?:(?:USA|AUS|CAN|GBR|NZL|FVEY|[A-Z]{3})(?:\s*(?:,|and|/)\s*|\s+))+",
    r"\b(?:USA|AUS|CAN|GBR|NZL)(?:\s*[,/]\s*(?:USA|AUS|CAN|GBR|NZL|FVEY))+\b",
    r"\bUK\s+(?:TOP\s+)?SECRET\b", r"\bUK\s+EYES\s+ONLY\b", r"\bUK\s+(?:OFFICIAL|CONFIDENTIAL|RESTRICTED|PROTECT)\b",
    r"(?i)Derived\s+From:?[^\n]*", r"(?i)Declassify\s+On:?[^\n]*", r"(?i)Classified\s+By:?[^\n]*",
    r"(?is)This information is exempt.{0,400}?(?:legislation|GCHQ)[^\n]*",
    r"(?i)Refer disclosure requests to[^\n]*",
    r"\b(?:TOP\s+SECRET|SECRET|CONFIDENTIAL|UNCLASSIFIED)\s*/{1,2}[A-Z0-9/ ,\-]{0,60}",
    r"\((?:U|C|S|TS|U//FOUO|[TSCU]{1,2}//[A-Z/ ,\-]+)\)",
]

CLASSIFICATION_RULES = [
    (10, r"TOP\s*SECRET", "TOP SECRET"),
    (20, r"\bSECRET\b", "SECRET"),
    (30, r"\bCONFIDENTIAL\b", "CONFIDENTIAL"),
    (40, r"\bUNCLASSIFIED\b|\bFOUO\b", "UNCLASSIFIED"),
]

# Originating body (first 20,000 characters). Agency letterhead rules are in the government pack.
ORIGIN_RULES = [
    (10, r"(?i)FOREIGN INTELLIGENCE SURVEILLANCE COURT|UNITED STATES DISTRICT COURT|COURT OF APPEALS|COURT OF REVIEW",
     "U.S. court filing"),
    (60, r"(?i)Office of the Director of National Intelligence|Department of Justice|Federal Bureau",
     "U.S. government (other)"),
]

_DECLASS = re.compile(r"(?i)Declassify\s+On:?\s*(\d{4})(\d{2})(\d{2})")


def declassify_minus_25(text, relpath, corpus):
    """'Declassify On: 20380101' usually means created ~25 years earlier (the default declassification period)."""
    m = _DECLASS.search(text)
    if m:
        y = int(m.group(1)) - 25
        if corpus.dates["declassify_min_year"] <= y <= corpus.dates["declassify_max_year"]:
            return f"{y:04d}", "declassify-on minus 25y (est.)"
    return None


DATE_HINTS = [(50, declassify_minus_25)]


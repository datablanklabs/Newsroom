"""Text helpers shared by the build scripts: tokenizer, alias matcher, name normalization."""
import re
import unicodedata

TYPES = ["person", "agency", "company", "program", "technology", "place", "organization", "idea", "identifier"]
TYPE_LABEL = {"person": "People", "agency": "Agencies", "company": "Companies", "program": "Programs & codenames",
              "technology": "Technologies", "place": "Places", "organization": "Organizations",
              "idea": "Ideas & themes", "identifier": "Identifiers & addresses"}


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def plain(s):
    """Lowercase ASCII fold: 'Peña Nieto' -> 'pena nieto'. Non-Latin names ('Банк России') keep their
    letters (diacritics removed) instead of folding to an empty string."""
    nfkd = unicodedata.normalize("NFKD", s)
    folded = nfkd.encode("ascii", "ignore").decode().lower()
    if folded.strip(" .,'-"):
        return folded
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower()


def _load_words():
    try:
        with open("/usr/share/dict/words") as f:
            return {line.strip() for line in f}
    except OSError:
        return set()


DICT_WORDS = _load_words()                         # as spelled ("Paris", "paris", ...)
DICT_LOWER = {w.lower() for w in DICT_WORDS}


def is_allcaps(text, min_letters=40, ratio=0.85):
    """True for teletype-style pages (old cables, telegrams) written entirely in capitals."""
    letters = upper = 0
    for ch in text[:20000]:
        if ch.isalpha():
            letters += 1
            upper += ch.isupper()
    return letters >= min_letters and upper / letters >= ratio


# =========================================================================== tokenizer + matcher

# letters/digits of any script (Latin, Cyrillic, Greek, Arabic ...), plus inner ' & . - !
TOKEN_RE = re.compile(r"[^\W_](?:[^\W_]|['’&.\-!])*")
DOTTED = re.compile(r"^(?:[A-Za-z]\.){2,}$")   # U.S., D.C., U.K.


def tokenize(text):
    out = []
    for m in TOKEN_RE.finditer(text):
        t = m.group().replace("’", "'")
        # strip trailing punctuation unless it's an abbreviation like U.S. or Yahoo!
        if not DOTTED.match(t):
            t = t.rstrip(".-'&")
        if t.endswith("'s") and len(t) > 3:
            t = t[:-2]
        if t:
            out.append(t)
    return out


class Matcher:
    """Greedy longest-match of token n-grams against an alias dictionary.

    Aliases that are one word, ALL CAPS or contain a digit match case-sensitively ("Turkey" but not
    "turkey"); other multi-word aliases match case-insensitively. Pages written entirely in capitals
    (find(..., allcaps=True)) also try an upper-cased form of each alias, except single words that
    are ordinary English words for people and companies ("TENET", "VISA", "ORANGE").
    """

    CAPS_OK_TYPES = {"place", "agency", "organization", "program", "technology", "idea"}

    def __init__(self):
        self.exact = {}     # tuple(tokens) -> key
        self.ci = {}        # tuple(lowercased tokens) -> key
        self.caps = {}      # tuple(UPPERCASED tokens) -> key, used on ALL-CAPS pages
        self.first = set()  # first tokens (exact + lower) for a fast reject
        self.caps_first = set()
        self.maxlen = 1

    @staticmethod
    def case_sensitive(alias):
        toks = alias.split()
        return len(toks) == 1 or any(ch.isdigit() for ch in alias) or alias.isupper()

    def add(self, alias, key, etype=None):
        toks = tuple(tokenize(alias))
        if not toks:
            return
        self.maxlen = max(self.maxlen, len(toks))
        if self.case_sensitive(alias):
            self.exact.setdefault(toks, key)
            self.first.add(toks[0])
            if len(toks) == 1 and alias.islower():   # "encryption" should also match "Encryption"
                cap = (toks[0][0].upper() + toks[0][1:],)
                self.exact.setdefault(cap, key)
                self.first.add(cap[0])
        else:
            low = tuple(t.lower() for t in toks)
            self.ci.setdefault(low, key)
            self.first.add(low[0])
        if not alias.isupper():
            up = tuple(t.upper() for t in toks)
            single_word = len(toks) == 1 and toks[0].lower() in DICT_LOWER
            if not single_word or (etype in self.CAPS_OK_TYPES and not alias.islower()):
                self.caps.setdefault(up, key)
                self.caps_first.add(up[0])

    def find(self, tokens, allcaps=False):
        """Yield matched keys."""
        n, i = len(tokens), 0
        lower = [t.lower() for t in tokens]
        first = self.first
        caps, caps_first = (self.caps, self.caps_first) if allcaps else ({}, ())
        while i < n:
            if tokens[i] not in first and lower[i] not in first and tokens[i] not in caps_first:
                i += 1
                continue
            hit = None
            for L in range(min(self.maxlen, n - i), 0, -1):
                span = tuple(tokens[i:i + L])
                k = self.exact.get(span)
                if k is not None and caps and L == 1 and span[0].isupper() and span[0].lower() in DICT_LOWER:
                    k = None    # on ALL-CAPS pages "ICE", "SEC", "SWIFT" are just words
                if k is None:
                    k = self.ci.get(tuple(lower[i:i + L]))
                if k is None and caps:
                    k = caps.get(span)
                if k is not None:
                    hit = (k, L)
                    break
            if hit:
                yield hit[0]
                i += hit[1]
            else:
                i += 1


# =========================================================================== person names (NER output)

TITLE_PREFIX = re.compile(
    r"^(?:(?:Lt\.?|Maj\.?|Brig\.?|Vice|Rear)\s+)?(?:Gen\.?|General|Admiral|Adm\.?|Dr\.?|Mr\.?|Mrs\.?|Ms\.?|Miss|President|"
    r"Prime Minister|Minister|Senator|Sen\.?|Rep\.?|Representative|Judge|Justice|Director|Chancellor|King|Prince|Princess|"
    r"Sheikh|Shaykh|Col\.?|Colonel|Major|Capt\.?|Captain|Lieutenant|Sergeant|Sgt\.?|SSgt|LTG|MG|BG|ADM|VADM|RADM|CDR|LCDR|LTC|"
    r"COL|CAPT|Secretary|Ambassador|Professor|Prof\.?|Deputy|Chief|Mullah|Imam|Sir|Lord|Lady|Dame|Governor|Mayor|"
    r"Kanzlerin|Bundeskanzlerin|Bundeskanzler|Kanzler|Präsident|Praesident|Herr|Frau)\s+")
NAME_TOKEN = re.compile(r"^(?:[A-Z][a-z]+(?:[-'][A-Za-z][a-z]+)*|al|al-[A-Z][a-z]+|bin|ibn|abu|Abu|de|van|von|der|da|du|la|le|el|El|Al|Bin)$")
NAME_STOP = set("""
The This That These Those And For From With Without Into Onto Over Under About After Before During Between Through
Director Office Center Centre Analysis Division Branch Service Services Agency Agencies Team Group Groups Program Programme
Project Run Date Chief Deputy Senior Technical National International Security Intelligence Signals Mission Operations Directorate
University Street Road Building Room Station Site Region Regional Department Ministry Committee Council Court District
Government Federal Republic Kingdom States United Union Army Navy Force Forces Marine Corps Command Joint Special Unit
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September
October November December Google Yahoo Microsoft Apple Facebook Skype Twitter Windows Linux Android Excel Word Outlook
Analyst Analysts Officer Officers Manager Leader Lead Customer Report Reports Reporting Target Targets Source Sources
North South East West Northern Southern Eastern Western Middle Central Islamic Muslim Arab Arabic Persian Chinese Russian
Iraqi Afghan Pakistani Iranian Israeli German French British American Canadian Australian Swedish Norwegian Danish Dutch
Data Network Networks System Systems Tool Tools Access Collection Internet Web Email Mail Phone Mobile Cell Satellite
Cyber Information Language Languages Policy Legal Counsel General Admiral President Minister Senator Judge Doctor
Happy New Year Day Week Month Holiday Christmas Thanksgiving Award Awards Medal Excellence Hall Fame Honor Honors
Seminar Conference Course School Training Class Lecture Session Panel Forum Summit Meeting Today Tomorrow Yesterday
Question Questions Answer Answers Note Notes Summary Overview Introduction Background Conclusion Slide Slides Page
Lab Labs Laboratory Institute Foundation Society Association Club Library Museum Hospital Airport Port Bay Island
Lake River Mountain Mount Valley Park Fort Camp Base Hill Gap Field Point Bridge Tower Gate Plaza Square
""".split())
NAME_TAIL_STOP = set("""Number Order Name Schedule Suite Line Prior Books Remarks Info Teams Commands Commanders Subpoena
Briefing Movants Nos Appendix Submit Lunch Auditorium Panorama Kaserne Strategy Metadata Registration Drill Advisor Bag
Dive Buy-In Transfer Clicks Client Adventures Learning Case Conspiracy Abroad Anonymous Headquarters Enforcement Canada
Sch Gel Springs Meade Directives Website Calendar Defending Extremism Doe Hotel Carlton Award Awards Building Hall Room Seminar Series Program Report Review Plan Policy Brief Guide Manual
Embassy Consulate Legation Bureau Commission Subject Redacted Deleted""".split())
NAME_HEAD_STOP = set("Ft Lt Der Die Das Rollout Booz Cryptologic Metadata Safeguarding Acronyms Communications Interns Counselfor Forrest".split())
PARTICLES = {"al", "bin", "ibn", "abu", "Abu", "de", "van", "von", "der", "da", "du", "la", "le", "el", "El", "Al", "Bin"}


def _name_token(t):
    """'Smith', 'al-Assad', "O'Neill" and also non-ASCII names ('José', 'Иван', 'Müller')."""
    if NAME_TOKEN.match(t):
        return True
    parts = re.split(r"[-']", t)
    return (len(parts[0]) >= 2 and all(p.isalpha() and p[0].isupper() and (len(p) == 1 or p[1:].islower()) for p in parts)
            and not t.isascii())


def _caps_surname(t, caps_stop):
    """An all-caps surname as typed reports write it ('FAUNTROY', 'PEÑA', "O'NEILL"), not an acronym, rank or
    form word ('DCI', 'KGB', 'SCLC', 'TO'): four or more letters with a vowel, and not in caps_stop."""
    letters = t.replace("-", "").replace("'", "")
    return (len(letters) >= 4 and letters.isalpha() and t.isupper() and t not in caps_stop
            and bool(re.search(r"[aeiouy]", plain(t))))


def _title(s):
    """'GARCÍA' -> 'García', "O'NEILL" -> "O'Neill", 'SMITH-JONES' -> 'Smith-Jones'."""
    return re.sub(r"[^\W\d_]+", lambda m: m.group(0).capitalize(), s)


def normalize_person(raw, caps_stop=frozenset(), allcaps=False):
    """An NER PERSON span -> 'Given Surname', or None if it does not look like a person's name. caps_stop:
    all-caps tokens that are never surnames (known acronyms and codenames). allcaps: also accept a name written
    entirely in capitals ('WALTER E. FAUNTROY'), which is otherwise more often a heading than a person."""
    s = norm_ws(raw.replace("’", "'"))
    s = re.sub(r"'[sS]$", "", s)
    if allcaps and s.isupper():
        s = _title(s)
    prev = None
    while prev != s:
        prev = s
        s = TITLE_PREFIX.sub("", s)
    toks = [t for t in s.split() if not re.fullmatch(r"[A-Z]\.?", t)]   # drop middle initials
    if not 2 <= len(toks) <= 4 or len(set(toks)) < len(toks):
        return None
    # typed government reports capitalise surnames ("Walter E. FAUNTROY", "Manuel TELLO Troncoso", "Enrique
    # PEÑA NIETO"): title-case one run of all-caps tokens after the given name. Anything else in capitals ("SAC
    # Robert Kennedy", "Richard Helms DCI", "Miami JMWAVE") is left as it is, and the name is rejected below.
    caps = [i for i, t in enumerate(toks) if t.isupper()]
    if (caps and caps[0] > 0 and caps[-1] - caps[0] == len(caps) - 1
            and all(_caps_surname(toks[i], caps_stop) for i in caps)):
        toks = [_title(t) if t.isupper() else t for t in toks]
    if len(toks) == 4 and not PARTICLES.intersection(toks):
        return None   # usually two names run together by OCR ("Marc Zwillinger Jacob Sommer")
    if not all(_name_token(t) for t in toks):
        return None
    if sum(1 for t in toks if t[0].isupper()) < 2:
        return None
    if any(t in NAME_STOP for t in toks) or toks[0] in NAME_HEAD_STOP or toks[-1] in NAME_TAIL_STOP:
        return None
    # the first token should look like a given name, not an ordinary English word ("Product Line", "Deep Dive")
    if toks[0] not in DICT_WORDS and toks[0].lower() in DICT_WORDS:
        return None
    name = " ".join(toks)
    if len(name) < 6:
        return None
    return name


def display_name_to_person(display):
    """Email display names: 'Podesta, John' / '"John Podesta" <..>' / 'JOHN PODESTA' -> 'John Podesta' or None."""
    s = norm_ws(display.strip().strip("'\"").replace("'", "'"))
    s = re.sub(r"\s*\(.*?\)\s*", " ", s).strip()          # "John Smith (Legal)"
    s = re.sub(r"\s+via\s+.*$", "", s, flags=re.I)        # "'John' via Group"
    m = re.fullmatch(r"([^,]+),\s*([^,]+)", s)
    if m:
        s = f"{m.group(2)} {m.group(1)}"
    if "@" in s or not s:
        return None
    if s.isupper() or s.islower():
        s = " ".join(w.capitalize() for w in s.split())
    return normalize_person(s)


ORG_SUFFIX = re.compile(r"(?i)\b(?:inc|incorporated|corp|corporation|co|company|ltd|limited|llc|llp|lp|plc|gmbh|ag|sa|s\.a|"
                        r"sarl|srl|spa|s\.p\.a|bv|b\.v|nv|n\.v|oy|ab|as|a/s|kg|pte|pty|holdings?|group|bank|trust|"
                        r"foundation|partners|capital|investments?|ventures|enterprises?|international|industries)\.?$")
ORG_STOP = {"the", "a", "an", "this", "that", "page", "table", "figure", "section", "chapter", "annex", "appendix",
            "attn", "fyi", "pac", "llc", "inc", "ltd", "dept", "admin", "staff", "team", "office", "committee", "board"}


def tidy_org(raw):
    s = norm_ws(raw.replace("’", "'"))
    s = re.sub(r"^(?:the|The|THE)\s+", "", s)
    return re.sub(r"'s$", "", s).strip(" .,;:-'\"()")


def normalize_org(raw):
    """Tidy an NER ORG/GPE span; None if it does not look like a proper name (ordinary words such as
    'State', 'Senate', 'Post' or generic abbreviations)."""
    s = tidy_org(raw)
    if not 2 <= len(s) <= 80 or s.lower() in ORG_STOP or not any(c.isalpha() for c in s):
        return None
    if s.islower() or len(s.split()) > 7 or re.search(r"[\n|{}<>@=]", s):
        return None
    if len(s) <= 3 and not s.isupper():
        return None
    toks = s.split()
    if len(toks) == 1:
        w = toks[0].lower()
        if w in DICT_LOWER or (w.endswith("s") and w[:-1] in DICT_LOWER):
            return None
    return s


def looks_like_company(name):
    return len(name.split()) >= 2 and bool(ORG_SUFFIX.search(name))

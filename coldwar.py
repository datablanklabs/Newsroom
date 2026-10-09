"""
Cold War and declassified-history pack: the JFK and MLK assassination records, Church Committee
material, CIA CREST documents and Cold War covert operations.

The metadata parser reads NARA's JFK Assassination Records identification forms (AGENCY,
RECORD NUMBER, ORIGINATOR, FROM, TO, TITLE, DATE, SUBJECTS ...) when a document carries one,
and otherwise recognises the record number in the release stamp (104-... CIA, 124-... FBI,
157-... Church Committee, 180-... HSCA). Military-style dates ("28 JAN 62") are read too.
"""
import re

DESCRIPTION = "Cold War & declassified history: JFK/RFK/MLK records, CIA covert operations, NARA record forms"
REQUIRES = ["core", "government"]

PERSON = [
    ("Lee Harvey Oswald", ["Oswald", "Lee Harvey Oswald", "Lee Oswald", "Lee H. Oswald", "Hidell", "A. J. Hidell", "Alek Hidell"], "Accused assassin of President Kennedy; shot dead by Jack Ruby on November 24, 1963."),
    ("Marina Oswald", ["Marina Oswald", "Marina Prusakova", "Marina Oswald Porter"], "Lee Harvey Oswald's Soviet-born wife."),
    ("Jack Ruby", ["Jack Ruby", "Jacob Rubenstein"], "Dallas nightclub owner who killed Lee Harvey Oswald."),
    ("Earl Warren", ["Earl Warren", "Chief Justice Warren"], "Chief Justice of the United States; chaired the Warren Commission."),
    ("James Jesus Angleton", ["Angleton", "James Angleton", "James Jesus Angleton"], "Chief of CIA counterintelligence 1954–1974."),
    ("E. Howard Hunt", ["E. Howard Hunt", "Howard Hunt", "Everette Howard Hunt"], "CIA officer; later a Watergate conspirator."),
    ("David Atlee Phillips", ["David Atlee Phillips", "David Phillips"], "CIA officer who served in Mexico City and on anti-Castro operations."),
    ("Winston Scott", ["Winston Scott", "Win Scott"], "CIA Mexico City station chief in 1963."),
    ("Jim Garrison", ["Jim Garrison", "District Attorney Garrison", "DA Garrison"], "New Orleans District Attorney who prosecuted Clay Shaw."),
    ("Clay Shaw", ["Clay Shaw", "Clay L. Shaw"], "New Orleans businessman acquitted in 1969 of conspiring to kill Kennedy."),
    ("David Ferrie", ["David Ferrie", "Ferrie"], "Pilot linked to Oswald in the Garrison investigation."),
    ("Guy Banister", ["Guy Banister"], "Former FBI agent and private investigator in New Orleans."),
    ("George de Mohrenschildt", ["de Mohrenschildt", "George de Mohrenschildt", "DeMohrenschildt"], "Petroleum geologist who befriended Oswald in Dallas."),
    ("Ruth Paine", ["Ruth Paine"], "Irving, Texas woman with whom Marina Oswald lived in 1963."),
    ("Valery Kostikov", ["Kostikov", "Valeriy Kostikov", "Valery Kostikov"], "Soviet consular officer in Mexico City identified by the CIA as KGB."),
    ("Sylvia Duran", ["Sylvia Duran", "Silvia Duran"], "Cuban consulate employee in Mexico City who dealt with Oswald."),
    ("Carlos Marcello", ["Carlos Marcello"], "New Orleans Mafia boss."),
    ("Santo Trafficante", ["Trafficante", "Santo Trafficante"], "Florida Mafia boss involved in CIA plots against Castro."),
    ("Sam Giancana", ["Giancana", "Sam Giancana"], "Chicago Mafia boss involved in CIA plots against Castro."),
    ("Johnny Roselli", ["Roselli", "Rosselli", "Johnny Roselli"], "Mafia figure recruited for CIA plots against Castro."),
    ("Che Guevara", ["Che Guevara", "Ernesto Guevara", "Ernesto \"Che\" Guevara"], "Argentine-born Cuban revolutionary; killed in Bolivia in 1967."),
    ("Rolando Cubela", ["Cubela", "Rolando Cubela"], "Cuban official recruited by the CIA to kill Castro (AMLASH)."),
    ("Yuri Nosenko", ["Nosenko"], "KGB defector (1964) who said the KGB had no ties to Oswald."),
    ("Anatoliy Golitsyn", ["Golitsyn", "Golitsin"], "KGB defector (1961) whose claims shaped CIA counterintelligence."),
    ("Kim Philby", ["Philby", "Kim Philby"], "British MI6 officer and Soviet spy who defected in 1963."),
    ("Oleg Penkovsky", ["Penkovsky"], "Soviet GRU colonel who spied for the U.S. and Britain; executed in 1963."),
    ("Francis Gary Powers", ["Gary Powers", "Francis Gary Powers"], "U-2 pilot shot down over the USSR in 1960."),
    ("Julius and Ethel Rosenberg", ["Julius Rosenberg", "Ethel Rosenberg", "the Rosenbergs"], "Americans executed in 1953 for atomic espionage for the USSR."),
    ("Alger Hiss", ["Alger Hiss"], "State Department official accused of Soviet espionage; convicted of perjury in 1950."),
    ("Joseph McCarthy", ["Joseph McCarthy", "Senator McCarthy", "Joe McCarthy"], "U.S. Senator who led anti-communist investigations in the 1950s."),
    ("Klaus Fuchs", ["Klaus Fuchs"], "Physicist who passed atomic secrets to the USSR."),
    ("Martin Luther King Jr.", ["Martin Luther King", "Martin Luther King Jr.", "Martin Luther King, Jr.", "Luther King", "Dr. King", "MLK", "Rev. King", "Reverend King"], "Civil rights leader; target of FBI surveillance; assassinated in Memphis on April 4, 1968."),
    ("Coretta Scott King", ["Coretta Scott King", "Coretta King"], "Civil rights leader; widow of Martin Luther King Jr."),
    ("Malcolm X", ["Malcolm X", "El-Hajj Malik El-Shabazz", "Malcolm Little"], "Black nationalist leader; assassinated in 1965."),
    ("Ralph Abernathy", ["Abernathy", "Ralph Abernathy"], "Civil rights leader and close associate of Martin Luther King Jr."),
    ("Stanley Levison", ["Stanley Levison"], "Adviser to Martin Luther King Jr. whom the FBI targeted as a suspected communist."),
    ("Andrew Young", ["Andrew Young"], "Civil rights leader; later UN Ambassador."),
    ("James Earl Ray", ["James Earl Ray"], "Convicted assassin of Martin Luther King Jr."),
    ("Loyd Jowers", ["Loyd Jowers", "Lloyd Jowers"], "Memphis man found liable in the King family's 1999 civil suit over the assassination."),
    ("William Sullivan (FBI)", ["William C. Sullivan", "William Sullivan"], "FBI assistant director who ran domestic intelligence and COINTELPRO."),
    ("Cartha DeLoach", ["DeLoach", "Cartha DeLoach", "Deke DeLoach"], "FBI assistant director under Hoover."),
    ("Nelson Rockefeller", ["Nelson Rockefeller", "Vice President Rockefeller"], "U.S. Vice President 1974–1977; chaired the Rockefeller Commission on CIA abuses."),
    ("Ngo Dinh Diem", ["Ngo Dinh Diem", "Diem"], "President of South Vietnam; killed in a November 1963 coup."),
    ("Ho Chi Minh", ["Ho Chi Minh"], "Leader of North Vietnam."),
    ("Sirhan Sirhan", ["Sirhan", "Sirhan Sirhan", "Sirhan Bishara Sirhan", "Sirhan B. Sirhan"], "Convicted assassin of Senator Robert F. Kennedy (June 5, 1968)."),
    ("Thane Eugene Cesar", ["Thane Eugene Cesar", "Thane Cesar"], "Security guard walking with Robert F. Kennedy when he was shot."),
    ("Juan Romero", ["Juan Romero"], "Ambassador Hotel busboy who knelt beside the wounded Robert F. Kennedy."),
    ("Rafael Trujillo", ["Trujillo"], "Dictator of the Dominican Republic; assassinated in 1961."),
    ("Mohammad Mosaddegh", ["Mosaddegh", "Mossadegh", "Mosaddeq"], "Prime Minister of Iran overthrown in the 1953 CIA/MI6-backed coup."),
    ("Jacobo Árbenz", ["Árbenz", "Arbenz"], "President of Guatemala overthrown in the 1954 CIA-backed coup."),
    ("Sukarno", ["Sukarno"], "First President of Indonesia."),
]

AGENCY = [
    ("Warren Commission", ["Warren Commission", "President's Commission on the Assassination of President Kennedy"], "Commission that investigated the Kennedy assassination (report 1964)."),
    ("House Select Committee on Assassinations", ["House Select Committee on Assassinations", "HSCA"], "Congressional committee that reinvestigated the Kennedy and King assassinations (1976–1979)."),
    ("Church Committee", ["Church Committee", "SSCIA", "Senate Select Committee to Study Governmental Operations"], "Senate committee that investigated intelligence abuses (1975–1976)."),
    ("Pike Committee", ["Pike Committee"], "House committee that investigated the intelligence agencies (1975–1976)."),
    ("Rockefeller Commission", ["Rockefeller Commission", "Commission on CIA Activities Within the United States"], "1975 presidential commission on CIA domestic activities."),
    ("Assassination Records Review Board", ["Assassination Records Review Board", "ARRB"], "Board that oversaw release of JFK records (1994–1998)."),
    ("Office of Strategic Services", ["Office of Strategic Services", "OSS"], "U.S. wartime intelligence agency; forerunner of the CIA."),
    ("Atomic Energy Commission", ["Atomic Energy Commission", "AEC"], "U.S. nuclear agency 1946–1974."),
    ("Dallas Police Department", ["Dallas Police Department", "Dallas Police"], "Dallas police."),
    ("Los Angeles Police Department", ["Los Angeles Police Department", "LAPD"], "Los Angeles police, who investigated the RFK assassination."),
    ("Special Unit Senator", ["Special Unit Senator"], "LAPD task force that investigated the RFK assassination (1968–1969)."),
]

PROGRAM = [
    ("Operation Mongoose", ["Operation Mongoose", "MONGOOSE", "Cuban Project"], "CIA covert campaign against Castro's Cuba, 1961–1962."),
    ("Bay of Pigs", ["Bay of Pigs", "Playa Girón", "JMATE"], "Failed CIA-backed invasion of Cuba, April 1961."),
    ("JMWAVE", ["JMWAVE", "JM/WAVE"], "CIA station in Miami running anti-Castro operations."),
    ("ZR/RIFLE", ["ZRRIFLE", "ZR/RIFLE", "ZR RIFLE"], "CIA program for assassination capability ('executive action')."),
    ("AMLASH", ["AMLASH", "AM/LASH"], "CIA operation with Rolando Cubela to kill Castro."),
    ("LIENVOY", ["LIENVOY"], "CIA telephone-tapping operation in Mexico City."),
    ("LIEMPTY", ["LIEMPTY"], "CIA photo surveillance of the Soviet embassy in Mexico City."),
    ("MKULTRA", ["MKULTRA", "MK-ULTRA", "MK ULTRA", "MKUltra"], "CIA program of mind-control and drug experiments on humans, 1953–1973."),
    ("COINTELPRO", ["COINTELPRO", "Counterintelligence Program"], "FBI program (1956–1971) to surveil, infiltrate and disrupt domestic political groups."),
    ("Operation CHAOS", ["MHCHAOS", "Operation CHAOS", "Operation Chaos"], "CIA domestic spying on anti-war and radical groups, 1967–1974."),
    ("HTLINGUAL", ["HTLINGUAL", "HT/LINGUAL"], "CIA program that opened mail between the U.S. and the USSR, 1952–1973."),
    ("Operation Northwoods", ["Operation Northwoods", "Northwoods"], "1962 Joint Chiefs proposal for false-flag attacks to justify war with Cuba (rejected)."),
    ("Family Jewels", ["Family Jewels"], "1973 internal CIA report on its illegal activities."),
    ("Project Blue Book", ["Project Blue Book", "Project Bluebook"], "U.S. Air Force study of UFO reports, 1952–1969."),
    ("Operation Paperclip", ["Operation Paperclip", "Project Paperclip"], "Recruitment of German scientists to the U.S. after World War II."),
    ("Venona", ["Venona", "VENONA"], "U.S. project that decrypted Soviet intelligence messages."),
    ("Operation Gladio", ["Gladio", "Operation Gladio"], "NATO stay-behind networks in Europe."),
    ("Operation Ajax (Iran 1953)", ["TPAJAX", "Operation Ajax", "AJAX"], "CIA/MI6 operation that overthrew Mosaddegh in Iran, 1953."),
    ("PBSUCCESS", ["PBSUCCESS", "PBSuccess"], "CIA operation that overthrew Árbenz in Guatemala, 1954."),
    ("Phoenix Program", ["Phoenix Program", "Operation Phoenix", "Phung Hoang"], "U.S./South Vietnamese program to neutralize the Viet Cong infrastructure."),
    ("Operation Condor", ["Operation Condor", "Plan Condor"], "Campaign of repression and assassination by South American dictatorships in the 1970s."),
    ("Iran-Contra", ["Iran-Contra", "Iran Contra", "Iran–Contra"], "1980s secret arms sales to Iran funding the Nicaraguan Contras."),
    ("Watergate", ["Watergate"], "Political scandal that led to Nixon's resignation in 1974."),
    ("Manhattan Project", ["Manhattan Project"], "U.S. atomic bomb program in World War II."),
    ("U-2 program", ["U-2", "U-2 incident", "AQUATONE"], "CIA high-altitude reconnaissance aircraft program."),
    ("CORONA", ["CORONA", "Corona satellite"], "U.S. photo-reconnaissance satellite program, 1960–1972."),
    ("Operation Rubicon", ["Operation Rubicon", "Rubikon"], "CIA/BND secret ownership of Crypto AG to read other countries' encrypted traffic."),
    ("Cuban Missile Crisis", ["Cuban Missile Crisis", "Cuban missile crisis", "October Crisis"], "October 1962 U.S.–Soviet confrontation over missiles in Cuba."),
    ("Gulf of Tonkin incident", ["Gulf of Tonkin", "Tonkin Gulf"], "1964 naval clashes used to justify U.S. escalation in Vietnam."),
    ("Pentagon Papers", ["Pentagon Papers"], "Secret history of the Vietnam War leaked by Daniel Ellsberg in 1971."),
    ("Vietnam War", ["Vietnam War", "Vietnam conflict"], "The Vietnam War."),
]

PLACE = [
    ("Dealey Plaza", ["Dealey Plaza", "grassy knoll"], "Dallas plaza where President Kennedy was shot."),
    ("Texas School Book Depository", ["Texas School Book Depository", "Book Depository", "TSBD"], "Building from which shots were fired at President Kennedy."),
    ("Memphis", ["Memphis"], "City where Martin Luther King Jr. was assassinated."),
    ("Lorraine Motel", ["Lorraine Motel"], "Memphis motel where Martin Luther King Jr. was shot."),
    ("Ambassador Hotel", ["Ambassador Hotel"], "Los Angeles hotel where Robert F. Kennedy was shot on June 5, 1968."),
    ("Berlin Wall", ["Berlin Wall"], "Barrier dividing Berlin, 1961–1989."),
]

ORGANIZATION = [
    ("Viet Cong", ["Viet Cong", "Vietcong", "National Liberation Front"], "Communist insurgency in South Vietnam."),
    ("Fair Play for Cuba Committee", ["Fair Play for Cuba Committee", "FPCC"], "Pro-Castro group; Oswald ran a one-man New Orleans chapter."),
    ("SCLC", ["Southern Christian Leadership Conference"], "Civil rights organization led by Martin Luther King Jr."),
    ("Black Panther Party", ["Black Panther Party", "Black Panthers"], "Black revolutionary organization targeted by COINTELPRO."),
]

# CIA cryptonyms for agencies and countries, as they appear in 1950s–70s cables and dispatches.
CRYPTONYMS = {
    "agency": [("CIA", ["KUBARK"], ""), ("FBI", ["ODENVY"], ""), ("State Department", ["ODACID"], "")],
    "place": [("United States", ["PBPRIME"], "")],
}

COMPANY = [("Cubana de Aviación", ["Cubana", "CUBANA", "Cubana de Aviacion"], "Cuba's state airline.")]

ENTITIES = {"person": PERSON, "agency": AGENCY + CRYPTONYMS["agency"], "organization": ORGANIZATION, "program": PROGRAM,
            "place": PLACE + CRYPTONYMS["place"], "company": COMPANY}

# CIA cable and dispatch boilerplate that must not become "codenames"
CODENAME_STOP = """GRADING DISPATCH ROUTING REPRODUCTION PROHIBITED INDEXING HEADQUARTERS PRIORITY IMMEDIATE ROUTINE
RYBAT TYPIC CITE INFO ACTION REFERENCE REFERENCES ATTACHMENT ATTACHED DISTRIBUTION ORIGINATING COORDINATING
RELEASING AUTHENTICATING OFFICER SIGNATURE CLASSIFICATION DOCUMENT IDENTIFICATION DISSEMINATION SOURCE SUBJECT
CHIEF STATION INFORMATION REPORT EVALUATION APPRAISAL CONTENT DETACHMENT ROUTE BACKGROUND IMPDET
SUPDATA FILENUMBER LASTREVIEW ALLINFORMATION ALLINFORMATIONCONTAINED CURRENTSTATUS FULLNAME FILEDIN TONAME
RECORDNUMBER RECORDSERIES AGENCYFILE DOCUMENTTYPE OPENINFULL NEWCLASS DATEOFLASTREVIEW"""

# Short names from the modern-world packs that misfire in OCR'd mid-century cables and reports. Most entities
# still match by their full names ("Securities and Exchange Commission"); those known only by such a name
# (Sony, ZTE, The Intercept) are left out. Only used by corpora that load no packs beyond coldwar and its
# requirements (jfk, rfk, mlk); a mixed-era corpus that also loads sigint or military keeps these names.
# Single words that are also dictionary words (ETA, SEC, ICE, EU, FRA) are already ignored on ALL-CAPS pages;
# they are listed because typed mixed-case memos use them the same way.
SUPPRESS_ALIASES = [
    # anachronisms that only ever match OCR noise or abbreviations here (EU before 1993, ICE before 2003)
    "AQ", "HTS", "LeT", "AWS", "MSN", "ICE", "TSA", "CBP", "EFF", "KSA", "GCC", "MBS", "UBL", "ZTE", "HRW", "DRC",
    "G7", "G8", "G-7", "G-8", "G20", "G-20", "EU", "ASD", "DSD", "CSE", "CSEC",
    # cable and memo abbreviations: estimated time of arrival, section, manuscripts, France ...
    "ETA", "SEC", "BP", "MSS", "FRA",
    # other readings that were more common then: the Interstate Commerce Commission, the Warsaw Treaty
    # Organization, a common Hispanic surname
    "ICC", "WTO", "Gonzales",
    # ordinary words in these files: "the intercept", anonymous letters; OCR junk read as brand names
    "The Intercept", "Anonymous", "Sony", "Apple",
]

STRIP_PATTERNS = [
    r"(?i)Released\s+under\s+the\s+John\s+F\.?\s*Kennedy[\s\-]*Assassination[\s\S]{0,60}?Records\s+Collection\s+Act\s+of\s+1992[\s\S]{0,40}?\(44\s*USC\s*2107\s*Note\)\.?",
    r"\bNW\s*\d{4,6}\s*(?:Doc\s*[Il1]d\s*:?\s*\d+\s*)?(?:Page\s*\d+|Date\s*:?\s*\d+[/-]\d+[/-]\d+|\d+/\d+/\d+)",
    r"(?i)Case\s*#\s*:?\s*NW\s*\d+[^\n]*",
]

RIF_PREFIX = {"104": "CIA (U.S.)", "124": "FBI (U.S.)", "157": "Church Committee (U.S. Senate)", "180": "HSCA (U.S. House)"}
_RIF_NUMBER = re.compile(r"\b(1\d{2})-(\d{5})-(\d{5})\b")
_RIF_FIELD = re.compile(r"(?m)^\s*(AGENCY|RECORD NUMBER|RECORD SERIES|AGENCY FILE NUMBER|ORIGINATOR|FROM|TO|TITLE|DATE|PAGES|SUBJECTS?|"
                        r"DOCUMENT TYPE|CLASSIFICATION|RESTRICTIONS|CURRENT STATUS|DATE OF LAST REVIEW|OPENING CRITERIA|COMMENTS)\s*:\s*(.*)$")
_MIL_DATE = re.compile(r"(?<!\d)(\d{1,2})\s?(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEPT?|OCT|NOV|DEC)\.?\s?(\d{2}|19\d{2})(?!\d)")
_MONTHS = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def _two_digit(y, corpus):
    y = int(y)
    return y if y > 99 else corpus.dates["two_digit_century"] + y


def nara_record(d, text, meta, corpus):
    head = text[:4000]
    m = _RIF_NUMBER.search(head[:600]) or _RIF_NUMBER.search(d["relpath"])
    fields = {}
    if "AGENCY" in head and "RECORD NUMBER" in head:
        key = None
        for fm in _RIF_FIELD.finditer(head):
            key, val = fm.group(1), fm.group(2).strip()
            if val:
                fields[key] = val
        subj = re.search(r"(?ms)^\s*SUBJECTS?\s*:\s*(.*?)(?=^\s*(?:DOCUMENT TYPE|CLASSIFICATION|RESTRICTIONS)\s*:)", head)
        if subj:
            fields["SUBJECTS"] = re.sub(r"\s*\n\s*", "; ", subj.group(1).strip())
    if not m and not fields:
        return
    if m:
        meta["fields"]["NARA record number"] = m.group(0)
        if not meta.get("origin") and m.group(1) in RIF_PREFIX:
            meta["origin"] = RIF_PREFIX[m.group(1)]
    for k in ("AGENCY", "ORIGINATOR", "FROM", "TO", "TITLE", "DATE", "PAGES", "DOCUMENT TYPE", "CLASSIFICATION", "RECORD SERIES", "AGENCY FILE NUMBER"):
        if k in fields:
            meta["fields"][k.title()] = fields[k]
    if fields.get("TITLE") and not meta.get("title"):
        meta["title"] = fields["TITLE"].title()[:200]
    if fields.get("AGENCY") and not meta.get("origin"):
        meta["origin"] = f"{fields['AGENCY'].upper()} (U.S.)"
    if fields.get("CLASSIFICATION") and not meta.get("classification"):
        meta["classification"] = fields["CLASSIFICATION"].upper()
    if fields.get("DATE") and not meta.get("date"):
        dm = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", fields["DATE"])
        if dm:
            y = _two_digit(dm.group(3), corpus)
            mo, dd = int(dm.group(1)), int(dm.group(2))
            if corpus.dates["min_year"] <= y <= corpus.dates["max_year"] and 1 <= mo <= 12:
                meta["date"] = f"{y:04d}-{mo:02d}-{dd:02d}" if 1 <= dd <= 31 else f"{y:04d}-{mo:02d}"
                meta["date_source"] = "NARA record form"
    for s in re.split(r"\s*;\s*", fields.get("SUBJECTS", "")):
        s = s.strip(" .,")
        if 3 <= len(s) <= 80:
            meta["entities"].append({"type": "idea", "name": f"Subject: {s.title()}", "source": "metadata",
                                     "description": "Subject heading from a NARA JFK record identification form."})
    if m and not meta.get("title"):
        agency = RIF_PREFIX.get(m.group(1), "").split(" (")[0]
        meta["title"] = f"{agency + ' record ' if agency else 'Record '}{m.group(0)}"


def military_date(text, relpath, corpus):
    """'28 JAN 62' style dates near the top of cables and memos (two-digit years read in the configured century)."""
    m = _MIL_DATE.search(text[:2500])
    if m:
        y = _two_digit(m.group(3), corpus)
        mo, d = _MONTHS[m.group(2)[:3]], int(m.group(1))
        if corpus.dates["min_year"] <= y <= corpus.dates["max_year"] and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}", "date in header (est.)"
    return None


METADATA = [nara_record]
DATE_HINTS = [(40, military_date)]

IDEAS = [
    ("Assassinations & plots", [r"(?i:\bassassinat)", r"(?i:\bsniper\b)", r"(?i:\bmotorcade\b)", r"(?i:\bexecutive action\b)", r"(?i:\bplot to kill\b)"],
     "Assassinations and assassination plots."),
    ("Defectors & double agents", [r"(?i:\bdefect(?:or|ed|ion))", r"(?i:\bdouble agent)", r"(?i:\bmole\b)", r"(?i:\bpenetration agent)", r"(?i:\bredefect)"],
     "Defectors, moles and double agents."),
    ("Communism & subversion", [r"(?i:\bcommunis[tm])", r"(?i:\bsubversi)", r"(?i:\bMarxist)", r"(?i:\bfellow traveler)", r"(?i:\bFair Play for Cuba\b)"],
     "Anti-communist investigations and alleged subversion."),
    ("Surveillance of activists", [r"(?i:\bcivil rights\b)", r"(?i:\binformants?\b)", r"(?i:\bsurveillance of\b)", r"(?i:\bdissidents?\b)", r"(?i:\banti-?war\b)", r"(?i:\bBlack Panther)"],
     "Domestic surveillance of activists and political movements."),
    ("Mail opening & wiretaps", [r"(?i:\bmail (?:cover|opening|intercept))", r"(?i:\bwiretaps?\b)", r"(?i:\btelephone taps?\b)", r"(?i:\bmicrophone surveillance\b)", r"(?i:\bbugg(?:ed|ing)\b)"],
     "Mail opening, wiretaps and bugging."),
    ("Mind control & human experiments", [r"\bLSD\b", r"(?i:\bhypnos)", r"(?i:\bbehavio(?:u)?r(?:al)? modification\b)", r"(?i:\bmind control\b)", r"(?i:\bunwitting (?:subjects|testing)\b)"],
     "Drug and mind-control experiments on people."),
    ("Organized crime", [r"(?i:\bMafia\b)", r"(?i:\bLa Cosa Nostra\b)", r"\bLCN\b", r"(?i:\borganized crime\b)", r"(?i:\bmobsters?\b)", r"(?i:\bsyndicate\b)"],
     "The Mafia and organized crime."),
    ("Cuba operations", [r"(?i:\banti-?Castro\b)", r"(?i:\bCuban exiles?\b)", r"(?i:\bCuban (?:consulate|embassy|government|intelligence)\b)", r"(?i:\bHavana\b)"],
     "Operations against and around Castro's Cuba."),
    ("UFOs & UAP", [r"\bUFOs?\b", r"\bUAPs?\b", r"(?i:\bunidentified (?:flying|aerial|anomalous))", r"(?i:\bflying saucers?\b)"],
     "Unidentified flying objects / unidentified anomalous phenomena."),
]

TIMELINE_PRESETS = [
    ("Oswald · Ruby · Castro · Khrushchev", "Lee Harvey Oswald|Jack Ruby|Fidel Castro|Nikita Khrushchev"),
    ("CIA · FBI · KGB", "CIA|FBI|KGB"),
]

"""
Offshore finance pack: secrecy jurisdictions, corporate-service providers and private banks, the
people at the center of the Panama / Paradise / Pandora Papers and bank leaks, and the vocabulary
of offshore structures (nominees, bearer shares, beneficial ownership ...).

Pairs well with the ICIJ Offshore Leaks importer ([[records]] type = "icij") and with
index.identifiers = ["email", "iban"].
"""

DESCRIPTION = "Offshore finance: tax havens, corporate-service providers, private banks, shell-company vocabulary"
REQUIRES = ["core"]

PLACE = [
    ("British Virgin Islands", ["British Virgin Islands", "BVI", "Tortola"], "British overseas territory; the most common jurisdiction for offshore companies in the Panama Papers."),
    ("Cayman Islands", ["Cayman Islands", "Grand Cayman", "Caymans"], "British overseas territory and offshore financial center."),
    ("Bermuda", ["Bermuda"], "British overseas territory and offshore financial center."),
    ("Jersey", ["Jersey", "Bailiwick of Jersey", "St Helier"], "British Crown Dependency and offshore financial center."),
    ("Guernsey", ["Guernsey"], "British Crown Dependency and offshore financial center."),
    ("Isle of Man", ["Isle of Man"], "British Crown Dependency and offshore financial center."),
    ("Gibraltar", ["Gibraltar"], "British overseas territory and offshore financial center."),
    ("Anguilla", ["Anguilla"], "British overseas territory and company registry."),
    ("Turks and Caicos", ["Turks and Caicos", "Turks & Caicos"], "British overseas territory."),
    ("Curaçao / Netherlands Antilles", ["Curaçao", "Curacao", "Netherlands Antilles", "Sint Maarten"], "Dutch Caribbean financial centers."),
    ("Aruba", ["Aruba"], "Dutch Caribbean island."),
    ("Saint Kitts and Nevis", ["Saint Kitts and Nevis", "St Kitts and Nevis", "St. Kitts", "Nevis"], "Caribbean federation known for anonymous companies and citizenship-by-investment."),
    ("Antigua and Barbuda", ["Antigua and Barbuda", "Antigua"], "Caribbean state with an offshore sector."),
    ("Saint Vincent and the Grenadines", ["Saint Vincent and the Grenadines", "St. Vincent", "St Vincent"], "Caribbean state with an offshore sector."),
    ("Dominica", ["Dominica", "Commonwealth of Dominica"], "Caribbean state selling citizenship-by-investment."),
    ("Niue", ["Niue"], "Pacific island whose company registry was run by Mossack Fonseca until 2006."),
    ("Cook Islands", ["Cook Islands"], "Pacific offshore trust jurisdiction."),
    ("Labuan", ["Labuan"], "Malaysian offshore financial center."),
    ("Ras Al Khaimah", ["Ras Al Khaimah", "Ras al-Khaimah"], "UAE emirate with an offshore company registry."),
    ("South Dakota", ["South Dakota"], "U.S. state popular for secretive trusts."),
    ("Madeira", ["Madeira"], "Portuguese island with a low-tax free trade zone."),
]

COMPANY = [
    ("Mossack Fonseca", ["Mossack Fonseca", "MossFon", "Mossfon", "Mossack Fonseca & Co."], "Panamanian law firm and offshore-service provider; source of the 2016 Panama Papers leak; closed in 2018."),
    ("Appleby", ["Appleby"], "Bermuda-founded offshore law firm; source of most of the 2017 Paradise Papers."),
    ("Alcogal", ["Alcogal", "Alemán, Cordero, Galindo & Lee"], "Panamanian law firm; a major source in the 2021 Pandora Papers."),
    ("Trident Trust", ["Trident Trust"], "Offshore corporate-service provider; a source in the Pandora Papers."),
    ("Asiaciti Trust", ["Asiaciti", "Asiaciti Trust"], "Singapore-based trust company; a source in the Pandora Papers."),
    ("Portcullis TrustNet", ["Portcullis TrustNet", "TrustNet"], "Offshore service provider; source of the 2013 Offshore Leaks."),
    ("Commonwealth Trust Limited", ["Commonwealth Trust Limited", "Commonwealth Trust Ltd"], "BVI corporate-service provider in the 2013 Offshore Leaks."),
    ("Estera", ["Estera"], "Fiduciary business spun off from Appleby."),
    ("Julius Baer", ["Julius Baer", "Julius Bär", "Bank Julius Baer", "BJB"], "Swiss private bank."),
    ("Pictet", ["Pictet"], "Swiss private bank."),
    ("Lombard Odier", ["Lombard Odier"], "Swiss private bank."),
    ("BSI", ["BSI SA", "Banca della Svizzera Italiana"], "Swiss bank closed in 2016 over the 1MDB scandal."),
    ("Banca Privada d'Andorra", ["Banca Privada d'Andorra"], "Andorran bank taken over in 2015 after U.S. money-laundering allegations."),
    ("ABLV Bank", ["ABLV Bank", "ABLV"], "Latvian bank that collapsed in 2018 after U.S. money-laundering allegations."),
    ("Pilatus Bank", ["Pilatus Bank"], "Maltese bank closed in 2018 after money-laundering charges."),
    ("FBME Bank", ["FBME Bank", "FBME"], "Tanzanian/Cypriot bank cut off from the U.S. system over money laundering."),
    ("Swedbank", ["Swedbank"], "Swedish bank tied to the Baltic money-laundering scandal."),
    ("Kaupthing", ["Kaupthing", "Kaupthing Bank"], "Icelandic bank that collapsed in October 2008."),
    ("Landsbanki", ["Landsbanki", "Icesave"], "Icelandic bank that collapsed in October 2008 (Icesave)."),
    ("Glitnir", ["Glitnir"], "Icelandic bank that collapsed in October 2008."),
    ("Rothschild", ["Rothschild", "Rothschild & Co"], "Banking group."),
    ("1MDB", ["1MDB", "1Malaysia Development Berhad"], "Malaysian state fund at the center of a multibillion-dollar embezzlement scandal."),
]

ORGANIZATION = [
    ("FATF", ["Financial Action Task Force"], "Financial Action Task Force: sets anti-money-laundering standards and keeps the grey and black lists."),
    ("Tax Justice Network", ["Tax Justice Network"], "Campaign group that publishes the Financial Secrecy Index."),
    ("Global Witness", ["Global Witness"], "Anti-corruption investigative group."),
]

AGENCY = [
    ("FinCEN", ["Financial Crimes Enforcement Network"], "U.S. Treasury's financial-intelligence unit (source of the 2020 FinCEN Files)."),
    ("OFAC", ["Office of Foreign Assets Control"], "U.S. Treasury office that administers sanctions."),
]

PERSON = [
    ("Jürgen Mossack", ["Jürgen Mossack", "Jurgen Mossack", "Juergen Mossack"], "Co-founder of Mossack Fonseca."),
    ("Ramón Fonseca", ["Ramón Fonseca", "Ramon Fonseca", "Ramón Fonseca Mora", "Ramon Fonseca Mora"], "Co-founder of Mossack Fonseca."),
    ("Sigmundur Davíð Gunnlaugsson", ["Gunnlaugsson", "Sigmundur Davíð", "Sigmundur David Gunnlaugsson"], "Prime Minister of Iceland who resigned in April 2016 after the Panama Papers revealed his offshore company."),
    ("Bastian Obermayer", ["Bastian Obermayer", "Obermayer"], "Süddeutsche Zeitung journalist who received the Panama Papers."),
    ("Frederik Obermaier", ["Frederik Obermaier", "Obermaier"], "Süddeutsche Zeitung journalist who received the Panama Papers."),
    ("Daphne Caruana Galizia", ["Daphne Caruana Galizia", "Caruana Galizia"], "Maltese investigative journalist killed by a car bomb in 2017."),
    ("Hervé Falciani", ["Hervé Falciani", "Herve Falciani", "Falciani"], "Former HSBC Private Bank (Suisse) employee whose client data became the SwissLeaks files."),
    ("Rudolf Elmer", ["Rudolf Elmer"], "Former Julius Baer executive in the Cayman Islands who passed client data to WikiLeaks."),
    ("Jho Low", ["Jho Low", "Low Taek Jho"], "Malaysian financier accused of masterminding the 1MDB fraud."),
    ("Najib Razak", ["Najib Razak"], "Prime Minister of Malaysia 2009–2018; convicted over 1MDB."),
]

ENTITIES = {"place": PLACE, "company": COMPANY, "organization": ORGANIZATION, "agency": AGENCY, "person": PERSON}

IDEAS = [
    ("Shell companies & offshore structures", [r"(?i:\bshell compan)", r"(?i:\boffshore (?:compan|entit|structure|account))", r"\bIBCs?\b", r"(?i:\binternational business compan)", r"(?i:\bspecial purpose vehicle)", r"\bSPV\b"],
     "Shell companies, IBCs and layered offshore structures."),
    ("Nominee directors & shareholders", [r"(?i:\bnominee)", r"(?i:\bfront (?:man|company)\b)", r"(?i:\bstraw (?:man|owner)\b)"],
     "Nominees who stand in for the real owners."),
    ("Bearer shares", [r"(?i:\bbearer (?:shares?|certificates?)\b)"], "Anonymous bearer shares."),
    ("Beneficial ownership", [r"(?i:\bbeneficial owner)", r"\bUBOs?\b", r"(?i:\bultimate (?:beneficial )?owner)"],
     "Who really owns and controls a company."),
    ("Tax evasion & avoidance", [r"(?i:\btax (?:evasion|avoidance|haven|fraud|planning)\b)", r"(?i:\bevade taxes\b)", r"(?i:\bundeclared\b)"],
     "Tax evasion, avoidance and havens."),
    ("Trusts & foundations", [r"(?i:\b(?:discretionary|offshore|family|private|purpose|blind|asset protection) trusts?\b)", r"(?i:\btrustees?\b)", r"(?i:\bsettlors?\b)", r"(?i:\btrust protector\b)", r"(?i:\bprivate (?:interest )?foundation\b)", r"(?i:\bStiftung\b)"],
     "Trusts, foundations, settlors and protectors."),
    ("Due diligence & PEPs", [r"(?i:\bdue diligence\b)", r"\bKYC\b", r"(?i:\bknow your customer\b)", r"\bPEPs?\b", r"(?i:\bpolitically exposed\b)", r"(?i:\bcompliance department\b)"],
     "Know-your-customer checks and politically exposed persons."),
    ("Powers of attorney & signatories", [r"(?i:\bpower of attorney\b)", r"(?i:\bauthori[sz]ed signator)", r"(?i:\bsigning authority\b)"],
     "Who may act for an offshore company."),
    ("Real estate & luxury assets", [r"(?i:\breal estate\b)", r"(?i:\byachts?\b)", r"(?i:\bprivate jets?\b)", r"(?i:\bmansion)", r"(?i:\bartworks?\b)", r"(?i:\bpenthouse)"],
     "Property, yachts, jets and art held through offshore vehicles."),
    ("Backdating & document fraud", [r"(?i:\bbackdat)", r"(?i:\bforg(?:ed|ery)\b)", r"(?i:\bfalsif)"],
     "Backdated or falsified paperwork."),
]

"""
Government records pack: the U.S. government — agencies, committees and senior office-holders —
plus FOIA/declassification stamps and agency-of-origin rules, for declassified releases, FOIA
productions, court records and leaked government documents. Classification markings come from
the markings pack it requires.
"""
DESCRIPTION = "Government records: U.S. agencies and officials, FOIA/declassification stamps, agency-of-origin rules"

REQUIRES = ["markings"]

# Classification markings; OCR misreadings of them (SEGRET, SECKET, CONFIDENTLAL) never become codenames.
MARKING_WORDS = ["SECRET", "TOPSECRET", "CONFIDENTIAL", "UNCLASSIFIED", "CLASSIFIED", "DECLASSIFY", "NOFORN",
                 "ORCON", "RESTRICTED", "LIMDIS", "EXDIS", "NODIS"]

# FOIA and declassification stamps (classification banners are stripped by the markings pack)
STRIP_PATTERNS = [
    r"\(b\)\s?\(\d\)(?:\s?\([A-F]\))?",                                        # (b)(1), (b)(7)(C) exemption codes
    r"(?i)(?:Sanitized Copy )?Approved For Release\s*\d{4}/\d{2}/\d{2}\s*:?\s*CIA-RDP[\w\-]+",   # CIA CREST page stamps
    r"(?i)DECLASSIFIED\s+(?:Authority|Under Authority)\b[^\n]*",
]

# Originating agency from the letterhead ("top" = first 3,000 characters). Court captions (10) and the
# generic U.S.-government rule (60) live in the markings pack.
ORIGIN_RULES = [
    (40, r"CIA-RDP\d|CENTRAL INTELLIGENCE AGENCY|Central Intelligence Agency", "CIA (U.S.)", "top"),
    (41, r"FEDERAL BUREAU OF INVESTIGATION|Federal Bureau of Investigation|\bFD-302\b", "FBI (U.S.)", "top"),
    (42, r"\bAMEMBASSY\b|\bSECSTATE\b|DEPARTMENT OF STATE|Department of State", "State Department (U.S.)", "top"),
    (43, r"DEPARTMENT OF DEFENSE|Department of Defense|DEPARTMENT OF THE (?:ARMY|NAVY|AIR FORCE)|JOINT CHIEFS OF STAFF", "Defense (U.S.)", "top"),
    (44, r"Congressional Record|HOUSE OF REPRESENTATIVES|UNITED STATES SENATE|U\.S\. SENATE|SELECT COMMITTEE|PERMANENT SELECT COMMITTEE",
     "U.S. Congress", "top"),
    (45, r"THE WHITE HOUSE|NATIONAL SECURITY COUNCIL", "White House / NSC (U.S.)", "top"),
    (46, r"DEPARTMENT OF HOMELAND SECURITY|Department of Homeland Security", "DHS (U.S.)", "top"),
]

AGENCY = [
    ("NSA", ["National Security Agency", "NSA/CSS", "NSACSS"], "U.S. National Security Agency / Central Security Service: signals intelligence and information assurance."),
    ("CIA", ["Central Intelligence Agency", "Agency (CIA)"], "U.S. Central Intelligence Agency."),
    ("FBI", ["Federal Bureau of Investigation", "Bureau (FBI)"], "U.S. Federal Bureau of Investigation."),
    ("DEA", ["Drug Enforcement Administration"], "U.S. Drug Enforcement Administration."),
    ("DHS", ["Department of Homeland Security"], "U.S. Department of Homeland Security."),
    ("DIA", ["Defense Intelligence Agency"], "U.S. Defense Intelligence Agency."),
    ("NRO", ["National Reconnaissance Office"], "U.S. satellite reconnaissance agency."),
    ("NGA", ["National Geospatial-Intelligence Agency", "NIMA"], "U.S. geospatial intelligence agency."),
    ("ODNI", ["Office of the Director of National Intelligence", "Director of National Intelligence", "DNI"], "Office of the U.S. Director of National Intelligence."),
    ("NCTC", ["National Counterterrorism Center"], "U.S. National Counterterrorism Center."),
    ("U.S. Cyber Command", ["USCYBERCOM", "CYBERCOM", "Cyber Command"], "U.S. military command for cyberspace operations."),
    ("Department of Defense", ["DoD", "Department of Defense", "Pentagon", "Defense Department", "Office of the Secretary of Defense"], "U.S. Department of Defense."),
    ("Joint Chiefs of Staff", ["Joint Chiefs of Staff", "Joint Chiefs", "JCS", "Joint Staff"], "The senior uniformed leaders of the U.S. military."),
    ("Department of Justice", ["DoJ", "DOJ", "Justice Department", "Department of Justice"], "U.S. Department of Justice."),
    ("Office of Legal Counsel", ["Office of Legal Counsel", "OLC"], "Justice Department office that issues binding legal opinions for the executive branch."),
    ("State Department", ["Department of State", "State Department", "SECSTATE", "SecState"], "U.S. Department of State."),
    ("Treasury Department", ["Department of the Treasury", "Treasury Department", "U.S. Treasury"], "U.S. Department of the Treasury."),
    ("Department of Energy", ["Department of Energy", "DOE", "Energy Department"], "U.S. Department of Energy (including nuclear weapons labs)."),
    ("Department of Commerce", ["Department of Commerce", "Commerce Department"], "U.S. Department of Commerce."),
    ("White House", ["White House", "Executive Office of the President", "Oval Office"], "U.S. White House / Executive Office of the President."),
    ("National Security Council", ["National Security Council", "NSC"], "U.S. National Security Council."),
    ("FISA Court", ["FISC", "FISA Court", "Foreign Intelligence Surveillance Court", "FISCR", "FISA court"], "U.S. Foreign Intelligence Surveillance Court (and Court of Review)."),
    ("U.S. Supreme Court", ["Supreme Court of the United States", "U.S. Supreme Court", "SCOTUS"], "U.S. Supreme Court."),
    ("U.S. Congress", ["Congress", "U.S. Congress", "House of Representatives", "U.S. Senate", "United States Senate"], "U.S. Congress."),
    ("Senate Intelligence Committee", ["SSCI", "Senate Intelligence Committee", "Senate Select Committee on Intelligence"], "U.S. Senate Select Committee on Intelligence."),
    ("House Intelligence Committee", ["HPSCI", "House Intelligence Committee", "House Permanent Select Committee on Intelligence"], "U.S. House Permanent Select Committee on Intelligence."),
    ("Senate Judiciary Committee", ["Senate Judiciary Committee", "Senate Committee on the Judiciary"], "U.S. Senate Judiciary Committee."),
    ("House Oversight Committee", ["House Oversight Committee", "Committee on Oversight and Reform", "Committee on Oversight and Government Reform"], "U.S. House oversight committee."),
    ("Government Accountability Office", ["Government Accountability Office", "General Accounting Office", "GAO"], "Congress's audit and investigations agency."),
    ("Secret Service", ["Secret Service", "U.S. Secret Service", "USSS"], "U.S. Secret Service (protection of the President; financial crimes)."),
    ("ATF", ["Bureau of Alcohol, Tobacco, Firearms and Explosives", "Bureau of Alcohol, Tobacco and Firearms"], "U.S. Bureau of Alcohol, Tobacco, Firearms and Explosives."),
    ("ICE", ["Immigration and Customs Enforcement"], "U.S. Immigration and Customs Enforcement."),
    ("CBP", ["Customs and Border Protection", "Border Patrol"], "U.S. Customs and Border Protection."),
    ("TSA", ["Transportation Security Administration"], "U.S. Transportation Security Administration."),
    ("USAID", ["Agency for International Development", "U.S. Agency for International Development"], "U.S. Agency for International Development."),
    ("National Archives", ["National Archives", "NARA", "National Archives and Records Administration"], "U.S. National Archives and Records Administration."),
    ("U.S. Marshals", ["U.S. Marshals", "Marshals Service"], "U.S. Marshals Service."),
    ("IRS", ["Internal Revenue Service"], "U.S. Internal Revenue Service."),
    ("SEC", ["Securities and Exchange Commission"], "U.S. Securities and Exchange Commission."),
    ("FCC", ["Federal Communications Commission"], "U.S. Federal Communications Commission."),
    ("NASA", ["National Aeronautics and Space Administration"], "U.S. space agency."),
    ("CENTCOM", ["USCENTCOM", "Central Command", "CENTCOM"], "U.S. Central Command (Middle East, Central Asia)."),
    ("SOCOM / JSOC", ["SOCOM", "USSOCOM", "JSOC", "Joint Special Operations Command", "Special Operations Command"], "U.S. special operations commands."),
    ("AFRICOM", ["USAFRICOM", "Africa Command"], "U.S. Africa Command."),
]

PERSON = [
    # intelligence
    ("Allen Dulles", ["Allen Dulles", "Allen W. Dulles"], "Director of Central Intelligence 1953–1961; member of the Warren Commission."),
    ("John McCone", ["McCone"], "Director of Central Intelligence 1961–1965."),
    ("Richard Helms", ["Helms", "Richard Helms"], "Director of Central Intelligence 1966–1973."),
    ("William Colby", ["Colby", "William Colby"], "Director of Central Intelligence 1973–1976."),
    ("Stansfield Turner", ["Stansfield Turner"], "Director of Central Intelligence 1977–1981."),
    ("William Casey", ["William Casey", "Bill Casey"], "Director of Central Intelligence 1981–1987."),
    ("William Webster", ["William Webster", "William H. Webster"], "FBI Director 1978–1987; Director of Central Intelligence 1987–1991."),
    ("Robert Gates", ["Secretary Gates", "Robert Gates", "SecDef Gates", "Robert M. Gates"], "Director of Central Intelligence 1991–1993; U.S. Secretary of Defense 2006–2011."),
    ("James Woolsey", ["James Woolsey", "R. James Woolsey"], "Director of Central Intelligence 1993–1995."),
    ("John Deutch", ["John Deutch"], "Director of Central Intelligence 1995–1996."),
    ("George Tenet", ["George Tenet", "DCI Tenet", "Tenet"], "Director of Central Intelligence 1997–2004."),
    ("Porter Goss", ["Porter Goss"], "CIA Director 2004–2006."),
    ("Michael Hayden", ["General Hayden", "Gen. Hayden", "Michael V. Hayden", "Michael Hayden"], "Director of NSA 1999–2005; CIA Director 2006–2009."),
    ("Leon Panetta", ["Panetta"], "CIA Director 2009–2011; Secretary of Defense 2011–2013."),
    ("David Petraeus", ["Petraeus"], "U.S. Army general (Iraq, CENTCOM, Afghanistan); CIA Director 2011–2012."),
    ("John Brennan", ["Brennan", "John O. Brennan"], "CIA Director 2013–2017."),
    ("Gina Haspel", ["Haspel"], "CIA Director 2018–2021."),
    ("William Burns", ["William J. Burns", "Bill Burns"], "CIA Director 2021–2025; earlier Deputy Secretary of State."),
    ("John Ratcliffe", ["Ratcliffe"], "Director of National Intelligence 2020–2021; CIA Director from 2025."),
    ("Keith Alexander", ["General Alexander", "Gen. Alexander", "Keith B. Alexander", "Keith Alexander"], "Director of NSA 2005–2014; first commander of U.S. Cyber Command."),
    ("Paul Nakasone", ["Nakasone"], "Director of NSA and Commander of U.S. Cyber Command 2018–2024."),
    ("John Negroponte", ["Negroponte"], "First Director of National Intelligence 2005–2007."),
    ("Mike McConnell", ["Admiral McConnell", "J. Michael McConnell", "Mike McConnell"], "Director of NSA 1992–1996; DNI 2007–2009."),
    ("Dennis Blair", ["Admiral Blair", "Dennis Blair"], "Director of National Intelligence 2009–2010."),
    ("James Clapper", ["Clapper", "James R. Clapper"], "Director of National Intelligence 2010–2017."),
    ("Dan Coats", ["Dan Coats"], "Director of National Intelligence 2017–2019."),
    ("Avril Haines", ["Avril Haines"], "Director of National Intelligence 2021–2025."),
    ("Tulsi Gabbard", ["Tulsi Gabbard"], "Director of National Intelligence from 2025."),
    # FBI and Justice
    ("J. Edgar Hoover", ["J. Edgar Hoover", "Hoover", "John Edgar Hoover", "Director Hoover"], "FBI Director 1924–1972."),
    ("Clarence Kelley", ["Clarence Kelley", "Clarence M. Kelley"], "FBI Director 1973–1978."),
    ("Louis Freeh", ["Louis Freeh", "Freeh"], "FBI Director 1993–2001."),
    ("Robert Mueller", ["Mueller", "Robert S. Mueller", "Robert Mueller"], "FBI Director 2001–2013; Special Counsel investigating Russian election interference 2017–2019."),
    ("James Comey", ["Comey", "James Comey", "James B. Comey"], "FBI Director 2013–2017."),
    ("Christopher Wray", ["Christopher Wray"], "FBI Director 2017–2025."),
    ("Kash Patel", ["Kash Patel", "Kashyap Patel"], "FBI Director from 2025."),
    ("Robert F. Kennedy", ["Robert F. Kennedy", "Robert Kennedy", "Bobby Kennedy", "RFK"], "U.S. Attorney General 1961–1964; senator; assassinated in 1968."),
    ("John Mitchell", ["John N. Mitchell", "Attorney General Mitchell"], "U.S. Attorney General 1969–1972; convicted in the Watergate affair."),
    ("Janet Reno", ["Janet Reno"], "U.S. Attorney General 1993–2001."),
    ("John Ashcroft", ["Ashcroft"], "U.S. Attorney General 2001–2005."),
    ("Alberto Gonzales", ["Alberto Gonzales", "Gonzales"], "White House Counsel and U.S. Attorney General 2005–2007."),
    ("Eric Holder", ["Eric Holder", "Attorney General Holder", "Eric H. Holder"], "U.S. Attorney General 2009–2015."),
    ("Loretta Lynch", ["Loretta Lynch"], "U.S. Attorney General 2015–2017."),
    ("Jeff Sessions", ["Jeff Sessions"], "U.S. Attorney General 2017–2018."),
    ("William Barr", ["William Barr", "Bill Barr", "William P. Barr"], "U.S. Attorney General 1991–1993 and 2019–2020."),
    ("Merrick Garland", ["Merrick Garland"], "U.S. Attorney General 2021–2025."),
    ("Pam Bondi", ["Pam Bondi"], "U.S. Attorney General from 2025."),
    # State
    ("Dean Rusk", ["Dean Rusk"], "U.S. Secretary of State 1961–1969."),
    ("Cyrus Vance", ["Cyrus Vance"], "U.S. Secretary of State 1977–1980."),
    ("George Shultz", ["George Shultz", "George P. Shultz"], "U.S. Secretary of State 1982–1989."),
    ("James Baker", ["James Baker", "James A. Baker"], "U.S. Secretary of State 1989–1992."),
    ("Warren Christopher", ["Warren Christopher"], "U.S. Secretary of State 1993–1997."),
    ("Madeleine Albright", ["Madeleine Albright", "Albright"], "U.S. Secretary of State 1997–2001."),
    ("Colin Powell", ["Colin Powell", "Secretary Powell"], "U.S. Secretary of State 2001–2005; Chairman of the Joint Chiefs 1989–1993."),
    ("Condoleezza Rice", ["Condoleezza Rice", "Secretary Rice", "Dr. Rice", "Condi Rice"], "U.S. National Security Advisor 2001–2005 and Secretary of State 2005–2009."),
    ("Hillary Clinton", ["Hillary Clinton", "Secretary Clinton", "Hillary Rodham Clinton", "HRC"], "U.S. Secretary of State 2009–2013; senator; 2016 Democratic presidential nominee."),
    ("John Kerry", ["John Kerry", "Secretary Kerry"], "U.S. Secretary of State 2013–2017."),
    ("Rex Tillerson", ["Tillerson"], "U.S. Secretary of State 2017–2018."),
    ("Mike Pompeo", ["Pompeo"], "CIA Director 2017–2018; U.S. Secretary of State 2018–2021."),
    ("Antony Blinken", ["Blinken"], "U.S. Secretary of State 2021–2025."),
    ("Marco Rubio", ["Marco Rubio"], "U.S. Senator 2011–2025; Secretary of State from 2025."),
    # Defense and the National Security Council
    ("Robert McNamara", ["McNamara", "Robert S. McNamara"], "U.S. Secretary of Defense 1961–1968."),
    ("Caspar Weinberger", ["Weinberger"], "U.S. Secretary of Defense 1981–1987."),
    ("William Perry", ["William Perry", "William J. Perry"], "U.S. Secretary of Defense 1994–1997."),
    ("William Cohen", ["William Cohen", "William S. Cohen"], "U.S. Secretary of Defense 1997–2001."),
    ("Donald Rumsfeld", ["Rumsfeld"], "U.S. Secretary of Defense 1975–1977 and 2001–2006."),
    ("Chuck Hagel", ["Hagel"], "U.S. Secretary of Defense 2013–2015."),
    ("Ash Carter", ["Ash Carter", "Ashton Carter"], "U.S. Secretary of Defense 2015–2017."),
    ("Jim Mattis", ["Mattis"], "U.S. Secretary of Defense 2017–2019."),
    ("Mark Esper", ["Esper"], "U.S. Secretary of Defense 2019–2020."),
    ("Lloyd Austin", ["Lloyd Austin"], "U.S. Secretary of Defense 2021–2025."),
    ("Pete Hegseth", ["Hegseth"], "U.S. Secretary of Defense from 2025."),
    ("McGeorge Bundy", ["McGeorge Bundy"], "U.S. National Security Advisor 1961–1966."),
    ("Zbigniew Brzezinski", ["Brzezinski"], "U.S. National Security Advisor 1977–1981."),
    ("Brent Scowcroft", ["Scowcroft"], "U.S. National Security Advisor 1975–1977 and 1989–1993."),
    ("John Poindexter", ["Poindexter"], "U.S. National Security Advisor 1985–1986; central figure in Iran-Contra."),
    ("Oliver North", ["Oliver North", "Ollie North"], "NSC staff member at the center of the Iran-Contra affair."),
    ("Stephen Hadley", ["Hadley"], "U.S. National Security Advisor 2005–2009."),
    ("Susan Rice", ["Susan Rice"], "U.S. Ambassador to the UN 2009–2013; National Security Advisor 2013–2017."),
    ("Michael Flynn", ["Michael Flynn", "Mike Flynn"], "Director of the DIA 2012–2014; National Security Advisor in 2017."),
    ("H. R. McMaster", ["McMaster", "H.R. McMaster", "H. R. McMaster"], "U.S. National Security Advisor 2017–2018."),
    ("John Bolton", ["Bolton", "John Bolton"], "U.S. Ambassador to the UN 2005–2006; National Security Advisor 2018–2019."),
    ("Jake Sullivan", ["Jake Sullivan"], "U.S. National Security Advisor 2021–2025."),
    # Congress (intelligence oversight)
    ("Frank Church", ["Frank Church", "Senator Church"], "U.S. Senator who chaired the 1975–1976 Church Committee on intelligence abuses."),
    ("Dianne Feinstein", ["Feinstein"], "U.S. Senator 1992–2023; chaired the Senate Intelligence Committee 2009–2015."),
    ("Ron Wyden", ["Wyden"], "U.S. Senator; member of the Senate Intelligence Committee."),
]

ENTITIES = {"person": PERSON, "agency": AGENCY}

IDEAS = [
    ("FOIA & declassification", [r"\bFOIA\b", r"\bFreedom of Information\b", r"(?i:\bdeclassif)", r"(?i:\bredact)", r"(?i:\bwithheld in (?:full|part)\b)", r"(?i:\bexempt(?:ion)?s? \(?b\)?)"],
     "Freedom of Information requests, redaction and declassification."),
    ("Congressional oversight", [r"(?i:\bhearing\b)", r"(?i:\bsubpoena)", r"(?i:\btestimony\b)", r"(?i:\btestified\b)", r"(?i:\boversight committee)", r"(?i:\bcongressional (?:inquiry|investigation|notification))"],
     "Hearings, subpoenas, testimony and congressional investigations."),
    ("Covert action", [r"(?i:\bcovert action)", r"(?i:\bcovert operation)", r"(?i:\bclandestine)", r"(?i:\bplausible deniability\b)", r"(?i:\bpresidential finding\b)"],
     "Covert and clandestine operations."),
    ("Whistleblowers & leaks", [r"(?i:\bwhistle-?blow)", r"(?i:\bleak(?:ed|s|er|ers|ing)?\b)", r"(?i:\bunauthori[sz]ed disclosure)", r"(?i:\bmedia leaks?\b)"],
     "Leaks, leakers and whistleblowers."),
]

"""
SIGINT / Five Eyes surveillance pack (built for the Snowden archive).

Curated people, agencies, companies, programs, technologies and places from the published
Snowden documents, plus surveillance themes, codename stop-words and the document conventions
of NSA/GCHQ material (SIDtoday "Run Date" lines, Five Eyes origin markings, news-org file names).
Descriptions reflect public reporting on the documents.

Each entry: (canonical name, [aliases...], description)
 - Aliases that are ALL CAPS or contain a digit are matched case-sensitively
   (acronyms / codenames); everything else is matched case-insensitively only when
   it is a multi-word phrase, and case-sensitively for single words (so "Turkey"
   matches but "turkey" does not).
 - The canonical name is always an alias as well.
"""
import re

DESCRIPTION = "Five Eyes signals intelligence and surveillance (Snowden archive)"
REQUIRES = ["markings"]

PERSON = [
    ("Edward Snowden", ["Snowden", "Edward J. Snowden", "Ed Snowden", "Snowden Edward"], "Former NSA contractor (Booz Allen Hamilton, Dell) who provided the archive to journalists in 2013."),
    ("Keith Alexander", ["General Alexander", "Gen. Alexander", "Gen Alexander", "GEN Alexander", "Keith B. Alexander", "LTG Alexander", "Director Alexander", "DIRNSA Alexander"], "Director of NSA and Chief of CSS 2005-2014; first commander of U.S. Cyber Command."),
    ("Michael Hayden", ["General Hayden", "Gen. Hayden", "Gen Hayden", "Lt Gen Hayden", "Michael V. Hayden", "Hayden"], "Director of NSA 1999-2005; later CIA Director. Oversaw the post-9/11 STELLARWIND program."),
    ("James Clapper", ["Clapper", "James R. Clapper"], "U.S. Director of National Intelligence 2010-2017."),
    ("Chris Inglis", ["Inglis", "John C. Inglis", "John Inglis"], "NSA Deputy Director 2006-2014."),
    ("Richard Ledgett", ["Ledgett", "Rick Ledgett"], "Led NSA's Media Leaks Task Force; NSA Deputy Director 2014-2017."),
    ("Michael Rogers (Admiral)", ["Admiral Rogers", "ADM Rogers", "Michael S. Rogers"], "Director of NSA 2014-2018."),
    ("Mike McConnell", ["Admiral McConnell", "J. Michael McConnell", "Mike McConnell"], "Director of NSA 1992-1996; DNI 2007-2009."),
    ("Dennis Blair", ["Admiral Blair", "Dennis Blair"], "Director of National Intelligence 2009-2010."),
    ("John Negroponte", ["Negroponte"], "First Director of National Intelligence 2005-2007."),
    ("George Tenet", ["George Tenet", "DCI Tenet", "Tenet"], "Director of Central Intelligence 1996-2004."),
    ("John Brennan", ["Brennan"], "CIA Director 2013-2017; earlier White House counterterrorism adviser."),
    ("David Petraeus", ["Petraeus"], "U.S. Army general (Iraq/CENTCOM/Afghanistan); CIA Director 2011-2012."),
    ("Robert Mueller", ["Mueller", "Robert S. Mueller"], "FBI Director 2001-2013."),
    ("Barack Obama", ["Obama", "President Obama"], "U.S. President 2009-2017."),
    ("George W. Bush", ["President Bush", "George W. Bush", "Bush administration", "George Bush"], "U.S. President 2001-2009; authorized STELLARWIND."),
    ("Dick Cheney", ["Cheney", "Vice President Cheney"], "U.S. Vice President 2001-2009."),
    ("Donald Rumsfeld", ["Rumsfeld"], "U.S. Secretary of Defense 2001-2006."),
    ("Robert Gates", ["Secretary Gates", "Robert Gates", "SecDef Gates"], "U.S. Secretary of Defense 2006-2011."),
    ("Leon Panetta", ["Panetta"], "CIA Director 2009-2011; Secretary of Defense 2011-2013."),
    ("Condoleezza Rice", ["Condoleezza Rice", "Secretary Rice", "Dr. Rice", "Condi Rice"], "U.S. National Security Advisor and Secretary of State."),
    ("Colin Powell", ["Colin Powell", "Secretary Powell"], "U.S. Secretary of State 2001-2005."),
    ("Hillary Clinton", ["Hillary Clinton", "Secretary Clinton", "Hillary Rodham Clinton"], "U.S. Secretary of State 2009-2013."),
    ("Eric Holder", ["Eric Holder", "Attorney General Holder", "Eric H. Holder"], "U.S. Attorney General 2009-2015."),
    ("Alberto Gonzales", ["Alberto Gonzales", "Gonzales"], "White House Counsel and U.S. Attorney General 2005-2007."),
    ("John Ashcroft", ["Ashcroft"], "U.S. Attorney General 2001-2005."),
    ("Dianne Feinstein", ["Feinstein"], "U.S. Senator; chair of the Senate Intelligence Committee 2009-2015."),
    ("Ron Wyden", ["Wyden"], "U.S. Senator; critic of bulk surveillance programs."),
    ("Angela Merkel", ["Merkel", "Chancellor Merkel"], "German Chancellor 2005-2021; her mobile phone was reportedly targeted by NSA."),
    ("Gerhard Schröder", ["Schröder", "Schroeder", "Gerhard Schroeder"], "German Chancellor 1998-2005."),
    ("Ronald Pofalla", ["Pofalla"], "German Chancellery chief of staff who oversaw intelligence services."),
    ("Gerhard Schindler", ["Schindler", "Gerhard Schindler"], "President of the BND 2011-2016."),
    ("Dilma Rousseff", ["Rousseff", "Dilma"], "President of Brazil 2011-2016; reportedly targeted by NSA."),
    ("Enrique Peña Nieto", ["Peña Nieto", "Pena Nieto"], "President of Mexico 2012-2018; communications reportedly read as a candidate."),
    ("Felipe Calderón", ["Calderón", "Calderon"], "President of Mexico 2006-2012; email reportedly accessed."),
    ("Vladimir Putin", ["Putin"], "President/Prime Minister of Russia."),
    ("Dmitry Medvedev", ["Medvedev"], "President of Russia 2008-2012."),
    ("Hu Jintao", ["Hu Jintao"], "President of China 2003-2013."),
    ("Xi Jinping", ["Xi Jinping"], "President of China since 2013."),
    ("Mahmoud Ahmadinejad", ["Ahmadinejad", "Ahmadinezhad"], "President of Iran 2005-2013."),
    ("Ali Khamenei", ["Khamenei"], "Supreme Leader of Iran."),
    ("Benjamin Netanyahu", ["Netanyahu"], "Prime Minister of Israel."),
    ("Ehud Olmert", ["Olmert"], "Prime Minister of Israel 2006-2009."),
    ("Ehud Barak", ["Ehud Barak"], "Israeli Prime Minister and Defense Minister."),
    ("Saddam Hussein", ["Saddam"], "President of Iraq until 2003."),
    ("Bashar al-Assad", ["Bashar al-Assad", "Assad"], "President of Syria."),
    ("Muammar Qaddafi", ["Qaddafi", "Qadhafi", "Gaddafi", "Gadhafi"], "Leader of Libya until 2011."),
    ("Hosni Mubarak", ["Mubarak"], "President of Egypt until 2011."),
    ("Mohamed Morsi", ["Morsi", "Mursi"], "President of Egypt 2012-2013."),
    ("Recep Tayyip Erdoğan", ["Erdogan", "Erdoğan"], "Prime Minister then President of Turkey."),
    ("Nouri al-Maliki", ["Maliki"], "Prime Minister of Iraq 2006-2014."),
    ("Hamid Karzai", ["Karzai"], "President of Afghanistan 2004-2014."),
    ("Pervez Musharraf", ["Musharraf"], "President of Pakistan 2001-2008."),
    ("Asif Ali Zardari", ["Zardari"], "President of Pakistan 2008-2013."),
    ("Kim Jong Il", ["Kim Jong Il", "Kim Jong-il"], "Leader of North Korea until 2011."),
    ("Kim Jong Un", ["Kim Jong Un", "Kim Jong-un"], "Leader of North Korea since 2011."),
    ("Hugo Chávez", ["Chavez", "Chávez"], "President of Venezuela 1999-2013."),
    ("Ban Ki-moon", ["Ban Ki-moon", "Ban Ki-Moon", "Ban Ki Moon"], "UN Secretary-General 2007-2016."),
    ("Tony Blair", ["Tony Blair"], "UK Prime Minister 1997-2007."),
    ("Gordon Brown", ["Gordon Brown"], "UK Prime Minister 2007-2010."),
    ("David Cameron", ["David Cameron"], "UK Prime Minister 2010-2016."),
    ("Nicolas Sarkozy", ["Sarkozy"], "President of France 2007-2012."),
    ("Silvio Berlusconi", ["Berlusconi"], "Prime Minister of Italy."),
    ("Susilo Bambang Yudhoyono", ["Yudhoyono"], "President of Indonesia 2004-2014; his phone was reportedly targeted by Australia's DSD."),
    ("Meles Zenawi", ["Meles Zenawi", "Meles"], "Prime Minister of Ethiopia until 2012."),
    ("Osama bin Laden", ["bin Laden", "Bin Laden", "Usama bin Laden", "Bin Ladin", "bin Ladin", "UBL"], "Founder of al-Qaida; killed in Abbottabad, Pakistan in May 2011."),
    ("Ayman al-Zawahiri", ["Zawahiri", "Zawahri"], "al-Qaida deputy, later leader."),
    ("Abu Musab al-Zarqawi", ["Zarqawi"], "Leader of al-Qaida in Iraq; killed 2006."),
    ("Anwar al-Awlaki", ["Awlaki", "Aulaqi"], "U.S.-born AQAP cleric killed in a 2011 drone strike."),
    ("Khalid Sheikh Mohammed", ["Khalid Sheikh Mohammed", "Khalid Shaykh Muhammad"], "Alleged architect of the 9/11 attacks."),
    ("Abu Bakr al-Baghdadi", ["Baghdadi"], "Leader of ISIS/ISIL."),
    ("Hassan Nasrallah", ["Nasrallah"], "Secretary-General of Hezbollah."),
    ("Ahmad Muaffaq Zaidan", ["Zaidan"], "Al Jazeera Islamabad bureau chief who appeared in an NSA SKYNET slide flagged as a courier-like pattern."),
    ("Glenn Greenwald", ["Greenwald"], "Journalist who received the archive and co-founded The Intercept."),
    ("Laura Poitras", ["Poitras"], "Filmmaker/journalist who received the archive (Citizenfour)."),
    ("Barton Gellman", ["Gellman"], "Washington Post journalist who reported on the archive."),
    ("Julian Assange", ["Assange"], "WikiLeaks founder."),
    ("Chelsea Manning", ["Bradley Manning", "Chelsea Manning", "PFC Manning"], "Army analyst who leaked documents to WikiLeaks in 2010."),
    ("Ladar Levison", ["Levison", "Ladar Levison", "Ladar Levinson", "Levinson"], "Founder of Lavabit, the encrypted email service Snowden used; shut it down rather than hand over keys."),
    ("Iain Lobban", ["Lobban"], "Director of GCHQ 2008-2014."),
    ("Ingvar Åkesson", ["Akesson", "Åkesson"], "Director General of Sweden's FRA."),
    ("John D. Bates", ["Judge Bates", "John D. Bates"], "FISC presiding judge who found NSA upstream collection unconstitutional in 2011."),
    ("Reggie Walton", ["Judge Walton", "Reggie B. Walton"], "FISC judge who criticized NSA phone-records compliance failures in 2009."),
    ("Colleen Kollar-Kotelly", ["Kollar-Kotelly"], "FISC judge who authorized internet metadata collection in 2004."),
    ("Leonie Brinkema", ["Brinkema"], "U.S. District Judge in Lavabit-related proceedings."),
    ("Claude Hilton", ["Judge Hilton", "Claude M. Hilton"], "U.S. District Judge who ordered Lavabit to provide its SSL keys."),
    ("William Binney", ["Binney"], "Former NSA technical director turned whistleblower."),
    ("Thomas Drake", ["Thomas Drake"], "Former NSA official prosecuted after disclosing waste to a reporter."),
    ("Mark Klein", ["Mark Klein"], "Former AT&T technician who exposed NSA fiber splitting in San Francisco (Room 641A)."),
]

AGENCY = [
    ("NSA", ["National Security Agency", "NSA/CSS", "NSACSS"], "U.S. National Security Agency / Central Security Service: signals intelligence and information assurance."),
    ("GCHQ", ["Government Communications Headquarters"], "UK signals intelligence agency (Cheltenham)."),
    ("CSEC", ["CSE", "Communications Security Establishment"], "Canada's signals intelligence agency (CSEC, renamed CSE)."),
    ("ASD/DSD", ["ASD", "DSD", "Australian Signals Directorate", "Defence Signals Directorate"], "Australia's signals intelligence agency (DSD, renamed ASD in 2013)."),
    ("GCSB", ["Government Communications Security Bureau"], "New Zealand's signals intelligence agency."),
    ("Five Eyes", ["FVEY", "5-Eyes", "5 Eyes", "UKUSA", "Second Parties", "Second Party"], "The UKUSA signals intelligence alliance: USA, UK, Canada, Australia, New Zealand."),
    ("BND", ["Bundesnachrichtendienst"], "Germany's foreign intelligence service; a close NSA 'Third Party' partner."),
    ("BfV", ["Bundesamt für Verfassungsschutz"], "Germany's domestic intelligence agency."),
    ("FRA", ["Försvarets radioanstalt", "National Defence Radio Establishment"], "Sweden's signals intelligence agency; partners with NSA and GCHQ."),
    ("DGSE", ["Direction Générale de la Sécurité Extérieure"], "France's foreign intelligence service."),
    ("ISNU (Unit 8200)", ["ISNU", "Israeli SIGINT National Unit", "Unit 8200"], "Israel's signals intelligence unit; shares raw SIGINT with NSA."),
    ("Danish DDIS", ["DDIS", "Danish Defence Intelligence Service"], "Denmark's defence intelligence service."),
    ("AIVD/MIVD", ["AIVD", "MIVD"], "Dutch intelligence and security services."),
    ("CIA", ["Central Intelligence Agency"], "U.S. Central Intelligence Agency."),
    ("FBI", ["Federal Bureau of Investigation"], "U.S. Federal Bureau of Investigation."),
    ("DEA", ["Drug Enforcement Administration"], "U.S. Drug Enforcement Administration."),
    ("DHS", ["Department of Homeland Security"], "U.S. Department of Homeland Security."),
    ("DIA", ["Defense Intelligence Agency"], "U.S. Defense Intelligence Agency."),
    ("NRO", ["National Reconnaissance Office"], "U.S. satellite reconnaissance agency."),
    ("NGA", ["National Geospatial-Intelligence Agency", "NIMA"], "U.S. geospatial intelligence agency."),
    ("ODNI", ["Office of the Director of National Intelligence", "Director of National Intelligence"], "Office of the U.S. Director of National Intelligence."),
    ("NCTC", ["National Counterterrorism Center"], "U.S. National Counterterrorism Center."),
    ("U.S. Cyber Command", ["USCYBERCOM", "CYBERCOM", "Cyber Command"], "U.S. military command for cyberspace operations, dual-hatted with NSA's director."),
    ("Department of Defense", ["DoD", "Department of Defense", "Pentagon"], "U.S. Department of Defense."),
    ("Department of Justice", ["DoJ", "DOJ", "Justice Department", "Department of Justice"], "U.S. Department of Justice."),
    ("State Department", ["Department of State", "State Department"], "U.S. Department of State."),
    ("Treasury Department", ["Department of the Treasury", "Treasury Department"], "U.S. Department of the Treasury."),
    ("White House", ["National Security Council"], "U.S. White House / National Security Council."),
    ("FISA Court", ["FISC", "FISA Court", "Foreign Intelligence Surveillance Court", "FISCR", "FISA court"], "U.S. Foreign Intelligence Surveillance Court (and Court of Review)."),
    ("U.S. Congress", ["Congress", "HPSCI", "SSCI", "House Intelligence Committee", "Senate Intelligence Committee", "House Permanent Select Committee on Intelligence", "Senate Select Committee on Intelligence"], "U.S. Congress and its intelligence oversight committees."),
    ("MI5", ["MI5"], "UK Security Service (domestic)."),
    ("MI6", ["MI6", "Secret Intelligence Service"], "UK Secret Intelligence Service (foreign)."),
    ("SIGINT Directorate (SID)", ["SID", "Signals Intelligence Directorate", "SIGINT Directorate"], "NSA's largest division, which publishes the SIDtoday newsletter."),
    ("TAO", ["Tailored Access Operations", "S32"], "NSA's elite hacking unit (Tailored Access Operations)."),
    ("SSO", ["Special Source Operations"], "NSA's Special Source Operations: collection via corporate partnerships and cable access."),
    ("JTRIG", ["Joint Threat Research Intelligence Group"], "GCHQ unit for online covert action, deception and 'effects' operations."),
    ("NTOC", ["NSA/CSS Threat Operations Center", "NTOC"], "NSA's cyber threat operations center."),
    ("Special Collection Service", ["Special Collection Service", "F6"], "Joint NSA/CIA unit operating covert collection sites in embassies."),
    ("Information Assurance Directorate", ["IAD", "Information Assurance Directorate"], "NSA's defensive (information security) arm."),
    ("CENTCOM", ["USCENTCOM", "Central Command"], "U.S. Central Command (Middle East, Central Asia)."),
    ("SOCOM / JSOC", ["SOCOM", "USSOCOM", "JSOC", "Joint Special Operations Command", "Special Operations Command"], "U.S. special operations commands."),
    ("AFRICOM", ["USAFRICOM"], "U.S. Africa Command."),
    ("Ethiopian INSA", ["INSA", "Information Network Security Agency"], "Ethiopia's Information Network Security Agency, an NSA partner."),
    ("Saudi Ministry of Interior", ["Ministry of Interior", "MOI"], "Saudi Arabian Ministry of Interior, a growing NSA partner per a 2013 memo."),
    ("Pakistani ISI", ["Inter-Services Intelligence"], "Pakistan's Inter-Services Intelligence."),
    ("FSB / SVR / GRU", ["FSB", "SVR", "GRU"], "Russian intelligence services."),
    ("Chinese MSS / PLA", ["Ministry of State Security", "PLA", "People's Liberation Army"], "Chinese state security and military."),
    ("IRGC", ["Islamic Revolutionary Guard Corps", "Revolutionary Guard"], "Iran's Islamic Revolutionary Guard Corps."),
    ("Mossad", ["Mossad"], "Israel's foreign intelligence service."),
]

ORGANIZATION = [
    ("United Nations", ["UN", "U.N.", "United Nations", "UNSC", "Security Council", "UN Security Council"], "The United Nations, including the Security Council."),
    ("IAEA", ["International Atomic Energy Agency"], "International Atomic Energy Agency."),
    ("NATO", ["North Atlantic Treaty Organization"], "North Atlantic Treaty Organization."),
    ("European Union", ["EU", "European Union", "European Commission", "European Parliament"], "European Union institutions."),
    ("G8 / G20", ["G8", "G20", "G-8", "G-20"], "Group of Eight / Group of Twenty summits."),
    ("OPEC", ["Organization of the Petroleum Exporting Countries"], "Organization of the Petroleum Exporting Countries."),
    ("GSMA", ["GSM Association", "GSMA"], "Mobile operators' trade body whose IR.21 roaming documents NSA collected (AURORAGOLD)."),
    ("World Bank / IMF", ["World Bank", "IMF", "International Monetary Fund"], "International financial institutions."),
    ("Interpol", ["INTERPOL", "Interpol"], "International Criminal Police Organization."),
    ("UN Climate Conference", ["UNFCCC", "climate change conference", "Climate Change Conference", "COP15", "COP-15"], "UN climate change negotiations (Copenhagen 2009, Cancun 2010)."),
    ("al-Qaida", ["al-Qa'ida", "al-Qaida", "al Qaida", "al-Qaeda", "al Qaeda", "Al Qaeda", "Al-Qaeda", "Al-Qa'ida", "AQ"], "Jihadist network founded by Osama bin Laden."),
    ("AQAP", ["al-Qa'ida in the Arabian Peninsula", "al-Qaeda in the Arabian Peninsula"], "al-Qaida in the Arabian Peninsula (Yemen)."),
    ("AQIM", ["al-Qa'ida in the Islamic Maghreb"], "al-Qaida in the Islamic Maghreb."),
    ("al-Shabaab", ["al-Shabaab", "al-Shabab", "Al-Shabaab", "al Shabaab"], "Somali jihadist group."),
    ("Taliban", ["Taliban", "Taleban"], "Afghan/Pakistani Taliban."),
    ("Hezbollah", ["Hizballah", "Hezbollah", "Hizbollah"], "Lebanese Shia militant group/party."),
    ("Hamas", ["HAMAS", "Hamas"], "Palestinian Islamist movement."),
    ("ISIS / ISIL", ["ISIL", "ISIS", "Islamic State"], "Islamic State."),
    ("Lashkar-e-Taiba", ["Lashkar-e-Tayyiba", "Lashkar-e-Taiba", "LeT"], "Pakistan-based militant group."),
    ("Haqqani Network", ["Haqqani"], "Afghan/Pakistani militant network."),
    ("FARC", ["FARC"], "Revolutionary Armed Forces of Colombia."),
    ("PKK", ["PKK", "Kurdistan Workers' Party"], "Kurdistan Workers' Party."),
    ("Muslim Brotherhood", ["Muslim Brotherhood"], "Islamist movement, Egypt and region."),
    ("Anonymous / hacktivists", ["Anonymous", "LulzSec", "hacktivist", "hacktivists"], "Hacktivist collectives targeted by GCHQ's JTRIG."),
    ("WikiLeaks", ["Wikileaks", "WikiLeaks"], "Publisher of leaked documents."),
    ("ACLU / EFF", ["ACLU", "American Civil Liberties Union", "EFF", "Electronic Frontier Foundation"], "Civil liberties organizations involved in surveillance litigation."),
    ("Al Jazeera", ["Al Jazeera", "Al-Jazeera", "Aljazeera"], "Qatar-based broadcaster whose internal communications NSA reportedly accessed."),
    ("Tor Project", ["Tor Project"], "Nonprofit that develops the Tor anonymity network."),
]

COMPANY = [
    ("Google", ["Gmail", "Google", "GMail"], "Internet company; PRISM provider; data-center links tapped under MUSCULAR."),
    ("Yahoo", ["Yahoo!", "Yahoo", "YAHOO"], "Internet company; PRISM provider; challenged FAA in the FISC (2008); webcam images collected via OPTIC NERVE."),
    ("Microsoft", ["Microsoft", "Hotmail", "Outlook.com", "MSN", "Windows Live", "SkyDrive"], "PRISM's first provider (2007)."),
    ("Skype", ["Skype"], "VoIP service (Microsoft from 2011); added to PRISM in 2011."),
    ("Facebook", ["Facebook"], "Social network; PRISM provider."),
    ("Apple", ["Apple"], "PRISM provider (2012); iPhone targeted by NSA/GCHQ tools."),
    ("AOL", ["AOL"], "PRISM provider."),
    ("PalTalk", ["PalTalk", "Paltalk"], "Chat service; PRISM provider."),
    ("YouTube", ["YouTube", "Youtube"], "Video service; PRISM provider; monitored by GCHQ."),
    ("Twitter", ["Twitter"], "Social network."),
    ("LinkedIn", ["LinkedIn", "Linkedin"], "Professional network; fake pages used in GCHQ's attack on Belgacom."),
    ("Dropbox", ["Dropbox"], "Cloud storage service slated to join PRISM."),
    ("Verizon", ["Verizon", "MCI"], "U.S. telecom; FISC order for all call records (2013); linked to STORMBREW."),
    ("AT&T", ["AT&T", "ATT"], "U.S. telecom; reported as the FAIRVIEW partner."),
    ("Sprint", ["Sprint"], "U.S. telecom."),
    ("BT", ["British Telecom", "BT"], "UK telecom; reported GCHQ cable partner."),
    ("Vodafone / Cable & Wireless", ["Vodafone", "Cable & Wireless", "Cable and Wireless", "Gerontic", "GERONTIC"], "Telecoms; Cable & Wireless (codename GERONTIC) reported as a key GCHQ cable partner."),
    ("Level 3", ["Level 3", "Level3"], "Backbone carrier reported as a GCHQ partner (LITTLE)."),
    ("Global Crossing", ["Global Crossing"], "Backbone carrier."),
    ("Belgacom", ["Belgacom", "BICS"], "Belgian telecom hacked by GCHQ (Operation SOCIALIST)."),
    ("Gemalto", ["Gemalto"], "SIM card maker whose encryption keys were targeted by GCHQ/NSA."),
    ("Huawei", ["Huawei", "HUAWEI"], "Chinese telecom equipment maker hacked by NSA (SHOTGIANT)."),
    ("ZTE", ["ZTE"], "Chinese telecom equipment maker."),
    ("Cisco", ["Cisco", "CISCO"], "Network equipment maker; routers intercepted and implanted (supply-chain interdiction)."),
    ("Juniper", ["Juniper"], "Network equipment maker; firewalls targeted by TAO implants."),
    ("Kaspersky", ["Kaspersky", "Kaspersky Lab"], "Russian antivirus vendor; GCHQ/NSA studied its software; exposed the Equation Group."),
    ("Antivirus vendors", ["Avast", "AVG", "F-Secure", "Symantec", "McAfee", "Bitdefender", "ESET", "Check Point"], "Security companies examined under Project CAMBERDADA and others."),
    ("Mozilla / Firefox", ["Mozilla", "Firefox"], "Browser targeted by EGOTISTICALGIRAFFE to de-anonymize Tor users."),
    ("Amazon", ["Amazon"], "E-commerce and cloud company."),
    ("Akamai", ["Akamai"], "Content delivery network."),
    ("Rovio / Angry Birds", ["Angry Birds", "Rovio"], "Mobile game whose data leaks were exploited ('leaky apps')."),
    ("BlackBerry", ["BlackBerry", "Blackberry", "RIM", "Research In Motion"], "Smartphone maker; BlackBerry traffic decoded by NSA/GCHQ."),
    ("Nokia", ["Nokia"], "Phone maker."),
    ("Samsung", ["Samsung"], "Phone maker."),
    ("Ericsson", ["Ericsson"], "Telecom equipment maker."),
    ("Alcatel", ["Alcatel", "Alcatel-Lucent"], "Telecom equipment maker; subject of GCHQ/French targeting doc."),
    ("Orange / France Télécom", ["Orange", "France Telecom", "France Télécom", "Wanadoo"], "French telecom."),
    ("Telefónica", ["Telefonica", "Telefónica"], "Spanish telecom."),
    ("Deutsche Telekom", ["Deutsche Telekom", "T-Mobile", "Netcologne"], "German telecoms targeted in TREASUREMAP planning."),
    ("Stellar / Cetel / IABG", ["Stellar", "Cetel", "IABG"], "German satellite/teleport firms whose networks GCHQ mapped."),
    ("Telstra / Optus / Singtel", ["Telstra", "Optus", "Singtel", "SingTel"], "Asia-Pacific telecoms."),
    ("Telenor / TeliaSonera", ["Telenor", "TeliaSonera", "Telia"], "Nordic telecoms."),
    ("Thuraya / Inmarsat / Iridium", ["Thuraya", "Inmarsat", "INMARSAT", "Iridium", "Intelsat", "INTELSAT"], "Satellite communications providers."),
    ("Petrobras", ["Petrobras"], "Brazilian state oil company targeted by NSA."),
    ("SWIFT", ["SWIFT"], "Interbank messaging network monitored by NSA."),
    ("Visa / MasterCard", ["Visa", "VISA", "MasterCard", "Mastercard"], "Payment networks monitored by NSA 'Follow the Money'."),
    ("Booz Allen Hamilton", ["Booz Allen", "Booz Allen Hamilton", "BAH"], "Defense contractor; Snowden's employer at NSA Hawaii."),
    ("Dell", ["Dell"], "Computer maker; earlier Snowden employer; servers targeted by DEITYBOUNCE."),
    ("SAIC / Lockheed / defense contractors", ["SAIC", "Lockheed Martin", "Lockheed", "Northrop Grumman", "Raytheon", "Boeing", "General Dynamics", "Harris Corporation"], "Defense/intelligence contractors."),
    ("Lavabit", ["Lavabit"], "Encrypted email service used by Snowden; shut down in 2013 after a government demand for its SSL keys."),
    ("UC Browser (Alibaba)", ["UC Web", "UCWeb", "UC Browser"], "Chinese mobile browser whose data leaks Five Eyes agencies exploited."),
    ("Chinese internet firms", ["Baidu", "Tencent", "Alibaba", "Sina", "QQ"], "Chinese internet companies."),
    ("Russian internet firms", ["Yandex", "Mail.ru", "VKontakte"], "Russian internet companies."),
    ("Hushmail / encrypted mail", ["Hushmail", "Riseup", "Tutanota", "Proton"], "Encrypted email services."),
    ("Pacnet", ["Pacnet", "PACNET"], "Asia-Pacific cable operator."),
    ("Siemens", ["Siemens"], "German conglomerate."),
    ("Aeroflot / airlines", ["Aeroflot", "Air France", "Lufthansa", "Emirates"], "Airlines (in-flight GSM collection docs)."),
    ("Mitsubishi / Japanese firms", ["Mitsubishi", "Toshiba", "Fujitsu", "NEC"], "Japanese companies."),
]

PROGRAM = [
    ("PRISM", ["PRISM", "US-984XN", "SIGAD US-984XN"], "Collection of stored communications from U.S. internet companies under FAA Section 702 ('downstream')."),
    ("Upstream", ["Upstream", "UPSTREAM"], "Collection from internet backbone cables with U.S. telecom help (FAIRVIEW, STORMBREW, BLARNEY, OAKSTAR)."),
    ("XKEYSCORE", ["XKEYSCORE", "X-KEYSCORE", "KEYSCORE", "XKeyscore", "XKeyScore", "Xkeyscore", "XKS"], "Distributed system for searching and analysing global internet traffic captured at collection sites."),
    ("MUSCULAR", ["MUSCULAR"], "NSA/GCHQ tapping of private links between Google and Yahoo data centers outside the U.S."),
    ("TEMPORA", ["TEMPORA", "Tempora"], "GCHQ buffering of full-take internet traffic from transatlantic cables."),
    ("BULLRUN", ["BULLRUN", "Bullrun"], "NSA program to defeat encryption via cryptanalysis, influence over standards, and covert access."),
    ("EDGEHILL", ["EDGEHILL", "Edgehill"], "GCHQ counterpart to BULLRUN."),
    ("BOUNDLESSINFORMANT", ["BOUNDLESSINFORMANT", "BOUNDLESS INFORMANT", "Boundless Informant", "BOUNDLESS-INFORMANT"], "NSA tool that counts and maps metadata collection by country and source."),
    ("STELLARWIND", ["STELLARWIND", "STLW", "President's Surveillance Program", "PSP"], "Post-9/11 warrantless surveillance program authorized by President Bush."),
    ("FAIRVIEW", ["FAIRVIEW", "Fairview"], "SSO corporate partnership for cable access, reported to be with AT&T."),
    ("STORMBREW", ["STORMBREW", "Stormbrew"], "SSO corporate partnership for cable access, reported to be with Verizon."),
    ("BLARNEY", ["BLARNEY", "Blarney"], "Long-running SSO partnership collecting under FISA authorities."),
    ("OAKSTAR", ["OAKSTAR", "Oakstar"], "SSO umbrella for corporate partnerships with access outside the U.S."),
    ("MYSTIC", ["MYSTIC"], "Program collecting phone metadata and audio of entire countries."),
    ("SOMALGET", ["SOMALGET"], "MYSTIC component recording full-take audio of every mobile call in a country (e.g. the Bahamas)."),
    ("DISHFIRE", ["DISHFIRE", "Dishfire"], "Database of hundreds of millions of collected SMS text messages."),
    ("CO-TRAVELER", ["CO-TRAVELER", "CO-TRAVELLER", "COTRAVELER", "co-traveler", "Co-Traveler"], "Analytics that find associates by correlating mobile phone locations."),
    ("FASCIA", ["FASCIA"], "Database of mobile phone location records."),
    ("OPTIC NERVE", ["OPTIC NERVE", "OPTICNERVE", "Optic Nerve"], "GCHQ collection of still images from Yahoo webcam chats."),
    ("QUANTUM", ["QUANTUM", "QUANTUMINSERT", "QUANTUM INSERT", "QUANTUMTHEORY", "QUANTUMHAND", "QUANTUMBOT", "QUANTUMCOPPER", "QUANTUMSQUIRREL", "QUANTUMNATION", "QUANTUMDNS", "QUANTUMSKY", "QUANTUMSMACKDOWN", "QUANTUMCOOKIE", "QUANTUMSPIM"], "'Man-on-the-side' packet injection used to redirect targets to exploit servers."),
    ("FOXACID", ["FOXACID", "FoxAcid"], "NSA exploit servers that deliver malware to targeted browsers."),
    ("TURBINE", ["TURBINE"], "Automated command-and-control system for managing large numbers of implants."),
    ("TURMOIL", ["TURMOIL"], "Passive collection sensors that detect targets for QUANTUM attacks."),
    ("TREASUREMAP", ["TREASUREMAP", "TREASURE MAP", "Treasure Map"], "Effort to build a near-real-time map of the global internet."),
    ("AURORAGOLD", ["AURORAGOLD"], "Monitoring of mobile operators' internal documents to find weaknesses in networks worldwide."),
    ("ICREACH", ["ICREACH"], "Google-like search engine sharing metadata with ~two dozen U.S. agencies."),
    ("SKYNET", ["SKYNET"], "Machine-learning analysis of Pakistani mobile metadata to flag suspected couriers."),
    ("EGOTISTICALGIRAFFE", ["EGOTISTICALGIRAFFE", "EGOTISTICAL GIRAFFE"], "Firefox exploit used to de-anonymize Tor Browser users."),
    ("HACIENDA", ["HACIENDA"], "Port-scanning of entire countries to find vulnerable services."),
    ("SHOTGIANT", ["SHOTGIANT"], "Operation to penetrate Huawei's networks."),
    ("Operation SOCIALIST", ["SOCIALIST", "Op Socialist", "Operation Socialist"], "GCHQ hack of Belgian telecom Belgacom."),
    ("DAPINO GAMMA", ["DAPINO GAMMA", "DAPINOGAMMA"], "GCHQ operation to steal SIM card encryption keys from Gemalto."),
    ("CAMBERDADA", ["CAMBERDADA"], "Project monitoring email to antivirus companies for new malware reports."),
    ("LOVELY HORSE", ["LOVELY HORSE", "LOVELYHORSE"], "GCHQ monitoring of security researchers and hackers on social media."),
    ("ANT catalog", ["ANT", "ANT catalog", "ANT Product Data"], "NSA TAO catalog of hardware and software implants."),
    ("DROPOUTJEEP", ["DROPOUTJEEP"], "ANT implant for the iPhone."),
    ("COTTONMOUTH", ["COTTONMOUTH", "COTTONMOUTH-I", "COTTONMOUTH-II", "COTTONMOUTH-III"], "ANT USB hardware implants."),
    ("DEITYBOUNCE", ["DEITYBOUNCE"], "ANT BIOS implant for Dell PowerEdge servers."),
    ("IRATEMONK", ["IRATEMONK"], "ANT implant hiding in hard-drive firmware."),
    ("FEEDTROUGH", ["FEEDTROUGH"], "ANT persistence implant for Juniper firewalls."),
    ("HEADWATER", ["HEADWATER"], "ANT backdoor for Huawei routers."),
    ("JETPLOW", ["JETPLOW"], "ANT firmware implant for Cisco PIX/ASA firewalls."),
    ("NIGHTSTAND", ["NIGHTSTAND"], "ANT wireless exploitation device."),
    ("RAGEMASTER", ["RAGEMASTER", "ANGRYNEIGHBOR"], "ANT radar retro-reflector (ANGRYNEIGHBOR family) capturing VGA video."),
    ("GENIE", ["GENIE"], "NSA's umbrella budget line for computer network exploitation."),
    ("PINWALE", ["PINWALE"], "NSA database of collected internet content."),
    ("MARINA", ["MARINA"], "NSA repository for internet metadata."),
    ("MAINWAY", ["MAINWAY"], "NSA repository for telephony metadata (contact chaining)."),
    ("NUCLEON", ["NUCLEON"], "NSA database of intercepted voice content."),
    ("TRAFFICTHIEF", ["TRAFFICTHIEF"], "NSA metadata database fed by XKEYSCORE."),
    ("WINDSTOP", ["WINDSTOP"], "Collection programs run with Second Party partners (including MUSCULAR and INCENSER)."),
    ("INCENSER", ["INCENSER"], "WINDSTOP access reportedly via GCHQ's partnership with Cable & Wireless."),
    ("RAMPART-A", ["RAMPART-A", "RAMPART", "RAMPART-T", "RAMPART-M", "RAMPART-I"], "Partnerships with foreign (Third Party) countries for cable access."),
    ("APPARITION / GHOSTHUNTER", ["APPARITION", "GHOSTHUNTER", "Apparition", "Ghosthunter"], "Menwith Hill programs to geolocate internet users via VSAT satellite links."),
    ("ECHELON", ["ECHELON", "Echelon"], "Five Eyes satellite-communications interception network (FORNSAT)."),
    ("HOMING PIGEON / THIEVING MAGPIE", ["HOMING PIGEON", "HOMINGPIGEON", "THIEVING MAGPIE", "THIEVINGMAGPIE"], "Interception of in-flight mobile phone use on airliners."),
    ("CRISSCROSS / PROTON", ["CRISSCROSS", "PROTON"], "CIA-run metadata system shared with other agencies; precursor to ICREACH."),
    ("SENTRY EAGLE", ["SENTRY EAGLE", "SENTRYEAGLE", "Core Secrets"], "NSA 'core secrets', including relationships with industry and covert operatives."),
    ("ORANGECRUSH / ORANGEBLOSSOM", ["ORANGECRUSH", "ORANGEBLOSSOM"], "FAIRVIEW-related third-party accesses."),
    ("SILVERZEPHYR", ["SILVERZEPHYR"], "FAIRVIEW access to Latin American traffic."),
    ("MONKEYROCKET", ["MONKEYROCKET"], "Covert access via a non-Western partner/product offering anonymization services."),
    ("TARMAC", ["TARMAC"], "Menwith Hill satellite collection initiative."),
    ("HIMR", ["HIMR", "Heilbronn Institute"], "GCHQ-funded Heilbronn Institute for Mathematical Research."),
    ("Section 702 (FAA)", ["Section 702", "FAA 702", "FAA702", "FISA Amendments Act", "FAA"], "Statute authorizing warrantless targeting of foreigners abroad, including PRISM and Upstream."),
    ("Section 215 (bulk phone records)", ["Section 215", "Business Records", "BR FISA", "Patriot Act"], "Patriot Act authority used for bulk collection of U.S. phone records."),
    ("EO 12333", ["EO 12333", "E.O. 12333", "Executive Order 12333", "12333"], "Executive order governing most NSA collection abroad."),
    ("USSID 18", ["USSID 18", "USSID SP0018", "USSID-18", "USSID18", "SP0018"], "NSA's core directive on protecting U.S. persons' privacy."),
    ("Parallel construction", ["parallel construction", "Parallel Construction", "Special Operations Division", "SOD"], "Practice of recreating evidence trails to conceal intelligence sources in criminal cases."),
]

TECHNOLOGY = [
    ("Tor", ["Tor", "TOR", "The Onion Router", "onion router"], "Anonymity network targeted by NSA and GCHQ."),
    ("VPN", ["VPN", "VPNs", "virtual private network"], "Virtual private networks; NSA sought to decrypt VPN traffic."),
    ("SSL/TLS/HTTPS", ["SSL", "TLS", "HTTPS", "SSL/TLS"], "Web encryption protocols targeted by BULLRUN and related efforts."),
    ("IPsec / PPTP / SSH", ["IPsec", "IPSec", "PPTP", "SSH"], "Encrypted tunnelling and remote-login protocols."),
    ("PGP / GPG", ["PGP", "GPG", "GnuPG"], "Email encryption software."),
    ("Encryption", ["encryption", "decryption", "cryptanalysis", "encrypted", "crypto"], "Encryption and cryptanalysis in general."),
    ("GSM / mobile networks", ["GSM", "GPRS", "UMTS", "LTE", "3G", "4G", "CDMA", "SS7", "mobile network", "mobile networks", "cellular network"], "Mobile phone networks and protocols."),
    ("SIM cards / IMSI", ["SIM card", "SIM cards", "IMSI", "IMEI", "MSISDN", "Ki "], "SIM cards and mobile identifiers."),
    ("SMS / text messages", ["SMS", "text messages", "MMS"], "Text messages."),
    ("VoIP", ["VoIP", "VOIP"], "Voice over IP."),
    ("Satellite (VSAT / FORNSAT)", ["VSAT", "FORNSAT", "satellite", "satellites", "SATCOM", "Satellite"], "Satellite communications and their interception."),
    ("Undersea / fiber-optic cables", ["undersea cable", "submarine cable", "fiber optic", "fibre optic", "fiber-optic", "fibre-optic", "cable", "cables"], "Fiber-optic and undersea cable infrastructure."),
    ("iPhone / iOS", ["iPhone", "iPhones", "iOS", "iPad"], "Apple mobile devices."),
    ("Android", ["Android"], "Google's mobile operating system."),
    ("Smartphones", ["smartphone", "smartphones", "Smartphone", "Smartphones"], "Smartphones in general."),
    ("Windows", ["Windows", "Microsoft Windows"], "Microsoft Windows."),
    ("Linux / Unix", ["Linux", "Unix", "UNIX"], "Linux/Unix systems."),
    ("Mac OS X", ["Mac OS X", "MacOS", "macOS", "OS X"], "Apple desktop OS."),
    ("BIOS / firmware", ["BIOS", "firmware", "Firmware", "UEFI"], "Low-level firmware targeted for persistent implants."),
    ("Routers / firewalls", ["router", "routers", "Router", "Routers", "firewall", "firewalls", "Firewall", "switches"], "Network infrastructure devices."),
    ("Webcams", ["webcam", "webcams", "Webcam"], "Webcams."),
    ("Cookies / user agents", ["cookie", "cookies", "user agent", "user-agent", "User-Agent", "user agents"], "Browser identifiers used for tracking and targeting."),
    ("IP addresses / DNS / BGP", ["IP address", "IP addresses", "DNS", "BGP"], "Internet addressing and routing."),
    ("Email", ["email", "e-mail", "webmail", "Email", "E-mail"], "Email."),
    ("Instant messaging / chat", ["instant messaging", "chat", "XMPP", "Jabber", "IRC", "Yahoo Messenger", "MSN Messenger"], "Chat and instant messaging."),
    ("Social networks", ["social network", "social networks", "social networking", "social media"], "Social networking services."),
    ("Malware / implants", ["malware", "implant", "implants", "Implant", "trojan", "keylogger", "rootkit", "botnet", "botnets"], "Malicious software and implants."),
    ("Exploits / zero-days", ["exploit", "exploits", "zero-day", "0-day", "vulnerability", "vulnerabilities"], "Software exploits and vulnerabilities."),
    ("Machine learning / big data", ["machine learning", "Machine Learning", "big data", "Big Data", "Hadoop", "cloud analytics", "data mining", "random forest", "classifier"], "Machine learning and large-scale analytics."),
    ("Cloud computing", ["cloud", "Cloud", "the cloud"], "Cloud computing."),
    ("Speech / language technology", ["speech recognition", "speech-to-text", "Human Language Technology", "HLT", "machine translation", "keyword spotting", "voice recognition", "speaker identification"], "Speech-to-text, translation and language technology."),
    ("Side-channel / hardware attacks", ["power analysis", "side-channel", "side channel", "TEMPEST", "de-processing", "DPA"], "Physical and side-channel attacks on chips and devices."),
    ("TPM / secure hardware", ["TPM", "Trusted Platform Module", "smart card", "smartcard"], "Trusted hardware and smart cards."),
    ("Wi-Fi / Bluetooth", ["Wi-Fi", "WiFi", "wifi", "802.11", "Bluetooth", "WLAN"], "Wireless local networking."),
    ("Bitcoin / cryptocurrency", ["Bitcoin", "bitcoin"], "Cryptocurrency."),
    ("Radar / radio", ["radar", "Radar", "HF", "VHF", "UHF", "microwave"], "Radio and radar signals."),
]

PLACE = [
    ("United States", ["United States", "U.S.", "USA", "America"], ""), ("United Kingdom", ["United Kingdom", "U.K.", "UK", "Britain", "England", "Scotland"], ""),
    ("Canada", ["Canada"], ""), ("Australia", ["Australia"], ""), ("New Zealand", ["New Zealand"], ""),
    ("Germany", ["Germany", "Federal Republic of Germany"], ""), ("France", ["France"], ""), ("Italy", ["Italy"], ""), ("Spain", ["Spain"], ""),
    ("Netherlands", ["Netherlands", "Holland"], ""), ("Belgium", ["Belgium"], ""), ("Sweden", ["Sweden"], ""), ("Norway", ["Norway"], ""),
    ("Denmark", ["Denmark"], ""), ("Finland", ["Finland"], ""), ("Austria", ["Austria"], ""), ("Switzerland", ["Switzerland"], ""),
    ("Poland", ["Poland"], ""), ("Czech Republic", ["Czech Republic"], ""), ("Hungary", ["Hungary"], ""), ("Romania", ["Romania"], ""),
    ("Greece", ["Greece"], ""), ("Cyprus", ["Cyprus"], ""), ("Turkey", ["Turkey"], ""), ("Ireland", ["Ireland"], ""), ("Portugal", ["Portugal"], ""),
    ("Croatia", ["Croatia"], ""), ("Serbia", ["Serbia"], ""), ("Kosovo", ["Kosovo"], ""), ("Bosnia", ["Bosnia"], ""), ("Ukraine", ["Ukraine"], ""),
    ("Belarus", ["Belarus"], ""), ("Georgia (country)", ["Republic of Georgia", "Tbilisi"], ""), ("Armenia", ["Armenia"], ""), ("Azerbaijan", ["Azerbaijan"], ""),
    ("Estonia", ["Estonia"], ""), ("Latvia", ["Latvia"], ""), ("Lithuania", ["Lithuania"], ""), ("Iceland", ["Iceland"], ""),
    ("Russia", ["Russia", "Russian Federation", "USSR", "Soviet Union"], ""), ("China", ["China", "PRC", "People's Republic of China"], ""),
    ("Taiwan", ["Taiwan"], ""), ("Hong Kong", ["Hong Kong"], ""), ("Japan", ["Japan"], ""), ("South Korea", ["South Korea", "ROK", "Republic of Korea"], ""),
    ("North Korea", ["North Korea", "DPRK"], ""), ("India", ["India"], ""), ("Pakistan", ["Pakistan"], ""), ("Afghanistan", ["Afghanistan"], ""),
    ("Bangladesh", ["Bangladesh"], ""), ("Sri Lanka", ["Sri Lanka"], ""), ("Nepal", ["Nepal"], ""),
    ("Iran", ["Iran"], ""), ("Iraq", ["Iraq"], ""), ("Syria", ["Syria"], ""), ("Lebanon", ["Lebanon"], ""), ("Israel", ["Israel"], ""),
    ("Palestinian territories", ["Gaza", "West Bank", "Palestinian Authority", "Palestine"], ""), ("Jordan", ["Jordan"], ""),
    ("Saudi Arabia", ["Saudi Arabia", "KSA"], ""), ("Yemen", ["Yemen"], ""), ("Oman", ["Oman"], ""), ("United Arab Emirates", ["UAE", "United Arab Emirates", "Dubai", "Abu Dhabi"], ""),
    ("Qatar", ["Qatar"], ""), ("Kuwait", ["Kuwait"], ""), ("Bahrain", ["Bahrain"], ""),
    ("Egypt", ["Egypt"], ""), ("Libya", ["Libya"], ""), ("Tunisia", ["Tunisia"], ""), ("Algeria", ["Algeria"], ""), ("Morocco", ["Morocco"], ""),
    ("Sudan", ["Sudan", "South Sudan"], ""), ("Ethiopia", ["Ethiopia"], ""), ("Eritrea", ["Eritrea"], ""), ("Somalia", ["Somalia"], ""),
    ("Kenya", ["Kenya"], ""), ("Uganda", ["Uganda"], ""), ("Nigeria", ["Nigeria"], ""), ("Mali", ["Mali"], ""), ("Niger", ["Niger"], ""),
    ("South Africa", ["South Africa"], ""), ("Democratic Republic of the Congo", ["Congo", "DRC"], ""), ("Djibouti", ["Djibouti"], ""),
    ("Indonesia", ["Indonesia"], ""), ("Malaysia", ["Malaysia"], ""), ("Singapore", ["Singapore"], ""), ("Thailand", ["Thailand"], ""),
    ("Philippines", ["Philippines"], ""), ("Vietnam", ["Vietnam"], ""), ("Burma", ["Burma", "Myanmar"], ""), ("Cambodia", ["Cambodia"], ""),
    ("Fiji / Pacific islands", ["Fiji", "Solomon Islands", "Tonga", "Samoa", "Vanuatu", "Nauru", "Tuvalu", "Kiribati", "New Caledonia", "Papua New Guinea"], ""),
    ("Kazakhstan", ["Kazakhstan"], ""), ("Uzbekistan", ["Uzbekistan"], ""), ("Turkmenistan", ["Turkmenistan"], ""), ("Kyrgyzstan", ["Kyrgyzstan"], ""), ("Tajikistan", ["Tajikistan"], ""),
    ("Mexico", ["Mexico"], ""), ("Brazil", ["Brazil", "Brasil"], ""), ("Argentina", ["Argentina"], ""), ("Chile", ["Chile"], ""),
    ("Colombia", ["Colombia"], ""), ("Venezuela", ["Venezuela"], ""), ("Ecuador", ["Ecuador"], ""), ("Peru", ["Peru"], ""), ("Bolivia", ["Bolivia"], ""),
    ("Cuba", ["Cuba"], ""), ("Haiti", ["Haiti"], ""), ("Bahamas", ["Bahamas"], ""), ("Guatemala", ["Guatemala"], ""), ("Honduras", ["Honduras"], ""),
    ("El Salvador", ["El Salvador"], ""), ("Nicaragua", ["Nicaragua"], ""), ("Panama", ["Panama"], ""), ("Costa Rica", ["Costa Rica"], ""),
    ("Fort Meade", ["Fort Meade", "Ft. Meade", "Ft Meade"], "NSA headquarters, Maryland."),
    ("Menwith Hill", ["Menwith Hill", "MHS", "RAF Menwith Hill"], "NSA-run surveillance base in North Yorkshire, UK."),
    ("Pine Gap", ["Pine Gap", "Alice Springs"], "Joint U.S.-Australian satellite ground station."),
    ("Bad Aibling", ["Bad Aibling"], "Former NSA station in Bavaria transferred to BND."),
    ("Bude", ["Bude", "GCHQ Bude", "CSOC"], "GCHQ satellite and cable interception station in Cornwall."),
    ("Cheltenham", ["Cheltenham"], "GCHQ headquarters."),
    ("NSA Hawaii (Kunia)", ["Kunia", "KRSOC", "NSA Hawaii", "Hawaii"], "NSA regional operations center where Snowden worked."),
    ("NSA Georgia", ["GRSOC", "NSA Georgia", "Fort Gordon"], "NSA regional operations center in Georgia, U.S."),
    ("NSA Texas", ["MRSOC", "NSA Texas", "Lackland"], "NSA regional operations center in Texas."),
    ("Guantanamo", ["Guantanamo", "GTMO"], "U.S. detention facility in Cuba."),
    ("Washington, D.C.", ["Washington, D.C.", "Washington DC", "Washington, DC"], ""), ("New York", ["New York", "NYC"], ""),
    ("Berlin", ["Berlin"], ""), ("Frankfurt", ["Frankfurt"], ""), ("Brussels", ["Brussels"], ""), ("Geneva", ["Geneva"], ""), ("Vienna", ["Vienna"], ""),
    ("Copenhagen", ["Copenhagen"], ""), ("Cancun", ["Cancun", "Cancún"], ""), ("Toronto", ["Toronto"], ""), ("London", ["London"], ""),
    ("Baghdad", ["Baghdad"], ""), ("Kabul", ["Kabul"], ""), ("Islamabad", ["Islamabad"], ""), ("Abbottabad", ["Abbottabad"], ""),
    ("Tehran", ["Tehran"], ""), ("Moscow", ["Moscow"], ""), ("Beijing", ["Beijing"], ""), ("Pyongyang", ["Pyongyang"], ""),
    ("Riyadh", ["Riyadh"], ""), ("Sanaa", ["Sanaa", "Sana'a"], ""), ("Mogadishu", ["Mogadishu"], ""), ("Addis Ababa", ["Addis Ababa"], ""),
    ("Waziristan / FATA", ["Waziristan", "FATA", "Tribal Areas"], ""), ("Helmand / Kandahar", ["Helmand", "Kandahar"], ""),
    ("Middle East", ["Middle East", "Mideast"], ""), ("Latin America", ["Latin America", "South America", "Central America"], ""),
    ("Horn of Africa", ["Horn of Africa"], ""), ("Persian Gulf", ["Persian Gulf", "Arabian Gulf"], ""), ("Balkans", ["Balkans"], ""), ("Caucasus", ["Caucasus"], ""),
]

# Themes ("ideas") are matched with regexes; a document is tagged when it has >= MIN_IDEA_HITS hits.
IDEAS = [
    ("Bulk / 'collect it all'", [r"\bbulk collection\b", r"\bcollect(?:ing)? it all\b", r"\bfull[- ]take\b", r"\bbulk (?:data|access|metadata|records)\b", r"\bsniff it all\b", r"\bexploit it all\b"],
     "Collecting everything rather than targeting."),
    ("Metadata & contact chaining", [r"\bmetadata\b", r"\bcontact[- ]chain", r"\bcall detail records?\b", r"\bCDRs?\b", r"\bDNR\b", r"\bpattern[- ]of[- ]life\b"],
     "Who-talks-to-whom data, call records and chaining."),
    ("Defeating encryption", [r"\bcryptanaly", r"\bdecrypt", r"\bbreak(?:ing)? (?:the )?encrypt", r"\bencryption keys?\b", r"\bbackdoor", r"\bweaken(?:ed|ing)? (?:the )?(?:standard|encrypt)"],
     "Cryptanalysis, key theft, backdoors and standards influence."),
    ("Legal authorities (FISA/702/12333)", [r"\bFISA\b", r"\bSection 702\b", r"\bFAA\b", r"\b12333\b", r"\bSection 215\b", r"\bcourt order", r"\bwarrant", r"\bRIPA\b", r"\bcertification"],
     "The legal basis for collection."),
    ("Privacy & U.S. persons", [r"\bU\.?S\.? persons?\b", r"\bminimiz", r"\bprivacy\b", r"\bcivil libert", r"\bFourth Amendment\b", r"\bUSSID ?(?:SP)?0?018\b"],
     "Protections for Americans' communications and privacy."),
    ("Compliance violations & oversight", [r"\bviolat", r"\bnon-?compliance\b", r"\bover-?collect", r"\bincident", r"\bInspector General\b", r"\bIG\b", r"\boversight\b", r"\bunauthori[sz]ed\b"],
     "Rule-breaking, overcollection, IG reviews and oversight."),
    ("Counterterrorism", [r"\bterroris", r"\bcounterterror", r"\bCT\b", r"\bjihad", r"\bextremis", r"\bsuicide bomb"],
     "Counterterrorism targeting."),
    ("Offensive hacking (CNE/CNA)", [r"\bCNE\b", r"\bCNA\b", r"\bcomputer network exploitation\b", r"\bcomputer network attack\b", r"\bimplant", r"\bexploit", r"\bhack"],
     "Computer network exploitation and attack."),
    ("Cyber defense", [r"\bcyber ?defen[cs]e\b", r"\bnetwork defen[cs]e\b", r"\bintrusion", r"\binformation assurance\b", r"\bcounter-?CNE\b", r"\bfourth[- ]party\b"],
     "Defending networks, fourth-party collection, counter-CNE."),
    ("Diplomatic targeting", [r"\bembass", r"\bdiplomat", r"\bconsulate", r"\bsummit\b", r"\bnegotiat", r"\bforeign minist", r"\bhead of state\b", r"\bleaders?hip communications\b"],
     "Spying on governments, diplomats, summits and negotiations."),
    ("Economic & financial intelligence", [r"\beconomic\b", r"\bfinancial\b", r"\btrade\b", r"\boil\b", r"\benergy\b", r"\bbanks?\b", r"\bFollow the Money\b", r"\bcommercial\b"],
     "Economic, energy and financial targeting."),
    ("Partner sharing & liaison", [r"\bThird Part(?:y|ies)\b", r"\bSecond Part(?:y|ies)\b", r"\bpartner(?:s|ship)?\b", r"\bliaison\b", r"\bburden[- ]sharing\b", r"\bSUSLO\b"],
     "Relationships with foreign intelligence partners."),
    ("Corporate cooperation", [r"\bcorporate partner", r"\bcommercial partner", r"\bprovider", r"\bindustry partner", r"\bcompelled\b", r"\bcooperat\w* compan"],
     "Help from telecoms and tech companies, voluntary or compelled."),
    ("Covert influence & deception", [r"\bdeception\b", r"\binfluence operation", r"\bpropaganda\b", r"\bdiscredit", r"\bhoney ?trap", r"\bonline covert action\b", r"\bEffects\b", r"\bmanipulat"],
     "Online covert action, deception and propaganda."),
    ("Information overload", [r"\binformation overload\b", r"\bdata deluge\b", r"\bdrowning\b", r"\btoo much data\b", r"\boverload", r"\bvolume of (?:data|traffic|collection)"],
     "Analysts overwhelmed by the volume of collected data."),
    ("Location tracking", [r"\bgeolocat", r"\blocation data\b", r"\bcell(?:ular)? tower", r"\bGPS\b", r"\btracking\b", r"\bco-?travel"],
     "Tracking where people are."),
    ("Military operations & targeted killing", [r"\bkinetic\b", r"\bdrone", r"\bairstrike", r"\bstrike\b", r"\bHVT\b", r"\bhigh[- ]value target", r"\bfind,? fix", r"\bcapture/kill\b", r"\bkilled\b", r"\bIED"],
     "SIGINT support to military operations and strikes."),
    ("Leaks & insider threat", [r"\bleak", r"\bunauthori[sz]ed disclosure", r"\binsider threat", r"\bmedia leaks?\b", r"\bwhistleblow"],
     "Leaks, insider threats and unauthorized disclosures."),
    ("Anonymity & privacy tools", [r"\bTor\b", r"\banonymi[sz]", r"\bVPN", r"\bproxy\b", r"\bproxies\b", r"\bPGP\b", r"\bencrypted (?:chat|email|messag)"],
     "Users' tools for anonymity and private communication."),
    ("Mobile phone exploitation", [r"\bsmartphone", r"\biPhone", r"\bAndroid\b", r"\bBlackBerry\b", r"\bmobile (?:phone|device|app)", r"\bapps?\b", r"\bSIM\b"],
     "Exploiting phones and mobile apps."),
    ("Supply-chain interdiction", [r"\binterdict", r"\bsupply[- ]chain\b", r"\bshipment", r"\bhardware implant"],
     "Intercepting and implanting hardware in transit."),
    ("Automation, analytics & ML", [r"\bmachine learning\b", r"\bautomat", r"\balgorithm", r"\banalytic", r"\bbig data\b", r"\bclassifier\b"],
     "Automated analytics and machine learning."),
    ("Language & translation", [r"\blinguist", r"\btranslat", r"\blanguage analyst", r"\bArabic\b", r"\bPashto\b", r"\bFarsi\b", r"\bDari\b", r"\bUrdu\b", r"\bMandarin\b"],
     "Linguists, language skills and translation."),
    ("Workforce & culture", [r"\bmorale\b", r"\bworkforce\b", r"\bpromotion", r"\bcareer", r"\btraining\b", r"\bmentor", r"\bhiring\b", r"\bdiversity\b"],
     "NSA workplace life, careers and culture (SIDtoday)."),
]
MIN_IDEA_HITS = 3


ENTITIES = {
    "person": PERSON,
    "agency": AGENCY,
    "organization": ORGANIZATION,
    "company": COMPANY,
    "program": PROGRAM,
    "technology": TECHNOLOGY,
    "place": PLACE,
}

# Tokens that look like codenames but are boilerplate, org codes, ranks, units, etc.
CODENAME_STOP = set("""
SECRET TOPSECRET DERIVED DYNAMIC HIGHEST POSSIBLE DATED DECLASSIFY NOFORN ORCON COMINT UNCLASSIFIED CONFIDENTIAL
UMBRA STRAP STRAP1 STRAP2 STRAP3 OFFICIAL PROFORMA SIGINT HUMINT ELINT FISINT IMINT MASINT GEOINT OSINT ACINT RADINT
OPELINT SIGDEV COMSEC OPSEC SINIO DIRNSA USSID SIGAD CONOP OPLAN CONPLAN CENTCOM EUCOM PACOM SOCOM INSCOM STRATCOM
SOUTHCOM NORTHCOM USSTRATCOM USSOCOM USSOUTHCOM USCENTCOM MARSOC USPACOM USEUCOM USNORTHCOM USAREUR AFSOC USASOC
PACAF NAVCENT SPACECOM TRANSCOM USTRANSCOM JFCOM SACEUR NORAD COCOM CONUS OCONUS SECDEF POTUS HPSCI JWICS NOIWON
DARPA IARPA GRSOC MRSOC KRSOC NCEUR NCPAC SUSLO SUSLOL SUSLAK SUSLAG SUSLOC SUSLOO SUSLOW SUSLAJ SUSLAI SUSLAT
CANSLO CANSLOW MSISDN C4ISR VBIED SCADA UNSCR UNICEF MINUSTAH USCYBERCOM CYBERCOM NSACSS DEFSMAC NASIC JIATF CJTF
APATS CFIOG NSCID NDIST DOCID IDOCID CALEA AFRICOM USAFRICOM SATCOM TACREP CRITIC CRITICOMM EGRAM ESECS SISECT
TEDNE JITF MNFI JDFPG TSPMO NMJIC CTMMC PDDNI ADDNI CHCSS SIGDASYS NZSIS COMEXT NSIAPS JICPAC JIEDDO CJSOTF NCOIC
NACSI NCNAR WATCHCON DOCEX SPCMA OHESS EXDIR NSACC SIDCI LAWUL APSTARS SIRVES ATCAE NTOC FVEY UKUSA GCHQ CSEC GCSB
FBI CIA DEA DHS NRO NGA DIA ODNI NCTC SID TAO SSO JTRIG FISC FISCR NSA BND DGSE ISNU AIVD MIVD FSB SVR GRU IRGC
ISAF NATO OPEC IAEA GSMA SWIFT VISA HUAWEI CISCO YAHOO INMARSAT INTELSAT PACNET INTERPOL HAMAS
ANNEX APPENDIX ATTACHMENT ENCLOSURE EXHIBIT SUBJECT SUMMARY BACKGROUND DISCUSSION RECOMMENDATION RECOMMENDATIONS
INTRODUCTION OVERVIEW CONCLUSION CONCLUSIONS OBJECTIVES OBJECTIVE QUESTIONS CONTACT CONTACTS TABLE CONTENTS AGENDA
MEMORANDUM ORDER OPINION COURT UNITED STATES DISTRICT AMERICA FOREIGN INTELLIGENCE SURVEILLANCE DEPARTMENT JUSTICE
REDACTED REDACTION CLASSIFIED UNCLASSIFIEDIIFOR UNCLASSIFIEDIIFOUO FOUO UFOUO NOTE NOTES IMPORTANT WARNING DRAFT FINAL
PAGE PAGES WORKING COPY SOURCE SOURCES TARGET TARGETS ANALYST ANALYSTS ANALYSIS REPORT REPORTS REPORTING PRODUCT
NETWORK NETWORKS ACCESS ACCESSES COLLECTION SYSTEM SYSTEMS PROGRAM PROGRAMS PROJECT PROJECTS MISSION MISSIONS
OFFICE BRANCH DIVISION DIRECTORATE GROUP GROUPS TEAM TEAMS CENTER CENTRE AGENCY STAFF CHIEF DEPUTY DIRECTOR
JANUARY FEBRUARY MARCH APRIL JUNE JULY AUGUST SEPTEMBER OCTOBER NOVEMBER DECEMBER MONDAY TUESDAY WEDNESDAY
THURSDAY FRIDAY SATURDAY SUNDAY
TOUSA PROPIN RELIDO DISTRJCT KHTML BSSID ISAKMP SDRAM MSNBC TAKEAWAYS TOPTOP ABCDEF DNVAG TESTE NOCON SSEUR DIRFA
EREPO DISES NOFORNI ORCONI IMCON HTTPS HTTP HTML JPEG ASCII UNICODE WINDOWS LINUX ORACLE EXCEL ADOBE INTEL INFOSEC
""".split())

# Classification markings and frequent OCR misreadings of them; tokens within edit distance 1-2 are dropped.
MARKING_WORDS = ["SECRET", "TOPSECRET", "COMINT", "NOFORN", "ORCON", "GCHQ", "NSACSS", "NSACSSM", "UNCLASSIFIED",
                 "PROPIN", "RELIDO", "NOCONTRACT", "CONFIDENTIAL", "CLASSIFIED", "DECLASSIFY"]


# --------------------------------------------------------------------------- document conventions

# Originating agency from markings. Lower priority numbers are tested first (court captions = 10,
# generic U.S. government = 60 live in the government pack).
ORIGIN_RULES = [
    (20, r"STRAP\s?[123]|UK\s+TOP\s+SECRET|UK\s+SECRET|UK\s+EYES\s+ONLY|Freedom of Information Act 2000", "GCHQ (UK)"),
    (21, r"CANADIAN\s+EYES\s+ONLY|\bCEO\b|Communications Security Establishment", "CSEC (Canada)"),
    (22, r"AUSTEO|AUSTRALIAN\s+EYES\s+ONLY", "ASD/DSD (Australia)"),
    (23, r"NZEO|GCSB", "GCSB (New Zealand)", "head", r"NSA/CSS"),
    (24, r"(?i)sidtoday", "NSA (U.S.)", "path"),
    (24, r"NSA/CSS|NSA/CSSM|SIDtoday|SID today|\bNSA\b", "NSA (U.S.)"),
]

_RUN_DATE = re.compile(r"Run Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})")


def run_date(text, relpath, corpus):
    """SIDtoday articles carry an exact 'Run Date: MM/DD/YYYY' line."""
    m = _RUN_DATE.search(text)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if corpus.dates["min_year"] <= y <= corpus.dates["max_year"] and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}", "run date"
    return None


DATE_HINTS = [(10, run_date)]


def published_date(relpath):
    """Publication date encoded in news-org filenames, e.g. '-intercept-15-0521' or 'spiegel-122814'."""
    m = re.search(r"-(1[3-9])-(0[1-9]|1[0-2])(\d{2})(?:[-./]|$)", relpath)
    if m:
        return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"spiegel-(\d{2})(\d{2})(1[3-9])\b", relpath)
    if m:
        return f"20{m.group(3)}-{m.group(1)}-{m.group(2)}"
    return ""


PUBLISHED_DATE = published_date

TIMELINE_PRESETS = [
    ("Iraq · Afghanistan · Iran · China · Russia", "Iraq|Afghanistan|Iran|China|Russia"),
    ("Encryption · Tor · Smartphones · Malware · ML", "Encryption|Tor|Smartphones|Malware / implants|Machine learning / big data"),
    ("Counterterrorism · Offensive hacking · Diplomacy · Overload", "Counterterrorism|Offensive hacking (CNE/CNA)|Diplomatic targeting|Information overload"),
    ("Google · Yahoo · Microsoft · Facebook · Skype", "Google|Yahoo|Microsoft|Facebook|Skype"),
    ("Partners: GCHQ · BND · FRA · CSEC · ISNU", "GCHQ|BND|FRA|CSEC|ISNU (Unit 8200)"),
]

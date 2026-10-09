"""
Political pack: campaigns, parties and political operatives, election investigations, influence
operations and hack-and-leak personas. Suits the DNC/Podesta emails, campaign opposition research,
the January 6th Committee records, Macron Leaks, Heritage Foundation and similar releases.
Descriptions are limited to documented roles and court outcomes.
"""

DESCRIPTION = "Politics: campaigns, parties, operatives, elections, influence operations, hack-and-leak personas"
REQUIRES = ["core", "government"]

PERSON = [
    ("Donald Trump", ["Trump"], ""),
    ("Donald Trump Jr.", ["Donald Trump Jr.", "Donald Trump, Jr.", "Don Jr.", "Donald J. Trump Jr."], "Eldest son of Donald Trump; Trump Organization executive."),
    ("Ivanka Trump", ["Ivanka Trump", "Ivanka"], "Daughter of Donald Trump; senior White House adviser 2017–2021."),
    ("Eric Trump", ["Eric Trump"], "Son of Donald Trump; Trump Organization executive."),
    ("Melania Trump", ["Melania Trump", "Melania"], "Wife of Donald Trump; First Lady 2017–2021 and from 2025."),
    ("Jared Kushner", ["Kushner", "Jared Kushner"], "Son-in-law of Donald Trump; senior White House adviser 2017–2021."),
    ("Steve Bannon", ["Bannon", "Steve Bannon", "Stephen Bannon", "Stephen K. Bannon"], "Chief executive of Trump's 2016 campaign; White House chief strategist in 2017."),
    ("Roger Stone", ["Roger Stone"], "Political consultant and Trump adviser; convicted in 2019 of obstruction and lying to Congress."),
    ("Paul Manafort", ["Manafort", "Paul Manafort"], "Chairman of Trump's 2016 campaign; convicted in 2018 of tax and bank fraud."),
    ("Rick Gates", ["Rick Gates", "Richard Gates"], "Deputy chairman of Trump's 2016 campaign; pleaded guilty in 2018 and cooperated with the Mueller investigation."),
    ("Michael Cohen", ["Michael Cohen", "Michael D. Cohen"], "Donald Trump's former personal lawyer; pleaded guilty in 2018 to charges including campaign-finance violations."),
    ("Rudy Giuliani", ["Giuliani", "Rudy Giuliani", "Rudolph Giuliani"], "Mayor of New York City 1994–2001; later Donald Trump's personal lawyer."),
    ("Mark Meadows", ["Mark Meadows"], "White House chief of staff 2020–2021."),
    ("Stephen Miller", ["Stephen Miller"], "Senior policy adviser to Donald Trump."),
    ("Kellyanne Conway", ["Kellyanne Conway"], "Trump 2016 campaign manager; White House counselor 2017–2020."),
    ("Hope Hicks", ["Hope Hicks"], "Trump campaign spokeswoman and White House communications director."),
    ("John Eastman", ["John Eastman"], "Lawyer who advised Donald Trump on challenging the 2020 election result."),
    ("Sidney Powell", ["Sidney Powell"], "Lawyer who pursued suits challenging the 2020 election; pleaded guilty in Georgia in 2023."),
    ("Enrique Tarrio", ["Enrique Tarrio"], "Former Proud Boys chairman; convicted in 2023 of seditious conspiracy over January 6."),
    ("Stewart Rhodes", ["Stewart Rhodes"], "Oath Keepers founder; convicted in 2022 of seditious conspiracy over January 6."),
    ("Jack Smith", ["Jack Smith", "Special Counsel Smith"], "Special counsel 2022–2025 in the federal cases against Donald Trump."),
    ("John Podesta", ["Podesta", "John Podesta"], "Chairman of Hillary Clinton's 2016 campaign; WikiLeaks published his emails in 2016."),
    ("Huma Abedin", ["Huma Abedin", "Abedin"], "Longtime aide to Hillary Clinton."),
    ("Debbie Wasserman Schultz", ["Wasserman Schultz", "Debbie Wasserman Schultz"], "U.S. Representative; DNC chair 2011–2016, resigned after the DNC email leak."),
    ("Donna Brazile", ["Donna Brazile"], "Democratic strategist; interim DNC chair 2016–2017."),
    ("Robby Mook", ["Robby Mook"], "Campaign manager for Hillary Clinton in 2016."),
    ("Bernie Sanders", ["Bernie Sanders", "Senator Sanders"], "U.S. Senator from Vermont; presidential candidate in 2016 and 2020."),
    ("Hunter Biden", ["Hunter Biden"], "Son of Joe Biden; lawyer and businessman."),
    ("Nancy Pelosi", ["Pelosi", "Nancy Pelosi"], "Speaker of the U.S. House 2007–2011 and 2019–2023."),
    ("Chuck Schumer", ["Schumer", "Chuck Schumer"], "U.S. Senator from New York; Senate Democratic leader."),
    ("Mitch McConnell", ["McConnell", "Mitch McConnell"], "U.S. Senator from Kentucky; Senate Republican leader 2007–2025."),
    ("Kevin McCarthy", ["Kevin McCarthy"], "Speaker of the U.S. House in 2023."),
    ("Mike Johnson (Speaker)", ["Speaker Johnson", "Speaker Mike Johnson"], "Speaker of the U.S. House from 2023."),
    ("Liz Cheney", ["Liz Cheney"], "U.S. Representative 2017–2023; vice chair of the January 6th Committee."),
    ("Adam Schiff", ["Schiff", "Adam Schiff"], "U.S. Representative who chaired the House Intelligence Committee 2019–2023; Senator from 2025."),
    ("Bennie Thompson", ["Bennie Thompson"], "U.S. Representative; chair of the January 6th Committee."),
    ("Lindsey Graham", ["Lindsey Graham"], "U.S. Senator from South Carolina."),
    ("Ron DeSantis", ["DeSantis", "Ron DeSantis"], "Governor of Florida from 2019."),
    ("Nikki Haley", ["Nikki Haley"], "Governor of South Carolina 2011–2017; U.S. Ambassador to the UN 2017–2018."),
    ("Elon Musk", ["Elon Musk", "Musk"], "Businessman (Tesla, SpaceX, X); led the Department of Government Efficiency in 2025."),
    ("George Soros", ["Soros", "George Soros"], "Investor and philanthropist (Open Society Foundations)."),
    ("Jeffrey Epstein", ["Epstein", "Jeffrey Epstein"], "Financier and convicted sex offender; died in federal custody in 2019."),
    ("Ghislaine Maxwell", ["Ghislaine Maxwell"], "Associate of Jeffrey Epstein; convicted of sex trafficking in 2021."),
    ("Robert F. Kennedy Jr.", ["Robert F. Kennedy Jr.", "RFK Jr.", "Robert Kennedy Jr."], "Lawyer and activist; 2024 presidential candidate; U.S. Secretary of Health and Human Services from 2025."),
    ("Christopher Steele", ["Christopher Steele"], "Former MI6 officer; author of the 2016 'Steele dossier' on Trump and Russia."),
    ("Yevgeny Prigozhin", ["Prigozhin", "Yevgeny Prigozhin"], "Founder of the Wagner Group and financier of the Internet Research Agency; died in 2023."),
    ("Oleg Deripaska", ["Deripaska", "Oleg Deripaska"], "Russian aluminum magnate; sanctioned by the U.S. in 2018."),
    ("Konstantin Kilimnik", ["Kilimnik", "Konstantin Kilimnik"], "Associate of Paul Manafort in Ukraine."),
    ("Natalia Veselnitskaya", ["Veselnitskaya", "Natalia Veselnitskaya"], "Russian lawyer at the June 2016 Trump Tower meeting."),
    ("Alexei Navalny", ["Navalny", "Alexei Navalny", "Aleksei Navalny"], "Russian opposition leader; died in prison in 2024."),
    ("Nigel Farage", ["Farage", "Nigel Farage"], "British politician; led UKIP, the Brexit Party and Reform UK."),
    ("Dominic Cummings", ["Dominic Cummings"], "Director of the Vote Leave campaign; adviser to Boris Johnson 2019–2020."),
]

ORGANIZATION = [
    ("DNC", ["Democratic National Committee", "DNC"], "U.S. Democratic National Committee."),
    ("RNC", ["Republican National Committee", "RNC"], "U.S. Republican National Committee."),
    ("Democratic Party", ["Democratic Party", "Democrats"], "U.S. Democratic Party."),
    ("Republican Party", ["Republican Party", "Republicans", "GOP"], "U.S. Republican Party."),
    ("DCCC", ["Democratic Congressional Campaign Committee", "DCCC"], "House Democrats' campaign committee (hacked in 2016)."),
    ("Hillary for America", ["Hillary for America", "Clinton campaign"], "Hillary Clinton's 2016 presidential campaign."),
    ("Trump campaign", ["Trump campaign", "Donald J. Trump for President", "Trump for President"], "Donald Trump's presidential campaigns."),
    ("Trump Organization", ["Trump Organization", "Trump Org"], "Donald Trump's real-estate and branding company."),
    ("Clinton Foundation", ["Clinton Foundation"], "Foundation founded by Bill Clinton."),
    ("Proud Boys", ["Proud Boys"], "Far-right group; leaders convicted of seditious conspiracy over January 6."),
    ("Oath Keepers", ["Oath Keepers"], "Far-right militia group; leaders convicted of seditious conspiracy over January 6."),
    ("Internet Research Agency", ["Internet Research Agency", "IRA troll farm", "Glavset"], "St. Petersburg 'troll farm' indicted for interfering in the 2016 U.S. election."),
    ("Guccifer 2.0", ["Guccifer 2.0", "Guccifer2", "Guccifer 2"], "Online persona that leaked DNC documents in 2016; U.S. investigators attributed it to Russia's GRU."),
    ("DCLeaks", ["DCLeaks", "DC Leaks"], "Website that published hacked emails in 2016; U.S. investigators attributed it to Russia's GRU."),
    ("Fusion GPS", ["Fusion GPS"], "Research firm that commissioned the Steele dossier."),
    ("Heritage Foundation", ["Heritage Foundation"], "Conservative think tank in Washington."),
    ("Project 2025", ["Project 2025"], "Heritage Foundation-led plan for a second Trump administration."),
    ("NRA", ["National Rifle Association"], "U.S. gun-rights lobby."),
    ("Open Society Foundations", ["Open Society Foundations", "Open Society Foundation"], "Philanthropic network founded by George Soros."),
    ("En Marche / Renaissance", ["En Marche", "La République En Marche", "LREM"], "Emmanuel Macron's party (Macron Leaks, 2017)."),
    ("National Rally", ["National Rally", "Rassemblement National", "Front National", "National Front (France)"], "French far-right party."),
    ("Conservative Party (UK)", ["Conservative Party", "Tories", "Tory party"], "UK Conservative Party."),
    ("Labour Party (UK)", ["Labour Party"], "UK Labour Party."),
    ("Reform UK / UKIP / Brexit Party", ["Reform UK", "UKIP", "Brexit Party"], "Farage-led British parties."),
    ("AfD", ["Alternative für Deutschland", "Alternative for Germany"], "German far-right party."),
    ("United Russia", ["United Russia", "Единая Россия"], "Russia's ruling party."),
    ("Likud", ["Likud"], "Israeli party led by Benjamin Netanyahu."),
]

AGENCY = [
    ("Federal Election Commission", ["Federal Election Commission", "FEC"], "U.S. campaign-finance regulator."),
    ("January 6th Committee", ["January 6th Committee", "January 6 Committee", "Jan. 6 committee", "Select Committee to Investigate the January 6th Attack"], "U.S. House select committee on the January 6, 2021 Capitol attack (2021–2023)."),
    ("Department of Government Efficiency", ["Department of Government Efficiency", "DOGE"], "Trump administration cost-cutting body led by Elon Musk in 2025."),
]

PROGRAM = [
    ("Brexit", ["Brexit", "Vote Leave", "Leave campaign"], "The UK's 2016 referendum and departure from the European Union."),
    ("Steele dossier", ["Steele dossier", "Steele Dossier"], "2016 opposition-research dossier on Trump and Russia."),
    ("Crossfire Hurricane", ["Crossfire Hurricane"], "FBI investigation of Trump campaign links to Russia opened in 2016."),
    ("Stop the Steal", ["Stop the Steal", "#StopTheSteal"], "Campaign claiming the 2020 election was stolen."),
]

ENTITIES = {"person": PERSON, "organization": ORGANIZATION, "agency": AGENCY, "program": PROGRAM}

IDEAS = [
    ("Campaign finance & fundraising", [r"(?i:\bfundrais)", r"(?i:\bdonors?\b)", r"(?i:\bsuper ?PACs?\b)", r"\bPACs?\b", r"(?i:\bcampaign (?:finance|contributions?)\b)", r"\bFEC\b"],
     "Donors, fundraising and campaign finance."),
    ("Opposition research", [r"(?i:\boppo\b)", r"(?i:\bopposition research\b)", r"(?i:\bvulnerabilit(?:y|ies) (?:report|memo)\b)", r"(?i:\bdossier\b)"],
     "Opposition research on rivals."),
    ("Polling & voter data", [r"(?i:\bpolls?\b)", r"(?i:\bpolling\b)", r"(?i:\bfocus groups?\b)", r"(?i:\bvoter (?:file|data|turnout|registration))", r"(?i:\bswing states?\b)"],
     "Polls, focus groups and voter data."),
    ("Election-fraud claims", [r"(?i:\belection fraud\b)", r"(?i:\bvoter fraud\b)", r"(?i:\bstolen election\b)", r"(?i:\brigged\b)", r"(?i:\bstop the steal\b)", r"(?i:\balternate electors\b)", r"(?i:\bfake electors\b)"],
     "Claims of a stolen or rigged election."),
    ("Capitol attack (January 6)", [r"(?i:\bJanuary 6(?:th)?\b)", r"(?i:\bJan\. 6\b)", r"(?i:\bCapitol (?:riot|attack|breach)\b)", r"(?i:\bstorm(?:ed|ing) the Capitol\b)"],
     "The January 6, 2021 attack on the U.S. Capitol."),
    ("Lobbying & foreign agents", [r"(?i:\blobby(?:ing|ist|ists)\b)", r"\bFARA\b", r"(?i:\bforeign agents?\b)"],
     "Lobbying and foreign-agent registration."),
    ("Impeachment", [r"(?i:\bimpeach)"], "Impeachment proceedings."),
    ("Messaging & media strategy", [r"(?i:\btalking points\b)", r"(?i:\bmessaging\b)", r"(?i:\bpress releases?\b)", r"(?i:\bop-eds?\b)", r"(?i:\boff the record\b)"],
     "Talking points, messaging and press strategy."),
    ("Hack-and-leak operations", [r"(?i:\bhack-and-leak\b)", r"(?i:\bGuccifer\b)", r"(?i:\bDCLeaks\b)", r"(?i:\bhacked emails?\b)", r"(?i:\bleaked emails?\b)"],
     "Hacked material laundered through leaks."),
    ("Foreign election interference", [r"(?i:\belection interference\b)", r"(?i:\bmeddl)", r"(?i:\binterfere(?:d|nce)? in (?:the|our) election)", r"(?i:\btroll farm)"],
     "Foreign interference in elections."),
]

TIMELINE_PRESETS = [
    ("Trump · Clinton · Biden", "Donald Trump|Hillary Clinton|Joe Biden"),
    ("DNC · RNC · Russia", "DNC|RNC|Russia"),
]

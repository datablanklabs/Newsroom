"""
Economic and financial pack: central banks, regulators, banks, sovereign funds, energy majors and
crypto, with themes for monetary policy, sanctions, capital flight and banking crises. Includes
Russian-language aliases and theme patterns for Russian-language leaks (e.g. the Central Bank of
Russia files); pair it with extract.ocr_lang = "eng+rus" for scans.
"""

DESCRIPTION = "Economics & finance: central banks, regulators, banks, crypto, monetary/fiscal themes (incl. Russian terms)"
REQUIRES = ["core"]

AGENCY = [
    ("Federal Reserve", ["Federal Reserve", "Federal Reserve Board", "Federal Reserve System", "FOMC", "Federal Open Market Committee"], "U.S. central bank."),
    ("European Central Bank", ["European Central Bank", "ECB"], "Central bank of the euro area."),
    ("Bank of England", ["Bank of England"], "UK central bank."),
    ("Bank of Japan", ["Bank of Japan", "BOJ"], "Japan's central bank."),
    ("People's Bank of China", ["People's Bank of China", "PBOC", "PBoC"], "China's central bank."),
    ("Central Bank of Russia", ["Central Bank of Russia", "Bank of Russia", "CBR", "Банк России", "Центральный банк", "ЦБ РФ", "Центробанк"], "Russia's central bank."),
    ("Swiss National Bank", ["Swiss National Bank", "SNB"], "Switzerland's central bank."),
    ("Bundesbank", ["Bundesbank", "Deutsche Bundesbank"], "Germany's central bank."),
    ("Bank for International Settlements", ["Bank for International Settlements"], "Central banks' bank (Basel)."),
    ("Rosfinmonitoring", ["Rosfinmonitoring", "Росфинмониторинг"], "Russia's financial-intelligence unit."),
    ("Ministry of Finance (Russia)", ["Минфин", "Ministry of Finance of Russia", "Russian Ministry of Finance"], "Russia's finance ministry."),
    ("Financial Conduct Authority", ["Financial Conduct Authority"], "UK financial regulator."),
    ("CFTC", ["Commodity Futures Trading Commission"], "U.S. derivatives regulator."),
    ("FDIC", ["Federal Deposit Insurance Corporation"], "U.S. deposit insurer and bank regulator."),
]

COMPANY = [
    ("SWIFT", ["SWIFT", "Society for Worldwide Interbank Financial Telecommunication"], "Interbank messaging network."),
    ("Sberbank", ["Sberbank", "Сбербанк", "Sber"], "Russia's largest bank (state-controlled)."),
    ("VTB", ["VTB", "VTB Bank", "ВТБ"], "Russian state-controlled bank."),
    ("Gazprombank", ["Gazprombank", "Газпромбанк"], "Russian bank linked to Gazprom."),
    ("Alfa-Bank", ["Alfa-Bank", "Alfa Bank", "Альфа-Банк"], "Russian private bank."),
    ("Bank Rossiya", ["Bank Rossiya", "Банк Россия"], "St. Petersburg bank sanctioned in 2014 as the bank of Putin's inner circle."),
    ("Raiffeisen", ["Raiffeisen", "Raiffeisen Bank International"], "Austrian banking group."),
    ("Qatar National Bank", ["Qatar National Bank", "QNB"], "Qatar's largest bank (its customer data leaked in 2016)."),
    ("Lehman Brothers", ["Lehman Brothers", "Lehman"], "U.S. investment bank whose 2008 bankruptcy triggered the financial crisis."),
    ("Bear Stearns", ["Bear Stearns"], "U.S. investment bank rescued in 2008."),
    ("AIG", ["American International Group"], "U.S. insurer bailed out in 2008."),
    ("Fannie Mae / Freddie Mac", ["Fannie Mae", "Freddie Mac"], "U.S. government-sponsored mortgage companies."),
    ("BlackRock", ["BlackRock"], "Asset manager."),
    ("Moody's", ["Moody's", "Moodys"], "Credit rating agency."),
    ("S&P Global", ["Standard & Poor's", "S&P Global", "Standard and Poor's"], "Credit rating agency."),
    ("Fitch Ratings", ["Fitch Ratings"], "Credit rating agency."),
    ("Binance", ["Binance"], "Cryptocurrency exchange."),
    ("FTX", ["FTX"], "Cryptocurrency exchange that collapsed in 2022."),
    ("Tether", ["Tether", "USDT"], "Dollar-pegged stablecoin issuer."),
    ("Norway's oil fund", ["Government Pension Fund Global", "Norges Bank Investment Management", "NBIM"], "Norway's sovereign wealth fund."),
    ("Russian Direct Investment Fund", ["Russian Direct Investment Fund", "RDIF", "РФПИ"], "Russia's sovereign wealth fund."),
    ("Public Investment Fund", ["Public Investment Fund", "PIF"], "Saudi Arabia's sovereign wealth fund."),
]

TECHNOLOGY = [
    ("Bitcoin / cryptocurrency", ["Bitcoin", "bitcoin", "BTC", "cryptocurrency", "cryptocurrencies", "Ethereum", "stablecoin", "блокчейн", "биткоин"], "Cryptocurrency."),
    ("Central bank digital currency", ["central bank digital currency", "CBDC", "digital ruble", "digital rouble", "цифровой рубль", "e-CNY", "digital euro"], "Central bank digital currencies."),
    ("SPFS / Mir payments", ["SPFS", "СПФС", "Mir payment system", "НСПК"], "Russia's alternatives to SWIFT and Visa/Mastercard."),
]

ENTITIES = {"agency": AGENCY, "company": COMPANY, "technology": TECHNOLOGY}

IDEAS = [
    ("Monetary policy & interest rates", [r"(?i:\binterest rates?\b)", r"(?i:\bkey rate\b)", r"(?i:\bmonetary policy\b)", r"(?i:\brate (?:hike|cut)s?\b)", r"(?i:\bquantitative easing\b)", r"(?i:ключев\w* ставк)", r"(?i:денежно-кредитн)"],
     "Interest rates and monetary policy."),
    ("Inflation", [r"(?i:\binflation\b)", r"\bCPI\b", r"(?i:\bconsumer prices\b)", r"(?i:инфляц)"],
     "Inflation and prices."),
    ("Currency & exchange rates", [r"(?i:\bexchange rates?\b)", r"(?i:\bdevaluation\b)", r"(?i:\bru[bo]u?ble\b)", r"(?i:\bforex\b)", r"(?i:\bcurrency\b)", r"(?i:курс\w* рубл)", r"(?i:валют)"],
     "Currencies, exchange rates and devaluation."),
    ("Capital flight & controls", [r"(?i:\bcapital (?:flight|controls?|outflows?)\b)", r"(?i:\boutflows?\b)", r"(?i:отток капитала)"],
     "Capital flight and capital controls."),
    ("Banking crisis & bailouts", [r"(?i:\bbail-?outs?\b)", r"(?i:\bbank run\b)", r"(?i:\binsolven)", r"(?i:\brecapitali[sz])", r"(?i:\blicen[cs]e (?:was )?revoked\b)", r"(?i:санаци)", r"(?i:отзыв лиценз)"],
     "Bank failures, bailouts and license revocations."),
    ("Sovereign debt & bonds", [r"(?i:\bsovereign debt\b)", r"(?i:\beurobonds?\b)", r"(?i:\bgovernment bonds?\b)", r"\bOFZ\b", r"(?i:\bdefault(?:ed)?\b)", r"(?i:\byields?\b)", r"(?i:облигац)"],
     "Government debt, bonds and default."),
    ("Budget & fiscal policy", [r"(?i:\bbudget deficit\b)", r"(?i:\bfiscal\b)", r"(?i:\btax revenues?\b)", r"(?i:\bpublic spending\b)", r"(?i:бюджет)"],
     "Budgets, taxes and public spending."),
    ("Gold & reserves", [r"(?i:\bgold reserves?\b)", r"(?i:\bforeign (?:exchange )?reserves\b)", r"(?i:\breserve assets\b)", r"(?i:золотовалютн)"],
     "Gold and foreign-currency reserves."),
    ("Payments & financial infrastructure", [r"\bSWIFT\b", r"(?i:\bcorrespondent (?:bank|account))", r"(?i:\bpayment system)", r"(?i:\bwire transfers?\b)", r"(?i:платежн)"],
     "Payment systems, correspondent banking and transfers."),
    ("Privatization & state assets", [r"(?i:\bprivati[sz])", r"(?i:\bstate-owned\b)", r"(?i:\bnationali[sz])", r"(?i:приватизац)"],
     "Privatization and state ownership."),
    ("Financial supervision & compliance", [r"(?i:\bbanking supervision\b)", r"(?i:\bregulator)", r"(?i:\bstress tests?\b)", r"(?i:\bcapital adequacy\b)", r"(?i:надзор)"],
     "Supervision, regulation and compliance."),
]

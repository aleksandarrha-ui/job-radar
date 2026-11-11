"""Everything you may want to change lives here. Edit it on GitHub with the pencil icon."""

DAYS_BACK = 30          # only look at postings published in the last N days

# Emails
SUBJECT_PREFIX = "[Job Radar]"

# ---------------------------------------------------------------------------
# 1) Working student jobs in Baden-Württemberg
# ---------------------------------------------------------------------------
# Search phrases sent to the job boards (each is combined with "Werkstudent" and "Working Student").
QUERY_TOPICS = [
    "IT Support", "Customer Success", "Customer Care", "Customer Experience", "Kundenservice",
    "Projektmanagement", "Project Management", "Asset Management", "IT Administration",
    "Data Analytics", "Business Intelligence", "Business Analyst", "Digital Analyst",
    "Business Operations", "Sales Support", "Vertrieb", "Account Management",
    "Technical Sales", "IT Consulting", "IT Beratung",
]

# A job is kept if its TITLE matches one of these (regex, case-insensitive). Add your own later.
TOPICS = [
    ("IT Support",          r"it[- ]?support|help ?desk|service ?desk|technical support|technischer support|it[- ]service"),
    ("Customer",            r"customer|kunden"),
    ("Project Support",     r"project|projekt|\bpmo\b"),
    ("Asset Management",    r"asset management|lizenz|licen[sc]e|\bsam\b"),
    ("IT Administration",   r"it[- ]?admin|system ?admin|systemadmin"),
    ("Data / BI / Analyst", r"\bdata\b|daten|analytic|analyst|\bbi\b|business intelligence|power ?bi|reporting"),
    ("Business Operations", r"business operations|bizops|\boperations\b"),
    ("Sales / Accounts",    r"sales|vertrieb|account (management|manager)|key account"),
    ("IT Consulting",       r"consult|berat"),
]

# The title must also say it is a student job:
STUDENT_RE = r"werkstud|working student|student(in)?\b|studentisch|studierend|student assistant"
# ...and must not be one of these:
EXCLUDE_RE = r"duales studium|dual student|ausbildung|abschlussarbeit|thesis"

# Companies to watch: jobs from these get a star on the dashboard and are searched by name.
WATCH_COMPANIES = [
    # Software / IT
    "SAP", "osapiens", "Jedox", "Bruker", "BMW Car IT", "Fraunhofer", "Bechtle", "Schwarz IT",
    "Vector Informatik", "IONOS", "1&1", "United Internet", "Fiducia", "Atruvia", "Dell",
    # Industry / automotive
    "Bosch", "Mercedes-Benz", "Porsche", "Daimler Truck", "ZF", "Trumpf", "Festo", "ZEISS",
    "Würth", "Siemens", "ABB", "Freudenberg", "Heidelberger Druckmaschinen", "Roche", "EnBW",
    "Kaufland", "Lidl", "Audi",
    # Consulting / finance
    "Deloitte", "PwC", "KPMG", "EY", "Accenture", "Capgemini", "LBBW", "L-Bank", "FIS",
]

# Cities used only as a fallback if searching by the state name returns nothing.
BW_CITIES = [
    "Stuttgart", "Karlsruhe", "Mannheim", "Heidelberg", "Walldorf", "Freiburg im Breisgau", "Ulm",
    "Pforzheim", "Heilbronn", "Konstanz", "Friedrichshafen", "Tübingen", "Reutlingen",
    "Esslingen am Neckar", "Ludwigsburg", "Böblingen", "Offenburg", "Aalen", "Oberkochen", "Neckarsulm",
]

# ---------------------------------------------------------------------------
# 2) TRAX / FIS related jobs anywhere in Germany, any role level
# ---------------------------------------------------------------------------
TRAX_QUERIES = [
    "FIS Trax", "Trax SWIFT", "Trax payments", "Trax banking", "Trax Zahlungsverkehr",
    "ECHOS FIS", "FIS SWIFT payments", "FIS account statements",
]
# "strong": the posting text contains the word TRAX plus at least one of these words
TRAX_CONTEXT = r"\bfis\b|swift|payment|zahlungsverkehr|banking|bank\b|echos|account statement|kontoauszug|kontoauszüge"
# "related": posted by FIS (or mentioning ECHOS) and about one of these topics
TRAX_RELATED = r"swift|echos|payments?|zahlungsverkehr|account statement|kontoauszug|trax"
FIS_EMPLOYER_RE = r"\bfis\b|fidelity national information"

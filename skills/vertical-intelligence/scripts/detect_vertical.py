#!/usr/bin/env python3
"""
Vertical Intelligence Classifier.
Returns { vertical, score, confidence, recommendations }.
Recommendations are embedded here (not in the orchestrator) to keep the
marketplace decomposition clean.
"""

import os
import re
import sys
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.abspath(os.path.join(SKILL_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(SKILLS_DIR, ".."))
SHARED_DIR = os.path.join(ROOT_DIR, "lib")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from lib.utils import safe_fetch, extract_visible_text


VERTICAL_TAXONOMY_MAP = {
    "e-commerce": [
        "cart", "checkout", "sku", "add to cart", "free shipping", "buy now",
        "shopping bag", "sell online", "merchant", "storefront", "point of sale",
        "payment processing", "ecommerce platform", "online store", "commerce platform",
        "product catalog", "shopping cart", "returns", "order tracking", "inventory",
    ],
    "saas": [
        "pricing", "features", "integrations", "free trial", "dashboard", "software",
        "subscription", "platform", "cloud", "api", "workflow", "automation",
        "deploy", "per seat", "per month", "self-serve", "onboarding",
        "enterprise plan", "usage-based", "sso",
    ],
    "airline": [
        "flight", "airline", "baggage", "boarding pass", "round trip", "fare",
        "skyteam", "one-way", "direct flight", "layover", "check-in", "frequent flyer",
        "business class", "economy class", "miles", "route map",
        "departure", "arrival", "codeshare", "star alliance",
    ],
    "hotel": [
        "room rate", "check-in", "suites", "amenities", "book room", "hotel",
        "resort", "king bed", "double room", "check-out", "concierge", "spa",
        "pool", "room service", "nightly rate", "loyalty program",
        "free cancellation", "guest reviews", "property", "5-star",
    ],
    "news": [
        "breaking news", "headline", "editor", "journalism", "published on",
        "opinion", "editorial", "reporter", "correspondent", "bureau",
        "world news", "politics", "latest", "updates", "live",
        "breaking", "exclusive", "investigation", "analysis", "article",
    ],
    "healthcare": [
        "patients", "doctors", "clinic", "specialties", "medical center",
        "physician", "hospital", "treatment", "appointment", "health",
        "wellness", "care", "diagnosis", "insurance accepted", "emergency",
        "surgery", "prescription", "pharmacy", "urgent care", "primary care",
    ],
    "real-estate": [
        "properties", "mortgage calculator", "realtor", "for sale", "bedrooms",
        "listing", "apartment", "condo", "square feet", "open house",
        "agent", "mls", "buy a home", "sell your home", "rent",
        "lease", "down payment", "closing costs", "property taxes", "neighborhood",
    ],
    "automotive": [
        "dealership", "test drive", "vehicle", "horsepower", "car", "sedan",
        "suv", "truck", "electric vehicle", "hybrid", "mpg",
        "horsepower", "torque", "trim", "msrp", "lease offer",
        "financing", "trade-in", "maintenance", "recall", "vin",
    ],
    "fintech": [
        "payments", "wallet", "transfers", "interest rate", "crypto",
        "banking", "neobank", "financial services", "lending", "credit",
        "transaction", "money transfer", "fraud", "investing", "checking",
        "savings", "apy", "loan", "debit card", "mortgage",
    ],
    "edtech": [
        "curriculum", "courses", "syllabus", "student portal", "tuition",
        "learning management", "online courses", "certifications", "degrees",
        "enroll", "learn online", "education platform", "lectures", "quizzes",
        "assignments", "instructors", "cohorts", "self-paced", "bootcamp", "skills",
    ],
    "higher-education": [
        "university", "college", "undergraduate", "graduate", "faculty",
        "admissions", "alumni", "campus", "research", "academic programs",
        "schools", "department of", "scholarship", "semester", "provost",
        "dean", "liberal arts", "majors", "minor", "honors program",
    ],
    "medtech": [
        "medical device", "fda approval", "diagnostics", "clinical trial",
        "biomedical", "imaging", "surgical", "patient monitoring", "ivd",
        "implant", "catheter", "sterilization", "point-of-care", "wearable",
        "remote monitoring", "clinical evidence", "ce marked", "510(k)",
    ],
    "legaltech": [
        "contract lifecycle", "e-discovery", "compliance", "litigation",
        "legal practice", "matter management", "legal operations", "clm",
        "billing", "docket", "patent", "trademark", "intellectual property",
        "attorney", "law firm", "paralegal", "case management", "brief",
        "deposition", "court filing",
    ],
    "proptech": [
        "tenant portal", "property management", "lease tracking", "smart building",
        "facility management", "rent collection", "maintenance requests", "mdu",
        "hoa", "landlord", "unit", "occupancy", "work orders", "amenities booking",
        "resident", "concierge app", "access control", "camera system", "energy monitoring",
    ],
    "gaming": [
        "gameplay", "esports", "multiplayer", "steam", "console", "game developer",
        "playstation", "xbox", "nintendo", "rpg", "fps",
        "mmo", "battle royale", "co-op", "single-player", "achievements",
        "loot", "dlc", "season pass", "leaderboard",
    ],
    "aerospace": [
        "avionics", "satellite", "propulsion", "launch vehicle", "aeronautical",
        "spacecraft", "orbit", "payload", "engine", "flight test",
        "fuselage", "wing", "turbine", "thrust", "mission",
        "satellite constellation", "space launch", "commercial space", "nasa", "esa",
    ],
    "energy": [
        "solar panels", "renewable energy", "grid", "wind farm", "power plant",
        "utility", "electricity", "natural gas", "oil", "offshore",
        "turbine", "megawatt", "kilowatt", "energy storage", "battery",
        "carbon neutral", "net zero", "grid-scale", "power distribution", "smart meter",
    ],
    "cybersecurity": [
        "threat intelligence", "zero trust", "firewall", "endpoint security",
        "siem", "soc", "incident response", "penetration testing", "malware",
        "ransomware", "vulnerability", "phishing", "iam", "mfa",
        "encryption", "compliance", "soc 2", "gdpr", "iso 27001", "ciso",
    ],
    "cleantech": [
        "carbon footprint", "sustainability", "decarbonization", "circular economy",
        "esg", "emissions", "recycling", "waste management", "water treatment",
        "air quality", "green energy", "climate", "carbon credits",
        "net zero", "renewable", "battery recycling", "sustainable materials", "eco",
    ],
    "insurtech": [
        "claim status", "underwriting", "policyholder", "deductible",
        "insurance quote", "auto insurance", "home insurance", "life insurance",
        "health insurance", "policy", "premium", "coverage", "copay",
        "renewal", "beneficiary", "actuary", "risk assessment", "claims",
    ],
    "logistics": [
        "freight", "waybill", "fleet management", "last mile", "warehousing",
        "carrier", "shipping", "supply chain", "trucking", "3pl",
        "fulfillment", "dispatch", "route optimization", "tracking number",
        "cold chain", "cross-docking", "ltl", "ftl", "customs", "port",
    ],
    "hrtech": [
        "applicant tracking", "payroll", "onboarding", "talent acquisition",
        "performance review", "hrms", "benefits", "time tracking", "ats",
        "headcount", "compensation", "employee engagement", "recruiting", "hiring",
        "learning development", "succession planning", "dei", "workforce", "people ops", "chro",
    ],
    "martech": [
        "campaign management", "attribution", "lead generation", "marketing automation",
        "crm", "email marketing", "sms", "customer data platform", "cdp",
        "personalization", "segmentation", "abm", "utm", "analytics",
        "roas", "engagement", "retention", "lifecycle", "funnel", "conversion",
    ],
    "govtech": [
        "public sector", "citizen services", "municipal", "procurement",
        "e-government", "open data", "permits", "licenses", "civic",
        "smart city", "digital identity", "records", "courts", "tax",
        "public safety", "emergency services", "policy", "regulation", "constituent", "portal",
    ],
    "agtech": [
        "precision farming", "crop yield", "irrigation", "agronomy",
        "livestock tracking", "soil health", "drones", "satellite imagery",
        "fertilizer", "pesticide", "harvest", "greenhouse", "farm management",
        "genetics", "yield", "sensors", "field", "grain", "crop rotation", "sustainable agriculture",
    ],
    "biotech": [
        "genomics", "therapeutics", "molecular", "recombinant", "drug discovery",
        "crispr", "biologics", "antibody", "clinical trial", "phase i",
        "rna", "dna", "protein", "cell therapy", "gene editing",
        "biomarker", "targeted therapy", "oncology", "pipeline", "ind",
    ],
    "deeptech": [
        "quantum computing", "nanotechnology", "photonics", "semiconductor",
        "superconducting", "qubit", "photolithography", "mems", "lidar",
        "materials science", "computational", "simulation", "patent pending", "r&d",
        "spin-off", "lab", "prototype", "cleanroom", "fab", "wafer",
    ],
    "ai-ml": [
        "neural network", "transformer model", "large language model", "inference",
        "fine-tuning", "foundation model", "rag", "embeddings", "tokenization",
        "training data", "gpu", "mlops", "feature store", "vector database",
        "prompt engineering", "agent", "benchmark", "model card", "checkpoint", "quantization",
    ],
    "entertainment": [
        "streaming", "box office", "episodes", "cinema", "discography",
        "trailers", "series", "season", "film", "movie",
        "documentary", "screenplay", "director", "cast", "premiere",
        "soundtrack", "studio", "showrunner", "episode", "binge",
    ],
    "sports": [
        "league", "tournament", "scoreboard", "coaching staff", "athletics",
        "playoffs", "fixtures", "season", "match", "team",
        "player", "roster", "draft", "championship", "cup",
        "stadium", "conference", "division", "standings", "league table",
    ],
    "travel": [
        "itinerary", "tour operator", "sightseeing", "excursion", "destination guide",
        "travel guide", "things to do", "trip", "vacation", "package",
        "day tour", "guided tour", "attraction", "landmark", "tips",
        "visa", "passport", "local cuisine", "best time to visit", "hidden gems",
    ],
    "hospitality": [
        "concierge", "hospitality services", "banquet", "guest experience",
        "front desk", "bellhop", "valet", "housekeeping", "reservations",
        "check-in", "lobby", "spa", "fitness center", "business center",
        "meeting rooms", "event space", "catering", "turn-down", "guest relations",
    ],
    "restaurant": [
        "menu", "table reservation", "takeout", "dine-in", "culinary",
        "bistro", "brunch", "dinner", "lunch", "appetizers",
        "entrees", "chef", "kitchen", "wine list", "cocktails",
        "happy hour", "reservations", "delivery", "specials", "course",
    ],
    "fashion": [
        "apparel", "runway", "haute couture", "footwear", "wardrobe",
        "garment", "collection", "lookbook", "ready-to-wear", "accessories",
        "spring/summer", "fall/winter", "designer", "boutique", "couture",
        "linen", "silhouette", "textile", "couturier", "atelier",
    ],
    "beauty": [
        "skincare", "cosmetics", "dermatologist", "makeup", "fragrance",
        "serum", "moisturizer", "cleanser", "sunscreen", "anti-aging",
        "acne", "exfoliant", "lipstick", "mascara", "foundation",
        "haircare", "shampoo", "conditioner", "spa", "ingredients",
    ],
    "fitness": [
        "workout plan", "gym membership", "personal trainer", "caloric deficit",
        "strength training", "cardio", "hiit", "yoga", "pilates",
        "crossfit", "rep", "set", "warm-up", "cool-down",
        "protein", "macros", "bmi", "class schedule", "trainer", "membership",
    ],
    "construction": [
        "general contractor", "blueprints", "scaffolding", "building permits",
        "construction management", "site work", "excavation", "framing", "roofing",
        "hvac", "electrical", "plumbing", "concrete", "steel",
        "commercial build", "residential build", "renovation", "estimating", "subcontractor", "safety compliance",
    ],
    "manufacturing": [
        "assembly line", "oem", "machining", "supply chain", "industrial equipment",
        "fabrication", "cnc", "injection molding", "quality control", "lean manufacturing",
        "iso 9001", "six sigma", "production line", "tooling", "fixtures",
        "stamping", "welding", "casting", "plant", "factory", "throughput",
    ],
    "supply-chain": [
        "inventory management", "procurement", "vendor management", "logistics network",
        "demand planning", "order management", "supplier", "warehouse management",
        "s&op", "erp", "bom", "moq", "lead time",
        "inventory turnover", "safety stock", "reorder point", "distribution", "network optimization", "control tower",
    ],
    "telecommunications": [
        "broadband", "5g network", "5g", "fiber optic", "fibre optic",
        "telecom operator", "cellular", "mobile network", "connectivity",
        "network provider", "roaming", "sim card", "mobile plans",
        "digital services", "telecom", "network operator",
        "lte", "4g", "wifi", "data plan", "mvno",
        "spectrum", "tower", "backhaul", "voip", "unlimited data",
    ],
    "defense": [
        "defense contractor", "military technology", "tactical systems", "national security",
        "aerospace defense", "command control", "c4isr", "cyber defense",
        "weapons system", "munitions", "radar", "drone", "uav",
        "soldier system", "logistics support", "it system", "encrypted comms", "satellite defense", "missile",
    ],
    "publishing": [
        "manuscript", "monograph", "academic press", "periodical", "imprint",
        "journal", "peer review", "editorial board", "open access", "doi",
        "isbn", "issn", "publication", "abstract", "citation",
        "author guidelines", "submission", "revision", "galley", "issue",
    ],
    "non-profit": [
        "donation", "philanthropy", "charitable", "volunteer", "501c3",
        "mission statement", "grant", "fundraising", "nonprofit", "ngo",
        "impact report", "beneficiaries", "outreach", "advocacy", "community",
        "tax-deductible", "sponsorship", "board of directors", "annual fund", "endowment",
    ],
    "venture-capital": [
        "portfolio companies", "seed round", "series a", "cap table", "venture firm",
        "term sheet", "due diligence", "fund", "lp", "gp",
        "lead investor", "follow-on", "valuation", "exit", "ipo",
        "pre-seed", "series b", "series c", "sector focus", "thesis", "conviction",
    ],
    "private-equity": [
        "buyout", "leveraged buyout", "asset management", "portfolio value",
        "carried interest", "irr", "fund", "lp", "gp",
        "acquisition", "platform company", "add-on", "roll-up", "dpi",
        "moic", "holding period", "operating partner", "value creation", "exit multiple", "dry powder",
    ],
    "banking": [
        "checking account", "mortgage rates", "credit card", "atm locator", "wire transfer",
        "savings account", "online banking", "routing number", "overdraft", "apy",
        "apr", "monthly fee", "minimum balance", "fdic", "branch",
        "debit card", "loan", "auto loan", "personal loan", "credit score",
    ],
    "wealth-management": [
        "asset allocation", "fiduciary", "portfolio manager", "estate planning",
        "wealth advisory", "family office", "discretionary", "advisory fee",
        "rebalancing", "diversification", "tax-loss harvesting", "esg investing", "impact investing",
        "retirement planning", "401k", "ira", "trust", "philanthropic", "private client", "hnw",
    ],
    "e-learning": [
        "video course", "self-paced", "certification", "instructor-led",
        "mooc", "cohort", "learning path", "quiz", "assignment",
        "capstone", "peer review", "certificate", "enrollment", "curriculum",
        "module", "lesson", "syllabus", "prerequisite", "credential", "upskill",
    ],
    "e-sports": [
        "tournament bracket", "prize pool", "pro team", "shoutcaster",
        "esports league", "esports tournament", "roster", "scrim", "meta",
        "patch", "ranked", "match", "team", "player",
        "casters", "majors", "grand final", "group stage", "bracket", "twitch",
    ],
    "architecture": [
        "architectural firm", "elevation plans", "structural design", "cad drawings",
        "schematic design", "design development", "construction documents", "permit set",
        "site plan", "floor plan", "rendering", "bim", "revit",
        "leed", "sustainable design", "urban planning", "interior design", "landscape architecture", "master plan",
    ],
    "consulting": [
        "advisory services", "management consulting", "case studies", "deliverables",
        "engagement", "client", "strategy", "operations", "transformation",
        "due diligence", "market entry", "cost reduction", "process improvement", "change management",
        "interim", "fractional", "sme", "subject matter expert", "deliverable", "workstream",
    ],
}

VERTICAL_RECOMMENDATIONS = {
    "higher-education": [
    "Structure academic programs with Schema.org/CollegeOrUniversity + EducationalOccupationalProgram.",
    "Publish degree programs, tuition, and admissions deadlines as static HTML, not JS-only.",
    ],
    "e-commerce": [
        "Structure product categories with Schema.org/OfferCatalog + ItemList.",
        "Expose price, availability, and SKU as static HTML, not JS-rendered.",
    ],
    "saas": [
        "Publish API reference docs with Schema.org/SoftwareApplication + machine-readable feature tags.",
        "Detect AI-referred traffic at the edge and preserve query context on pricing/docs pages.",
    ],
    "airline": [
        "Embed Schema.org/Flight + Airline structured metadata for real-time itinerary parsing.",
        "Expose deep-link anchors for route/date queries (e.g., /flights/del-bom#schedule).",
    ],
    "hotel": [
        "Emit Schema.org/Hotel + Accommodation JSON-LD with room types, amenities, and policies.",
        "Serve check-in policies and room specs as static text above the fold, not JS modals.",
    ],
    "news": [
        "Emit Schema.org/NewsArticle with ISO-8601 datePublished and dateModified.",
        "Integrate IndexNow for sub-minute crawl triggers on breaking stories.",
    ],
    "healthcare": [
        "Structure providers and specialties with Schema.org/MedicalBusiness + Physician.",
        "Publish HIPAA-adjacent disclaimers in machine-readable meta tags.",
    ],
    "real-estate": [
        "Use Schema.org/RealEstateListing with geocoordinates and price for each listing.",
        "Expose listings as a structured JSON feed for AI-assisted comparison.",
    ],
    "automotive": [
        "Emit Schema.org/Vehicle + AutoDealer JSON-LD with model specs.",
        "Expose horsepower, dimensions, and trim data as static HTML tables.",
    ],
    "fintech": [
        "Structure products with Schema.org/FinancialProduct + BankAccount.",
        "Publish rates, fees, and eligibility criteria as crawlable HTML.",
    ],
    "edtech": [
        "Use Schema.org/Course + EducationalOccupationalProgram.",
        "Provide course catalogs as an indexed JSON-LD ItemList.",
    ],
    "medtech": [
        "Structure device metadata with Schema.org/MedicalDevice + regulatory IDs.",
        "Cross-link FDA approvals to external registries via sameAs.",
    ],
    "legaltech": [
        "Structure practice areas and jurisdictions with Schema.org/LegalService.",
        "Publish case studies with schema-qualified outcome data.",
    ],
    "proptech": [
        "Structure listings with Schema.org/RealEstateListing + geocoordinates.",
        "Publish tenant-facing property data as static JSON-LD.",
    ],
    "gaming": [
        "Structure titles with Schema.org/VideoGame + platform metadata.",
        "Expose a stable /catalog.json for titles, platforms, release dates.",
    ],
    "aerospace": [
        "Structure capabilities with Schema.org/Organization + NAICS classifications.",
        "Publish technical whitepapers with ScholarlyArticle JSON-LD.",
    ],
    "energy": [
        "Structure services with Schema.org/Service + coverage regions.",
        "Publish rate tables and coverage maps as static HTML.",
    ],
    "cybersecurity": [
        "Structure product capabilities with Schema.org/SoftwareApplication + feature enums.",
        "Publish threat research as ScholarlyArticle with sameAs DOIs.",
    ],
    "cleantech": [
        "Structure sustainability claims with Schema.org/Organization + verified data.",
        "Publish carbon metrics as structured JSON-LD PropertyValue.",
    ],
    "insurtech": [
        "Structure products with Schema.org/InsuranceAgency + policy enums.",
        "Publish coverage tables as static HTML.",
    ],
    "logistics": [
        "Structure services with Schema.org/DeliveryEvent + coverage regions.",
        "Publish SLA data as JSON-LD PropertyValue.",
    ],
    "hrtech": [
        "Structure job postings with Schema.org/JobPosting + salary ranges.",
        "Publish ATS API docs with Schema.org/SoftwareApplication.",
    ],
    "martech": [
        "Structure capabilities with Schema.org/SoftwareApplication + features.",
        "Publish integrations as a Schema.org/ItemList.",
    ],
    "govtech": [
        "Structure services with Schema.org/GovernmentService + jurisdiction.",
        "Publish FOIA-adjacent metadata as machine-readable JSON.",
    ],
    "agtech": [
        "Structure equipment with Schema.org/Product + agricultural properties.",
        "Publish agronomic data as structured JSON-LD.",
    ],
    "biotech": [
        "Structure entities with Schema.org/BioChemEntity + DOI sameAs.",
        "Publish pipeline data as structured JSON-LD.",
    ],
    "deeptech": [
        "Publish technical whitepapers as ScholarlyArticle with DOI sameAs.",
        "Structure labs and equipment with Schema.org/Organization.",
    ],
    "ai-ml": [
        "Structure models with Schema.org/SoftwareSourceCode + benchmark metadata.",
        "Publish evaluation results as structured JSON-LD ItemList.",
    ],
    "entertainment": [
        "Structure titles with Schema.org/Movie, MusicGroup, or TVSeries.",
        "Emit datePublished for episodic content.",
    ],
    "sports": [
        "Structure teams and events with Schema.org/SportsTeam + SportsEvent.",
        "Publish fixtures and results as machine-readable JSON-LD.",
    ],
    "travel": [
        "Structure attractions with Schema.org/TouristAttraction + Trip.",
        "Expose itineraries as structured lists, not image carousels.",
    ],
    "hospitality": [
        "Structure venues with Schema.org/LodgingBusiness + amenity enums.",
        "Publish menus and hours as static HTML.",
    ],
    "restaurant": [
        "Structure menus with Schema.org/Menu + MenuItem.",
        "Publish hours and locations as static HTML.",
    ],
    "fashion": [
        "Structure products with Schema.org/Product + color/size/material.",
        "Publish size charts as static text tables.",
    ],
    "beauty": [
        "Structure products with Schema.org/Product + ingredient/vegan properties.",
        "Publish INCI ingredient lists as static text.",
    ],
    "fitness": [
        "Structure programs with Schema.org/ExercisePlan + HealthClub.",
        "Publish class schedules as static HTML tables.",
    ],
    "construction": [
        "Structure projects with Schema.org/CreativeWork + location.",
        "Publish safety and permit data as static HTML.",
    ],
    "manufacturing": [
        "Structure capabilities with Schema.org/Product + OEM/ODM specs.",
        "Publish datasheets as static PDF + Schema.org attachment.",
    ],
    "supply-chain": [
        "Structure services with Schema.org/Service + coverage regions.",
        "Publish SLA and capacity data as JSON-LD.",
    ],
    "telecommunications": [
        "Structure plans with Schema.org/TelecomService + coverage metadata.",
        "Publish coverage maps as SVG + alt text.",
    ],
    "defense": [
        "Structure contract vehicles with Schema.org/Organization + NAICS.",
        "Publish capability statements as structured JSON-LD.",
    ],
    "publishing": [
        "Structure books/journals with Schema.org/Book + ScholarlyArticle.",
        "Emit ISBN/DOI as machine-readable identifiers.",
    ],
    "non-profit": [
        "Structure mission and programs with Schema.org/NGO.",
        "Publish donation impact data as structured JSON-LD.",
    ],
    "venture-capital": [
        "Structure portfolio with Schema.org/ItemList linking to Organization nodes.",
        "Publish thesis and fund data as static JSON-LD.",
    ],
    "private-equity": [
        "Structure portfolio with Schema.org/Organization relationships.",
        "Publish fund performance as structured PropertyValue.",
    ],
    "banking": [
        "Structure products with Schema.org/FinancialProduct.",
        "Publish rate tables as static HTML with Schema.org/PropertyValue.",
    ],
    "wealth-management": [
        "Structure services with Schema.org/FinancialService.",
        "Publish fiduciary disclosures as static HTML.",
    ],
    "e-learning": [
        "Structure courses with Schema.org/Course + time commitments.",
        "Publish syllabi as static text, not JS collapsibles.",
    ],
    "e-sports": [
        "Structure tournaments with Schema.org/SportsEvent + SportsTeam.",
        "Publish brackets as structured JSON-LD.",
    ],
    "architecture": [
        "Structure portfolios with Schema.org/CreativeWork + location.",
        "Publish project data as static HTML with images + captions.",
    ],
    "consulting": [
        "Structure services with Schema.org/ProfessionalService.",
        "Publish case studies with quantified outcomes as static text.",
    ],
}

GENERIC_RECOMMENDATIONS = [
    "Deploy /llms.txt and /llms-full.txt to give RAG systems clean brand context.",
    "Include sameAs links (Wikidata, Wikipedia, Crunchbase) in Organization JSON-LD to strengthen entity consensus.",
]


def get_vertical_recommendations(vertical):
    """Return recommendations as {text, priority} objects so they can be
    rendered alongside findings in the report."""
    recs = []
    for i, text in enumerate(GENERIC_RECOMMENDATIONS):
        recs.append({"text": text, "priority": "high" if i == 0 else "medium"})
    for i, text in enumerate(VERTICAL_RECOMMENDATIONS.get(vertical, [])):
        recs.append({"text": text, "priority": "medium" if i == 0 else "low"})
    return recs


def _match_keyword(kw, text):
    tokens = [re.escape(t) for t in re.split(r"[\s\-_]+", kw) if t]
    if not tokens:
        return False
    pattern = r"\b" + r"[\s\-_]+".join(tokens) + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def detect_vertical(target_url):
    res = safe_fetch(target_url)
    if res["status"] != 200 or not res["body"]:
        return {"vertical": "general", "score": 0, "confidence": 0.0}

    clean_text = extract_visible_text(res["body"])
    url_path = urllib.parse.urlparse(target_url).path

    scores = {}
    for vertical, keywords in VERTICAL_TAXONOMY_MAP.items():
        score = 0
        for kw in keywords:
            if _match_keyword(kw, url_path):
                score += 5
            if _match_keyword(kw, clean_text):
                score += 1
        if score > 0:
            scores[vertical] = score

    if not scores:
        return {"vertical": "general", "score": 0, "confidence": 0.0}

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_vertical, best_score = ordered[0]
    second_best = ordered[1][1] if len(ordered) > 1 else 0

    if best_score < 2:
        return {"vertical": "general", "score": 0, "confidence": 0.0}
    if (best_score - second_best < 1) and best_score < 6:
        return {"vertical": "general", "score": 0, "confidence": 0.0}

    confidence = min(1.0, round(best_score / 6.0, 2))
    return {"vertical": best_vertical, "score": best_score, "confidence": confidence}


def check_vertical(target_url):
    try:
        result = detect_vertical(target_url)
        vertical = result.get("vertical", "general") or "general"
        confidence = float(result.get("confidence", 0.0) or 0.0)
        recommendations = get_vertical_recommendations(vertical)
    except Exception as e:
        sys.stderr.write(f"Vertical detection failed: {e}\n")
        vertical, confidence = "general", 0.0
        recommendations = list(GENERIC_RECOMMENDATIONS)

    return {
        "vertical": vertical,
        "confidence": confidence,
        "recommendations": recommendations,
    }
if __name__ == "__main__":
    import json
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(check_vertical(target), indent=2))
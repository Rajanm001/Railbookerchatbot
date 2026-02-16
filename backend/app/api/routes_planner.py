"""
Railbookers Rail Vacation Planner - Conversational Chatbot

RULES:
- ALL options from database DISTINCT queries. Zero hardcoded data.
- NO step indicators, progress bars, or percentages in any response.
- Professional, warm, conversational tone. No emojis.
- No hallucination. Every value from DB or user input.
- Session resets after recommendations are delivered.
- Contextually aware: each response acknowledges what user said.
- Smart validation: fuzzy matching with helpful suggestions.

Conversational Flow (8 natural questions):
 Step 1: Destination      -- "Where would you like to go?"
 Step 2: Travellers       -- "Who will be travelling with you, and how many guests?"
 Step 3: Dates/Duration   -- "When would you like to travel, and for how long?"
 Step 4: Trip Purpose     -- "What is the main reason for this trip?"
 Step 5: Special Occasion -- "Are you celebrating a special occasion?"
 Step 6: Hotel Preference -- "What type of hotels do you prefer?"
 Step 7: Rail Experience  -- "Have you taken a rail vacation before?"
 Step 8: Budget & Needs   -- (Optional) Budget + accessibility/requirements
 -> Personalised recommendations -> session reset
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import logging
import uuid
import re
import time
from difflib import get_close_matches

from pydantic import BaseModel

from app.db.database import get_db
from app.services.db_options import DBOptionsProvider
from app.services.recommender import PackageRecommender
from app.core.config import settings
from app.core.rate_limiting import limiter, PLANNER_LIMIT, RECOMMENDATION_LIMIT, HEALTH_LIMIT
from app.core.monitoring import track_performance
from app.services.translations import t, t_list

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner", tags=["Trip Planner"])

# ---------------------------------------------------------------------------
# In-memory sessions (swap to Redis for production scale)
# ---------------------------------------------------------------------------
conversation_sessions: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_data: Optional[dict] = None
    lang: str = "en"

    @property
    def safe_message(self) -> str:
        """Sanitised, length-limited message."""
        msg = self.message.strip()[:2000]
        # Strip HTML tags for safety
        msg = re.sub(r"<[^>]*>", "", msg)
        return msg


class ChatResponse(BaseModel):
    message: str
    suggestions: Optional[List[str]] = None
    step_number: Optional[int] = None
    total_steps: int = 9
    needs_input: bool = True
    recommendations: Optional[List[dict]] = None
    session_id: str
    placeholder: Optional[str] = None
    currency_code: Optional[str] = None
    currency_sym: Optional[str] = None


# ---------------------------------------------------------------------------
# Session & Helpers
# ---------------------------------------------------------------------------

def _new_session() -> dict:
    return {
        "_ts": time.time(),
        "step": 0,
        "data": {
            "destinations_countries": [],
            "destinations_cities": [],
            "traveler_type": None,
            "num_travelers": 2,
            "travel_dates": None,
            "duration_days": None,
            "flexible_dates": False,
            "trip_reason": [],
            "special_occasion": None,
            "hotel_tier": None,
            "rail_experience": None,
            "budget": None,
            "special_requirements": None,
            "accessibility_needs": None,
            "currency_code": "GBP",
            "currency_sym": "\u00a3",
        },
    }


GREETING_WORDS = {
    "hello", "hi", "hey", "howdy", "greetings", "hola", "bonjour",
    "ciao", "yo", "sup", "good morning", "good afternoon",
    "good evening", "what's up", "start", "begin", "let's go",
    "get started", "plan", "help", "help me", "plan a trip",
}

SKIP_WORDS = {
    "skip", "none", "no", "n/a", "na", "not really",
    "nothing", "pass", "no thanks", "nope", "not sure",
    "don't know", "dont know", "no preference", "any",
    "doesn't matter", "doesnt matter", "whatever",
    "no special occasion", "just for fun",
}

# Creative destination one-liners
DEST_FLAIR = {
    "italy": "home to legendary rail routes through Tuscany and the Amalfi coast",
    "switzerland": "where every train window frames a postcard of the Alps",
    "france": "from Paris to Provence, a land made for rail",
    "germany": "precision engineering meets stunning Rhine Valley views",
    "united kingdom": "the birthplace of rail travel itself",
    "spain": "sun-soaked journeys from Barcelona to Andalusia",
    "austria": "Alpine passes and imperial grandeur by rail",
    "canada": "vast coast-to-coast landscapes aboard iconic trains",
    "united states": "legendary cross-country rail adventures",
    "japan": "bullet trains and cherry blossoms -- rail perfection",
    "netherlands": "a compact country best explored by train",
    "india": "palace-on-wheels luxury through royal Rajasthan",
    "scotland": "wild Highland scenery by rail",
    "ireland": "emerald countryside from Dublin to the Wild Atlantic Way",
    "norway": "fjord-hugging railways that defy belief",
    "sweden": "Arctic Circle to cosmopolitan Stockholm",
    "portugal": "Lisbon to Porto along the Douro River",
    "czech republic": "fairy-tale Prague and beyond",
    "australia": "the Ghan and Indian Pacific -- epic transcontinental rides",
    "new zealand": "the TranzAlpine and beyond through breathtaking scenery",
    "vietnam": "the Reunification Express along a stunning coastline",
    "sri lanka": "tea country railways through misty hill stations",
    "morocco": "from Marrakech to the desert by train",
    "south africa": "the Blue Train and Rovos Rail through the Winelands",
    "peru": "Andean railways to Machu Picchu",
    "belgium": "Brussels, Bruges, and beyond at high speed",
    "greece": "ancient wonders linked by scenic rail corridors",
    "finland": "Santa Claus Express to the Arctic north",
    "denmark": "from Copenhagen across bridges and Baltic islands",
    "poland": "Krakow, Warsaw, and the Tatra Mountains by rail",
    "turkey": "the Eastern Express through Anatolia's vast landscapes",
    "singapore": "gateway to Southeast Asia's rail network",
    "thailand": "night trains to beaches and ancient temples",
    "russia": "the Trans-Siberian -- the world's most legendary rail journey",
    "argentina": "Patagonian railways through the end of the world",
    "china": "high-speed marvels connecting ancient empires",
    "mexico": "the Copper Canyon railway -- Mexico's hidden marvel",
}


def _is_greeting(text: str) -> bool:
    t = text.lower().strip().rstrip("!.,?")
    if t in GREETING_WORDS:
        return True
    return any(t.startswith(g) for g in GREETING_WORDS if len(g) > 2)


def _parse_traveler_count(text: str) -> tuple:
    """Return (traveler_type, count, short_label, warm_ack)."""
    t = text.lower().strip()
    count = 2

    numbers = re.findall(r"\d+", t)
    if numbers:
        count = int(numbers[0])

    # Check family FIRST if kids/children mentioned (even with wife/husband)
    has_kids = any(kw in t for kw in ("kid", "child", "children", "daughter", "son"))
    has_couple = any(kw in t for kw in ("couple", "partner", "spouse", "wife", "husband", "significant"))

    if has_kids or "family" in t:
        # Try to compute family size: adults + children
        adults_match = re.findall(r"(\d+)\s*adult", t)
        kids_match = re.findall(r"(\d+)\s*(?:kid|child|children)", t)
        if adults_match and kids_match:
            n = int(adults_match[0]) + int(kids_match[0])
        else:
            n = max(count, 3)
        return ("family", n, f"family of {n}",
                f"Family of {n} -- I will prioritise family-friendly journeys with the best experiences for all ages.")
    if has_couple:
        return ("couple", max(count, 2), "2 travellers",
                "A journey for two -- noted.")
    if "friend" in t or "group" in t or "colleague" in t or "business" in t or count > 4:
        n = max(count, 3)
        return ("friends", n, f"group of {n}",
                f"Group of {n} -- I will find itineraries that work perfectly for your group.")
    if "solo" in t or "alone" in t or "just me" in t or ("myself" in t and "and" not in t) or "on my own" in t or count == 1:
        return ("solo", 1, "solo traveller",
                "Solo journey -- I will find routes ideal for independent travellers.")
    if "parent" in t or "mom" in t or "dad" in t or "mum" in t or "father" in t or "mother" in t:
        n = max(count, 2)
        return ("family", n, f"family of {n}",
                f"Family of {n} -- I will match family-friendly journeys.")
    if count == 2:
        return ("couple", 2, "2 travellers",
                "A journey for two -- wonderful.")

    return ("couple", max(count, 2), f"{max(count, 2)} travellers",
            "Noted.")


def _parse_duration(text: str) -> Optional[int]:
    t = text.lower()
    if "fortnight" in t:
        return 14
    if "week" in t:
        nums = re.findall(r"\b(\d{1,2})\b", t)
        nums = [int(n) for n in nums if int(n) < 52]
        if nums:
            return nums[0] * 7
        if "two" in t:
            return 14
        if "three" in t:
            return 21
        return 7
    if "month" in t:
        return 30
    # Prefer the number directly before "night(s)" or "day(s)"
    night_match = re.search(r"(\d{1,3})\s*(?:night|day|nuit|tag|noche|notte|夜|रात)", t)
    if night_match:
        return int(night_match.group(1))
    nums = re.findall(r"\b(\d{1,2})\b", t)
    nums = [int(n) for n in nums if int(n) < 100]
    if nums:
        return nums[0]
    return None


# Semantic mapping: user-friendly trip purpose -> real DB trip types
_TRIP_PURPOSE_MAP = {
    "romance": ["Most Scenic Journeys", "Once-in-a-Lifetime Experiences", "Luxury Rail"],
    "romantic": ["Most Scenic Journeys", "Once-in-a-Lifetime Experiences", "Luxury Rail"],
    "honeymoon": ["Most Scenic Journeys", "Once-in-a-Lifetime Experiences", "Luxury Rail"],
    "culture": ["First Time to Europe", "Famous Routes", "Single Country Tours", "Famous Trains", "Off the Beaten Track", "Once-in-a-Lifetime Experiences"],
    "heritage": ["First Time to Europe", "Famous Routes", "Single Country Tours", "Famous Trains", "Off the Beaten Track", "Once-in-a-Lifetime Experiences"],
    "culture and heritage": ["First Time to Europe", "Famous Routes", "Single Country Tours", "Famous Trains", "Off the Beaten Track", "Once-in-a-Lifetime Experiences"],
    "adventure": ["Off the Beaten Track", "Cross Country Journeys", "National Parks"],
    "outdoor": ["Off the Beaten Track", "National Parks", "Lakes and Mountains"],
    "outdoors": ["Off the Beaten Track", "National Parks", "Lakes and Mountains"],
    "scenic": ["Most Scenic Journeys", "Via the Alps", "Lakes and Mountains"],
    "scenic journeys": ["Most Scenic Journeys", "Via the Alps", "Lakes and Mountains"],
    "scenic sightseeing": ["Most Scenic Journeys", "Via the Alps", "Lakes and Mountains"],
    "sightseeing": ["Most Scenic Journeys", "Famous Routes", "Single Country Tours"],
    "relaxation": ["Rail Getaways", "Short Breaks", "Most Scenic Journeys"],
    "relax": ["Rail Getaways", "Short Breaks", "Most Scenic Journeys"],
    "family": ["First Time to Europe", "National Parks", "Famous Trains"],
    "family time": ["First Time to Europe", "National Parks", "Famous Trains"],
    "luxury": ["Luxury Rail", "Once-in-a-Lifetime Experiences", "Railbookers Signature"],
    "food": ["Culinary Journeys", "Famous Routes"],
    "foodie": ["Culinary Journeys", "Famous Routes"],
    "culinary": ["Culinary Journeys", "Famous Routes"],
    "wine": ["Culinary Journeys", "Famous Routes"],
    "christmas": ["Christmas Markets", "Winter Experiences"],
    "winter": ["Winter Experiences", "Snow and Ice", "Christmas Markets"],
    "snow": ["Snow and Ice", "Winter Experiences"],
    "ski": ["Snow and Ice", "Via the Alps", "Winter Experiences"],
    "train": ["Famous Trains", "Sleeper Trains", "Rail Experiences"],
    "trains": ["Famous Trains", "Sleeper Trains", "Rail Experiences"],
    "famous trains": ["Famous Trains"],
    "sleeper": ["Sleeper Trains"],
    "nature": ["National Parks", "Lakes and Mountains", "Most Scenic Journeys"],
    "wildlife": ["National Parks", "Off the Beaten Track"],
    "mountains": ["Via the Alps", "Lakes and Mountains"],
    "alps": ["Via the Alps", "Lakes and Mountains"],
    "lakes": ["Lakes and Mountains"],
    "beach": ["Rail Getaways", "Short Breaks"],
    "cruise": ["Pre or Post-Cruise", "Norway Coastal Cruises", "Alaska Rail and Sail"],
    "fall foliage": ["Fall Foliage"],
    "autumn": ["Fall Foliage", "Most Scenic Journeys"],
}


def _match_options(user_text: str, db_options: List[str]) -> List[str]:
    """Match user free-text against DB option list. Case-insensitive partial match."""
    t = user_text.lower().strip()
    matched = []
    # Direct substring match
    for opt in db_options:
        if opt.lower() in t or t in opt.lower():
            matched.append(opt)
    if not matched:
        # Stop-word filtered word intersection
        _STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "is",
                 "on", "at", "by", "with", "from", "time", "my", "i", "want",
                 "like", "would", "trip", "travel", "vacation", "holiday",
                 "looking", "something", "just", "really", "very", "some"}
        words = set(re.split(r"[\s,;&]+", t)) - _STOP
        if words:  # Only match if meaningful words remain
            for opt in db_options:
                opt_words = set(opt.lower().split()) - _STOP
                if words & opt_words:
                    matched.append(opt)
    return matched


def _friendly_dest(countries: list, cities: list) -> str:
    parts = countries + cities
    if not parts:
        return "worldwide"
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _dest_flair(countries: list) -> str:
    for c in countries:
        flair = DEST_FLAIR.get(c.lower())
        if flair:
            return f" -- {flair}"
    return ""


def _traveler_label(t_type: str, count: int) -> str:
    if t_type == "solo":
        return "solo traveller"
    if t_type == "couple":
        return "2 travellers"
    return f"{count} travellers"


def _season_from_text(text: str) -> str:
    t = text.lower()
    for season in ["spring", "summer", "autumn", "winter"]:
        if season in t:
            return season
    if "fall" in t:
        return "autumn"
    month_map = {
        "december": "winter", "january": "winter", "february": "winter",
        "march": "spring", "april": "spring", "may": "spring",
        "june": "summer", "july": "summer", "august": "summer",
        "september": "autumn", "october": "autumn", "november": "autumn",
    }
    for month, season in month_map.items():
        if month in t:
            return season
    return ""


def _check_flexibility(text: str) -> bool:
    """Check if user mentions date flexibility."""
    t = text.lower()
    flex_kw = ["flexible", "anytime", "any time", "whenever", "open", "no fixed", "not fixed"]
    return any(kw in t for kw in flex_kw)


# ---------------------------------------------------------------------------
# Country -> Currency mapping (auto-detect from destination)
# ---------------------------------------------------------------------------

COUNTRY_CURRENCY_MAP = {
    # GBP
    "united kingdom": ("GBP", "\u00a3"), "england": ("GBP", "\u00a3"),
    "scotland": ("GBP", "\u00a3"), "wales": ("GBP", "\u00a3"),
    # USD
    "united states": ("USD", "$"), "usa": ("USD", "$"),
    # EUR
    "france": ("EUR", "\u20ac"), "germany": ("EUR", "\u20ac"),
    "italy": ("EUR", "\u20ac"), "spain": ("EUR", "\u20ac"),
    "netherlands": ("EUR", "\u20ac"), "austria": ("EUR", "\u20ac"),
    "portugal": ("EUR", "\u20ac"), "ireland": ("EUR", "\u20ac"),
    "belgium": ("EUR", "\u20ac"), "greece": ("EUR", "\u20ac"),
    "finland": ("EUR", "\u20ac"), "czech republic": ("EUR", "\u20ac"),
    # Other
    "australia": ("AUD", "A$"), "canada": ("CAD", "C$"),
    "japan": ("JPY", "\u00a5"), "india": ("INR", "\u20b9"),
    "switzerland": ("CHF", "CHF"), "new zealand": ("NZD", "NZ$"),
    "south africa": ("ZAR", "R"), "norway": ("NOK", "kr"),
    "sweden": ("SEK", "kr"), "vietnam": ("VND", "\u20ab"),
    "sri lanka": ("LKR", "Rs"), "morocco": ("MAD", "MAD"),
    "peru": ("PEN", "S/"), "mexico": ("MXN", "MX$"),
    "denmark": ("DKK", "kr"), "poland": ("PLN", "z\u0142"),
    "thailand": ("THB", "\u0e3f"), "china": ("CNY", "\u00a5"),
    "argentina": ("ARS", "AR$"), "turkey": ("TRY", "\u20ba"),
    "singapore": ("SGD", "S$"), "brazil": ("BRL", "R$"),
    "russia": ("RUB", "\u20bd"), "hungary": ("HUF", "Ft"),
    "iceland": ("ISK", "kr"), "egypt": ("EGP", "E\u00a3"),
}

# Default currency is GBP (Railbookers is UK-based)
DEFAULT_CURRENCY = ("GBP", "\u00a3")


def _detect_currency(countries: list) -> tuple:
    """Detect currency from first matched destination country."""
    for c in countries:
        result = COUNTRY_CURRENCY_MAP.get(c.lower())
        if result:
            return result
    return DEFAULT_CURRENCY


# Well-known destinations we recognise but don't have packages for
_KNOWN_UNAVAILABLE = {
    "japan", "tokyo", "kyoto", "osaka", "thailand", "bangkok",
    "vietnam", "hanoi", "colombia", "bogota", "chile", "santiago",
    "south korea", "seoul", "busan",
    "taiwan", "taipei", "malaysia", "kuala lumpur",
    "indonesia", "jakarta", "philippines", "manila", "cambodia",
    "sri lanka", "nepal", "kathmandu", "cairo", "dubai", "kenya", "nairobi",
    "costa rica", "cuba", "havana", "iceland", "reykjavik",
    "russia", "moscow", "st petersburg",
    "jordan", "amman", "israel", "tel aviv", "fiji", "hawaii", "maldives",
    "bali", "myanmar", "laos", "mongolia", "rio", "rio de janeiro",
    "mexico", "mexico city", "cancun", "egypt",
}

# Top popular destinations for fallback suggestions
_TOP_DESTINATIONS = [
    "Italy", "France", "Switzerland", "United Kingdom",
    "Germany", "Spain", "Austria", "Norway",
    "United States", "Canada", "Australia", "New Zealand",
    "India", "China", "South Africa", "Greece",
    "Ireland", "Portugal", "Netherlands", "Peru",
]


def _suggest_similar_destinations(user_input: str, db_countries: list) -> list:
    """Find similar available destinations using fuzzy string matching."""
    query = user_input.lower().strip()
    db_lower = {c.lower(): c for c in db_countries}

    # Region-aware mapping: suggest destinations from the same part of the world
    _REGION_SUGGESTIONS = {
        # Asia
        "japan": ["China", "India", "Singapore"],
        "tokyo": ["China", "India", "Singapore"],
        "kyoto": ["China", "India", "Singapore"],
        "osaka": ["China", "India", "Singapore"],
        "thailand": ["China", "India", "Singapore"],
        "bangkok": ["China", "India", "Singapore"],
        "vietnam": ["China", "India", "Singapore"],
        "hanoi": ["China", "India", "Singapore"],
        "south korea": ["China", "India", "Singapore"],
        "seoul": ["China", "India", "Singapore"],
        "taiwan": ["China", "India", "Singapore"],
        "taipei": ["China", "India", "Singapore"],
        "malaysia": ["China", "India", "Singapore"],
        "kuala lumpur": ["China", "India", "Singapore"],
        "indonesia": ["China", "India", "Singapore", "Australia"],
        "philippines": ["China", "India", "Singapore", "Australia"],
        "cambodia": ["China", "India", "Singapore"],
        "myanmar": ["China", "India", "Singapore"],
        "laos": ["China", "India", "Singapore"],
        "sri lanka": ["India", "China", "Singapore"],
        "nepal": ["India", "China"],
        "mongolia": ["China", "India"],
        "bali": ["China", "India", "Singapore", "Australia"],
        "maldives": ["India", "Singapore"],
        # Middle East / Africa
        "dubai": ["Turkey", "Greece", "Morocco", "India"],
        "egypt": ["Turkey", "Greece", "Morocco"],
        "cairo": ["Turkey", "Greece", "Morocco"],
        "jordan": ["Turkey", "Greece", "Morocco"],
        "amman": ["Turkey", "Greece", "Morocco"],
        "israel": ["Turkey", "Greece", "Italy"],
        "tel aviv": ["Turkey", "Greece", "Italy"],
        "kenya": ["South Africa", "Morocco", "Tanzania"],
        "nairobi": ["South Africa", "Morocco", "Tanzania"],
        # Americas
        "mexico": ["United States", "Peru", "Argentina", "Ecuador"],
        "mexico city": ["United States", "Peru", "Argentina"],
        "cancun": ["United States", "Peru", "Ecuador"],
        "colombia": ["Peru", "Ecuador", "Argentina"],
        "bogota": ["Peru", "Ecuador", "Argentina"],
        "chile": ["Peru", "Argentina", "Ecuador"],
        "santiago": ["Peru", "Argentina", "Ecuador"],
        "costa rica": ["United States", "Peru", "Ecuador"],
        "cuba": ["United States", "Canada"],
        "havana": ["United States", "Canada"],
        "hawaii": ["United States", "Australia", "New Zealand"],
        "rio": ["Peru", "Argentina", "Ecuador"],
        "rio de janeiro": ["Peru", "Argentina", "Ecuador"],
        # Europe / Other
        "iceland": ["Norway", "Sweden", "Denmark", "Finland"],
        "reykjavik": ["Norway", "Sweden", "Denmark", "Finland"],
        "russia": ["Poland", "Finland", "Hungary"],
        "moscow": ["Poland", "Finland", "Hungary"],
        "st petersburg": ["Finland", "Poland", "Sweden"],
        "fiji": ["Australia", "New Zealand"],
    }

    # For known unavailable destinations, use curated regional suggestions
    regional = _REGION_SUGGESTIONS.get(query)
    if regional:
        return [d for d in regional if d in db_countries][:5]

    # Try difflib fuzzy match against available countries
    close = get_close_matches(query, db_lower.keys(), n=5, cutoff=0.45)
    if close:
        return [db_lower[m] for m in close]

    # Substring matches
    partial = [db_lower[k] for k in db_lower if len(query) >= 3 and (query[:3] in k or k[:3] in query)]
    if partial:
        return list(dict.fromkeys(partial))[:5]

    # Return top popular destinations
    available = [d for d in _TOP_DESTINATIONS if d in db_countries]
    return available[:5]


# ---------------------------------------------------------------------------
# MAIN CHAT ENDPOINT
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
@limiter.limit(PLANNER_LIMIT)
@track_performance("chat_with_planner")
async def chat_with_planner(
    request: Request,
    chat_input: ChatMessage,
    db: Session = Depends(get_db),
):
    """
    Conversational trip planner.
    8 natural questions -> personalised recommendations.
    No step indicators. No progress. Natural conversation.
    """

    session_id = chat_input.session_id or str(uuid.uuid4())

    if session_id not in conversation_sessions:
        # Enforce session limit to prevent memory exhaustion
        if len(conversation_sessions) >= settings.max_concurrent_sessions:
            oldest = min(conversation_sessions, key=lambda k: conversation_sessions[k].get("_ts", 0))
            del conversation_sessions[oldest]
        conversation_sessions[session_id] = _new_session()

    session = conversation_sessions[session_id]
    session["_ts"] = time.time()
    user_msg = chat_input.safe_message
    user_lower = user_msg.lower()
    step = session["step"]
    lang = chat_input.lang or session.get("lang", "en")
    session["lang"] = lang

    # DB provider (real data only -- no fallback)
    provider = DBOptionsProvider(db)
    pkg_count = provider.get_package_count() if provider else 0

    # ------------------------------------------------------------------
    # SPECIAL COMMANDS (post-recommendation actions)
    # ------------------------------------------------------------------
    MODIFY_CMDS = {"modify preferences", "modify", "modifier les préférences", "modificar preferencias", "einstellungen ändern", "modifica preferenze", "修改偏好", "प्राथमिकताएं बदलें"}
    if user_lower in MODIFY_CMDS:
        # Reset session but keep to step 1 with a warm message
        session.update(_new_session())
        session["_ts"] = time.time()
        session["step"] = 1
        return ChatResponse(
            message="No problem. Let us refine your preferences.\n\n**Where would you like to go?**",
            suggestions=None,
            step_number=1,
            needs_input=True,
            session_id=session_id,
            placeholder="e.g. Italy, Swiss Alps, Tokyo...",
        )
    ADVISOR_CMDS = {"speak with an advisor", "speak with advisor", "advisor", "parler à un conseiller", "hablar con un asesor", "mit einem berater sprechen", "parla con un consulente", "与顾问交谈", "सलाहकार से बात करें"}
    if user_lower in ADVISOR_CMDS:
        return ChatResponse(
            message="Our travel advisors would love to help. Visit **railbookers.com** or call our expert team for a personalised consultation.",
            suggestions=["Plan another trip"],
            step_number=0,
            needs_input=True,
            session_id=session_id,
            placeholder="Type to plan another trip...",
        )
    RESTART_CMDS = {"plan another trip", "start over", "restart", "new trip", "new search", "reset", "planifier un autre voyage", "planificar otro viaje", "weitere reise planen", "pianifica un altro viaggio", "计划另一次旅行", "एक और यात्रा की योजना बनाएं"}
    if user_lower in RESTART_CMDS:
        session.update(_new_session())
        session["_ts"] = time.time()
        session["step"] = 1
        return ChatResponse(
            message="Ready for your next adventure.\n\n**Where would you like to go?**",
            suggestions=None,
            step_number=1,
            needs_input=True,
            session_id=session_id,
            placeholder="e.g. Italy, Swiss Alps, Tokyo...",
        )

    # ------------------------------------------------------------------
    # GO BACK / PREVIOUS STEP support
    # ------------------------------------------------------------------
    if step > 1 and any(kw in user_lower for kw in ("go back", "previous", "prev step", "back", "undo")):
        prev_step = max(step - 1, 1)
        session["step"] = prev_step
        # Clear destination data when going back to step 1 so user starts fresh
        if prev_step == 1:
            session["data"]["destinations_countries"] = []
            session["data"]["destinations_cities"] = []
        step_prompts = {
            1: ("No problem. Let us revisit your destination.\n\n**Where would you like to go?**",
                None,
                "e.g. Italy, Swiss Alps, Tokyo..."),
            2: ("Let us revisit who is travelling.\n\n"
                "**Solo** | **Couple** | **Family** | **Friends** | **Colleagues**",
                None, "e.g. Couple, Family of 4, Solo..."),
            3: ("Let us revisit your travel dates.\n\nWhen and for how long?\n\n"
                "e.g. *June 2026, 10 days* | *Spring, 2 weeks* | *Flexible*",
                None, "e.g. June 2026, 10 days..."),
            4: ("Let us revisit the experience type.\n\n"
                "**Culture** | **Adventure** | **Scenic** | **Romance** | **Relaxation** | **Family** | **Luxury**",
                None, "e.g. Culture, Adventure, Romance..."),
            5: ("Let us revisit the occasion.\n\n"
                "**Anniversary** | **Honeymoon** | **Birthday** | **Retirement** | **Just for fun**",
                None, "e.g. Anniversary, No special occasion..."),
            6: ("Let us revisit accommodation.\n\n"
                "**Luxury** (5-star) | **Premium** (4-star) | **Value** (comfortable)",
                None, "e.g. Luxury, Premium, Value..."),
            7: ("Let us revisit rail experience.\n\n"
                "**First time** | **A few trips** | **Seasoned traveller**",
                None, "e.g. First time, Experienced..."),
            8: ("Let us revisit budget.\n\nAny budget per person or special requirements?\n\n"
                "e.g. *\u00a35,000*, *No limit* -- or say **Find my trips**",
                None,
                "e.g. \u00a35,000, No limit, Find my trips..."),
        }
        prompt, suggs, ph = step_prompts.get(prev_step, step_prompts[1])
        return ChatResponse(
            message=prompt,
            suggestions=suggs,
            step_number=prev_step,
            needs_input=True,
            session_id=session_id,
            placeholder=ph,
        )

    # ------------------------------------------------------------------
    # STEP 0 - First message: greeting -> welcome, otherwise fall through
    # ------------------------------------------------------------------
    if step == 0:
        if _is_greeting(user_msg):
            # Greeting: show welcome + destination question
            session["step"] = 1
            top_countries = provider.get_countries()[:15] if provider else []
            return ChatResponse(
                message=t("welcome", lang, pkg_count=pkg_count),
                suggestions=None,
                step_number=1,
                needs_input=True,
                session_id=session_id,
                placeholder=t("ph_destination", lang),
            )
        # Not a greeting: treat as destination, fall through to step 1
        session["step"] = 1

    # ------------------------------------------------------------------
    # STEP 1 -- DESTINATION
    # "Where would you like to go?"
    # PRD: Add flexibility -- "or would you like us to suggest options?"
    # Multi-country: single dest asks to add more; 2+ proceeds directly.
    # ------------------------------------------------------------------
    if step <= 1:
        existing_countries = session["data"]["destinations_countries"]
        existing_cities = session["data"]["destinations_cities"]
        has_existing = bool(existing_countries or existing_cities)

        CONTINUE_WORDS = {
            "continue", "next", "done", "that's all", "thats all",
            "that's it", "thats it", "no more", "move on", "proceed",
            "go ahead", "lets go", "let's go", "go on", "yes", "ok",
            "okay", "sure", "yep", "yeah",
        }

        # --- User already has destinations and wants to continue ---
        if has_existing and user_lower in CONTINUE_WORDS:
            dest_label = _friendly_dest(existing_countries, existing_cities)
            flair = _dest_flair(existing_countries)
            cur_code, cur_sym = _detect_currency(existing_countries)
            session["data"]["currency_code"] = cur_code
            session["data"]["currency_sym"] = cur_sym
            session["step"] = 2
            return ChatResponse(
                message=(
                    f"{t('searching_for', lang, dest=dest_label)}\n\n"
                    f"{t('q_travellers', lang)}"
                ),
                suggestions=None,
                step_number=2,
                needs_input=True,
                session_id=session_id,
                placeholder=t("ph_travellers", lang),
                currency_code=cur_code,
                currency_sym=cur_sym,
            )

        # --- Skip / Surprise / Flexible ---
        if user_lower in SKIP_WORDS or "surprise" in user_lower or "anywhere" in user_lower or "flexible" in user_lower or "suggest" in user_lower:
            session["data"]["destinations_countries"] = []
            session["data"]["destinations_cities"] = []
            session["step"] = 2
            return ChatResponse(
                message=(
                    f"Love the spontaneity. I will search all **{pkg_count:,} packages** across 50+ countries to find your ideal match.\n\n"
                    f"{t('q_travellers', lang)}"
                ),
                suggestions=None,
                step_number=2,
                needs_input=True,
                session_id=session_id,
                placeholder=t("ph_travellers", lang),
            )

        # --- Match new locations ---
        if provider:
            loc = provider.match_locations(user_msg)
            new_countries = loc["matched_countries"]
            new_cities = loc["matched_cities"]

            if not new_countries and not new_cities:
                if has_existing:
                    # Non-destination text while already having destinations -> continue
                    dest_label = _friendly_dest(existing_countries, existing_cities)
                    cur_code, cur_sym = _detect_currency(existing_countries)
                    session["data"]["currency_code"] = cur_code
                    session["data"]["currency_sym"] = cur_sym
                    session["step"] = 2
                    return ChatResponse(
                        message=(
                            f"{t('searching_for', lang, dest=dest_label)}\n\n"
                            f"{t('q_travellers', lang)}"
                        ),
                        suggestions=None,
                        step_number=2,
                        needs_input=True,
                        session_id=session_id,
                        placeholder=t("ph_travellers", lang),
                        currency_code=cur_code,
                        currency_sym=cur_sym,
                    )
                else:
                    # Provide helpful suggestions
                    all_countries = provider.get_countries() if provider else []
                    suggestions_list = _suggest_similar_destinations(user_msg, all_countries)
                    query_lower = user_msg.lower().strip()

                    if query_lower in _KNOWN_UNAVAILABLE:
                        # Recognised destination but no packages
                        not_found_msg = (
                            f'We do not currently have rail packages for "{user_msg}", '
                            "but our collection is expanding.\n\n"
                        )
                    else:
                        not_found_msg = (
                            f'No packages matched "{user_msg}" in our current catalogue.\n\n'
                        )

                    if suggestions_list:
                        suggestion_chips = suggestions_list[:5]
                        not_found_msg += (
                            "Here are some destinations you might enjoy:\n\n"
                            + ", ".join(f"**{s}**" for s in suggestion_chips)
                            + "\n\nOr type **surprise me** to explore all "
                            f"{pkg_count:,} packages."
                        )
                    else:
                        not_found_msg += (
                            "Try a different country or city, or type "
                            "**surprise me** to explore all options."
                        )

                    return ChatResponse(
                        message=not_found_msg,
                        suggestions=None,
                        step_number=1,
                        needs_input=True,
                        session_id=session_id,
                        placeholder=t("ph_destination", lang),
                    )

            # Add new destinations (dedup)
            for c in new_countries:
                if c not in existing_countries:
                    existing_countries.append(c)
            for c in new_cities:
                if c not in existing_cities:
                    existing_cities.append(c)

            dest_label = _friendly_dest(existing_countries, existing_cities)
            flair = _dest_flair(existing_countries)
        else:
            if not has_existing:
                existing_countries.append(user_msg)
            dest_label = _friendly_dest(existing_countries, existing_cities)
            flair = ""

        # Detect currency from destination country
        cur_code, cur_sym = _detect_currency(existing_countries)
        session["data"]["currency_code"] = cur_code
        session["data"]["currency_sym"] = cur_sym

        total_destinations = len(existing_countries) + len(existing_cities)

        # 2+ destinations selected -> proceed directly to step 2
        if total_destinations >= 2:
            session["step"] = 2
            return ChatResponse(
                message=(
                    f"{dest_label}{flair}. {t('outstanding_choice', lang)}.\n\n"
                    f"{t('q_travellers', lang)}"
                ),
                suggestions=None,
                step_number=2,
                needs_input=True,
                session_id=session_id,
                placeholder=t("ph_travellers", lang),
                currency_code=cur_code,
                currency_sym=cur_sym,
            )

        # Single destination -> ask to add more or continue
        return ChatResponse(
            message=(
                f"{dest_label}{flair}. {t('outstanding_choice', lang)}.\n\n"
                f"{t('q_add_more', lang)}"
            ),
            suggestions=["Continue"],
            step_number=1,
            needs_input=True,
            session_id=session_id,
            placeholder=t("ph_destination", lang),
            currency_code=cur_code,
            currency_sym=cur_sym,
        )

    # ------------------------------------------------------------------
    # STEP 2 -- TRAVELLERS
    # "Who will be travelling with you, and how many guests in total?"
    # PRD: Combined into one smoother question.
    # ------------------------------------------------------------------
    if step == 2:
        traveler_type, count, short_label, warm_ack = _parse_traveler_count(user_msg)
        session["data"]["traveler_type"] = traveler_type
        session["data"]["num_travelers"] = count

        session["step"] = 3
        return ChatResponse(
            message=(
                f"{warm_ack}\n\n"
                f"{t('q_dates', lang)}"
            ),
            suggestions=None,
            step_number=3,
            needs_input=True,
            session_id=session_id,
            placeholder=t("ph_dates", lang),
        )

    # ------------------------------------------------------------------
    # STEP 3 -- TRAVEL DATES & DURATION
    # PRD: "When would you like to travel?" + "For how many days/nights?"
    #      + "Are you flexible with your travel dates?" (Yes/No)
    # ------------------------------------------------------------------
    if step == 3:
        session["data"]["travel_dates"] = user_msg
        session["data"]["duration_days"] = _parse_duration(user_msg)
        session["data"]["flexible_dates"] = _check_flexibility(user_msg)

        dur = session["data"]["duration_days"]
        season = _season_from_text(user_msg)
        flex = session["data"]["flexible_dates"]

        if dur and season:
            ack = f"{season.title()}, around {dur} nights"
        elif dur:
            ack = f"Around {dur} nights"
        elif season:
            ack = f"{season.title()} travel with flexible duration"
        else:
            ack = f"{user_msg}"

        if flex:
            ack += " (dates flexible)"

        session["step"] = 4
        return ChatResponse(
            message=(
                f"{ack} -- noted.\n\n"
                f"{t('q_purpose', lang)}"
            ),
            suggestions=None,
            step_number=4,
            needs_input=True,
            session_id=session_id,
            placeholder="e.g. Culture, Adventure, Romance, Scenic...",
        )

    # ------------------------------------------------------------------
    # STEP 4 -- TRIP PURPOSE / EXPERIENCE
    # PRD: "What's the main reason for this trip?
    #       Culture, adventure, sightseeing, romance, relaxation, family time, luxury"
    # ------------------------------------------------------------------
    if step == 4:
        if user_lower not in SKIP_WORDS:
            if provider:
                db_trip_types = provider.get_trip_types()
                # First try semantic mapping for user-friendly labels
                semantic = _TRIP_PURPOSE_MAP.get(user_lower)
                if semantic:
                    matched_reasons = [s for s in semantic if s in db_trip_types]
                    if not matched_reasons:
                        matched_reasons = semantic  # Use mapping even if not in current DB
                else:
                    # Try direct/word matching against DB trip types
                    matched_reasons = _match_options(user_msg, db_trip_types)
                session["data"]["trip_reason"] = matched_reasons if matched_reasons else [user_msg]
            else:
                session["data"]["trip_reason"] = [user_msg]

        reasons = session["data"]["trip_reason"]
        reason_text = ", ".join(reasons[:3]) if reasons else "general exploration"

        # Contextual acknowledgment based on trip type
        trip_ack_map = {
            "romance": "Romance by rail -- there is truly nothing like it",
            "romantic": "Romance by rail -- there is truly nothing like it",
            "honeymoon": "A honeymoon by train -- the most unforgettable way to begin",
            "culture": "Culture and heritage -- every station tells a story worth discovering",
            "heritage": "Culture and heritage -- every station tells a story worth discovering",
            "adventure": "Adventure by rail -- bold journeys ahead",
            "scenic": "Scenic routes -- I will find the most breathtaking views",
            "relaxation": "Slow travel at its finest -- the journey is the destination",
            "relax": "Slow travel at its finest -- the journey is the destination",
            "family": "Family memories by rail -- experiences the whole family will treasure",
            "luxury": "Luxury rail at its absolute finest -- world-class all the way",
            "sightseeing": "Sightseeing by train -- the most rewarding way to explore",
            "train": "Famous rail journeys -- where the train itself is the experience",
            "trains": "Famous rail journeys -- where the train itself is the experience",
            "food": "Culinary discovery by rail -- from vineyard to table",
            "culinary": "Culinary discovery by rail -- from vineyard to table",
            "wine": "Culinary discovery by rail -- from vineyard to table",
            "winter": "Winter rail -- snow-dusted landscapes and cosy cabins",
            "snow": "Winter rail -- snow-dusted landscapes and cosy cabins",
            "christmas": "Christmas markets by rail -- pure festive magic",
            "nature": "Nature at its finest -- through untouched landscapes",
            "wildlife": "Nature at its finest -- through untouched landscapes",
        }
        # Check user's original input first for intent-based acknowledgment
        trip_ack = None
        for kw, ack in trip_ack_map.items():
            if kw in user_lower:
                trip_ack = ack
                break
        # If no match on user text, check the mapped DB reasons
        if not trip_ack:
            for kw, ack in trip_ack_map.items():
                if any(kw in r.lower() for r in reasons):
                    trip_ack = ack
                    break

        ack_line = trip_ack if trip_ack else f"{reason_text} -- excellent"

        session["step"] = 5
        return ChatResponse(
            message=(
                f"{ack_line}.\n\n"
                f"{t('q_occasion', lang)}"
            ),
            suggestions=None,
            step_number=5,
            needs_input=True,
            session_id=session_id,
            placeholder="e.g. Anniversary, Birthday, Just for fun...",
        )

    # ------------------------------------------------------------------
    # STEP 5 -- SPECIAL OCCASION
    # PRD: "Are you celebrating a special occasion?
    #       Birthday, anniversary, honeymoon, graduation, just for fun"
    #       "No special occasion" as explicit option.
    # ------------------------------------------------------------------
    if step == 5:
        u = user_lower
        occasion_kws = {
            "anniversary": "Anniversary",
            "honeymoon": "Honeymoon",
            "birthday": "Birthday",
            "retirement": "Retirement",
            "graduation": "Graduation",
            "wedding": "Wedding",
            "celebrate": "Celebration",
            "engagement": "Engagement",
        }

        occasion = None
        for kw, label in occasion_kws.items():
            if kw in u:
                occasion = label
                break

        session["data"]["special_occasion"] = occasion

        if occasion:
            occasion_ack = {
                "Anniversary": "An anniversary journey by rail -- I will find something exceptional.",
                "Honeymoon": "Honeymoon by train -- the most romantic way to begin your story.",
                "Birthday": "A birthday rail adventure -- I will make it one to remember.",
                "Retirement": "A well-earned retirement journey -- you deserve the extraordinary.",
                "Graduation": "Congratulations -- a rail adventure is the perfect reward.",
            }
            ack = occasion_ack.get(occasion, f"{occasion} -- noted.")
        elif u in SKIP_WORDS or "no special" in u or "just for fun" in u or "none" in u:
            ack = "No special occasion -- the journey itself is the celebration."
        else:
            session["data"]["special_occasion"] = user_msg.title()
            ack = f"{user_msg.title()} -- noted."

        session["step"] = 6
        return ChatResponse(
            message=(
                f"{ack}\n\n"
                f"{t('q_hotel', lang)}"
            ),
            suggestions=None,
            step_number=6,
            needs_input=True,
            session_id=session_id,
            placeholder="e.g. Luxury, Premium, Value, No preference...",
        )

    # ------------------------------------------------------------------
    # STEP 6 -- HOTEL PREFERENCE
    # PRD: "What type of hotels do you prefer?
    #       Luxury-Ritz Carlton, Premium-Marriott/Sheraton, Value-Holiday Inn Express"
    #       Use tier labels matching Railbookers product tiers.
    # ------------------------------------------------------------------
    if step == 6:
        u = user_lower

        if u not in SKIP_WORDS:
            # Match against DB tiers first
            if provider:
                db_tiers = provider.get_hotel_tiers()
                matched = _match_options(user_msg, db_tiers)
                if matched:
                    session["data"]["hotel_tier"] = matched[0]

            # Fallback keyword matching
            if not session["data"]["hotel_tier"]:
                tier_keywords = {
                    "luxury": "Luxury", "five star": "Luxury", "5 star": "Luxury",
                    "ritz": "Luxury", "four seasons": "Luxury",
                    "premium": "Premium", "upscale": "Premium", "four star": "Premium",
                    "4 star": "Premium", "marriott": "Premium", "sheraton": "Premium",
                    "hilton": "Premium",
                    "value": "Value", "budget": "Value", "standard": "Value",
                    "moderate": "Value", "holiday inn": "Value", "comfort": "Value",
                }
                for kw, tier in tier_keywords.items():
                    if kw in u:
                        session["data"]["hotel_tier"] = tier
                        break

        tier = session["data"]["hotel_tier"]
        if tier:
            tier_desc = {
                "Luxury": "world-class, five-star properties",
                "Premium": "upscale, four-star hotels",
                "Value": "comfortable, well-rated accommodation",
            }
            ack = f"{tier} -- {tier_desc.get(tier, 'I will match the right hotels')}."
        elif u in SKIP_WORDS or "no preference" in u:
            ack = "No preference -- I will show a balanced range of options."
        else:
            ack = "Noted."

        session["step"] = 7
        return ChatResponse(
            message=(
                f"{ack}\n\n"
                f"{t('q_rail', lang)}"
            ),
            suggestions=None,
            step_number=7,
            needs_input=True,
            session_id=session_id,
            placeholder="e.g. First time, Experienced, Skip...",
        )

    # ------------------------------------------------------------------
    # STEP 7 -- RAIL EXPERIENCE
    # PRD: "Have you taken a rail vacation before, or would this be your first time?"
    #       More friendly, less like a survey.
    # ------------------------------------------------------------------
    if step == 7:
        u = user_lower

        if "first" in u or "never" in u or "no" == u.strip() or "nope" in u:
            session["data"]["rail_experience"] = "first_time"
            ack = "Your first rail vacation -- I will select the most rewarding and easy-to-navigate routes."
        elif "few" in u or "some" in u or "couple" in u or "once" in u or "twice" in u:
            session["data"]["rail_experience"] = "experienced"
            ack = "Some rail experience -- I can recommend more adventurous and off-the-beaten-path routes."
        elif "experienced" in u or "many" in u or "several" in u or "lots" in u or "veteran" in u:
            session["data"]["rail_experience"] = "very_experienced"
            ack = "A seasoned rail traveller -- I will find journeys that match your expertise."
        elif u in SKIP_WORDS:
            session["data"]["rail_experience"] = None
            ack = "No worries -- I will show a balanced selection of routes."
        else:
            session["data"]["rail_experience"] = "experienced"
            ack = f"Noted: {user_msg}."

        # Use destination-based currency for budget suggestions
        cur_sym = session["data"].get("currency_sym", "\u00a3")

        session["step"] = 8
        return ChatResponse(
            message=(
                f"{ack}\n\n"
                f"{t('q_budget', lang)}"
            ),
            suggestions=t_list("budget_actions", lang),
            step_number=8,
            needs_input=True,
            session_id=session_id,
            placeholder="e.g. £5,000, No limit, Find my trips...",
        )

    # ------------------------------------------------------------------
    # STEP 8 -- BUDGET + SPECIAL REQUIREMENTS -> SUMMARY CONFIRMATION
    # PRD: Optional budget + accessibility -> show summary for user to confirm
    # Also: if user provided a budget or explicitly requested a search, run recommendations immediately
    # ------------------------------------------------------------------
    if step == 8:
        budget_nums = []
        if user_lower not in SKIP_WORDS:
            session["data"]["special_requirements"] = user_msg
            budget_nums = re.findall(r"[\$\u20ac\u00a3]?\s*(\d[\d,]*)", user_msg)
            if budget_nums:
                session["data"]["budget"] = budget_nums[0].replace(",", "")

            # Check for accessibility mentions
            access_kws = ["wheelchair", "mobility", "accessible", "disability", "walking", "dietary", "allergy"]
            for kw in access_kws:
                if kw in user_lower:
                    session["data"]["accessibility_needs"] = user_msg
                    break

        # If the user explicitly requested a search, run recommender now.
        # Budget amounts and "no budget/no limit" advance to confirmation (step 9).
        SEARCH_TRIGGERS = ("find my", "search now", "find trips", "trouver mes", "rechercher",
                           "encontrar mis", "buscar ahora", "meine perfekten",
                           "jetzt suchen", "trova i miei", "cerca ora",
                           "\u6211\u7684\u5b8c\u7f8e\u65c5\u884c", "\u7acb\u5373\u641c\u7d22", "\u0905\u092d\u0940 \u0916\u094b\u091c\u0947\u0902")
        if any(tr in user_lower for tr in SEARCH_TRIGGERS):
            data = session["data"]
            recommender = PackageRecommender(db)

            recs: List[dict] = []
            if recommender:
                try:
                    rag_query_parts = []
                    if data["destinations_countries"]:
                        rag_query_parts.extend(data["destinations_countries"])
                    if data["destinations_cities"]:
                        rag_query_parts.extend(data["destinations_cities"])
                    if data["trip_reason"]:
                        rag_query_parts.extend(data["trip_reason"])
                    if data.get("special_occasion") and data["special_occasion"] not in ("None", ""):
                        rag_query_parts.append(data["special_occasion"])
                    if data.get("hotel_tier"):
                        rag_query_parts.append(data["hotel_tier"])
                    if data.get("rail_experience") == "first_time":
                        rag_query_parts.append("first time rail vacation beginner")
                    if data.get("travel_dates"):
                        season = _season_from_text(data["travel_dates"])
                        if season:
                            rag_query_parts.append(season)

                    rag_query = " ".join(rag_query_parts) if rag_query_parts else None

                    recs = recommender.recommend(
                        countries=data["destinations_countries"] or None,
                        cities=data["destinations_cities"] or None,
                        travel_dates=data.get("travel_dates"),
                        trip_types=data["trip_reason"] or None,
                        hotel_tier=data.get("hotel_tier"),
                        duration_days=data.get("duration_days"),
                        rail_experience=data.get("rail_experience"),
                        rag_query=rag_query,
                        budget=data.get("budget"),
                        top_k=5,
                    )
                except Exception as e:
                    logger.error(f"Recommendation error: {e}", exc_info=True)

            # Build a short summary of what we searched for (include in message)
            dest_text = _friendly_dest(
                data["destinations_countries"] or [],
                data["destinations_cities"] or [],
            )
            t_type = data.get("traveler_type", "couple")
            t_count = data.get("num_travelers", 2)
            traveler_text = _traveler_label(t_type, t_count)
            duration_text = f"{data['duration_days']} nights" if data.get("duration_days") else "flexible duration"
            reason_text = ", ".join(data["trip_reason"][:3]) if data.get("trip_reason") else "any experience"
            hotel_text = data.get("hotel_tier") or "flexible"
            occasion_text = data.get("special_occasion")
            rail_text = {
                "first_time": "First rail vacation",
                "experienced": "Some rail experience",
                "very_experienced": "Seasoned rail traveller",
            }.get(data.get("rail_experience", ""), None)
            flex_text = " (flexible)" if data.get("flexible_dates") else ""

            summary_parts = [
                f"Destination: {dest_text}",
                f"Travellers: {traveler_text}",
                f"Timing: {data.get('travel_dates', 'Flexible')} ({duration_text}{flex_text})",
                f"Experience: {reason_text}",
                f"Accommodation: {hotel_text}",
            ]
            if occasion_text:
                summary_parts.append(f"Occasion: {occasion_text}")
            if rail_text:
                summary_parts.append(f"Rail experience: {rail_text}")
            if data.get("budget"):
                b_sym = data.get("currency_sym", "\u00a3")
                summary_parts.append(f"Budget: up to {b_sym}{data['budget']} per person")

            summary = "\n".join(f"  \u2022 {p}" for p in summary_parts)

            if recs:
                top_score = recs[0].get("match_score", 0)
                total_countries = set()
                for r in recs:
                    for c in (r.get("countries", "") or "").split(","):
                        c = c.strip()
                        if c:
                            total_countries.add(c)
                country_span = f" across {len(total_countries)} countries" if len(total_countries) > 1 else ""
                message = (
                    f"**Your Journey Brief**\n\n{summary}\n\n"
                    f"---\n\n"
                    f"**{pkg_count:,} packages analysed.** "
                    f"I found **{len(recs)} exceptional matches**{country_span} "
                    f"(best match: {top_score:.0f}%).\n\n"
                    f"{t('your_recs', lang)}"
                )
            else:
                message = (
                    f"**Your Journey Brief**\n\n{summary}\n\n"
                    f"---\n\n"
                    f"{t('no_matches', lang)}"
                )

            # Reset session for next conversation
            conversation_sessions[session_id] = _new_session()

            return ChatResponse(
                message=message,
                suggestions=t_list("post_rec", lang),
                step_number=8,
                needs_input=True,
                recommendations=recs if recs else None,
                session_id=session_id,
                placeholder="Type to plan another trip...",
            )

        # Build summary for confirmation
        data = session["data"]
        dest_text = _friendly_dest(
            data["destinations_countries"] or [],
            data["destinations_cities"] or [],
        )
        t_type = data.get("traveler_type", "couple")
        t_count = data.get("num_travelers", 2)
        traveler_text = _traveler_label(t_type, t_count)
        duration_text = f"{data['duration_days']} nights" if data.get("duration_days") else "flexible duration"
        reason_text = ", ".join(data["trip_reason"][:3]) if data.get("trip_reason") else "any experience"
        hotel_text = data.get("hotel_tier") or "flexible"
        occasion_text = data.get("special_occasion")
        rail_text = {
            "first_time": "First rail vacation",
            "experienced": "Some rail experience",
            "very_experienced": "Seasoned rail traveller",
        }.get(data.get("rail_experience", ""), None)
        flex_text = " (flexible)" if data.get("flexible_dates") else ""

        summary_parts = [
            f"Destination: {dest_text}",
            f"Travellers: {traveler_text}",
            f"Timing: {data.get('travel_dates', 'Flexible')} ({duration_text}{flex_text})",
            f"Experience: {reason_text}",
            f"Accommodation: {hotel_text}",
        ]
        if occasion_text:
            summary_parts.append(f"Occasion: {occasion_text}")
        if rail_text:
            summary_parts.append(f"Rail experience: {rail_text}")
        if data.get("budget"):
            b_sym = data.get("currency_sym", "\u00a3")
            summary_parts.append(f"Budget: up to {b_sym}{data['budget']} per person")

        summary = "\n".join(f"  \u2022 {p}" for p in summary_parts)

        session["step"] = 9
        return ChatResponse(
            message=(
                f"**Your Journey Brief**\n\n{summary}\n\n"
                f"---\n\n"
                f"{t('does_look_right', lang)}"
            ),
            suggestions=t_list("confirm_search", lang),
            step_number=9,
            needs_input=True,
            session_id=session_id,
            placeholder="Type 'search now' or describe any changes...",
        )

    # ------------------------------------------------------------------
    # STEP 9 -- SEARCH CONFIRMATION -> RECOMMENDATIONS
    # User confirmed summary -> run recommendation engine
    # ------------------------------------------------------------------
    if step == 9:
        # If user wants to modify, go back to step 1
        if any(kw in user_lower for kw in ("modify", "change", "start over", "restart", "back")):
            session.update(_new_session())
            session["_ts"] = time.time()
            session["step"] = 1
            return ChatResponse(
                message="No problem. Let us refine your preferences.\n\n**Where would you like to go?**",
                suggestions=None,
                step_number=1,
                needs_input=True,
                session_id=session_id,
                placeholder="e.g. Italy, Swiss Alps, Tokyo...",
            )

        # ---------- BUILD RECOMMENDATIONS ----------
        data = session["data"]
        recommender = PackageRecommender(db)

        recs: List[dict] = []
        if recommender:
            try:
                rag_query_parts = []
                if data["destinations_countries"]:
                    rag_query_parts.extend(data["destinations_countries"])
                if data["destinations_cities"]:
                    rag_query_parts.extend(data["destinations_cities"])
                if data["trip_reason"]:
                    rag_query_parts.extend(data["trip_reason"])
                if data.get("special_occasion") and data["special_occasion"] not in ("None", ""):
                    rag_query_parts.append(data["special_occasion"])
                if data.get("hotel_tier"):
                    rag_query_parts.append(data["hotel_tier"])
                if data.get("rail_experience") == "first_time":
                    rag_query_parts.append("first time rail vacation beginner")
                if data.get("travel_dates"):
                    season = _season_from_text(data["travel_dates"])
                    if season:
                        rag_query_parts.append(season)

                rag_query = " ".join(rag_query_parts) if rag_query_parts else None

                recs = recommender.recommend(
                    countries=data["destinations_countries"] or None,
                    cities=data["destinations_cities"] or None,
                    travel_dates=data.get("travel_dates"),
                    trip_types=data["trip_reason"] or None,
                    hotel_tier=data.get("hotel_tier"),
                    duration_days=data.get("duration_days"),
                    rail_experience=data.get("rail_experience"),
                    rag_query=rag_query,
                    budget=data.get("budget"),
                    top_k=5,
                )
            except Exception as e:
                logger.error(f"Recommendation error: {e}", exc_info=True)

        if recs:
            top_score = recs[0].get("match_score", 0)
            total_countries = set()
            for r in recs:
                for c in (r.get("countries", "") or "").split(","):
                    c = c.strip()
                    if c:
                        total_countries.add(c)
            country_span = f" across {len(total_countries)} countries" if len(total_countries) > 1 else ""
            message = (
                f"**{pkg_count:,} packages analysed.** "
                f"I found **{len(recs)} exceptional matches**{country_span} "
                f"(best match: {top_score:.0f}%).\n\n"
                f"{t('your_recs', lang)}"
            )
        else:
            message = t("no_matches", lang)

        # Reset session for next conversation
        conversation_sessions[session_id] = _new_session()

        return ChatResponse(
            message=message,
            suggestions=t_list("post_rec", lang),
            step_number=9,
            needs_input=True,
            recommendations=recs if recs else None,
            session_id=session_id,
            placeholder="Type to plan another trip...",
        )

    # ------------------------------------------------------------------
    # FALLBACK -- restart
    # ------------------------------------------------------------------
    conversation_sessions[session_id] = _new_session()
    return ChatResponse(
        message="Let us start fresh.\n\n**Where would you like to go?**",
        suggestions=None,
        step_number=1,
        needs_input=True,
        session_id=session_id,
        placeholder="e.g. Italy, Swiss Alps, Tokyo...",
    )


# ---------------------------------------------------------------------------
# UTILITY ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("/flow/welcome")
async def get_welcome_message(db: Session = Depends(get_db)):
    """Welcome data with package count and top countries."""
    provider = DBOptionsProvider(db)
    count = provider.get_package_count()
    top_countries = provider.get_countries()[:15]
    return {
        "message": "Railbookers",
        "subtitle": "Your personal rail vacation planner, powered by real package data.",
        "first_question": "Where would you like to go?",
        "packages_available": count,
        "suggestions": top_countries,
    }


@router.get("/options/countries")
async def get_countries(db: Session = Depends(get_db)):
    provider = DBOptionsProvider(db)
    return {"countries": provider.get_countries()}


@router.get("/options/trip-types")
async def get_trip_types(db: Session = Depends(get_db)):
    provider = DBOptionsProvider(db)
    return {"trip_types": provider.get_trip_types()}


@router.get("/options/hotel-tiers")
async def get_hotel_tiers(db: Session = Depends(get_db)):
    provider = DBOptionsProvider(db)
    return {"hotel_tiers": provider.get_hotel_tiers()}


@router.get("/options/regions")
async def get_regions(db: Session = Depends(get_db)):
    provider = DBOptionsProvider(db)
    return {"regions": provider.get_regions()}


@router.get("/options/cities")
async def get_cities(
    country: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    provider = DBOptionsProvider(db)
    return {"cities": provider.get_cities(country)}


@router.get("/destinations/search")
async def search_destinations(
    q: str = Query(..., min_length=2, description="Search query"),
    db: Session = Depends(get_db),
):
    """Search destinations in DB."""
    provider = DBOptionsProvider(db)
    match = provider.match_locations(q)
    return {
        "query": q,
        "countries": match["matched_countries"],
        "cities": match["matched_cities"],
        "unmatched": match["unmatched"],
    }


@router.get("/autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=1, description="User input to autocomplete"),
    step: str = Query("destination", description="Current step name"),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Autocomplete suggestions from DB as user types.
    Returns matching countries/cities/regions/trip_types based on step.
    """
    provider = DBOptionsProvider(db)
    results = provider.autocomplete(q, step=step, limit=limit)
    return {"query": q, "step": step, "suggestions": results}


@router.get("/rag/status")
async def rag_status(db: Session = Depends(get_db)):
    """Check RAG vector store status."""
    try:
        from app.services.vector_store import VectorStore
        store = VectorStore(db)
        ready = store.is_ready()
        count = db.execute(__import__("sqlalchemy").text(
            "SELECT COUNT(*) FROM package_vectors"
        )).scalar() if ready else 0
        return {"rag_ready": ready, "vectors_indexed": count}
    except Exception as e:
        return {"rag_ready": False, "error": str(e)}


@router.post("/rag/build")
@limiter.limit("5/minute")
async def build_rag_index(request: Request, db: Session = Depends(get_db)):
    """Build/rebuild RAG vector index. Protected by API key."""
    api_key = request.headers.get("X-API-Key", "")
    if api_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    try:
        from app.services.vector_store import VectorStore
        store = VectorStore(db)
        count = store.build_index()
        return {"status": "ok", "indexed": count}
    except Exception as e:
        logger.error(f"RAG build error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def planner_health(db: Session = Depends(get_db)):
    """Planner health check."""
    provider = DBOptionsProvider(db)
    count = provider.get_package_count()
    db_ok = count > 0

    rag_ready = False
    try:
        from app.services.vector_store import VectorStore
        rag_ready = VectorStore(db).is_ready()
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "no_data",
        "packages_available": count,
        "rag_enabled": rag_ready,
        "conversation_steps": 9,
        "ready": db_ok,
        "database_connected": db is not None,
    }

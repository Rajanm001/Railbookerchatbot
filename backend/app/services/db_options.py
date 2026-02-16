"""
DB-Driven Options Provider
ALL chatbot options come from the database rag_packages table.
All values sourced from the database.

PERFORMANCE: Uses in-memory TTL cache (5 min) to avoid hitting DB
on every request. Options change rarely; cache is auto-refreshed.

Data format in DB (confirmed from live data analysis):
  - included_countries: pipe-delimited  "Italy | Switzerland"
  - included_cities:    pipe-delimited  "Rome | Florence | Milan"
  - included_regions:   pipe-delimited  "Europe | North America"
  - triptype:           pipe-delimited  "Famous Trains | Most Scenic Journeys"
  - profitability_group: plain string   "Packages - High" / "Packages - Standard Margin" / "Packages - Low"
  - duration:           plain number    "11" (nights)
  - departure_type:     plain string    "Anyday" / "Seasonal" / "Fixed"
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import re
import time

from app.db.models import TravelPackage

logger = logging.getLogger(__name__)

# ---- Profitability group -> user-friendly hotel tier label ----
HOTEL_TIER_MAP = {
    "Packages - High": "Luxury",
    "Packages - Standard Margin": "Premium",
    "Packages - Low": "Value",
}
HOTEL_TIER_REVERSE = {v.lower(): k for k, v in HOTEL_TIER_MAP.items()}

# ---- In-memory TTL cache (shared across requests) ----
_CACHE: Dict[str, Any] = {}
_CACHE_TS: Dict[str, float] = {}
_CACHE_TTL = 300  # 5 minutes


def _cached(key: str) -> Any:
    ts = _CACHE_TS.get(key, 0)
    if time.time() - ts < _CACHE_TTL and key in _CACHE:
        return _CACHE[key]
    return None


def _set_cache(key: str, val: Any) -> Any:
    _CACHE[key] = val
    _CACHE_TS[key] = time.time()
    return val


def clear_cache():
    """Clear all cached options (used after seeding)."""
    _CACHE.clear()
    _CACHE_TS.clear()


def warm_cache(db) -> int:
    """Pre-load ALL caches at startup for instant first responses."""
    try:
        provider = DBOptionsProvider(db)
        loaded = 0
        for fn in (provider.get_countries, provider.get_regions, provider.get_cities,
                   provider.get_trip_types, provider.get_hotel_tiers,
                   provider.get_durations, provider.get_package_count):
            fn()
            loaded += 1
        logger.info(f"Cache warmed: {loaded} lookups pre-loaded")
        return loaded
    except Exception as e:
        logger.warning(f"Cache warming failed: {e}")
        return 0


class DBOptionsProvider:
    """
    Provides ALL chatbot dropdown/suggestion values from the database.
    Every value shown to the user MUST originate from this class.
    Uses TTL cache for speed -- DB queried at most once per 5 minutes.

    If `db` is None, returns empty lists. All data from the database.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._db_alive = False

        # Probe the database to check if it's actually reachable
        if self.db is not None:
            try:
                self.db.execute(text("SELECT 1"))
                self._db_alive = True
            except Exception:
                logger.warning("DB session provided but connection is down")
                self.db = None
                self._db_alive = False

    # ------------------------------------------------------------------
    # COUNTRIES (frequency-sorted)
    # ------------------------------------------------------------------
    def get_countries(self) -> List[str]:
        """All unique countries, sorted by package frequency (most popular first)."""
        cached = _cached("countries")
        if cached is not None:
            return cached
        if not self.db:
            return []
        try:
            rows = self.db.execute(
                text("SELECT included_countries FROM rag_packages "
                     "WHERE included_countries IS NOT NULL AND included_countries != ''")
            ).fetchall()
            counter: Counter = Counter()
            for (raw,) in rows:
                for part in raw.split("|"):
                    c = part.strip()
                    if c:
                        counter[c] += 1
            result = [c for c, _ in counter.most_common()]
            return _set_cache("countries", result)
        except Exception as e:
            logger.error(f"get_countries error: {e}")
            return []

    # ------------------------------------------------------------------
    # REGIONS
    # ------------------------------------------------------------------
    def get_regions(self) -> List[str]:
        cached = _cached("regions")
        if cached is not None:
            return cached
        if not self.db:
            return _set_cache("regions", [])
        try:
            rows = self.db.execute(
                text("SELECT DISTINCT included_regions FROM rag_packages "
                     "WHERE included_regions IS NOT NULL AND included_regions != ''")
            ).fetchall()
            regions: set = set()
            for (raw,) in rows:
                for part in raw.split("|"):
                    r = part.strip()
                    if r:
                        regions.add(r)
            result = sorted(regions)
            return _set_cache("regions", result)
        except Exception as e:
            logger.error(f"get_regions error: {e}")
            return []

    # ------------------------------------------------------------------
    # CITIES
    # ------------------------------------------------------------------
    def get_cities(self, country: Optional[str] = None) -> List[str]:
        cache_key = f"cities:{country or 'all'}"
        cached = _cached(cache_key)
        if cached is not None:
            return cached
        if not self.db:
            return []
        try:
            if country:
                rows = self.db.execute(
                    text("SELECT included_cities, start_location, end_location "
                         "FROM rag_packages "
                         "WHERE included_countries LIKE :pattern"),
                    {"pattern": f"%{country}%"},
                ).fetchall()
            else:
                rows = self.db.execute(
                    text("SELECT included_cities, start_location, end_location "
                         "FROM rag_packages")
                ).fetchall()

            cities: set = set()
            for included, start, end in rows:
                for field in [included, start, end]:
                    if field:
                        for part in field.split("|"):
                            c = part.strip()
                            if c:
                                cities.add(c)
            result = sorted(cities)
            return _set_cache(cache_key, result)
        except Exception as e:
            logger.error(f"get_cities error: {e}")
            return []

    # ------------------------------------------------------------------
    # LOCATION MATCHING (multi-location free text with NL understanding)
    # ------------------------------------------------------------------

    # Common aliases: non-English country names, sub-regions, demonyms -> DB country name
    _COUNTRY_ALIASES = {
        # Sub-regions / alternative names -> DB country
        "scotland": "United Kingdom", "scottish": "United Kingdom",
        "england": "United Kingdom", "wales": "United Kingdom",
        "northern ireland": "United Kingdom", "britain": "United Kingdom",
        "great britain": "United Kingdom", "uk": "United Kingdom",
        "holland": "Netherlands", "dutch": "Netherlands",
        "usa": "United States", "america": "United States", "american": "United States",
        "czech": "Czech Republic", "czechia": "Czech Republic",
        "ivory coast": "Ivory Coast",
        # French
        "italie": "Italy", "suisse": "Switzerland", "allemagne": "Germany",
        "espagne": "Spain", "autriche": "Austria", "pays-bas": "Netherlands",
        "royaume-uni": "United Kingdom", "angleterre": "United Kingdom",
        "ecosse": "United Kingdom", "irlande": "Ireland", "norvege": "Norway",
        "suede": "Sweden", "danemark": "Denmark", "grece": "Greece",
        "turquie": "Turkey", "afrique du sud": "South Africa",
        "nouvelle-zelande": "New Zealand", "etats-unis": "United States",
        "finlande": "Finland", "pologne": "Poland", "roumanie": "Romania",
        "perou": "Peru", "inde": "India", "maroc": "Morocco", "chine": "China",
        "belgique": "Belgium",
        # Spanish
        "italia": "Italy", "suiza": "Switzerland", "alemania": "Germany",
        "francia": "France", "reino unido": "United Kingdom",
        "estados unidos": "United States", "paises bajos": "Netherlands",
        "nueva zelanda": "New Zealand", "sudafrica": "South Africa",
        # German
        "italien": "Italy", "schweiz": "Switzerland", "deutschland": "Germany",
        "frankreich": "France", "spanien": "Spain", "osterreich": "Austria",
        "niederlande": "Netherlands", "vereinigtes konigreich": "United Kingdom",
        "vereinigte staaten": "United States", "griechenland": "Greece",
        "turkei": "Turkey", "indien": "India", "marokko": "Morocco",
        "neuseeland": "New Zealand",
        # Hindi transliterations
        "bharat": "India",
        # Common demonyms
        "swiss": "Switzerland", "italian": "Italy", "french": "France",
        "spanish": "Spain", "german": "Germany", "austrian": "Austria",
        "irish": "Ireland", "canadian": "Canada", "australian": "Australia",
        "norwegian": "Norway", "swedish": "Sweden", "finnish": "Finland",
        "greek": "Greece", "turkish": "Turkey", "moroccan": "Morocco",
        "indian": "India", "peruvian": "Peru", "brazilian": "Brazil",
        "portuguese": "Portugal",
        # Sub-region names
        "highlands": "United Kingdom", "alps": "Switzerland",
        "tuscany": "Italy", "lombardy": "Italy", "sicily": "Italy",
        "sardinia": "Italy", "provence": "France", "normandy": "France",
        "andalusia": "Spain", "catalonia": "Spain", "bavaria": "Germany",
        "tyrol": "Austria", "patagonia": "Argentina", "rajasthan": "India",
    }

    # Preamble phrases to strip from natural language input
    _NL_PREAMBLES = [
        r"i(?:'m| am) (?:looking|interested|thinking)(?: (?:for|in|about|of))? (?:a )?(?:package|trip|vacation|journey|tour|holiday)?s?\s*(?:in|to|for|around|through|across)?\s*",
        r"(?:can|could) you (?:find|show|search|get|suggest|recommend)(?: me)? (?:packages|trips|vacations|tours|holidays|journeys)?\s*(?:in|to|for|around|through|across)?\s*",
        r"(?:find|show|search|get|suggest|recommend)(?: me)? (?:packages|trips|vacations|tours|holidays|journeys)?\s*(?:in|to|for|around|through|across)?\s*",
        r"(?:i )?(?:want|would like|would love|wish|plan|hope) (?:to )?\s*(?:go|travel|visit|explore|see|fly|tour|take a trip|vacation)\s*(?:in|to|for|around|through|across)?\s*",
        r"(?:take|bring|fly) me (?:to|in|around|through|across)\s*",
        r"(?:looking|searching) (?:for|at)\s*(?:a )?(?:trip|package|vacation|tour|holiday)?\s*(?:in|to|for|around|through|across)?\s*",
        r"(?:i(?:'d| would) (?:like|love|prefer))(?: to)?\s*(?:go|travel|visit|explore|see)?\s*(?:in|to|for|around|through|across)?\s*",
        r"(?:please |pls )?(?:book|plan|arrange|organize)\s*(?:a )?(?:trip|package|vacation|tour|holiday|journey)?\s*(?:in|to|for|around|through|across)?\s*",
    ]

    def _strip_preamble(self, text: str) -> str:
        """Remove natural language preambles to extract location intent."""
        cleaned = text.strip()
        for pattern in self._NL_PREAMBLES:
            cleaned = re.sub(r"^\s*" + pattern, "", cleaned, count=1, flags=re.IGNORECASE)
        # Also strip trailing noise like "please", "by train", "rail journey" etc.
        cleaned = re.sub(
            r"\s+(?:please|pls|by train|by rail|rail journey|rail vacation|"
            r"safari by train|train trip|train journey|trip|journey|vacation|"
            r"holiday|tour)\.?\s*$",
            "", cleaned, flags=re.IGNORECASE
        )
        return cleaned.strip()

    def _build_city_lookup(self) -> Dict[str, str]:
        """
        Build city lookup that handles suffixed names.
        "Boston, MA" -> keys: "boston, ma", "boston"
        "New York City, NY" -> keys: "new york city, ny", "new york city", "new york"
        """
        lookup: Dict[str, str] = {}
        for city in self.get_cities():
            full = city.lower()
            lookup[full] = city
            # Also add without state/region suffix (e.g. "Boston, MA" -> "boston")
            if ", " in full:
                base = full.split(", ")[0].strip()
                if base and len(base) >= 3:
                    # Only add if not ambiguous (don't override existing)
                    if base not in lookup:
                        lookup[base] = city
        return lookup

    def match_locations(self, user_input: str) -> Dict[str, list]:
        """
        Match user free-text against DB countries/cities/regions.
        Uses two-pass approach:
          1. Scan entire input for known multi-word location names (longest first)
          2. Tokenize remaining text and try partial matching

        Handles natural language like:
          "I'm looking for a package in Rome and Venice and Switzerland"
          "Take me to Paris please"
          "Can you find trips to Boston and New York"
        """
        # Strip natural language preambles
        cleaned = self._strip_preamble(user_input)
        if not cleaned:
            cleaned = user_input.strip()

        db_countries = {c.lower(): c for c in self.get_countries()}
        db_cities_full = self._build_city_lookup()
        db_regions = {r.lower(): r for r in self.get_regions()}

        matched_countries: list = []
        matched_cities: list = []
        consumed = set()  # Character positions consumed (shared across passes)

        input_lower = cleaned.lower()

        # ---- PASS 0: Resolve aliases (Scottish->UK, Italie->Italy, etc.) ----
        # Add aliases to the country lookup so pass 1 can find them
        for alias_lower, db_name in self._COUNTRY_ALIASES.items():
            if alias_lower in input_lower and db_name in db_countries.values():
                # Check word boundary
                idx = input_lower.find(alias_lower)
                if idx != -1:
                    end_idx = idx + len(alias_lower)
                    before_ok = (idx == 0 or not input_lower[idx - 1].isalpha())
                    after_ok = (end_idx >= len(input_lower) or not input_lower[end_idx].isalpha())
                    if before_ok and after_ok:
                        if db_name not in matched_countries:
                            matched_countries.append(db_name)
                        # Mark alias chars as consumed so they are not
                        # reported as unmatched later.
                        for pos in range(idx, end_idx):
                            consumed.add(pos)

        # ---- PASS 1: Scan for known multi-word names (longest first) ----
        # This catches "New York City", "Czech Republic", "South Africa", etc.
        all_names: List[tuple] = []  # (lower_name, original, type)
        for key, val in db_countries.items():
            all_names.append((key, val, "country"))
        for key, val in db_cities_full.items():
            all_names.append((key, val, "city"))
        for key, val in db_regions.items():
            all_names.append((key, val, "region"))

        # Sort by length descending so longer names match first
        all_names.sort(key=lambda x: len(x[0]), reverse=True)

        # Track which parts of the input have been consumed
        # (consumed set initialised before Pass 0)

        for name_lower, name_orig, name_type in all_names:
            if len(name_lower) < 3:
                continue  # Skip very short names to avoid false positives

            # Find all occurrences of this name in the input
            start = 0
            while True:
                idx = input_lower.find(name_lower, start)
                if idx == -1:
                    break

                end_idx = idx + len(name_lower)

                # Check word boundaries to avoid matching "france" inside "fragrance"
                before_ok = (idx == 0 or not input_lower[idx - 1].isalpha())
                after_ok = (end_idx >= len(input_lower) or not input_lower[end_idx].isalpha())

                if before_ok and after_ok:
                    # Check if this range is already consumed
                    overlap = any(pos in consumed for pos in range(idx, end_idx))
                    if not overlap:
                        for pos in range(idx, end_idx):
                            consumed.add(pos)

                        if name_type == "country":
                            matched_countries.append(name_orig)
                        elif name_type == "region":
                            matched_countries.append(name_orig)
                        else:
                            matched_cities.append(name_orig)

                start = end_idx

        # ---- PASS 2: Tokenize unconsumed text for partial matches ----
        unmatched_tokens: list = []

        if not matched_countries and not matched_cities:
            # Nothing found in pass 1 — try tokenizing and partial matching
            tokens = re.split(r"[,;&]+|\band\b", cleaned, flags=re.IGNORECASE)
            tokens = [t.strip() for t in tokens if t.strip()]

            for token in tokens:
                tl = token.lower().strip()
                if len(tl) < 2:
                    continue
                found = False
                # Partial match country
                for key, val in db_countries.items():
                    if tl in key or key in tl:
                        matched_countries.append(val)
                        found = True
                        break
                if not found:
                    # Partial match city
                    for key, val in db_cities_full.items():
                        if tl in key or key in tl:
                            matched_cities.append(val)
                            found = True
                            break
                if not found and len(tl) >= 3:
                    unmatched_tokens.append(token.strip())
        else:
            # Pass 1 found matches — extract unconsumed tokens to report
            # unmatched place-name fragments back to the caller.
            _stop_words = {
                "i", "me", "my", "we", "us", "the", "a", "an", "to", "in",
                "for", "of", "on", "at", "is", "it", "am", "are", "and",
                "or", "but", "with", "from", "by", "up", "about", "into",
                "want", "like", "love", "looking", "trip", "travel",
                "going", "go", "please", "can", "you", "find", "show",
                "take", "explore", "visit", "see", "also", "maybe",
                "would", "could", "should", "that", "this", "some",
                "have", "has", "had", "do", "does", "did", "will",
                "been", "being", "was", "were", "be",
            }
            # Build string of unconsumed characters
            unconsumed_chars = []
            for i, ch in enumerate(input_lower):
                if i not in consumed:
                    unconsumed_chars.append(ch)
                else:
                    unconsumed_chars.append(" ")
            unconsumed_text = "".join(unconsumed_chars)
            fragments = re.split(r"[,;&\s]+|\band\b", unconsumed_text, flags=re.IGNORECASE)
            for frag in fragments:
                frag_clean = frag.strip()
                if len(frag_clean) >= 3 and frag_clean.lower() not in _stop_words:
                    # Capitalise for display
                    unmatched_tokens.append(frag_clean.title())

        # Deduplicate while preserving order
        return {
            "matched_countries": list(dict.fromkeys(matched_countries)),
            "matched_cities": list(dict.fromkeys(matched_cities)),
            "unmatched": list(dict.fromkeys(unmatched_tokens)),
        }

    # ------------------------------------------------------------------
    # AUTOCOMPLETE: match partial user input against DB values
    # ------------------------------------------------------------------
    def autocomplete(self, query: str, step: str = "destination", limit: int = 10) -> List[Dict[str, str]]:
        """
        Autocomplete suggestions from DB as user types.
        Returns list of {label, value, type} matching the query prefix.
        Searches appropriate data based on the current step.
        """
        if not query or len(query) < 1:
            return []

        q = query.lower().strip()
        results: List[Dict[str, str]] = []

        if step in ("destination", "1"):
            # Search countries first, then cities, then regions
            for c in self.get_countries():
                if q in c.lower():
                    results.append({"label": c, "value": c, "type": "country"})
                    if len(results) >= limit:
                        return results
            for c in self.get_cities():
                if q in c.lower():
                    results.append({"label": c, "value": c, "type": "city"})
                    if len(results) >= limit:
                        return results
            for r in self.get_regions():
                if q in r.lower():
                    results.append({"label": r, "value": r, "type": "region"})
                    if len(results) >= limit:
                        return results

        elif step in ("trip_type", "4"):
            for tt in self.get_trip_types():
                if q in tt.lower():
                    results.append({"label": tt, "value": tt, "type": "trip_type"})
                    if len(results) >= limit:
                        return results

        elif step in ("hotel_tier", "5"):
            for ht in self.get_hotel_tiers():
                if q in ht.lower():
                    results.append({"label": ht, "value": ht, "type": "hotel_tier"})
                    if len(results) >= limit:
                        return results

        elif step in ("duration", "3"):
            for d in self.get_durations():
                if q in str(d).lower():
                    results.append({"label": f"{d} nights", "value": str(d), "type": "duration"})
                    if len(results) >= limit:
                        return results

        else:
            # Generic: search all categories
            for c in self.get_countries():
                if q in c.lower():
                    results.append({"label": c, "value": c, "type": "country"})
            for c in self.get_cities():
                if q in c.lower():
                    results.append({"label": c, "value": c, "type": "city"})
            for tt in self.get_trip_types():
                if q in tt.lower():
                    results.append({"label": tt, "value": tt, "type": "trip_type"})

        return results[:limit]

    # ------------------------------------------------------------------
    # TRIP TYPES (from triptype column, pipe-delimited, frequency-sorted)
    # ------------------------------------------------------------------
    def get_trip_types(self) -> List[str]:
        cached = _cached("trip_types")
        if cached is not None:
            return cached
        if not self.db:
            return []
        try:
            rows = self.db.execute(
                text("SELECT triptype FROM rag_packages "
                     "WHERE triptype IS NOT NULL AND triptype != ''")
            ).fetchall()
            counter: Counter = Counter()
            for (raw,) in rows:
                for part in raw.split("|"):
                    t = part.strip()
                    if t:
                        counter[t] += 1
            result = [t for t, _ in counter.most_common()]
            return _set_cache("trip_types", result)
        except Exception as e:
            logger.error(f"get_trip_types error: {e}")
            return []

    # ------------------------------------------------------------------
    # HOTEL TIERS (profitability_group column)
    # ------------------------------------------------------------------
    def get_hotel_tiers(self) -> List[str]:
        cached = _cached("hotel_tiers")
        if cached is not None:
            return cached
        if not self.db:
            return []
        try:
            rows = self.db.execute(
                text("SELECT DISTINCT profitability_group FROM rag_packages "
                     "WHERE profitability_group IS NOT NULL AND profitability_group != ''")
            ).fetchall()
            raw_groups = [r[0].strip() for r in rows if r[0] and r[0].strip()]
            labels = []
            for g in raw_groups:
                label = HOTEL_TIER_MAP.get(g)
                if label and label not in labels:
                    labels.append(label)
            order = ["Luxury", "Premium", "Value"]
            result = [l for l in order if l in labels]
            return _set_cache("hotel_tiers", result)
        except Exception as e:
            logger.error(f"get_hotel_tiers error: {e}")
            return []

    def hotel_label_to_db(self, label: str) -> Optional[str]:
        """Convert user-selected label back to DB profitability_group value."""
        return HOTEL_TIER_REVERSE.get(label.lower())

    # ------------------------------------------------------------------
    # DURATIONS (numeric nights)
    # ------------------------------------------------------------------
    def get_durations(self) -> List[str]:
        cached = _cached("durations")
        if cached is not None:
            return cached
        if not self.db:
            return []
        try:
            rows = self.db.execute(
                text("SELECT DISTINCT duration FROM rag_packages "
                     "WHERE duration IS NOT NULL AND duration != ''")
            ).fetchall()
            raw = [r[0] for r in rows if r[0]]
            # Sort numerically (safe for PostgreSQL: no CAST in ORDER BY with DISTINCT)
            def _dur_key(v):
                try:
                    return int(v)
                except (ValueError, TypeError):
                    return 9999
            result = sorted(raw, key=_dur_key)
            return _set_cache("durations", result)
        except Exception as e:
            logger.error(f"get_durations error: {e}")
            return []

    # ------------------------------------------------------------------
    # PACKAGE COUNT
    # ------------------------------------------------------------------
    def get_package_count(self) -> int:
        cached = _cached("pkg_count")
        if cached is not None:
            return cached
        if not self.db:
            return 0
        try:
            # Rollback any aborted transaction before querying
            try:
                self.db.rollback()
            except Exception:
                pass
            r = self.db.execute(text("SELECT COUNT(*) FROM rag_packages"))
            count = r.scalar() or 0
            return _set_cache("pkg_count", count)
        except Exception as e:
            logger.error(f"get_package_count error: {e}")
            return 0

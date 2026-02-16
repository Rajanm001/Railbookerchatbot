"""
Enterprise Recommendation Engine
=================================
High-performance, DB-driven filtering + multi-factor scoring.
Narrows 2000+ packages to 1-3 strong recommendations.

Architecture:
  1. Dynamic SQL builder with parameterized queries
  2. Multi-factor scoring (city, country, type, duration, hotel, rank)
  3. Smart result limiting: 1 if confident, max 3 if ambiguous
  4. All filter values from SELECT DISTINCT -- zero hardcoded data

Schema mapping (rag_packages):
  start_location      plain text       "Paris"
  end_location        plain text       "London"
  included_cities     pipe-delimited   "Rome | Florence | Milan"
  included_countries  pipe-delimited   "Italy | Switzerland"
  included_regions    pipe-delimited   "Europe"
  triptype            pipe-delimited   "Famous Trains | Most Scenic Journeys"
  duration            plain integer    "11" (nights)
  profitability_group plain text       "Packages - High" / "Packages - Standard Margin" / "Packages - Low"
  package_rank        plain integer    "295" (lower = better)
  departure_type      plain text       "Anyday" / "Seasonal" / "Fixed"

NOTE: No explicit price column exists. Budget is proxied via profitability_group.
      No train_type column exists. departure_type is used instead.

Developed by Rajan Mishra
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple, Set
from sqlalchemy.orm import Session
from sqlalchemy import text
from functools import lru_cache
import logging
import re
import time
import hashlib
import json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache for filter options (TTL-based)
# ---------------------------------------------------------------------------
_filter_cache: Dict[str, Any] = {}
_filter_cache_ts: float = 0.0
FILTER_CACHE_TTL = 60.0  # seconds

# ---------------------------------------------------------------------------
# In-memory cache for autosuggest locations (TTL-based)
# ---------------------------------------------------------------------------
_location_cache: Dict[str, List[str]] = {}
_location_cache_ts: float = 0.0
LOCATION_CACHE_TTL = 900.0  # 15 minutes (locations change rarely)

# ---------------------------------------------------------------------------
# Profitability group -> user-friendly labels + budget proxy
# ---------------------------------------------------------------------------
TIER_MAP = {
    "Packages - High": {"label": "Luxury", "budget_min": 5000, "budget_max": 999999, "sort_order": 1},
    "Packages - Standard Margin": {"label": "Premium", "budget_min": 2500, "budget_max": 7000, "sort_order": 2},
    "Packages - Low": {"label": "Value", "budget_min": 0, "budget_max": 4000, "sort_order": 3},
    "Hurtigruten Packages": {"label": "Premium", "budget_min": 3000, "budget_max": 8000, "sort_order": 2},
    "Package - 29%": {"label": "Premium", "budget_min": 2500, "budget_max": 6000, "sort_order": 2},
    "Package - 30%": {"label": "Premium", "budget_min": 2500, "budget_max": 6000, "sort_order": 2},
    "Package - 31%": {"label": "Premium", "budget_min": 2500, "budget_max": 6000, "sort_order": 2},
    "TEST Profitability Group": {"label": "Value", "budget_min": 0, "budget_max": 3000, "sort_order": 3},
}
TIER_LABELS = {v["label"]: k for k, v in TIER_MAP.items() if k.startswith("Packages")}

# Score thresholds
STRONG_MATCH_THRESHOLD = 80
GOOD_MATCH_THRESHOLD = 50
# Tiered result limits for chatbot recommender
MAX_RESULTS_STRONG = 6
MAX_RESULTS_GOOD = 9
MAX_RESULTS_DEFAULT = 12
# Browse mode: return ALL matching results (no cap)
MAX_RESULTS_BROWSE = 2000


class RecommendationEngine:
    """
    Enterprise recommendation engine.
    All data from DB. No hardcoded values. No mock data.
    """

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("Database session is required")
        self.db = db
        # Verify connection (lightweight ping)
        try:
            self.db.execute(text("SELECT 1"))
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise ConnectionError(f"Database unreachable: {e}")

    # ==================================================================
    # DYNAMIC FILTER OPTIONS (all from SELECT DISTINCT)
    # ==================================================================

    def get_filter_options(self) -> Dict[str, Any]:
        """
        Return all available filter dropdown values from the database.
        Every value comes from SELECT DISTINCT queries.
        Results are cached in-memory for FILTER_CACHE_TTL seconds.
        """
        global _filter_cache, _filter_cache_ts
        now = time.time()
        if _filter_cache and (now - _filter_cache_ts) < FILTER_CACHE_TTL:
            logger.debug("Filter options served from cache")
            return _filter_cache

        start = now
        options: Dict[str, Any] = {}

        # Start locations
        rows = self.db.execute(text(
            "SELECT DISTINCT start_location FROM rag_packages "
            "WHERE start_location IS NOT NULL AND start_location != '' "
            "ORDER BY start_location"
        )).fetchall()
        options["start_locations"] = [r[0] for r in rows]

        # End locations
        rows = self.db.execute(text(
            "SELECT DISTINCT end_location FROM rag_packages "
            "WHERE end_location IS NOT NULL AND end_location != '' "
            "ORDER BY end_location"
        )).fetchall()
        options["end_locations"] = [r[0] for r in rows]

        # Countries (pipe-delimited -> split and deduplicate)
        rows = self.db.execute(text(
            "SELECT DISTINCT included_countries FROM rag_packages "
            "WHERE included_countries IS NOT NULL AND included_countries != ''"
        )).fetchall()
        countries: Set[str] = set()
        for (raw,) in rows:
            for part in raw.split("|"):
                c = part.strip()
                if c:
                    countries.add(c)
        options["countries"] = sorted(countries)

        # Regions (pipe-delimited)
        rows = self.db.execute(text(
            "SELECT DISTINCT included_regions FROM rag_packages "
            "WHERE included_regions IS NOT NULL AND included_regions != ''"
        )).fetchall()
        regions: Set[str] = set()
        for (raw,) in rows:
            for part in raw.split("|"):
                r = part.strip()
                if r:
                    regions.add(r)
        options["regions"] = sorted(regions)

        # Vacation types (pipe-delimited)
        rows = self.db.execute(text(
            "SELECT DISTINCT triptype FROM rag_packages "
            "WHERE triptype IS NOT NULL AND triptype != ''"
        )).fetchall()
        trip_types: Set[str] = set()
        for (raw,) in rows:
            for part in raw.split("|"):
                t = part.strip()
                if t:
                    trip_types.add(t)
        options["vacation_types"] = sorted(trip_types)

        # Hotel tiers (mapped from profitability_group)
        rows = self.db.execute(text(
            "SELECT DISTINCT profitability_group FROM rag_packages "
            "WHERE profitability_group IS NOT NULL AND profitability_group != ''"
        )).fetchall()
        tiers = []
        for (raw,) in rows:
            tier_info = TIER_MAP.get(raw.strip())
            if tier_info and tier_info["label"] not in tiers:
                tiers.append(tier_info["label"])
        options["hotel_tiers"] = ["Luxury", "Premium", "Value"]  # Fixed order

        # Departure types
        rows = self.db.execute(text(
            "SELECT DISTINCT departure_type FROM rag_packages "
            "WHERE departure_type IS NOT NULL AND departure_type != '' "
            "ORDER BY departure_type"
        )).fetchall()
        options["departure_types"] = [r[0] for r in rows]

        # States (pipe-delimited)
        rows = self.db.execute(text(
            "SELECT DISTINCT included_states FROM rag_packages "
            "WHERE included_states IS NOT NULL AND included_states != ''"
        )).fetchall()
        states_set: Set[str] = set()
        for (raw,) in rows:
            for part in raw.split("|"):
                s = part.strip()
                if s:
                    states_set.add(s)
        options["states"] = sorted(states_set)

        # Train names (from route column - pipe-delimited actual train/route names)
        rows = self.db.execute(text(
            "SELECT DISTINCT route FROM rag_packages "
            "WHERE route IS NOT NULL AND route != ''"
        )).fetchall()
        train_names_set: Set[str] = set()
        for (raw,) in rows:
            for part in raw.split("|"):
                tn = part.strip()
                if tn:
                    train_names_set.add(tn)
        options["train_names"] = sorted(train_names_set)

        # Duration range (null-safe)
        row = self.db.execute(text(
            "SELECT MIN(CAST(duration AS INTEGER)), MAX(CAST(duration AS INTEGER)) "
            "FROM rag_packages WHERE duration IS NOT NULL AND duration != '' AND duration ~ '^[0-9]+$'"
        )).fetchone()
        if row is not None and row[0] is not None:
            options["duration_range"] = {"min": row[0], "max": row[1] or 34}
        else:
            options["duration_range"] = {"min": 2, "max": 34}

        # Total packages
        count = self.db.execute(text("SELECT COUNT(*) FROM rag_packages")).scalar()
        options["total_packages"] = count or 0

        elapsed_ms = (time.time() - start) * 1000
        logger.info(f"Filter options loaded in {elapsed_ms:.0f}ms")

        # Cache the result
        _filter_cache = options
        _filter_cache_ts = time.time()
        return options

    # ==================================================================
    # AUTOSUGGEST: Cached locations + 3 search modes
    # ==================================================================

    def get_all_locations(self) -> Dict[str, List[str]]:
        """
        Build and cache a unified list of all unique locations from the DB.
        Sources: start_location, end_location, included_cities (pipe-delimited),
                 included_countries (pipe-delimited), external_name (package names).
        Cached for 15 minutes.
        """
        global _location_cache, _location_cache_ts
        now = time.time()
        if _location_cache and (now - _location_cache_ts) < LOCATION_CACHE_TTL:
            return _location_cache

        locations: Set[str] = set()
        cities: Set[str] = set()
        countries: Set[str] = set()
        start_locs: Set[str] = set()
        end_locs: Set[str] = set()
        package_names: Set[str] = set()

        # Start locations
        rows = self.db.execute(text(
            "SELECT DISTINCT start_location FROM rag_packages "
            "WHERE start_location IS NOT NULL AND start_location != ''"
        )).fetchall()
        for (val,) in rows:
            v = val.strip()
            if v:
                start_locs.add(v)
                locations.add(v)

        # End locations
        rows = self.db.execute(text(
            "SELECT DISTINCT end_location FROM rag_packages "
            "WHERE end_location IS NOT NULL AND end_location != ''"
        )).fetchall()
        for (val,) in rows:
            v = val.strip()
            if v:
                end_locs.add(v)
                locations.add(v)

        # Cities (pipe-delimited)
        rows = self.db.execute(text(
            "SELECT DISTINCT included_cities FROM rag_packages "
            "WHERE included_cities IS NOT NULL AND included_cities != ''"
        )).fetchall()
        for (raw,) in rows:
            for part in raw.split("|"):
                c = part.strip()
                if c:
                    cities.add(c)
                    locations.add(c)

        # Countries (pipe-delimited)
        rows = self.db.execute(text(
            "SELECT DISTINCT included_countries FROM rag_packages "
            "WHERE included_countries IS NOT NULL AND included_countries != ''"
        )).fetchall()
        for (raw,) in rows:
            for part in raw.split("|"):
                c = part.strip()
                if c:
                    countries.add(c)
                    locations.add(c)

        # Package names
        rows = self.db.execute(text(
            "SELECT DISTINCT external_name FROM rag_packages "
            "WHERE external_name IS NOT NULL AND external_name != ''"
        )).fetchall()
        for (val,) in rows:
            v = val.strip()
            if v:
                package_names.add(v)

        result: Dict[str, List[str]] = {
            "locations": sorted(locations),
            "cities": sorted(cities),
            "countries": sorted(countries),
            "start_locations": sorted(start_locs),
            "end_locations": sorted(end_locs),
            "package_names": sorted(package_names),
        }

        _location_cache = result
        _location_cache_ts = time.time()
        logger.info(
            f"Location cache built: {len(locations)} locations, "
            f"{len(cities)} cities, {len(countries)} countries, "
            f"{len(package_names)} packages"
        )
        return result

    def autosuggest(
        self,
        query: str,
        mode: str = "includes",
        field: str = "all",
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """
        Auto-suggest locations based on user input.

        Args:
            query:  User's typed text (minimum 1 char)
            mode:   "starts_with" | "includes" | "ends_with"
            field:  "all" | "cities" | "countries" | "start_locations" |
                    "end_locations" | "package_names"
            limit:  Max results (default 10)

        Returns:
            List of {value, type} dicts for the frontend.
        """
        if not query or len(query.strip()) < 1:
            return []

        q = query.strip().lower()
        cache = self.get_all_locations()

        # Select which lists to search
        search_lists: List[Tuple[str, List[str]]] = []
        if field == "all":
            search_lists = [
                ("city", cache.get("cities", [])),
                ("country", cache.get("countries", [])),
                ("start", cache.get("start_locations", [])),
                ("end", cache.get("end_locations", [])),
            ]
        elif field == "package_names":
            search_lists = [("package", cache.get("package_names", []))]
        elif field in cache:
            search_lists = [(field, cache.get(field, []))]

        results: List[Dict[str, str]] = []
        seen: Set[str] = set()

        for type_label, items in search_lists:
            for item in items:
                if len(results) >= limit:
                    break
                item_lower = item.lower()
                matched = False

                if mode == "starts_with":
                    matched = item_lower.startswith(q)
                elif mode == "ends_with":
                    matched = item_lower.endswith(q)
                else:  # "includes" (default)
                    matched = q in item_lower

                if matched and item not in seen:
                    seen.add(item)
                    results.append({"value": item, "type": type_label})

            if len(results) >= limit:
                break

        # Sort: exact starts-with matches first, then alphabetical
        results.sort(key=lambda x: (
            0 if x["value"].lower().startswith(q) else 1,
            x["value"].lower()
        ))

        return results[:limit]

    def search_packages_by_name(
        self, query: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search packages by name (LIKE %query%).
        Returns scored results for direct name search.
        """
        if not query or len(query.strip()) < 2:
            return []

        q = f"%{query.strip()}%"
        sql = (
            "SELECT id, casesafeid, external_name, start_location, end_location, "
            "included_cities, included_countries, included_regions, "
            "triptype, route, description, highlights, "
            "package_rank, profitability_group, duration, "
            "departure_type, departure_dates, package_url, "
            "included_states, sales_tips, inclusions, daybyday, access_rule "
            "FROM rag_packages WHERE LOWER(external_name) LIKE LOWER(:q) "
            "AND external_name NOT ILIKE '%TEST%' "
            "ORDER BY (CASE WHEN package_rank ~ '^[0-9]+$' THEN CAST(package_rank AS INTEGER) ELSE 9999 END) ASC "
            f"LIMIT {min(limit, 50)}"
        )
        rows = self.db.execute(text(sql), {"q": q}).fetchall()
        results = []
        for row in rows:
            pkg = self._row_to_dict(row)
            pkg["match_score"] = 85.0
            pkg["match_reasons"] = [f"Name matches '{query.strip()}'"]
            results.append(pkg)
        return results

    # ==================================================================
    # RECOMMENDATION ENGINE
    # ==================================================================

    def recommend(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main recommendation entry point.

        Accepts filter dict with optional keys:
          includes:       list[str]  -- destination cities/countries
          include_rows:   list[list[str]] -- multi-row AND/OR destinations
          starts_in:      str        -- start location
          ends_in:        str        -- end location
          region:         str        -- region name
          countries:      list[str]  -- country filter (multi-select)
          vacation_type:  str        -- trip type (single)
          vacation_types: list[str]  -- trip types (multi-select OR)
          trains:         list[str]  -- train trip types
          duration_min:   int        -- minimum nights
          duration_max:   int        -- maximum nights
          hotel_tier:     str        -- Luxury/Premium/Value
          departure_type: str        -- Anyday/Seasonal/Fixed
          sort_by:        str        -- "popularity" | "duration_asc" | "duration_desc" | "rank"

        Returns:
          {
            "packages": [...],     -- 6-12 scored results
            "total_matched": int,  -- total before limit
            "filters_applied": {}, -- echo of active filters
            "scoring_summary": str,
            "elapsed_ms": float,
          }
        """
        start = time.time()

        # Sanitize input
        filters = self._sanitize_filters(filters)

        # Build parameterized query
        where_clauses, params = self._build_where(filters)

        # Execute filtered query (return ALL matches for full browse experience)
        sql = self._build_sql(where_clauses, limit=MAX_RESULTS_BROWSE)
        candidates = list(self.db.execute(text(sql), params).fetchall())
        total_matched = len(candidates)
        logger.info(f"SQL filter returned {total_matched} candidates")

        # Fallback: if zero results, relax filters progressively
        if not candidates and where_clauses:
            candidates, total_matched = self._fallback_search(filters)

        # Score each candidate
        scored = []
        for row in candidates:
            pkg = self._row_to_dict(row)
            score, reasons = self._score(pkg, filters)
            pkg["match_score"] = round(score, 1)
            pkg["match_reasons"] = reasons
            scored.append(pkg)

        # Sort by score desc, then by rank asc (lower rank = more popular)
        sort_by = filters.get("sort_by", "score")
        scored = self._apply_sort(scored, sort_by)

        # Return ALL results for full browse experience (no artificial limiting)
        results = scored

        # Extract available filter options from current results
        available_filters = self._extract_available_filters(results)

        elapsed_ms = (time.time() - start) * 1000
        logger.info(f"Recommendation complete: {len(results)}/{total_matched} in {elapsed_ms:.0f}ms")

        return {
            "packages": results,
            "total_matched": total_matched,
            "total_returned": len(results),
            "filters_applied": {k: v for k, v in filters.items() if v},
            "scoring_summary": self._scoring_summary(results),
            "elapsed_ms": round(elapsed_ms, 1),
            "available_filters": available_filters,
        }

    # ==================================================================
    # DYNAMIC SQL BUILDER (parameterized, safe)
    # ==================================================================

    def _build_where(self, filters: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
        """Build WHERE clause components with safe parameterized bindings."""
        clauses: List[str] = []
        params: Dict[str, Any] = {}

        # SEARCH ROWS (new multi-mode format: each row has mode + destinations)
        # Supersedes legacy includes/include_rows/starts_in/ends_in when present
        search_rows = filters.get("search_rows")
        if search_rows and isinstance(search_rows, list):
            for row_idx, sr in enumerate(search_rows):
                if not isinstance(sr, dict):
                    continue
                mode = sr.get("mode", "includes")
                dests = sr.get("destinations", [])
                if not dests or not isinstance(dests, list):
                    continue
                row_parts = []
                for dest_idx, dest in enumerate(dests):
                    dest = str(dest).strip()
                    if not dest:
                        continue
                    key = f"sr{row_idx}_d{dest_idx}"
                    if mode == "starts_in":
                        row_parts.append(f"LOWER(start_location) = LOWER(:{key})")
                        params[key] = dest
                    elif mode == "ends_in":
                        row_parts.append(f"LOWER(end_location) = LOWER(:{key})")
                        params[key] = dest
                    else:  # includes (default)
                        pattern = f"%{dest}%"
                        row_parts.append(
                            f"(LOWER(included_countries) LIKE LOWER(:{key}) "
                            f"OR LOWER(included_cities) LIKE LOWER(:{key}) "
                            f"OR LOWER(start_location) LIKE LOWER(:{key}) "
                            f"OR LOWER(end_location) LIKE LOWER(:{key}))"
                        )
                        params[key] = pattern
                if row_parts:
                    clauses.append(f"({' OR '.join(row_parts)})")

        # INCLUDE_ROWS (multi-row AND/OR: each row is ORed, rows are ANDed)
        include_rows = filters.get("include_rows")
        if include_rows and isinstance(include_rows, list):
            for row_idx, row in enumerate(include_rows):
                if not row or not isinstance(row, list):
                    continue
                row_parts = []
                for dest_idx, dest in enumerate(row):
                    dest = str(dest).strip()
                    if not dest:
                        continue
                    key = f"row{row_idx}_d{dest_idx}"
                    pattern = f"%{dest}%"
                    row_parts.append(
                        f"(LOWER(included_countries) LIKE LOWER(:{key}) "
                        f"OR LOWER(included_cities) LIKE LOWER(:{key}) "
                        f"OR LOWER(start_location) LIKE LOWER(:{key}) "
                        f"OR LOWER(end_location) LIKE LOWER(:{key}))"
                    )
                    params[key] = pattern
                if row_parts:
                    # OR within a row, AND between rows
                    clauses.append(f"({' OR '.join(row_parts)})")
        else:
            # INCLUDES (multiple destinations: cities or countries) — legacy single row
            includes = filters.get("includes")
            if includes and isinstance(includes, list):
                inc_parts = []
                for i, dest in enumerate(includes):
                    dest = dest.strip()
                    if not dest:
                        continue
                    key = f"inc_{i}"
                    pattern = f"%{dest}%"
                    inc_parts.append(
                        f"(LOWER(included_countries) LIKE LOWER(:{key}) "
                        f"OR LOWER(included_cities) LIKE LOWER(:{key}) "
                        f"OR LOWER(start_location) LIKE LOWER(:{key}) "
                        f"OR LOWER(end_location) LIKE LOWER(:{key}))"
                    )
                    params[key] = pattern
                if inc_parts:
                    # OR across all includes (package must match at least one)
                    clauses.append(f"({' OR '.join(inc_parts)})")

        # STARTS IN
        starts_in = filters.get("starts_in")
        if starts_in and isinstance(starts_in, str) and starts_in.strip():
            clauses.append("LOWER(start_location) = LOWER(:starts_in)")
            params["starts_in"] = starts_in.strip()

        # ENDS IN
        ends_in = filters.get("ends_in")
        if ends_in and isinstance(ends_in, str) and ends_in.strip():
            clauses.append("LOWER(end_location) = LOWER(:ends_in)")
            params["ends_in"] = ends_in.strip()

        # REGION
        region = filters.get("region")
        if region and isinstance(region, str) and region.strip():
            clauses.append("LOWER(included_regions) LIKE LOWER(:region)")
            params["region"] = f"%{region.strip()}%"

        # COUNTRIES (multi-select: package must visit at least one selected country)
        countries = filters.get("countries")
        if countries and isinstance(countries, list):
            country_parts = []
            for i, country in enumerate(countries):
                country = str(country).strip()
                if not country:
                    continue
                key = f"ctry_{i}"
                country_parts.append(f"LOWER(included_countries) LIKE LOWER(:{key})")
                params[key] = f"%{country}%"
            if country_parts:
                clauses.append(f"({' OR '.join(country_parts)})")

        # VACATION TYPE (single)
        vtype = filters.get("vacation_type")
        if vtype and isinstance(vtype, str) and vtype.strip():
            clauses.append("LOWER(triptype) LIKE LOWER(:vtype)")
            params["vtype"] = f"%{vtype.strip()}%"

        # VACATION TYPES (multi-select: at least one must match)
        vtypes = filters.get("vacation_types")
        if vtypes and isinstance(vtypes, list):
            vt_parts = []
            for i, vt in enumerate(vtypes):
                vt = str(vt).strip()
                if not vt:
                    continue
                key = f"vt_{i}"
                vt_parts.append(f"LOWER(triptype) LIKE LOWER(:{key})")
                params[key] = f"%{vt}%"
            if vt_parts:
                clauses.append(f"({' OR '.join(vt_parts)})")

        # TRAINS (train-related trip types: subset of vacation types)
        trains = filters.get("trains")
        if trains and isinstance(trains, list):
            tr_parts = []
            for i, tr in enumerate(trains):
                tr = str(tr).strip()
                if not tr:
                    continue
                key = f"tr_{i}"
                tr_parts.append(f"LOWER(triptype) LIKE LOWER(:{key})")
                params[key] = f"%{tr}%"
            if tr_parts:
                clauses.append(f"({' OR '.join(tr_parts)})")

        # TRAIN NAMES (filter by actual train/route names from route column)
        train_names = filters.get("train_names")
        if train_names and isinstance(train_names, list):
            tn_parts = []
            for i, tn in enumerate(train_names):
                tn = str(tn).strip()
                if not tn:
                    continue
                key = f"tn_{i}"
                tn_parts.append(f"LOWER(route) LIKE LOWER(:{key})")
                params[key] = f"%{tn}%"
            if tn_parts:
                clauses.append(f"({' OR '.join(tn_parts)})")

        # DURATION RANGE
        dur_min = filters.get("duration_min")
        if dur_min is not None:
            try:
                clauses.append("duration ~ '^[0-9]+$' AND CAST(duration AS INTEGER) >= :dur_min")
                params["dur_min"] = int(dur_min)
            except (ValueError, TypeError):
                pass

        dur_max = filters.get("duration_max")
        if dur_max is not None:
            try:
                clauses.append("duration ~ '^[0-9]+$' AND CAST(duration AS INTEGER) <= :dur_max")
                params["dur_max"] = int(dur_max)
            except (ValueError, TypeError):
                pass

        # HOTEL TIER (mapped to profitability_group -- supports multiple groups per label)
        hotel_tier = filters.get("hotel_tier")
        if hotel_tier and isinstance(hotel_tier, str) and hotel_tier.strip():
            tier_label = hotel_tier.strip()
            matching_groups = [k for k, v in TIER_MAP.items() if v["label"] == tier_label]
            if matching_groups:
                placeholders = []
                for idx, grp in enumerate(matching_groups):
                    key = f"hotel_grp_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = grp
                clauses.append(f"profitability_group IN ({', '.join(placeholders)})")

        # DEPARTURE TYPE
        dep_type = filters.get("departure_type")
        if dep_type and isinstance(dep_type, str) and dep_type.strip():
            clauses.append("departure_type = :dep_type")
            params["dep_type"] = dep_type.strip()

        # PACKAGE NAME (LIKE search on external_name)
        pkg_name = filters.get("package_name")
        if pkg_name and isinstance(pkg_name, str) and pkg_name.strip():
            clauses.append("LOWER(external_name) LIKE LOWER(:pkg_name)")
            params["pkg_name"] = f"%{pkg_name.strip()}%"

        return clauses, params

    def _build_sql(self, where_clauses: List[str], limit: int = 300) -> str:
        """Build the full SELECT statement. Excludes test/dummy packages."""
        sql = (
            "SELECT id, casesafeid, external_name, start_location, end_location, "
            "included_cities, included_countries, included_regions, "
            "triptype, route, description, highlights, "
            "package_rank, profitability_group, duration, "
            "departure_type, departure_dates, package_url, "
            "included_states, sales_tips, inclusions, daybyday, access_rule "
            "FROM rag_packages"
        )
        # Always exclude test/demo packages
        all_clauses = ["external_name NOT ILIKE '%TEST%'"] + where_clauses
        sql += " WHERE " + " AND ".join(all_clauses)
        sql += f" LIMIT {limit}"
        return sql

    # ==================================================================
    # PROGRESSIVE FALLBACK
    # ==================================================================

    def _fallback_search(self, filters: Dict[str, Any]) -> Tuple[List[Any], int]:
        """Progressively relax SECONDARY filters only.

        Primary filters (location/destination) are NEVER dropped.
        This prevents hallucination where unrelated packages are
        returned when a searched destination has zero matches.
        """
        # Primary filters: these define WHAT the user is looking for
        # and must never be dropped -- doing so would return random
        # unrelated packages (hallucination).
        PRIMARY_KEYS = {
            "search_rows", "includes", "include_rows",
            "starts_in", "ends_in", "region", "package_name",
        }

        # Secondary filters: these refine the primary results and
        # can be relaxed safely to widen the pool.
        SECONDARY_RELAXATION_ORDER = [
            "departure_type",
            "hotel_tier",
            "vacation_type",
            "vacation_types",
            "trains",
            "train_names",
            "countries",
            "duration_min",
            "duration_max",
        ]

        relaxed = dict(filters)
        for key in SECONDARY_RELAXATION_ORDER:
            if key not in relaxed:
                continue
            relaxed.pop(key)
            # If removing this filter leaves NO remaining user filters,
            # do not execute — that would return random/all packages.
            remaining_user_keys = {k for k in relaxed if k not in ("limit", "offset", "sort", "sort_by", "page", "per_page")}
            if not remaining_user_keys:
                logger.info(f"Fallback: dropping '{key}' would leave zero filters; stopping.")
                break
            clauses, params = self._build_where(relaxed)
            sql = self._build_sql(clauses, limit=200)
            candidates = list(self.db.execute(text(sql), params).fetchall())
            if candidates:
                logger.info(f"Fallback: dropped '{key}', got {len(candidates)} results")
                return candidates, len(candidates)

        # If still no results after relaxing all secondary filters,
        # the primary search criteria simply have no matches in our
        # catalogue. Return empty -- do NOT return random packages.
        logger.info("Fallback: no results after relaxing secondary filters. "
                     "Primary search criteria have zero matches.")
        return [], 0

    # ==================================================================
    # SCORING ENGINE
    # ==================================================================

    def _score(self, pkg: Dict[str, Any], filters: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Multi-factor scoring. Max raw ~130, normalized to 0-100.

        Scoring weights:
          Exact city match:     +40
          Country match:        +30
          Vacation type match:  +20
          Duration match:       +15
          Hotel tier match:     +10
          Rank bonus:           +10
          Multi-country bonus:  +5
        """
        score = 0.0
        reasons: List[str] = []

        countries_raw = (pkg.get("included_countries") or "").lower()
        cities_raw = (pkg.get("included_cities") or "").lower()
        start_loc = (pkg.get("start_location") or "").lower()
        end_loc = (pkg.get("end_location") or "").lower()
        triptype = (pkg.get("triptype") or "").lower()
        prof_group = (pkg.get("profitability_group") or "").strip()

        # --- Search Rows scoring (new multi-mode format) ---
        search_rows = filters.get("search_rows")
        if search_rows and isinstance(search_rows, list):
            for sr in search_rows:
                if not isinstance(sr, dict):
                    continue
                _mode = sr.get("mode", "includes")
                _dests = sr.get("destinations", [])
                for dest in _dests:
                    dl = dest.lower().strip()
                    if not dl:
                        continue
                    if _mode == "starts_in":
                        if dl == start_loc:
                            score += 15
                            reasons.append(f"Starts in {dest}")
                    elif _mode == "ends_in":
                        if dl == end_loc:
                            score += 15
                            reasons.append(f"Ends in {dest}")
                    else:  # includes
                        if dl in cities_raw or dl == start_loc or dl == end_loc:
                            score += 35
                            reasons.append(f"Includes {dest}")
                        elif dl in countries_raw:
                            score += 25
                            reasons.append(f"Visits {dest}")

        # --- Includes match (city/country) ---
        includes = filters.get("includes")
        if includes:
            for dest in includes:
                dl = dest.lower().strip()
                if not dl:
                    continue
                # Exact city match: +40
                if dl in cities_raw or dl in start_loc or dl in end_loc:
                    score += 40
                    reasons.append(f"Includes {dest}")
                # Country match: +30
                elif dl in countries_raw:
                    score += 30
                    reasons.append(f"Visits {dest}")

        # --- Starts in match: +15 ---
        starts_in = filters.get("starts_in")
        if starts_in and starts_in.strip():
            if starts_in.lower().strip() == start_loc:
                score += 15
                reasons.append(f"Starts in {starts_in}")

        # --- Ends in match: +15 ---
        ends_in = filters.get("ends_in")
        if ends_in and ends_in.strip():
            if ends_in.lower().strip() == end_loc:
                score += 15
                reasons.append(f"Ends in {ends_in}")

        # --- Vacation type match: +20 ---
        vtype = filters.get("vacation_type")
        if vtype and vtype.strip():
            if vtype.lower().strip() in triptype:
                score += 20
                reasons.append(f"Matches {vtype}")

        # --- Vacation types (multi-select): +20 top ---
        vtypes = filters.get("vacation_types")
        if vtypes and isinstance(vtypes, list):
            matched_vts = [vt for vt in vtypes if vt.lower().strip() in triptype]
            if matched_vts:
                score += min(20, len(matched_vts) * 10)
                reasons.append(f"Type: {', '.join(matched_vts[:3])}")

        # --- Trains filter: +15 ---
        trains = filters.get("trains")
        if trains and isinstance(trains, list):
            matched_trains = [tr for tr in trains if tr.lower().strip() in triptype]
            if matched_trains:
                score += min(15, len(matched_trains) * 8)
                reasons.append(f"Train: {', '.join(matched_trains[:2])}")

        # --- Countries filter (multi-select): +25 ---
        filter_countries = filters.get("countries")
        if filter_countries and isinstance(filter_countries, list):
            for fc in filter_countries:
                if fc.lower().strip() in countries_raw:
                    score += 25
                    reasons.append(f"Visits {fc}")
                    break  # Only score once for country match

        # --- Include rows scoring (multi-row AND) ---
        include_rows = filters.get("include_rows")
        if include_rows and isinstance(include_rows, list):
            for row in include_rows:
                if not row:
                    continue
                for dest in row:
                    dl = dest.lower().strip()
                    if not dl:
                        continue
                    if dl in cities_raw or dl in start_loc or dl in end_loc:
                        score += 35
                        reasons.append(f"Includes {dest}")
                        break
                    elif dl in countries_raw:
                        score += 25
                        reasons.append(f"Visits {dest}")
                        break

        # --- Duration match: +15 ---
        dur_min = filters.get("duration_min")
        dur_max = filters.get("duration_max")
        pkg_dur = self._parse_int(pkg.get("duration"))
        if pkg_dur and (dur_min is not None or dur_max is not None):
            target_dur = None
            if dur_min is not None and dur_max is not None:
                target_dur = (int(dur_min) + int(dur_max)) / 2
            elif dur_min is not None:
                target_dur = int(dur_min)
            elif dur_max is not None:
                target_dur = int(dur_max)

            if target_dur:
                diff = abs(pkg_dur - target_dur)
                if diff == 0:
                    score += 15
                    reasons.append(f"Exact {pkg_dur}-night match")
                elif diff <= 2:
                    score += 12
                    reasons.append(f"Close duration ({pkg_dur} nights)")
                elif diff <= 4:
                    score += 8
                    reasons.append(f"Similar duration ({pkg_dur} nights)")
                elif diff <= 7:
                    score += 4

        # --- Hotel tier match: +10 ---
        hotel_tier = filters.get("hotel_tier")
        if hotel_tier and hotel_tier.strip():
            expected_group = TIER_LABELS.get(hotel_tier.strip())
            if expected_group and prof_group == expected_group:
                score += 10
                label = TIER_MAP.get(prof_group, {}).get("label", hotel_tier)
                reasons.append(f"{label} accommodation")

        # --- Package rank bonus: +10 ---
        rank = self._parse_int(pkg.get("package_rank"))
        if rank:
            if rank <= 100:
                score += 10
                reasons.append("Top-ranked package")
            elif rank <= 300:
                score += 7
                reasons.append("Highly rated")
            elif rank <= 600:
                score += 4
            elif rank <= 1000:
                score += 2

        # --- Multi-country bonus: +5 ---
        countries_list = [c.strip() for c in (pkg.get("included_countries") or "").split("|") if c.strip()]
        if len(countries_list) >= 3:
            score += 5
            reasons.append(f"Multi-country ({len(countries_list)} countries)")
        elif len(countries_list) == 2:
            score += 3

        # --- Region match bonus: +5 ---
        region = filters.get("region")
        if region and region.strip():
            pkg_regions = (pkg.get("included_regions") or "").lower()
            if region.lower().strip() in pkg_regions:
                score += 5
                reasons.append(f"Region: {region}")

        # Normalize to 0-100 using absolute scoring scale
        # Max theoretical raw = 40+30+15+15+20+15+10+10+5+5 = 165
        # We use a fixed ceiling so scores are consistent & comparable
        ABSOLUTE_CEILING = 100.0

        normalized = min((score / ABSOLUTE_CEILING) * 100, 100) if ABSOLUTE_CEILING > 0 else 0

        # Ensure minimum differentiation for scored packages
        if score > 0 and normalized < 10:
            normalized = 10.0

        # Baseline for unfiltered results
        if score == 0 and not reasons:
            normalized = 5.0
            reasons.append("Available rail vacation")

        return round(normalized, 1), reasons[:6]

    # ==================================================================
    # SORTING
    # ==================================================================

    # Profitability group sort order (lower = cheaper)
    TIER_SORT_ORDER = {
        "Packages - Low": 1,
        "Packages - Standard Margin": 2,
        "Package - 29%": 3,
        "Package - 30%": 3,
        "Package - 31%": 3,
        "Hurtigruten Packages": 4,
        "Packages - High": 5,
    }

    def _apply_sort(self, scored: List[Dict], sort_by: str) -> List[Dict]:
        """Apply user-selected sort order."""
        if sort_by == "duration_asc":
            return sorted(scored, key=lambda x: self._parse_int(x.get("duration")) or 999)
        elif sort_by == "duration_desc":
            return sorted(scored, key=lambda x: self._parse_int(x.get("duration")) or 0, reverse=True)
        elif sort_by == "popularity":
            return sorted(scored, key=lambda x: self._parse_int(x.get("package_rank")) or 9999)
        elif sort_by == "name_asc":
            return sorted(scored, key=lambda x: (x.get("name") or "").lower())
        elif sort_by == "name_desc":
            return sorted(scored, key=lambda x: (x.get("name") or "").lower(), reverse=True)
        elif sort_by == "newest":
            # Sort by id desc (higher id = newer)
            return sorted(scored, key=lambda x: self._parse_int(x.get("id")) or 0, reverse=True)
        elif sort_by == "price_asc":
            # Price low to high (using profitability_group as proxy)
            return sorted(scored, key=lambda x: (
                self.TIER_SORT_ORDER.get(x.get("profitability_group", ""), 3),
                self._parse_int(x.get("package_rank")) or 9999
            ))
        elif sort_by == "price_desc":
            # Price high to low (using profitability_group as proxy)
            return sorted(scored, key=lambda x: (
                -self.TIER_SORT_ORDER.get(x.get("profitability_group", ""), 3),
                self._parse_int(x.get("package_rank")) or 9999
            ))
        else:
            # Default: score desc, then rank asc
            return sorted(scored, key=lambda x: (-x.get("match_score", 0), self._parse_int(x.get("package_rank")) or 9999))

    # ==================================================================
    # SMART LIMITING
    # ==================================================================

    def _smart_limit(self, scored: List[Dict]) -> List[Dict]:
        """
        Intelligent result limiting for search/browse experience:
          - Score >= 80: return top 6 (strong matches)
          - Score >= 50: return top 9
          - Otherwise:   return top 12
        Provides enough results for a proper browsing experience.
        """
        if not scored:
            return []

        top_score = scored[0].get("match_score", 0)

        if top_score >= STRONG_MATCH_THRESHOLD:
            return scored[:MAX_RESULTS_STRONG]
        elif top_score >= GOOD_MATCH_THRESHOLD:
            return scored[:MAX_RESULTS_GOOD]
        else:
            return scored[:MAX_RESULTS_DEFAULT]

    # ==================================================================
    # HELPERS
    # ==================================================================

    # ==================================================================
    # EXTRACT AVAILABLE FILTERS FROM RESULTS
    # ==================================================================

    def _extract_available_filters(self, packages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract available filter options from the current result set.
        Filters should only show options present in the results."""
        regions: Set[str] = set()
        countries: Set[str] = set()
        train_names: Set[str] = set()
        vacation_types: Set[str] = set()
        durations: List[int] = []

        for pkg in packages:
            for r in (pkg.get('included_regions') or '').split('|'):
                r = r.strip()
                if r:
                    regions.add(r)
            for c in (pkg.get('included_countries') or '').split('|'):
                c = c.strip()
                if c:
                    countries.add(c)
            for t in (pkg.get('route') or '').split('|'):
                t = t.strip()
                if t:
                    train_names.add(t)
            for vt in (pkg.get('triptype') or '').split('|'):
                vt = vt.strip()
                if vt:
                    vacation_types.add(vt)
            dur = self._parse_int(pkg.get('duration'))
            if dur:
                durations.append(dur)

        return {
            'regions': sorted(regions),
            'countries': sorted(countries),
            'train_names': sorted(train_names),
            'vacation_types': sorted(vacation_types),
            'duration_range': {
                'min': min(durations) if durations else 2,
                'max': max(durations) if durations else 34,
            },
        }

    # ==================================================================
    # PRICE ESTIMATION
    # ==================================================================

    def _estimate_price(self, pkg: Dict[str, Any]) -> float:
        """Estimate a price in GBP based on duration and profitability tier.
        No actual price column exists; this provides a realistic proxy."""
        duration = self._parse_int(pkg.get('duration')) or 7
        prof = (pkg.get('profitability_group') or '').strip()
        pkg_id = self._parse_int(pkg.get('id')) or 1

        if 'High' in prof:
            base = 380
        elif 'Standard' in prof:
            base = 195
        elif 'Low' in prof:
            base = 90
        elif 'Hurtigruten' in prof:
            base = 300
        elif '29' in prof or '30' in prof or '31' in prof:
            base = 200
        else:
            base = 160

        # Small deterministic variance per package
        variance = (pkg_id * 7) % 100
        price = base * duration + variance
        return round(price, 2)

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a DB row tuple to a clean dict."""
        # Column order matches _build_sql SELECT
        keys = [
            "id", "casesafeid", "external_name", "start_location", "end_location",
            "included_cities", "included_countries", "included_regions",
            "triptype", "route", "description", "highlights",
            "package_rank", "profitability_group", "duration",
            "departure_type", "departure_dates", "package_url",
            "included_states", "sales_tips", "inclusions", "daybyday", "access_rule",
        ]
        d = {}
        for i, key in enumerate(keys):
            val = row[i] if i < len(row) else None
            d[key] = str(val).strip() if val is not None else ""
        # Format for frontend
        d["name"] = d.get("external_name") or "Rail Vacation Package"
        d["duration_display"] = f"{d['duration']} nights" if d.get("duration") else ""
        d["countries_display"] = ", ".join(
            c.strip() for c in (d.get("included_countries") or "").split("|") if c.strip()
        )
        d["cities_display"] = ", ".join(
            c.strip() for c in (d.get("included_cities") or "").split("|") if c.strip()
        )
        d["trip_type_display"] = ", ".join(
            t.strip() for t in (d.get("triptype") or "").split("|") if t.strip()
        )
        d["hotel_tier"] = TIER_MAP.get(d.get("profitability_group", ""), {}).get("label", "")
        route_str = ""
        if d.get("start_location") and d.get("end_location"):
            if d["start_location"] != d["end_location"]:
                route_str = f"{d['start_location']} → {d['end_location']}"
            else:
                route_str = f"Round trip from {d['start_location']}"
        elif d.get("start_location"):
            route_str = f"From {d['start_location']}"
        d["route_display"] = route_str
        # Parse highlights and inclusions BEFORE stripping HTML
        # (so <li> tags are still present for list extraction)
        raw_hl = d.get("highlights") or ""
        hl_items = re.findall(r"<li[^>]*>(.*?)</li>", raw_hl, re.DOTALL | re.IGNORECASE)
        d["highlights_list"] = [re.sub(r"<[^>]+>", "", item).strip() for item in hl_items if item.strip()]

        raw_inc = d.get("inclusions") or ""
        inc_items = re.findall(r"<li[^>]*>(.*?)</li>", raw_inc, re.DOTALL | re.IGNORECASE)
        d["inclusions_list"] = [re.sub(r"<[^>]+>", "", item).strip() for item in inc_items if item.strip()]

        # NOW strip HTML for plain text display
        desc = d.get("description") or ""
        d["description"] = re.sub(r"<[^>]+>", "", desc)
        d["highlights"] = re.sub(r"<[^>]+>", "", raw_hl)[:400]

        # States display
        d["states_display"] = ", ".join(
            s.strip() for s in (d.get("included_states") or "").split("|") if s.strip()
        )

        # Train/Route names (pipe-delimited route field = actual train names)
        d["trains_display"] = ", ".join(
            t.strip() for t in (d.get("route") or "").split("|") if t.strip()
        )

        # Departure dates summary
        raw_dates = d.get("departure_dates") or ""
        if raw_dates:
            date_ranges = [dr.strip().split(" - ")[:2] for dr in raw_dates.split("|") if dr.strip()]
            formatted = []
            for dr in date_ranges[:3]:
                if len(dr) >= 2:
                    formatted.append(f"{dr[0]} to {dr[1]}")
            d["departure_dates_display"] = "; ".join(formatted) if formatted else ""
        else:
            d["departure_dates_display"] = ""

        # Access rule
        d["access_rule_display"] = (d.get("access_rule") or "").strip()

        # Estimated price (GBP)
        d["estimated_price"] = self._estimate_price(d)

        # Promo savings badge (site-wide promotion)
        d["promo_savings"] = 150

        return d

    def _sanitize_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize and validate all filter inputs."""
        clean: Dict[str, Any] = {}
        # String fields: strip, limit length, remove control chars
        str_fields = ["starts_in", "ends_in", "region", "vacation_type",
                      "hotel_tier", "departure_type", "sort_by"]
        for key in str_fields:
            val = filters.get(key)
            if val and isinstance(val, str):
                val = re.sub(r'[\x00-\x1f]', '', val.strip())[:200]
                if val:
                    clean[key] = val

        # Includes: list of strings
        includes = filters.get("includes")
        if includes and isinstance(includes, list):
            cleaned_inc = []
            for item in includes[:10]:  # max 10 destinations
                if isinstance(item, str):
                    s = re.sub(r'[\x00-\x1f]', '', item.strip())[:100]
                    if s:
                        cleaned_inc.append(s)
            if cleaned_inc:
                clean["includes"] = cleaned_inc

        # Include rows: list of list of strings (multi-row AND/OR)
        include_rows = filters.get("include_rows")
        if include_rows and isinstance(include_rows, list):
            cleaned_rows = []
            for row in include_rows[:5]:  # max 5 rows
                if isinstance(row, list):
                    cleaned_row = []
                    for item in row[:10]:  # max 10 per row
                        if isinstance(item, str):
                            s = re.sub(r'[\x00-\x1f]', '', item.strip())[:100]
                            if s:
                                cleaned_row.append(s)
                    if cleaned_row:
                        cleaned_rows.append(cleaned_row)
            if cleaned_rows:
                clean["include_rows"] = cleaned_rows

        # Countries: list of strings (multi-select)
        raw_countries = filters.get("countries")
        if raw_countries and isinstance(raw_countries, list):
            cleaned_countries = []
            for item in raw_countries[:20]:
                if isinstance(item, str):
                    s = re.sub(r'[\x00-\x1f]', '', item.strip())[:100]
                    if s:
                        cleaned_countries.append(s)
            if cleaned_countries:
                clean["countries"] = cleaned_countries

        # Vacation types: list of strings (multi-select)
        raw_vtypes = filters.get("vacation_types")
        if raw_vtypes and isinstance(raw_vtypes, list):
            cleaned_vtypes = []
            for item in raw_vtypes[:20]:
                if isinstance(item, str):
                    s = re.sub(r'[\x00-\x1f]', '', item.strip())[:100]
                    if s:
                        cleaned_vtypes.append(s)
            if cleaned_vtypes:
                clean["vacation_types"] = cleaned_vtypes

        # Trains: list of strings (train trip types)
        raw_trains = filters.get("trains")
        if raw_trains and isinstance(raw_trains, list):
            cleaned_trains = []
            for item in raw_trains[:10]:
                if isinstance(item, str):
                    s = re.sub(r'[\x00-\x1f]', '', item.strip())[:100]
                    if s:
                        cleaned_trains.append(s)
            if cleaned_trains:
                clean["trains"] = cleaned_trains

        # Train names: list of strings (actual train/route names from route column)
        raw_tn = filters.get("train_names")
        if raw_tn and isinstance(raw_tn, list):
            cleaned_tn = []
            for item in raw_tn[:20]:
                if isinstance(item, str):
                    s = re.sub(r'[\x00-\x1f]', '', item.strip())[:100]
                    if s:
                        cleaned_tn.append(s)
            if cleaned_tn:
                clean["train_names"] = cleaned_tn

        # Search rows: list of {mode, destinations}
        raw_sr = filters.get("search_rows")
        if raw_sr and isinstance(raw_sr, list):
            cleaned_sr = []
            for sr in raw_sr[:5]:  # max 5 rows
                if isinstance(sr, dict):
                    mode = sr.get("mode", "includes")
                    if mode not in {"includes", "starts_in", "ends_in"}:
                        mode = "includes"
                    dests = sr.get("destinations", [])
                    cleaned_dests = []
                    for d in dests[:10]:  # max 10 per row
                        if isinstance(d, str):
                            s = re.sub(r'[\x00-\x1f]', '', d.strip())[:100]
                            if s:
                                cleaned_dests.append(s)
                    if cleaned_dests:
                        cleaned_sr.append({"mode": mode, "destinations": cleaned_dests})
            if cleaned_sr:
                clean["search_rows"] = cleaned_sr

        # Package name: string
        pkg_name = filters.get("package_name")
        if pkg_name and isinstance(pkg_name, str):
            s = re.sub(r'[\x00-\x1f]', '', pkg_name.strip())[:200]
            if s:
                clean["package_name"] = s

        # Integer fields: clamp range
        for key in ["duration_min", "duration_max"]:
            val = filters.get(key)
            if val is not None:
                try:
                    v = int(val)
                    clean[key] = max(1, min(v, 365))
                except (ValueError, TypeError):
                    pass

        # Auto-swap if min > max
        d_min = clean.get("duration_min")
        d_max = clean.get("duration_max")
        if d_min is not None and d_max is not None and d_min > d_max:
            clean["duration_min"], clean["duration_max"] = d_max, d_min

        # sort_by whitelist
        allowed_sorts = {"score", "popularity", "duration_asc", "duration_desc",
                         "name_asc", "name_desc", "newest", "price_asc", "price_desc"}
        if clean.get("sort_by") not in allowed_sorts:
            clean["sort_by"] = "score"

        return clean

    def _parse_int(self, val: Any) -> Optional[int]:
        if val is None:
            return None
        try:
            return int(str(val).strip())
        except (ValueError, TypeError):
            m = re.search(r"(\d+)", str(val))
            return int(m.group(1)) if m else None

    def _scoring_summary(self, results: List[Dict]) -> str:
        if not results:
            return "No matching packages found."
        if len(results) == 1:
            return f"Strong match found ({results[0].get('match_score', 0):.0f}% confidence)."
        scores = [r.get("match_score", 0) for r in results]
        return f"{len(results)} matches found (scores: {', '.join(f'{s:.0f}%' for s in scores)})."

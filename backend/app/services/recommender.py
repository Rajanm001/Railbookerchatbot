"""
Package Recommendation Engine
Combines TF-IDF vector search with structured SQL filtering
and multi-factor scoring. All data sourced from the database.

Architecture:
  1. RAG Retrieval: Use TF-IDF vectors to find semantically relevant packages
  2. SQL Filtering: Apply structured filters (location, type, hotel tier)
  3. Scoring: Multi-factor scoring (location, duration, type, hotel, rank, RAG)
  4. Ranking: Sort by combined score, return top K

DB column formats (confirmed from live analysis of 2000 packages):
  - included_countries: pipe-delimited  "Italy | Switzerland"
  - included_cities:    pipe-delimited  "Rome | Florence"
  - triptype:           pipe-delimited  "Famous Trains | Most Scenic Journeys"
  - profitability_group: plain          "Packages - High" / "Packages - Standard Margin" / "Packages - Low"
  - duration:           plain integer   "11" (nights)
  - departure_dates:    pipe-delimited date ranges
  - package_url:        full URL string
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Dict, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, text, text as sa_text
import logging
import re
import time
import math
from collections import Counter

from app.db.models import TravelPackage
from app.services.db_options import HOTEL_TIER_REVERSE, HOTEL_TIER_MAP

logger = logging.getLogger(__name__)


def _s(val: Any) -> str:
    """Safely convert a SQLAlchemy Column value to str."""
    if val is None:
        return ""
    return str(val)


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words, removing stop words."""
    stop = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "is", "on", "at", "by", "with", "from"}
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if w not in stop and len(w) > 1]


def _cosine_sim(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two text strings using term frequency.
    Returns 0.0 to 1.0. Fast, no external dependencies."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    counter_a = Counter(tokens_a)
    counter_b = Counter(tokens_b)
    all_terms = set(counter_a.keys()) | set(counter_b.keys())
    dot = sum(counter_a.get(t, 0) * counter_b.get(t, 0) for t in all_terms)
    mag_a = math.sqrt(sum(v * v for v in counter_a.values()))
    mag_b = math.sqrt(sum(v * v for v in counter_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class PackageRecommender:
    """Recommendation engine. Vector search + SQL filtering + scoring.

    If `db` is None, returns empty results. NO demo fallback.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        # Verify the DB connection is actually alive
        if self.db is not None:
            try:
                self.db.execute(text("SELECT 1"))
            except Exception:
                logger.warning("PackageRecommender: DB session provided but unreachable")
                self.db = None

    def recommend(
        self,
        countries: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
        travel_dates: Optional[str] = None,
        trip_types: Optional[List[str]] = None,
        hotel_tier: Optional[str] = None,
        duration_days: Optional[int] = None,
        rail_experience: Optional[str] = None,
        rag_query: Optional[str] = None,
        budget: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid recommender: RAG vector retrieval + structured SQL + scoring.
        """
        start = time.time()

        # No DB = no results
        if not self.db:
            logger.warning("No database connection -- returning empty recommendations")
            return []

        try:
            # ---- STEP 1: RAG RETRIEVAL (if vector store is available) ----
            rag_scores: Dict[int, float] = {}
            rag_candidate_ids: Optional[Set[int]] = None

            if rag_query:
                try:
                    from app.services.vector_store import VectorStore
                    store = VectorStore(self.db)
                    if store.is_ready():
                        rag_results = store.semantic_search(rag_query, top_k=50)
                        if rag_results:
                            rag_scores = {pid: score for pid, score in rag_results}
                            rag_candidate_ids = set(rag_scores.keys())
                            logger.info(f"RAG retrieved {len(rag_scores)} candidates "
                                       f"(top score: {rag_results[0][1]:.3f})")
                except Exception as e:
                    logger.warning(f"RAG retrieval failed, falling back to SQL: {e}")

            # ---- STEP 2: SQL FILTERING ----
            query = self.db.query(TravelPackage).filter(
                ~TravelPackage.external_name.ilike('%TEST%')
            )

            # LOCATION FILTER
            loc_conditions = []
            if countries:
                for c in countries:
                    loc_conditions.append(
                        func.lower(TravelPackage.included_countries).contains(c.lower())
                    )
            if cities:
                for ci in cities:
                    loc_conditions.append(
                        or_(
                            func.lower(TravelPackage.included_cities).contains(ci.lower()),
                            func.lower(TravelPackage.start_location).contains(ci.lower()),
                            func.lower(TravelPackage.end_location).contains(ci.lower()),
                        )
                    )
            if loc_conditions:
                query = query.filter(or_(*loc_conditions))

            # TRIP TYPE FILTER
            if trip_types:
                tt_conds = []
                for tt in trip_types:
                    tt_conds.append(
                        func.lower(TravelPackage.triptype).contains(tt.lower())
                    )
                query = query.filter(or_(*tt_conds))

            # HOTEL TIER FILTER
            if hotel_tier:
                db_group = HOTEL_TIER_REVERSE.get(hotel_tier.lower())
                if db_group:
                    query = query.filter(TravelPackage.profitability_group == db_group)

            # Fetch SQL candidates
            candidates = query.limit(300).all()
            logger.info(f"SQL query returned {len(candidates)} candidates in {(time.time()-start)*1000:.0f}ms")

            # Fallback chain if no results
            if not candidates:
                query2 = self.db.query(TravelPackage)
                if loc_conditions:
                    query2 = query2.filter(or_(*loc_conditions))
                if trip_types:
                    tt_conds2 = [func.lower(TravelPackage.triptype).contains(tt.lower()) for tt in trip_types]
                    query2 = query2.filter(or_(*tt_conds2))
                candidates = query2.limit(200).all()
                logger.info(f"Fallback-1 (no hotel) returned {len(candidates)} candidates")

            if not candidates:
                query3 = self.db.query(TravelPackage)
                if loc_conditions:
                    query3 = query3.filter(or_(*loc_conditions))
                candidates = query3.limit(200).all()
                logger.info(f"Fallback-2 (location only) returned {len(candidates)} candidates")

            # If primary location filters found nothing, do NOT return
            # random top-ranked packages.  That would be hallucination.
            if not candidates and loc_conditions:
                logger.info("No packages match the requested destinations -- returning empty")
                return []

            if not candidates and not loc_conditions:
                # Only fall back to top-ranked when NO location was specified
                candidates = self.db.query(TravelPackage).order_by(
                    TravelPackage.package_rank.asc()
                ).limit(50).all()
                logger.info(f"Fallback-3 (top ranked, no location filter) returned {len(candidates)} candidates")

            # ---- STEP 2b: Ensure destination packages are always represented ----
            # When trip-type filters are restrictive, destination-only results may
            # be excluded.  Merge location-only candidates so scoring can decide.
            if loc_conditions and trip_types and candidates:
                existing_ids = {pkg.id for pkg in candidates}  # type: ignore[misc]
                loc_only_q = self.db.query(TravelPackage).filter(or_(*loc_conditions)).limit(100)
                for pkg in loc_only_q:
                    if pkg.id not in existing_ids:  # type: ignore[operator]
                        candidates.append(pkg)
                        existing_ids.add(pkg.id)  # type: ignore[arg-type]
                logger.info(f"After location back-fill: {len(candidates)} total candidates")

            # ---- STEP 3: If RAG found candidates not in SQL results, merge them ----
            if rag_candidate_ids:
                sql_ids: set[int] = {int(pkg.id) for pkg in candidates}  # type: ignore[arg-type]
                missing_rag = rag_candidate_ids - sql_ids
                if missing_rag:
                    # Fetch top RAG candidates not already in SQL results
                    top_missing = sorted(missing_rag, key=lambda pid: rag_scores.get(pid, 0), reverse=True)[:20]
                    extra = self.db.query(TravelPackage).filter(
                        TravelPackage.id.in_(top_missing)
                    ).all()
                    candidates.extend(extra)
                    logger.info(f"Merged {len(extra)} RAG-only candidates")

            # ---- STEP 4: SCORE EACH ----
            scored: List[Tuple[TravelPackage, float, List[str]]] = []
            for pkg in candidates:
                score, reasons = self._score(
                    pkg, countries, cities, travel_dates,
                    trip_types, hotel_tier, duration_days, rail_experience,
                    rag_scores, budget,
                )
                scored.append((pkg, score, reasons))

            scored.sort(key=lambda x: x[1], reverse=True)

            # Deduplicate packages with same name (.com vs .co.uk variants)
            seen_names: dict = {}
            deduped: List[Tuple[TravelPackage, float, List[str]]] = []
            for pkg, score, reasons in scored:
                name = _s(pkg.external_name).strip().lower()
                if name not in seen_names:
                    seen_names[name] = True
                    deduped.append((pkg, score, reasons))

            # ---- Multi-destination fairness ----
            # When user requests 2+ destinations, guarantee at least 1 result per
            # destination (if packages exist), so no destination is drowned out.
            if countries and len(countries) >= 2:
                final: List[Tuple[TravelPackage, float, List[str]]] = []
                used_names: set = set()
                remaining_slots = top_k

                # First pass: pick the best package for each destination
                for dest in countries:
                    dest_lower = dest.lower()
                    for pkg, score, reasons in deduped:
                        name = _s(pkg.external_name).strip().lower()
                        if name in used_names:
                            continue
                        pkg_countries = _s(pkg.included_countries).lower()
                        if dest_lower in pkg_countries:
                            final.append((pkg, score, reasons))
                            used_names.add(name)
                            remaining_slots -= 1
                            break

                # If a destination had no packages in the deduped pool, try a
                # relaxed DB query (location-only, no trip-type / hotel filter)
                for dest in countries:
                    dest_lower = dest.lower()
                    already_covered = any(
                        dest_lower in _s(pkg.included_countries).lower()
                        for pkg, _, _ in final
                    )
                    if not already_covered and remaining_slots > 0:
                        extra_pkgs = self.db.query(TravelPackage).filter(
                            func.lower(TravelPackage.included_countries).contains(dest_lower)
                        ).order_by(TravelPackage.package_rank.asc()).limit(5).all()
                        for epkg in extra_pkgs:
                            ename = _s(epkg.external_name).strip().lower()
                            if ename not in used_names:
                                escore, ereasons = self._score(
                                    epkg, countries, cities, travel_dates,
                                    trip_types, hotel_tier, duration_days,
                                    rail_experience, rag_scores, budget,
                                )
                                final.append((epkg, escore, ereasons))
                                used_names.add(ename)
                                remaining_slots -= 1
                                break

                # Second pass: fill remaining slots from top deduped results
                for pkg, score, reasons in deduped:
                    if remaining_slots <= 0:
                        break
                    name = _s(pkg.external_name).strip().lower()
                    if name not in used_names:
                        final.append((pkg, score, reasons))
                        used_names.add(name)
                        remaining_slots -= 1

                # Re-sort by score so best matches appear first
                final.sort(key=lambda x: x[1], reverse=True)
                deduped = final

            results = [self._format(pkg, score, reasons) for pkg, score, reasons in deduped[:top_k]]

            elapsed = (time.time() - start) * 1000
            logger.info(f"Recommendation complete: {len(results)} results in {elapsed:.0f}ms "
                       f"(RAG: {'yes' if rag_scores else 'no'})")
            return results

        except Exception as e:
            logger.error(f"Recommendation engine error: {e}", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # SCORING (max ~115, normalized to 100)
    # ------------------------------------------------------------------
    def _score(
        self,
        pkg: TravelPackage,
        countries: Optional[List[str]],
        cities: Optional[List[str]],
        travel_dates: Optional[str],
        trip_types: Optional[List[str]],
        hotel_tier: Optional[str],
        duration_days: Optional[int],
        rail_experience: Optional[str],
        rag_scores: Optional[Dict[int, float]] = None,
        budget: Optional[str] = None,
    ) -> Tuple[float, List[str]]:
        score = 0.0
        reasons: List[str] = []
        rag_scores = rag_scores or {}

        # --- RAG relevance (max 15) ---
        rag_sim = rag_scores.get(int(pkg.id), 0.0)  # type: ignore[arg-type]
        if rag_sim > 0.05:
            rag_bonus = min(15, int(rag_sim * 30))
            score += rag_bonus
            if rag_sim > 0.2:
                reasons.append("High semantic relevance")
            elif rag_sim > 0.1:
                reasons.append("Good content match")

        # --- Location match (max 35) ---
        if countries:
            pkg_countries = _s(pkg.included_countries).lower()
            matched = [c for c in countries if c.lower() in pkg_countries]
            if matched:
                score += min(35, len(matched) * 18)
                reasons.append(f"Visits {', '.join(matched)}")

        if cities:
            pkg_locs = " ".join([
                _s(pkg.included_cities), _s(pkg.start_location), _s(pkg.end_location)
            ]).lower()
            matched = [c for c in cities if c.lower() in pkg_locs]
            if matched:
                score += min(15, len(matched) * 10)
                reasons.append(f"Includes {', '.join(matched)}")

        # --- Duration match (max 20) ---
        if duration_days:
            pkg_dur = self._parse_duration(_s(pkg.duration))
            if pkg_dur:
                diff = abs(pkg_dur - duration_days)
                if diff == 0:
                    score += 20
                    reasons.append(f"Exact {pkg_dur}-night match")
                elif diff <= 2:
                    score += 15
                    reasons.append(f"Close duration ({pkg_dur} nights)")
                elif diff <= 4:
                    score += 10
                    reasons.append(f"Similar duration ({pkg_dur} nights)")
                elif diff <= 7:
                    score += 5

        # --- Trip type match (max 20) ---
        if trip_types:
            pkg_tt = _s(pkg.triptype)
            direct_matched = [t for t in trip_types if t.lower() in pkg_tt.lower()]
            if direct_matched:
                score += min(20, len(direct_matched) * 10)
                reasons.append(f"Matches: {', '.join(direct_matched)}")
            else:
                user_tt_text = " ".join(trip_types)
                sim = _cosine_sim(user_tt_text, pkg_tt)
                if sim > 0.3:
                    bonus = min(15, int(sim * 20))
                    score += bonus
                    reasons.append(f"Similar trip style ({sim:.0%} match)")

        # --- Hotel tier match (max 15) ---
        if hotel_tier:
            db_group = HOTEL_TIER_REVERSE.get(hotel_tier.lower(), "")
            pg = _s(pkg.profitability_group)
            if db_group and db_group.lower() == pg.lower():
                score += 15
                tier_label = HOTEL_TIER_MAP.get(pg, hotel_tier)
                reasons.append(f"{tier_label} accommodation")

        # --- Description relevance via cosine (max 5 bonus) ---
        if countries or trip_types:
            user_context = " ".join((countries or []) + (trip_types or []))
            pkg_text = f"{_s(pkg.description)} {_s(pkg.highlights)}"
            if pkg_text.strip():
                desc_sim = _cosine_sim(user_context, pkg_text)
                if desc_sim > 0.15:
                    bonus = min(5, int(desc_sim * 10))
                    score += bonus
                    if desc_sim > 0.25:
                        reasons.append("Strong content relevance")

        # --- Rail experience bonus (max 5) ---
        if rail_experience == "first_time":
            pkg_tt = _s(pkg.triptype).lower()
            if "first time" in pkg_tt or "first-time" in pkg_tt:
                score += 5
                reasons.append("Ideal for first-time rail travellers")

        # --- Package rank bonus (max 10) ---
        try:
            rank = int(_s(pkg.package_rank) or "9999")
            if rank <= 50:
                score += 10
                reasons.append("Top-ranked package")
            elif rank <= 150:
                score += 7
                reasons.append("Highly rated")
            elif rank <= 300:
                score += 4
            elif rank <= 500:
                score += 2
        except (ValueError, TypeError):
            pass

        # --- Multi-country itinerary bonus (max 5) ---
        pkg_country_list = [c.strip() for c in _s(pkg.included_countries).split("|") if c.strip()]
        if len(pkg_country_list) >= 3:
            score += 5
            reasons.append(f"Multi-country journey ({len(pkg_country_list)} countries)")
        elif len(pkg_country_list) == 2:
            score += 3

        # --- Season match bonus (max 5) ---
        if travel_dates:
            season = self._season_from_text(travel_dates)
            dept_raw = _s(getattr(pkg, 'departure_dates', '') or '')
            if season and dept_raw:
                season_months = {
                    'spring': ['mar', 'apr', 'may'],
                    'summer': ['jun', 'jul', 'aug'],
                    'autumn': ['sep', 'oct', 'nov'],
                    'winter': ['dec', 'jan', 'feb'],
                }
                for m in season_months.get(season, []):
                    if m in dept_raw.lower():
                        score += 5
                        reasons.append(f"Available in {season}")
                        break

        # --- Budget match bonus (max 5) ---
        if budget:
            try:
                budget_val = int(budget.replace(",", ""))
                pg = _s(pkg.profitability_group).lower()
                # Match budget against hotel tier proxy
                if budget_val <= 3000 and "low" in pg:
                    score += 5
                    reasons.append("Within budget range")
                elif 3000 < budget_val <= 5000 and "standard" in pg:
                    score += 5
                    reasons.append("Within budget range")
                elif budget_val > 5000 and "high" in pg:
                    score += 5
                    reasons.append("Premium within budget")
                elif "low" in pg:
                    # Value packages work for any budget
                    score += 3
            except (ValueError, TypeError):
                pass

        # Baseline
        if score == 0.0:
            score = 5.0
            reasons.append("Available rail vacation")

        # --- Normalize score to 0-100 based on achievable max ---
        # Use realistic achievable ceilings (not theoretical max) so
        # a genuinely good match reads 70-95% instead of 40-50%.
        max_achievable = 8.0   # RAG + description (hard to max out)
        max_achievable += 5    # Package rank (most are mid-range)
        max_achievable += 3    # Multi-country bonus
        if countries:
            max_achievable += 30  # Top country match ~18-35 raw
        if cities:
            max_achievable += 10
        if duration_days:
            max_achievable += 12  # Exact match is rare; close is common
        if trip_types:
            max_achievable += 12  # Partial match is common
        if hotel_tier:
            max_achievable += 12
        if rail_experience:
            max_achievable += 2
        if travel_dates:
            max_achievable += 3
        if budget:
            max_achievable += 3

        if max_achievable > 0:
            normalized = (score / max_achievable) * 100
        else:
            normalized = score

        # Floor: even weak matches should show at least 15%
        normalized = max(normalized, 15.0)

        return min(round(normalized, 1), 100), reasons

    def _season_from_text(self, text: str) -> str:
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

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _parse_duration(self, dur_str: Optional[str]) -> Optional[int]:
        if not dur_str:
            return None
        try:
            return int(dur_str.strip())
        except (ValueError, TypeError):
            m = re.search(r"(\d+)", dur_str)
            return int(m.group(1)) if m else None

    def _format(self, pkg: TravelPackage, score: float, reasons: List[str]) -> Dict[str, Any]:
        desc = self._strip_html(_s(pkg.description))[:500]
        highlights = self._strip_html(_s(pkg.highlights))[:500]
        dur = _s(pkg.duration)
        start = _s(pkg.start_location)
        end = _s(pkg.end_location)
        route = f"{start} to {end}" if start and end and start != end else start or end or ""

        countries_raw = _s(pkg.included_countries)
        cities_raw = _s(pkg.included_cities)
        countries_clean = ", ".join(c.strip() for c in countries_raw.split("|") if c.strip()) if countries_raw else ""
        cities_clean = ", ".join(c.strip() for c in cities_raw.split("|") if c.strip()) if cities_raw else ""

        trip_type_raw = _s(pkg.triptype)
        trip_type_clean = ", ".join(t.strip() for t in trip_type_raw.split("|") if t.strip()) if trip_type_raw else ""

        # Hotel tier label from profitability group
        pg = _s(pkg.profitability_group)
        hotel_tier = HOTEL_TIER_MAP.get(pg, "")

        # Departure type
        dep_type = _s(getattr(pkg, 'departure_type', '') or '')

        return {
            "id": pkg.id,
            "casesafeid": _s(pkg.casesafeid),
            "name": _s(pkg.external_name) or "Rail Vacation Package",
            "description": desc,
            "highlights": highlights,
            "duration": f"{dur} nights" if dur else "",
            "countries": countries_clean,
            "cities": cities_clean,
            "route": route,
            "start_location": start,
            "end_location": end,
            "trip_type": trip_type_clean,
            "hotel_tier": hotel_tier,
            "departure_type": dep_type,
            "package_url": _s(pkg.package_url),
            "match_score": score,
            "match_reasons": reasons[:6],
        }

    def _strip_html(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()

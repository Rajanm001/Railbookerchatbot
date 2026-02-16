"""
Recommendation API Routes
==========================
Enterprise-grade recommendation filtering endpoint.
Separate from chatbot -- chatbot is NOT modified.

Endpoints:
  GET  /recommendations/filters      -- Dynamic filter options from DB
  GET  /recommendations/locations     -- All cached locations for autosuggest
  GET  /recommendations/autosuggest   -- Live autosuggest with starts_with/includes/ends_with
  POST /recommendations/search        -- Filtered + scored recommendations
  GET  /recommendations/search-by-name -- Search packages by name

Developed by Rajan Mishra
"""

from fastapi import APIRouter, Depends, Request, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import logging
import time

from app.db.database import get_db
from app.services.recommendation_engine import RecommendationEngine
from app.core.rate_limiting import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class RecommendationRequest(BaseModel):
    """Filter criteria for recommendation search."""
    includes: Optional[List[str]] = Field(None, description="Destination cities or countries")
    include_rows: Optional[List[List[str]]] = Field(None, description="Multi-row AND/OR destinations")
    starts_in: Optional[str] = Field(None, description="Start location", max_length=200)
    ends_in: Optional[str] = Field(None, description="End location", max_length=200)
    region: Optional[str] = Field(None, description="Region (e.g. Europe, Asia)", max_length=100)
    countries: Optional[List[str]] = Field(None, description="Country filter (multi-select)")
    vacation_type: Optional[str] = Field(None, description="Trip type (e.g. Famous Trains)", max_length=200)
    vacation_types: Optional[List[str]] = Field(None, description="Multiple trip types (OR)")
    trains: Optional[List[str]] = Field(None, description="Train-related trip types")
    train_names: Optional[List[str]] = Field(None, description="Actual train names from route column")
    package_name: Optional[str] = Field(None, description="Search by package name", max_length=200)
    search_rows: Optional[List[Dict[str, Any]]] = Field(None, description="Multi-mode search rows [{mode, destinations}]")
    duration_min: Optional[int] = Field(None, ge=1, le=365, description="Minimum nights")
    duration_max: Optional[int] = Field(None, ge=1, le=365, description="Maximum nights")
    hotel_tier: Optional[str] = Field(None, description="Luxury / Premium / Value", max_length=50)
    departure_type: Optional[str] = Field(None, description="Anyday / Seasonal / Fixed", max_length=50)
    sort_by: Optional[str] = Field("score", description="score / popularity / duration_asc / duration_desc / name_asc / name_desc / newest")

    @validator('sort_by')
    def validate_sort(cls, v):
        allowed = {'score', 'popularity', 'duration_asc', 'duration_desc', 'name_asc', 'name_desc', 'newest', 'price_asc', 'price_desc'}
        if v and v not in allowed:
            return 'score'
        return v or 'score'


class PackageResult(BaseModel):
    id: int
    casesafeid: str
    name: str
    description: str
    highlights: str
    duration_display: str
    countries_display: str
    cities_display: str
    route_display: str
    start_location: str
    end_location: str
    trip_type_display: str
    hotel_tier: str
    departure_type: str
    package_url: str
    match_score: float
    match_reasons: List[str]


class RecommendationResponse(BaseModel):
    packages: List[Dict[str, Any]]
    total_matched: int
    total_returned: int
    filters_applied: Dict[str, Any]
    scoring_summary: str
    elapsed_ms: float
    available_filters: Optional[Dict[str, Any]] = None


class FilterOptionsResponse(BaseModel):
    start_locations: List[str]
    end_locations: List[str]
    countries: List[str]
    regions: List[str]
    states: List[str]
    vacation_types: List[str]
    hotel_tiers: List[str]
    departure_types: List[str]
    train_names: List[str]
    duration_range: Dict[str, int]
    total_packages: int


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("/filters", response_model=FilterOptionsResponse)
@limiter.limit("60/minute")
async def get_filter_options(request: Request, db: Session = Depends(get_db)):
    """
    Return all available filter values from the database.
    Every dropdown value is dynamically sourced from SELECT DISTINCT queries.
    No hardcoded data. Response is cached for 60s server-side.
    """
    if db is None:
        logger.warning("Filter options called with no DB session")
        return FilterOptionsResponse(
            start_locations=[], end_locations=[], countries=[], regions=[], states=[],
            vacation_types=[], hotel_tiers=[], departure_types=[], train_names=[],
            duration_range={"min": 1, "max": 30}, total_packages=0
        )
    try:
        start = time.time()
        engine = RecommendationEngine(db)
        options = engine.get_filter_options()
        elapsed = (time.time() - start) * 1000
        logger.info(f"GET /filters completed in {elapsed:.0f}ms")
        return options
    except Exception as e:
        logger.error(f"Filter options error: {e}", exc_info=True)
        return FilterOptionsResponse(
            start_locations=[], end_locations=[], countries=[], regions=[], states=[],
            vacation_types=[], hotel_tiers=[], departure_types=[], train_names=[],
            duration_range={"min": 1, "max": 30}, total_packages=0
        )


@router.post("/search", response_model=RecommendationResponse)
@limiter.limit("30/minute")
async def search_recommendations(
    request: Request,
    body: RecommendationRequest,
    db: Session = Depends(get_db),
):
    """
    Search and score packages against filter criteria.
    Returns 6-12 best-matching packages for a proper browsing experience.

    Scoring:
      Exact city match:     +40
      Country match:        +30
      Vacation type match:  +20
      Duration match:       +15
      Hotel tier match:     +10
      Rank bonus:           +10
      Multi-country:        +5

    Strong match (>= 80%): returns up to 6 results.
    Good match (>= 50%):   returns up to 9 results.
    Otherwise:             returns up to 12 results.
    """
    empty = RecommendationResponse(
        packages=[], total_matched=0, total_returned=0,
        filters_applied=body.dict(exclude_none=True),
        scoring_summary="No results found", elapsed_ms=0.0
    )
    if db is None:
        logger.warning("Search called with no DB session")
        return empty
    try:
        engine = RecommendationEngine(db)
        filters = body.dict(exclude_none=True)
        # Auto-swap duration if min > max
        d_min = filters.get('duration_min')
        d_max = filters.get('duration_max')
        if d_min and d_max and d_min > d_max:
            filters['duration_min'], filters['duration_max'] = d_max, d_min
        result = engine.recommend(filters)
        return result
    except Exception as e:
        logger.error(f"Recommendation search error: {e}", exc_info=True)
        return empty


# ---------------------------------------------------------------------------
# AUTOSUGGEST ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("/locations")
@limiter.limit("60/minute")
async def get_all_locations(request: Request, db: Session = Depends(get_db)):
    """
    Return all unique locations from DB (cached 15min).
    Used by frontend to pre-populate autosuggest cache.
    Sources: start_location, end_location, included_cities, included_countries.
    """
    try:
        engine = RecommendationEngine(db)
        data = engine.get_all_locations()
        return {
            "locations": data.get("locations", []),
            "cities": data.get("cities", []),
            "countries": data.get("countries", []),
            "start_locations": data.get("start_locations", []),
            "end_locations": data.get("end_locations", []),
            "package_names": data.get("package_names", []),
            "total": len(data.get("locations", [])),
        }
    except Exception as e:
        logger.error(f"Locations endpoint error: {e}", exc_info=True)
        return {"locations": [], "total": 0}


@router.get("/autosuggest")
@limiter.limit("120/minute")
async def autosuggest(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    mode: str = Query("includes", description="starts_with | includes | ends_with"),
    field: str = Query("all", description="all | cities | countries | start_locations | end_locations | package_names"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    db: Session = Depends(get_db),
):
    """
    Auto-suggest locations/packages as user types.
    Supports 3 search modes: starts_with, includes, ends_with.
    Results come from cached DB data (15min TTL).
    """
    # Validate mode
    valid_modes = {"starts_with", "includes", "ends_with"}
    if mode not in valid_modes:
        mode = "includes"

    # Validate field
    valid_fields = {"all", "cities", "countries", "start_locations", "end_locations", "package_names"}
    if field not in valid_fields:
        field = "all"

    try:
        engine = RecommendationEngine(db)
        suggestions = engine.autosuggest(query=q, mode=mode, field=field, limit=limit)
        return {
            "query": q,
            "mode": mode,
            "field": field,
            "suggestions": suggestions,
            "count": len(suggestions),
        }
    except Exception as e:
        logger.error(f"Autosuggest error: {e}", exc_info=True)
        return {"query": q, "suggestions": [], "count": 0}


@router.get("/search-by-name")
@limiter.limit("30/minute")
async def search_by_name(
    request: Request,
    q: str = Query(..., min_length=2, max_length=200, description="Package name query"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Search packages directly by name.
    Returns matching packages sorted by rank.
    """
    try:
        engine = RecommendationEngine(db)
        results = engine.search_packages_by_name(query=q, limit=limit)
        return {
            "query": q,
            "packages": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"Search by name error: {e}", exc_info=True)
        return {"query": q, "packages": [], "total": 0}


@router.get("/package/{package_id}")
@limiter.limit("60/minute")
async def get_package_detail(
    request: Request,
    package_id: int,
    db: Session = Depends(get_db),
):
    """
    Get full enriched package detail by ID.
    Returns all fields including parsed highlights, inclusions,
    day-by-day itinerary, sales tips, estimated price, etc.
    Used by the View Itinerary detail page.
    """
    try:
        engine = RecommendationEngine(db)
        sql = (
            "SELECT id, casesafeid, external_name, start_location, end_location, "
            "included_cities, included_countries, included_regions, "
            "triptype, route, description, highlights, "
            "package_rank, profitability_group, duration, "
            "departure_type, departure_dates, package_url, "
            "included_states, sales_tips, inclusions, daybyday, access_rule "
            "FROM rag_packages WHERE id = :pid"
        )
        from sqlalchemy import text as sa_text
        row = db.execute(sa_text(sql), {"pid": package_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Package not found")

        pkg = engine._row_to_dict(row)
        pkg["match_score"] = 100.0
        pkg["match_reasons"] = ["Direct view"]

        # Return raw HTML fields for detail page rendering
        keys = [
            "id", "casesafeid", "external_name", "start_location", "end_location",
            "included_cities", "included_countries", "included_regions",
            "triptype", "route", "description", "highlights",
            "package_rank", "profitability_group", "duration",
            "departure_type", "departure_dates", "package_url",
            "included_states", "sales_tips", "inclusions", "daybyday", "access_rule",
        ]
        raw = {}
        for i, key in enumerate(keys):
            val = row[i] if i < len(row) else None
            raw[key] = str(val).strip() if val is not None else ""

        pkg["raw_description"] = raw.get("description", "")
        pkg["raw_highlights"] = raw.get("highlights", "")
        pkg["raw_inclusions"] = raw.get("inclusions", "")
        pkg["raw_daybyday"] = raw.get("daybyday", "")
        pkg["raw_sales_tips"] = raw.get("sales_tips", "")

        return {"package": pkg}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Package detail error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load package details")

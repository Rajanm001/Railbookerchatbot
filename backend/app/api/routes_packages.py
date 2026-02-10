from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from app.db.repositories import TravelPackageRepository
from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["packages"])


def _package_to_dict(package) -> Dict[str, Any]:
    """Convert package model to dictionary for API response."""
    if hasattr(package, '__dict__'):
        return {
            k: v for k, v in package.__dict__.items() 
            if not k.startswith('_')
        }
    return {}


# ============================================================================
# PRODUCTION ENDPOINTS - Query real Excel/JSON data
# ============================================================================

@router.get("/packages", response_model=List[Dict[str, Any]])
def list_packages(
    limit: int = Query(50, ge=1, le=500, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    List all packages with pagination.
    Returns real data from Excel/JSON source.
    """
    if db is None:
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
        return []
    try:
        repo = TravelPackageRepository(db)
        packages = repo.get_all(limit=limit, offset=offset)
        if not packages and settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="No packages available in database")
        return [_package_to_dict(p) for p in packages]
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"List packages failed: {e}")
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: internal error")
        return []


@router.get("/packages/filter", response_model=List[Dict[str, Any]])
def filter_packages(
    country: Optional[str] = Query(None, description="Filter by country"),
    region: Optional[str] = Query(None, description="Filter by region"),
    city: Optional[str] = Query(None, description="Filter by city"),
    trip_type: Optional[str] = Query(None, description="Filter by trip type"),
    min_duration: Optional[int] = Query(None, description="Minimum duration in days"),
    max_duration: Optional[int] = Query(None, description="Maximum duration in days"),
    profitability_group: Optional[str] = Query(None, description="Filter by profitability group"),
    search: Optional[str] = Query(None, description="Full-text search"),
    limit: int = Query(50, ge=1, le=200, description="Number of results"),
    db: Session = Depends(get_db)
):
    """
    Filter packages by multiple criteria.
    All filters are optional - SQL-first, no hallucination.
    """
    repo = TravelPackageRepository(db)
    packages = repo.filter_packages(
        country=country,
        region=region,
        city=city,
        trip_type=trip_type,
        min_duration=min_duration,
        max_duration=max_duration,
        profitability_group=profitability_group,
        search_text=search,
        limit=limit
    )
    return [_package_to_dict(p) for p in packages]


@router.get("/packages/recommend", response_model=List[Dict[str, Any]])
def recommend_packages(
    region: Optional[str] = Query(None, description="Preferred region"),
    profitability_group: Optional[str] = Query(None, description="Profitability group"),
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    db: Session = Depends(get_db)
):
    """
    Get recommended packages based on criteria.
    SQL-first recommendations - no AI guessing.
    """
    repo = TravelPackageRepository(db)
    packages = repo.recommend_packages(
        region=region,
        profitability_group=profitability_group,
        limit=limit
    )
    return [_package_to_dict(p) for p in packages]


@router.get("/packages/search", response_model=List[Dict[str, Any]])
def search_packages(
    q: str = Query(..., min_length=1, description="Search text"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Full-text search on package content.
    Searches name, description, highlights, cities, route.
    """
    repo = TravelPackageRepository(db)
    packages = repo.search_by_text(q, limit=limit)
    return [_package_to_dict(p) for p in packages]


@router.get("/packages/by-id/{package_id}", response_model=Dict[str, Any])
def get_package_by_id(
    package_id: int,
    db: Session = Depends(get_db)
):
    """Get package by database ID."""
    repo = TravelPackageRepository(db)
    package = repo.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return _package_to_dict(package)


@router.get("/packages/{casesafeid}", response_model=Dict[str, Any])
def get_package_details(
    casesafeid: str,
    db: Session = Depends(get_db)
):
    """
    Get full details for a specific package by CASESAFEID.
    Returns only DB-backed data.
    """
    repo = TravelPackageRepository(db)
    package = repo.get_by_casesafeid(casesafeid)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return _package_to_dict(package)


@router.get("/packages/count/total")
def get_package_count(db: Session = Depends(get_db)):
    """Get total count of packages in database."""
    if db is None:
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
        raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
    try:
        repo = TravelPackageRepository(db)
        count = repo.count_packages()
        if count == 0:
            raise HTTPException(status_code=503, detail="No packages available in database")
        return {"total_packages": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Package count failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable: internal error")


@router.get("/packages/meta/countries", response_model=List[str])
def get_unique_countries(db: Session = Depends(get_db)):
    """Get list of all unique countries from package data."""
    if db is None:
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
        raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
    try:
        repo = TravelPackageRepository(db)
        result = repo.get_unique_countries()
        if not result:
            raise HTTPException(status_code=503, detail="No countries found in database")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Countries fetch failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable: internal error")


@router.get("/packages/meta/trip-types", response_model=List[str])
def get_unique_trip_types(db: Session = Depends(get_db)):
    """Get list of all unique trip types from package data."""
    if db is None:
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
        raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
    try:
        repo = TravelPackageRepository(db)
        result = repo.get_unique_trip_types()
        if not result:
            raise HTTPException(status_code=503, detail="No trip types found in database")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trip types fetch failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable: internal error")


@router.get("/packages/meta/regions", response_model=List[str])
def get_unique_regions(db: Session = Depends(get_db)):
    """Get list of all unique regions from package data."""
    if db is None:
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
        raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
    try:
        repo = TravelPackageRepository(db)
        result = repo.get_unique_regions()
        if not result:
            raise HTTPException(status_code=503, detail="No regions found in database")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regions fetch failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable: internal error")


@router.get("/packages/meta/cities", response_model=List[str])
def get_unique_cities(
    country: Optional[str] = Query(None, description="Filter cities by country"),
    db: Session = Depends(get_db)
):
    """Get list of all unique cities from package data, optionally filtered by country."""
    if db is None:
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
        return []
    try:
        repo = TravelPackageRepository(db)
        result = repo.get_unique_cities(country=country)
        if not result and settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="No cities found in database")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Cities fetch failed: {e}")
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: internal error")
        return []


@router.get("/packages/meta/durations", response_model=List[str])
def get_unique_durations(db: Session = Depends(get_db)):
    """Get list of all unique durations from package data."""
    if db is None:
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
        raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
    try:
        repo = TravelPackageRepository(db)
        result = repo.get_unique_durations()
        if not result:
            raise HTTPException(status_code=503, detail="No durations found in database")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Durations fetch failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable: internal error")


@router.get("/packages/meta/hotel-tiers", response_model=List[str])
def get_hotel_tiers(db: Session = Depends(get_db)):
    """Get list of available hotel tiers (profitability groups)."""
    if db is None:
        if settings.enforce_real_data:
            raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
        raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
    try:
        repo = TravelPackageRepository(db)
        result = repo.get_unique_profitability_groups()
        if not result:
            raise HTTPException(status_code=503, detail="No hotel tiers found in database")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hotel tiers fetch failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable: internal error")


@router.get("/packages/meta/stats", response_model=Dict[str, Any])
def get_metadata_stats(db: Session = Depends(get_db)):
    """
    Get comprehensive metadata statistics for the chatbot.
    Returns counts and lists of all filterable attributes.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Service unavailable: database not connected")
    try:
        repo = TravelPackageRepository(db)
        countries = repo.get_unique_countries() or []
        regions = repo.get_unique_regions() or []
        return {
            "total_packages": repo.count_packages(),
            "countries": countries,
            "regions": regions,
            "trip_types": repo.get_unique_trip_types() or [],
            "durations": repo.get_unique_durations() or [],
            "hotel_tiers": repo.get_unique_profitability_groups() or [],
            "total_countries": len(countries),
            "total_regions": len(regions)
        }
    except Exception as e:
        logger.error(f"Stats fetch failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable: internal error")

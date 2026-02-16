"""
Repository pattern for data access.
SQL-first queries for travel packages. No hardcoded data.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, Integer
import logging

from app.db.models import TravelPackage

logger = logging.getLogger(__name__)


class TravelPackageRepository:
    """
    Repository for TravelPackage data access (rag_packages table).
    All queries are database-backed.
    """

    def __init__(self, db: Session):
        self.db = db
    
    def get_by_casesafeid(self, casesafeid: str) -> Optional[TravelPackage]:
        """Get package by CASESAFEID (unique identifier from Excel)."""
        try:
            return self.db.query(TravelPackage).filter(
                TravelPackage.casesafeid == casesafeid
            ).first()
        except Exception as e:
            logger.error(f"Error fetching package {casesafeid}: {str(e)}")
            return None
    
    def get_by_id(self, package_id: int) -> Optional[TravelPackage]:
        """Get package by database ID."""
        try:
            return self.db.query(TravelPackage).filter(
                TravelPackage.id == package_id
            ).first()
        except Exception as e:
            logger.error(f"Error fetching package {package_id}: {str(e)}")
            return None
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[TravelPackage]:
        """Get all packages with pagination."""
        try:
            return self.db.query(TravelPackage).limit(limit).offset(offset).all()
        except Exception as e:
            logger.error(f"Error fetching packages: {str(e)}")
            return []
    
    def filter_packages(
        self,
        country: Optional[str] = None,
        region: Optional[str] = None,
        city: Optional[str] = None,
        trip_type: Optional[str] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        profitability_group: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: int = 50
    ) -> List[TravelPackage]:
        """
        Filter packages by multiple criteria from Excel data.
        All filters are optional - only applied if provided.
        SQL-first, database-driven.
        """
        try:
            query = self.db.query(TravelPackage)
            
            # Country filter
            if country:
                query = query.filter(
                    TravelPackage.included_countries.ilike(f"%{country}%")
                )
            
            # Region filter
            if region:
                query = query.filter(
                    TravelPackage.included_regions.ilike(f"%{region}%")
                )
            
            # City filter
            if city:
                query = query.filter(
                    or_(
                        TravelPackage.included_cities.ilike(f"%{city}%"),
                        TravelPackage.start_location.ilike(f"%{city}%"),
                        TravelPackage.end_location.ilike(f"%{city}%")
                    )
                )
            
            # Trip type filter
            if trip_type:
                query = query.filter(
                    TravelPackage.triptype.ilike(f"%{trip_type}%")
                )
            
            # Duration filter (parse from text field)
            if min_duration is not None:
                # Try to extract numeric duration
                query = query.filter(
                    func.regexp_replace(TravelPackage.duration, '[^0-9]', '', 'g').cast(Integer) >= min_duration
                )
            
            if max_duration is not None:
                query = query.filter(
                    func.regexp_replace(TravelPackage.duration, '[^0-9]', '', 'g').cast(Integer) <= max_duration
                )
            
            # Profitability filter
            if profitability_group:
                query = query.filter(
                    TravelPackage.profitability_group.ilike(f"%{profitability_group}%")
                )
            
            # Full text search
            if search_text:
                search_pattern = f"%{search_text}%"
                query = query.filter(
                    or_(
                        TravelPackage.external_name.ilike(search_pattern),
                        TravelPackage.description.ilike(search_pattern),
                        TravelPackage.highlights.ilike(search_pattern),
                        TravelPackage.included_cities.ilike(search_pattern),
                        TravelPackage.route.ilike(search_pattern)
                    )
                )
            
            results = query.limit(limit).all()
            logger.debug(f"Filter query returned {len(results)} packages")
            return results
        
        except Exception as e:
            logger.error(f"Filter query error: {str(e)}")
            return []
    
    def search_by_text(self, search_text: str, limit: int = 20) -> List[TravelPackage]:
        """
        Full-text search on package content.
        Searches: name, description, highlights, cities, route.
        """
        try:
            search_pattern = f"%{search_text}%"
            
            return self.db.query(TravelPackage).filter(
                or_(
                    TravelPackage.external_name.ilike(search_pattern),
                    TravelPackage.description.ilike(search_pattern),
                    TravelPackage.highlights.ilike(search_pattern),
                    TravelPackage.included_cities.ilike(search_pattern),
                    TravelPackage.route.ilike(search_pattern),
                    TravelPackage.triptype.ilike(search_pattern)
                )
            ).limit(limit).all()
        
        except Exception as e:
            logger.error(f"Text search error: {str(e)}")
            return []
    
    def get_by_country(self, country: str, limit: int = 50) -> List[TravelPackage]:
        """Get packages by country."""
        try:
            return self.db.query(TravelPackage).filter(
                TravelPackage.included_countries.ilike(f"%{country}%")
            ).limit(limit).all()
        except Exception as e:
            logger.error(f"Country search error: {str(e)}")
            return []
    
    def get_by_trip_type(self, trip_type: str, limit: int = 50) -> List[TravelPackage]:
        """Get packages by trip type."""
        try:
            return self.db.query(TravelPackage).filter(
                TravelPackage.triptype.ilike(f"%{trip_type}%")
            ).limit(limit).all()
        except Exception as e:
            logger.error(f"Trip type search error: {str(e)}")
            return []
    
    def recommend_packages(
        self,
        region: Optional[str] = None,
        profitability_group: Optional[str] = None,
        limit: int = 10
    ) -> List[TravelPackage]:
        """
        Get recommended packages based on criteria.
        SQL-first, prioritizes by package_rank and profitability.
        """
        try:
            query = self.db.query(TravelPackage)
            
            if region:
                query = query.filter(
                    TravelPackage.included_regions.ilike(f"%{region}%")
                )
            
            if profitability_group:
                query = query.filter(
                    TravelPackage.profitability_group.ilike(f"%{profitability_group}%")
                )
            
            # Order by package rank (higher ranks first)
            query = query.order_by(TravelPackage.package_rank.desc())
            
            return query.limit(limit).all()
        
        except Exception as e:
            logger.error(f"Recommendation error: {str(e)}")
            return []
    
    def count_packages(self) -> int:
        """Get total count of packages."""
        try:
            return self.db.query(TravelPackage).count()
        except Exception as e:
            logger.error(f"Count error: {str(e)}")
            return 0
    
    def get_unique_countries(self) -> List[str]:
        """Get list of unique countries from data (pipe-delimited)."""
        try:
            results = self.db.query(TravelPackage.included_countries).distinct().all()
            countries = set()
            for row in results:
                if row[0]:
                    for c in str(row[0]).split('|'):
                        c = c.strip()
                        if c:
                            countries.add(c)
            return sorted(list(countries))
        except Exception as e:
            logger.error(f"Countries fetch error: {str(e)}")
            return []
    
    def get_unique_trip_types(self) -> List[str]:
        """Get list of unique trip types from data."""
        try:
            results = self.db.query(TravelPackage.triptype).distinct().all()
            return sorted([r[0] for r in results if r[0]])
        except Exception as e:
            logger.error(f"Trip types fetch error: {str(e)}")
            return []
    
    def get_unique_regions(self) -> List[str]:
        """Get list of unique regions from data (pipe-delimited)."""
        try:
            results = self.db.query(TravelPackage.included_regions).distinct().all()
            regions = set()
            for row in results:
                if row[0]:
                    for r in str(row[0]).split('|'):
                        r = r.strip()
                        if r:
                            regions.add(r)
            return sorted(list(regions))
        except Exception as e:
            logger.error(f"Regions fetch error: {str(e)}")
            return []
    
    def get_unique_cities(self, country: Optional[str] = None) -> List[str]:
        """Get list of unique cities from data, optionally filtered by country."""
        try:
            query = self.db.query(TravelPackage.included_cities, TravelPackage.start_location, 
                                  TravelPackage.end_location, TravelPackage.included_countries)
            
            if country:
                query = query.filter(
                    TravelPackage.included_countries.ilike(f"%{country}%")
                )
            
            results = query.all()
            cities = set()
            
            for row in results:
                # Add cities from included_cities (pipe-delimited)
                if row[0]:
                    for c in str(row[0]).split('|'):
                        c = c.strip()
                        if c:
                            cities.add(c)
                # Add start_location
                if row[1]:
                    cities.add(str(row[1]).strip())
                # Add end_location
                if row[2]:
                    cities.add(str(row[2]).strip())
            
            return sorted(list(cities))
        except Exception as e:
            logger.error(f"Cities fetch error: {str(e)}")
            return []
    
    def get_unique_durations(self) -> List[str]:
        """Get list of unique durations from data."""
        try:
            results = self.db.query(TravelPackage.duration).distinct().all()
            durations = [r[0] for r in results if r[0]]
            return sorted(durations)
        except Exception as e:
            logger.error(f"Durations fetch error: {str(e)}")
            return []
    
    def get_unique_profitability_groups(self) -> List[str]:
        """Get list of unique profitability groups (hotel tiers)."""
        try:
            results = self.db.query(TravelPackage.profitability_group).distinct().all()
            groups = [r[0] for r in results if r[0]]
            return sorted(groups)
        except Exception as e:
            logger.error(f"Profitability groups fetch error: {str(e)}")
            return []


def get_travel_package_repository(db: Session) -> TravelPackageRepository:
    """FastAPI dependency for travel package repository."""
    return TravelPackageRepository(db)

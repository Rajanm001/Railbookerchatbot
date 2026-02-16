"""
Database models -- SQLAlchemy ORM definitions.
Single source of truth: rag_packages table (maps to cleaned_packages.json).
Compatible with both PostgreSQL and SQLite.
"""

from sqlalchemy import Column, Integer, Text, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TravelPackage(Base):
    """
    Rail vacation packages from Excel/JSON data.
    Maps 1:1 to cleaned_packages.json fields.
    Table: rag_packages (2004 rows seeded from KT_package_filtering_output Excel).
    """
    __tablename__ = "rag_packages"

    id = Column(Integer, primary_key=True, index=True)
    casesafeid = Column(Text, unique=True, index=True)
    external_name = Column(Text, index=True)
    start_location = Column(Text, index=True)
    end_location = Column(Text, index=True)
    included_cities = Column(Text, index=True)
    included_states = Column(Text)
    included_countries = Column(Text, index=True)
    included_regions = Column(Text, index=True)
    triptype = Column(Text, index=True)
    route = Column(Text)
    sales_tips = Column(Text)
    description = Column(Text)
    highlights = Column(Text)
    inclusions = Column(Text)
    daybyday = Column(Text)
    package_rank = Column(Text, index=True)
    profitability_group = Column(Text, index=True)
    access_rule = Column(Text)
    duration = Column(Text, index=True)
    departure_type = Column(Text, index=True)
    departure_dates = Column(Text)
    package_url = Column(Text)

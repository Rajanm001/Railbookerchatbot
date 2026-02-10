"""
Seed SQLite database with 2004 packages from cleaned_packages.json.
Creates rag_packages table and inserts all packages.
Run: python seed_sqlite.py
"""

import json
import os
import sys

# Add parent directory to path for app imports
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, TravelPackage


def main():
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), "rail_planner.db")
    db_url = f"sqlite:///{db_path}"

    print(f"Database: {db_path}")

    # Create engine with SQLite optimizations
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable WAL mode for better concurrency
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.execute(text("PRAGMA cache_size=-65536"))
        conn.commit()

    # Create all tables
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Tables created")

    # Load JSON data
    json_path = os.path.join(
        os.path.dirname(__file__),
        "app", "ingestion", "cleaned_packages.json",
    )

    with open(json_path, "r", encoding="utf-8") as f:
        packages = json.load(f)

    print(f"Loaded {len(packages)} packages from JSON")

    # JSON field -> model column mapping
    FIELD_MAP = {
        "CASESAFEID__c": "casesafeid",
        "KaptioTravel__ExternalName__c": "external_name",
        "startlocation": "start_location",
        "endlocation": "end_location",
        "includedcities": "included_cities",
        "includedstates_provinces": "included_states",
        "includedcountries": "included_countries",
        "includedregions": "included_regions",
        "triptype": "triptype",
        "route": "route",
        "KaptioTravel__Value__c": "sales_tips",
        "packagedescription": "description",
        "packagehighlights": "highlights",
        "packageinclusions": "inclusions",
        "packagedaybyday": "daybyday",
        "packagerank": "package_rank",
        "profitabilitygroup": "profitability_group",
        "accessrule": "access_rule",
        "duration": "duration",
        "departuretype": "departure_type",
        "departuredates": "departure_dates",
        "package_url": "package_url",
    }

    Session = sessionmaker(bind=engine)
    session = Session()

    count = 0
    errors = 0
    seen_ids = set()

    for pkg_data in packages:
        caseid = pkg_data.get("CASESAFEID__c", "")
        if not caseid or caseid in seen_ids:
            errors += 1
            continue
        seen_ids.add(caseid)

        row = {}
        for json_key, col_name in FIELD_MAP.items():
            val = pkg_data.get(json_key, "")
            if val is None:
                val = ""
            row[col_name] = str(val).strip()

        pkg = TravelPackage(**row)
        session.add(pkg)
        count += 1

        if count % 500 == 0:
            session.commit()
            print(f"  ...inserted {count}")

    session.commit()

    # Verify
    total = session.execute(text("SELECT COUNT(*) FROM rag_packages")).scalar()
    countries = session.execute(
        text("SELECT COUNT(DISTINCT included_countries) FROM rag_packages "
             "WHERE included_countries IS NOT NULL AND included_countries != ''")
    ).scalar()

    print(f"\nDone! Inserted {count} packages ({errors} skipped)")
    print(f"Verified: {total} rows in rag_packages")
    print(f"Distinct country combos: {countries}")

    # Build RAG vector index
    print("\nBuilding RAG vector index...")
    from app.services.vector_store import VectorStore
    store = VectorStore(session)
    indexed = store.build_index()
    print(f"RAG index built: {indexed} vectors")

    session.close()
    engine.dispose()
    print("\nSeed complete!")


if __name__ == "__main__":
    main()

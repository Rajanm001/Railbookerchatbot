"""
Seed rag_packages table from cleaned_packages.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.db.database import engine, SessionLocal, init_db

JSON_PATH = Path(__file__).parent / "app" / "ingestion" / "cleaned_packages.json"

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


def seed():
    print("Initializing database schema...")
    init_db()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        packages = json.load(f)
    print(f"Loaded {len(packages)} packages from JSON")

    db = SessionLocal()
    try:
        # Clear existing
        db.execute(text("DELETE FROM rag_packages"))
        db.commit()
        print("Cleared existing rag_packages rows")

        count = 0
        seen_ids = set()
        skipped = 0
        for pkg in packages:
            case_id = str(pkg.get("CASESAFEID__c", "")).strip()
            if case_id in seen_ids:
                skipped += 1
                continue
            seen_ids.add(case_id)

            row = {}
            for json_key, col_name in FIELD_MAP.items():
                val = pkg.get(json_key, "")
                if val is None:
                    val = ""
                row[col_name] = str(val).strip()
            
            cols = ", ".join(row.keys())
            placeholders = ", ".join(f":{k}" for k in row.keys())
            sql = f"INSERT INTO rag_packages ({cols}) VALUES ({placeholders})"
            db.execute(text(sql), row)
            count += 1
            if count % 500 == 0:
                db.commit()
                print(f"  Inserted {count}...")

        db.commit()
        
        # Verify
        result = db.execute(text("SELECT COUNT(*) FROM rag_packages")).scalar()
        print(f"\nDone! Total rows in rag_packages: {result} (skipped {skipped} duplicates)")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

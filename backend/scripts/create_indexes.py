"""Create performance indexes for recommendation engine."""
import sqlite3

conn = sqlite3.connect("rail_planner.db")
c = conn.cursor()

indexes = [
    ("idx_rp_start_loc", "start_location"),
    ("idx_rp_end_loc", "end_location"),
    ("idx_rp_inc_cities", "included_cities"),
    ("idx_rp_pkg_rank", "package_rank"),
    ("idx_rp_dep_type", "departure_type"),
]

for idx_name, col in indexes:
    c.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON rag_packages ({col})")
    print(f"  Created {idx_name} on {col}")

conn.commit()

# Show all indexes
rows = c.execute(
    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='rag_packages'"
).fetchall()
print(f"\nAll indexes on rag_packages ({len(rows)}):")
for r in rows:
    print(f"  {r[0]}")

conn.close()
print("\nDone.")

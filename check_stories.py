import sqlite3
import os

db = os.path.join(os.path.dirname(__file__), "news.db")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

total = conn.execute("SELECT COUNT(*) FROM discovered_stories").fetchone()[0]
print(f"\nTotal stories in DB: {total}")

print("\n--- By Category ---")
for row in conn.execute("SELECT category, COUNT(*) as cnt FROM discovered_stories GROUP BY category ORDER BY cnt DESC"):
    print(f"  {row['category']:<20} {row['cnt']}")

print("\n--- By Source ---")
for row in conn.execute("SELECT source_name, COUNT(*) as cnt FROM discovered_stories GROUP BY source_name ORDER BY cnt DESC"):
    print(f"  {row['source_name']:<40} {row['cnt']}")

print("\n--- By Status ---")
for row in conn.execute("SELECT status, COUNT(*) as cnt FROM discovered_stories GROUP BY status ORDER BY cnt DESC"):
    print(f"  {row['status']:<20} {row['cnt']}")

print("\n--- Latest 20 Stories ---\n")
rows = conn.execute("""
    SELECT title, source_name, category, credibility_score, priority_score, discovered_at
    FROM discovered_stories
    ORDER BY discovered_at DESC
    LIMIT 20
""").fetchall()

for i, r in enumerate(rows, 1):
    print(f"{i:>2}. [{r['category']}] {r['title'][:80]}")
    print(f"     Source: {r['source_name'][:40]}  |  Credibility: {r['credibility_score']}  |  Priority: {r['priority_score']:.2f}")
    print(f"     Discovered: {r['discovered_at']}")
    print()

conn.close()
input("\nPress Enter to exit...")

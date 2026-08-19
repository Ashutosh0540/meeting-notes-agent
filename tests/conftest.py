import os

# Keep tests independent from a developer's local Supabase configuration.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

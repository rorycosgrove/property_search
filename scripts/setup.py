"""Run database migrations and initial setup."""
import subprocess
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    print("=== Property Search Setup ===\n")

    # 1. Alembic migrations
    print("1. Running database migrations...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("   ✓ Migrations complete")
    else:
        print(f"   ✗ Migration failed: {result.stderr}")
        # Try creating tables directly as fallback
        print("   Falling back to direct table creation...")
        from packages.storage.database import engine
        from packages.storage.models import Base
        Base.metadata.create_all(bind=engine)
        print("   ✓ Tables created directly")

    # 2. Seed default sources
    print("\n2. Seeding default sources...")
    from scripts.seed import seed_sources
    seed_sources()

    print("\n=== Setup complete ===")
    print("Deploy to AWS:       cd infra && npx cdk deploy --all")
    print("Or run locally with: uvicorn apps.api.main:app --reload --port 8000")


if __name__ == "__main__":
    main()

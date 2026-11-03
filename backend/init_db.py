"""Database initialization and seeding script for deployment (Render, Docker, VPS).

Run directly with:
    python init_db.py
"""
import os
import sys

from wsgi import application
from app.extensions import db
from app.models.plan import Plan, PlanTier


def init_database():
    """Create all tables and seed required initial system plans."""
    with application.app_context():
        print("Creating database tables if not exist...")
        db.create_all()
        print("Database schema successfully verified.")

        # Seed initial plans
        existing_plans = Plan.query.count()
        if existing_plans == 0:
            print("Seeding default subscription plans...")
            free_plan = Plan(
                name="Free",
                tier=PlanTier.FREE,
                description="Essential features for individual creators",
                price_monthly_cents=0,
                price_yearly_cents=0,
                max_social_accounts=2,
                max_team_members=1,
                max_ai_generations_per_month=30,
                max_image_generations_per_month=10,
                audit_history_days=7,
            )
            starter_plan = Plan(
                name="Starter",
                tier=PlanTier.STARTER,
                description="For growing brands and small teams",
                price_monthly_cents=1500,
                price_yearly_cents=15000,
                max_social_accounts=5,
                max_team_members=3,
                max_ai_generations_per_month=100,
                max_image_generations_per_month=40,
                audit_history_days=30,
            )
            pro_plan = Plan(
                name="Pro",
                tier=PlanTier.PRO,
                description="Complete AI social automation suite for agencies",
                price_monthly_cents=4900,
                price_yearly_cents=49000,
                max_social_accounts=25,
                max_team_members=10,
                max_ai_generations_per_month=500,
                max_image_generations_per_month=200,
                audit_history_days=90,
            )
            enterprise_plan = Plan(
                name="Enterprise",
                tier=PlanTier.ENTERPRISE,
                description="Unlimited scale, custom security, and SLAs",
                price_monthly_cents=19900,
                price_yearly_cents=199000,
                max_social_accounts=-1,
                max_team_members=-1,
                max_ai_generations_per_month=-1,
                max_image_generations_per_month=-1,
                audit_history_days=365,
            )
            db.session.add_all([free_plan, starter_plan, pro_plan, enterprise_plan])
            db.session.commit()
            print("Successfully seeded 4 subscription tiers (Free, Starter, Pro, Enterprise).")
        else:
            print(f"Plans table already has {existing_plans} tiers. Skipping plan seed.")

        print("Database initialization complete.")


if __name__ == "__main__":
    init_database()


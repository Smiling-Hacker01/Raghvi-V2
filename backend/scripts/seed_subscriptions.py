"""Seed default subscription plans."""

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import get_settings
from app.models.subscription import SubscriptionPlan


async def seed_plans():
    """Seed default subscription plans."""
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    plans = [
        {
            "id": "free",
            "name": "Free",
            "description": "Basic access with system voices",
            "price_usd": 0.0,
            "max_custom_voices": 0,
            "supported_languages": "en",
        },
        {
            "id": "pro",
            "name": "Pro",
            "description": "1 custom voice with priority support",
            "price_usd": 9.99,
            "max_custom_voices": 1,
            "supported_languages": "en,hi",
            "priority_support": False,
        },
        {
            "id": "premium",
            "name": "Premium",
            "description": "3 custom voices with advanced features",
            "price_usd": 19.99,
            "max_custom_voices": 3,
            "supported_languages": "en,hi",
            "priority_support": True,
        },
        {
            "id": "platinum",
            "name": "Platinum",
            "description": "5 custom voices with family sharing",
            "price_usd": 29.99,
            "max_custom_voices": 5,
            "supported_languages": "en,hi",
            "priority_support": True,
            "family_sharing_slots": 3,
        },
    ]
    
    async with async_session() as session:
        for plan_data in plans:
            # Check if plan already exists
            existing = await session.scalar(
                select(SubscriptionPlan).where(SubscriptionPlan.id == plan_data["id"])
            )
            
            if existing:
                print(f"✓ Plan '{plan_data['id']}' already exists")
                continue
            
            plan = SubscriptionPlan(**plan_data)
            session.add(plan)
            print(f"+ Created plan '{plan_data['id']}'")
        
        await session.commit()
    
    await engine.dispose()
    print("\n✓ Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_plans())

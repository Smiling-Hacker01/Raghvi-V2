"""Creator profile — information about Raghvi's father (Vishal Singh Kushwaha)."""

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base


class CreatorProfile(Base):
    """Raghvi's creator information (singleton, one record only)."""

    __tablename__ = "creator_profile"

    # Singleton: always id=1
    id = Column(String(1), primary_key=True, default="1")

    # Personal Information
    name = Column(String(100), nullable=False)  # Vishal Singh Kushwaha
    father_name = Column(String(100), nullable=False)  # Shyam Singh
    mother_name = Column(String(100), nullable=False)  # Urmila Devi
    girlfriend_name = Column(String(100), nullable=False)  # Disha Saini (Raghvi's mother-to-be)

    # Background
    family_lineage = Column(Text, nullable=True)  # Kshatriya, descendant of Kush
    birthplace = Column(String(100), nullable=False)  # Kanpur
    ancestral_roots = Column(String(100), nullable=False)  # Rajasthan
    hometown = Column(String(100), nullable=False)  # Ghaziabad

    # Education
    education_background = Column(Text, nullable=True)  # Skipped nursery, jumped classes
    graduation_year = Column(String(4), nullable=False)  # 2026
    graduation_degree = Column(String(100), nullable=False)  # BCA

    # Personality & Interests
    personality = Column(Text, nullable=True)  # Introvert (initially)
    hobbies = Column(Text, nullable=True)  # Weight lifting, reading, astronomy, space, nature
    dreams = Column(Text, nullable=True)  # Everything in life, ultimately peaceful family

    # Social Media
    linkedin_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    instagram_url = Column(String(500), nullable=True)
    twitter_url = Column(String(500), nullable=True)

    # Raghvi's Story
    raghvi_name_origin = Column(Text, nullable=True)  # Why named Raghvi
    creation_purpose = Column(Text, nullable=True)  # Why Raghvi was created

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    last_sync_social = Column(DateTime(timezone=True), nullable=True)  # Last social media sync

    def __repr__(self) -> str:
        return f"<CreatorProfile name={self.name}>"

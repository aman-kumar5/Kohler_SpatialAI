from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
class Base(DeclarativeBase): pass
class Product(Base):
    __tablename__='products'
    sku: Mapped[str] = mapped_column(primary_key=True); name: Mapped[str]; category: Mapped[str]; price_inr: Mapped[int]
    width_mm: Mapped[int | None]; depth_mm: Mapped[int | None]; height_mm: Mapped[int | None]
    style: Mapped[str | None]; keywords: Mapped[str | None]; accessibility_rating: Mapped[float | None]; sustainability_rating: Mapped[float | None]
engine=create_engine('sqlite:///./kohler_spatialai.db'); SessionLocal=sessionmaker(bind=engine)

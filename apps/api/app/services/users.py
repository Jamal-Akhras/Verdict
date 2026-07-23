"""Demo user until Clerk auth lands (ticket #4)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import User

DEMO_CLERK_ID = "demo"


def get_or_create_demo_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.clerk_id == DEMO_CLERK_ID))
    if user is None:
        user = User(clerk_id=DEMO_CLERK_ID, email="demo@verdict.local", name="Demo Founder")
        db.add(user)
        db.flush()
    return user

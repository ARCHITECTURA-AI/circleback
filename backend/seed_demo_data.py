import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Ensure we can import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from circleback.config import get_settings  # noqa: E402
from circleback.db.models import (  # noqa: E402
    Base,
    ChannelType,
    Commitment,
    CommitmentDirection,
    CommitmentEvent,
    CommitmentEventType,
    CommitmentStatus,
    CommitmentType,
    Message,
    Person,
    Thread,
    User,
)


async def seed():
    print("Starting database seed for demo...")
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    # Create all tables (useful for fresh SQLite databases)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Get or create the main user
        result = await session.execute(select(User))
        main_user = result.scalars().first()
        if not main_user:
            print("Creating dummy user account...")
            main_user = User(id=str(uuid4()), email="demo@circleback.ai")
            session.add(main_user)
            await session.commit()

        uid = main_user.id

        # 1. Create Persons (Identities)
        me = Person(user_id=uid, display_name="Me", email_addresses=["me@example.com"], is_self=True)
        alice = Person(user_id=uid, display_name="Alice Client", email_addresses=["alice@client.com"], is_self=False)
        bob = Person(user_id=uid, display_name="Bob Engineering", email_addresses=["bob@eng.com"], is_self=False)

        session.add_all([me, alice, bob])
        await session.commit()

        # 2. Create Threads
        thread_overdue = Thread(user_id=uid, channel=ChannelType.EMAIL, external_thread_id="th_overdue", participant_person_ids=[me.id, alice.id])
        thread_open = Thread(user_id=uid, channel=ChannelType.SLACK, external_thread_id="th_open", participant_person_ids=[me.id, bob.id])

        session.add_all([thread_overdue, thread_open])
        await session.commit()

        # 3. Create Messages
        msg1 = Message(
            user_id=uid, thread_id=thread_overdue.id, channel=ChannelType.EMAIL,
            external_message_id="msg_1", sender_handle="alice@client.com", sender_person_id=alice.id,
            raw_text="I'll send you the finalized Q3 contract by Tuesday.",
            timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        msg2 = Message(
            user_id=uid, thread_id=thread_open.id, channel=ChannelType.SLACK,
            external_message_id="msg_2", sender_handle="me@example.com", sender_person_id=me.id,
            raw_text="I will deploy the new Groq integration on Friday.",
            timestamp=datetime.now(timezone.utc) - timedelta(days=1)
        )

        session.add_all([msg1, msg2])
        await session.commit()

        # 4. Create Commitments
        # Commitment 1: Overdue (Alice owes Me)
        c_overdue = Commitment(
            user_id=uid,
            thread_id=thread_overdue.id,
            source_message_id=msg1.id,
            status=CommitmentStatus.OVERDUE,
            commitment_type=CommitmentType.SIMPLE,
            direction=CommitmentDirection.OWED_TO_USER,
            committer_person_id=alice.id,
            recipient_person_ids=[me.id],
            raw_text_span="I'll send you the finalized Q3 contract by Tuesday",
            raw_temporal_phrase="by Tuesday",
            resolved_deadline=datetime.now(timezone.utc) - timedelta(days=1), # Missed yesterday
            extraction_confidence=0.95
        )

        # Commitment 2: Open (I owe Bob)
        c_open = Commitment(
            user_id=uid,
            thread_id=thread_open.id,
            source_message_id=msg2.id,
            status=CommitmentStatus.OPEN,
            commitment_type=CommitmentType.SIMPLE,
            direction=CommitmentDirection.MADE_BY_USER,
            committer_person_id=me.id,
            recipient_person_ids=[bob.id],
            raw_text_span="I will deploy the new Groq integration on Friday",
            raw_temporal_phrase="on Friday",
            resolved_deadline=datetime.now(timezone.utc) + timedelta(days=2), # Due in 2 days
            extraction_confidence=0.98
        )

        session.add_all([c_overdue, c_open])
        await session.commit()

        # 5. Create Audit Events
        ev1 = CommitmentEvent(commitment_id=c_overdue.id, type=CommitmentEventType.EXTRACTED, evidence_message_id=msg1.id)
        ev2 = CommitmentEvent(commitment_id=c_open.id, type=CommitmentEventType.EXTRACTED, evidence_message_id=msg2.id)

        session.add_all([ev1, ev2])
        await session.commit()

        print(f"[SUCCESS] Demo data seeded successfully for User ID: {uid[:8]}...")
        print("You can now open the dashboard at http://localhost:3000 to record the Loom!")

if __name__ == "__main__":
    asyncio.run(seed())

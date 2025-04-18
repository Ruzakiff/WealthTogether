import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import os
from uuid import uuid4

from backend.app.models.models import Base, User, Couple, BankAccount, FinancialGoal, AllocationMap, GoalType
from backend.app.database import get_db_session
from backend.app.main import app

# Use a test database
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    # Teardown - drop all tables
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test.db"):
        os.remove("./test.db")

@pytest.fixture(scope="function")
def db_session(db_engine):
    """Returns a fresh SQLAlchemy session for each test"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    
    # Clear out test data from previous run
    session.query(AllocationMap).delete()
    session.query(FinancialGoal).delete()
    session.query(BankAccount).delete()
    session.query(Couple).delete()
    session.query(User).delete()
    session.commit()
    
    yield session
    session.close()

@pytest.fixture
def client(db_session):
    """Test client fixture that uses the db_session fixture"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db_session] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user(db_session):
    """Creates a test user and returns it"""
    user = User(
        id=str(uuid4()),
        email="test@example.com",
        display_name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def test_couple(db_session, test_user):
    """Creates a test couple with two users and returns it"""
    # Create a second user
    partner = User(
        id=str(uuid4()),
        email="partner@example.com",
        display_name="Partner User"
    )
    db_session.add(partner)
    db_session.commit()
    
    # Create the couple
    couple = Couple(
        id=str(uuid4()),
        partner_1_id=test_user.id,
        partner_2_id=partner.id
    )
    db_session.add(couple)
    db_session.commit()
    db_session.refresh(couple)
    return couple

@pytest.fixture
def test_account(db_session, test_user):
    """Creates a test bank account and returns it"""
    account = BankAccount(
        id=str(uuid4()),
        user_id=test_user.id,
        name="Test Account",
        balance=10000.0,
        is_manual=True,
        institution_name="Test Bank"
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account

@pytest.fixture
def test_goal(db_session, test_couple):
    """Creates a test financial goal and returns it"""
    from backend.app.models.models import GoalType
    
    # Check the actual values in the enum
    print("Available GoalType values:", [e.name for e in GoalType])
    
    # Use the correct enum value - uppercase EMERGENCY
    goal = FinancialGoal(
        id=str(uuid4()),
        couple_id=test_couple.id,
        name="Test Goal",
        target_amount=5000.0,
        type=GoalType.EMERGENCY,
        current_allocation=0.0,
        priority=1
    )
    db_session.add(goal)
    db_session.commit()
    db_session.refresh(goal)
    return goal 
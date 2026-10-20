import os
os.environ['DATABASE_URL']='sqlite:///test-netbot.db'
os.environ['ALLOW_HTTP_LOCAL']='true'
import pytest
from core.db import Base, engine
from core import models

@pytest.fixture(autouse=True)
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

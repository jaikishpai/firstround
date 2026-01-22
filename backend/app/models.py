import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


class RoleName(str, enum.Enum):
    admin = "admin"
    candidate = "candidate"


class SessionStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    submitted = "submitted"
    auto_submitted = "auto_submitted"
    expired = "expired"


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(Enum(RoleName), unique=True, nullable=False)

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    role = relationship("Role", back_populates="users")
    assignments = relationship("TestAssignment", back_populates="user")
    sessions = relationship("TestSession", back_populates="user")


class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    test_type_id = Column(Integer, ForeignKey("test_types.id"), nullable=False, index=True)
    question_set_id = Column(Integer, ForeignKey("question_sets.id"), nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    warning_minutes = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    test_type = relationship("TestType", back_populates="tests")
    question_set = relationship("QuestionSet", back_populates="tests")
    assignments = relationship("TestAssignment", back_populates="test")
    sessions = relationship("TestSession", back_populates="test")


class TestType(Base):
    __tablename__ = "test_types"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tests = relationship("Test", back_populates="test_type")


class QuestionSet(Base):
    __tablename__ = "question_sets"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    test_type_id = Column(Integer, ForeignKey("test_types.id"), nullable=False, index=True)
    duration_minutes = Column(Integer, default=60, nullable=False)
    warning_minutes = Column(Integer, default=5, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    test_type = relationship("TestType")
    questions = relationship("QuestionSetQuestion", back_populates="question_set")
    tests = relationship("Test", back_populates="question_set")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    sections = Column(Text, nullable=True)
    answer_type = Column(String(50), default="long_text", nullable=False)
    allow_multiple = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    sets = relationship("QuestionSetQuestion", back_populates="question")
    answers = relationship("Answer", back_populates="question")
    options = relationship("QuestionOption", back_populates="question")


class QuestionOption(Base):
    __tablename__ = "question_options"
    __table_args__ = (Index("idx_question_options_question", "question_id"),)

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    order = Column(Integer, default=0, nullable=False)

    question = relationship("Question", back_populates="options")


class QuestionSetQuestion(Base):
    __tablename__ = "question_set_questions"
    __table_args__ = (
        UniqueConstraint("question_set_id", "question_id"),
        UniqueConstraint("question_id"),
    )

    id = Column(Integer, primary_key=True)
    question_set_id = Column(
        Integer, ForeignKey("question_sets.id"), nullable=False, index=True
    )
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    order = Column(Integer, default=0, nullable=False)

    question_set = relationship("QuestionSet", back_populates="questions")
    question = relationship("Question", back_populates="sets")


class TestAssignment(Base):
    __tablename__ = "test_assignments"
    __table_args__ = (UniqueConstraint("session_code"),)

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=True, index=True)
    question_set_id = Column(
        Integer, ForeignKey("question_sets.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_code = Column(String(32), nullable=False, index=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    test = relationship("Test", back_populates="assignments")
    question_set = relationship("QuestionSet")
    user = relationship("User", back_populates="assignments")
    sessions = relationship("TestSession", back_populates="assignment")


class TestSession(Base):
    __tablename__ = "test_sessions"
    __table_args__ = (
        Index("idx_sessions_user_test", "user_id", "test_id"),
    )

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=True, index=True)
    question_set_id = Column(
        Integer, ForeignKey("question_sets.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("test_assignments.id"), nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.assigned, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    violation_token = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    test = relationship("Test", back_populates="sessions")
    question_set = relationship("QuestionSet")
    user = relationship("User", back_populates="sessions")
    assignment = relationship("TestAssignment", back_populates="sessions")
    answers = relationship("Answer", back_populates="session")
    violations = relationship("Violation", back_populates="session")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("test_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    answer_text = Column(Text, nullable=True)
    is_final = Column(Boolean, default=False, nullable=False)
    last_saved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    session = relationship("TestSession", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    selected_options = relationship("AnswerOption", back_populates="answer")


class AnswerOption(Base):
    __tablename__ = "answer_options"
    __table_args__ = (Index("idx_answer_options_answer", "answer_id"),)

    id = Column(Integer, primary_key=True)
    answer_id = Column(Integer, ForeignKey("answers.id"), nullable=False)
    option_id = Column(Integer, ForeignKey("question_options.id"), nullable=False)

    answer = relationship("Answer", back_populates="selected_options")


class ViolationType(str, enum.Enum):
    fullscreen_exit = "fullscreen_exit"
    tab_switch = "tab_switch"
    window_blur = "window_blur"
    devtools_open = "devtools_open"
    unknown = "unknown"


class Violation(Base):
    __tablename__ = "violations"
    __table_args__ = (Index("idx_violations_session", "session_id"),)

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("test_sessions.id"), nullable=False)
    event_type = Column(Enum(ViolationType), nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("TestSession", back_populates="violations")


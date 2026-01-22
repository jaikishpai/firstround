import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import (
    Answer,
    AnswerOption,
    Question,
    QuestionOption,
    QuestionSet,
    QuestionSetQuestion,
    Role,
    RoleName,
    SessionStatus,
    Test,
    TestAssignment,
    TestSession,
    TestType,
    User,
    Violation,
    ViolationType,
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleName


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: RoleName


class UserUpdateRequest(BaseModel):
    password: Optional[str] = None
    is_active: Optional[bool] = None


class TestCreateRequest(BaseModel):
    title: str
    test_type_id: int
    question_set_id: int
    duration_minutes: int = Field(gt=0)
    warning_minutes: int = Field(default=5, ge=1)


class TestUpdateRequest(BaseModel):
    title: Optional[str] = None
    test_type_id: Optional[int] = None
    question_set_id: Optional[int] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    warning_minutes: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None


class OptionInput(BaseModel):
    option_text: str
    is_correct: bool = False


class QuestionCreateRequest(BaseModel):
    title: str
    body: str
    sections: Optional[str] = None
    answer_type: str = Field(default="long_text")
    allow_multiple: bool = False
    options: Optional[list[OptionInput]] = None


class QuestionUpdateRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    sections: Optional[str] = None
    answer_type: Optional[str] = None
    allow_multiple: Optional[bool] = None
    options: Optional[list[OptionInput]] = None


class QuestionSetCreateRequest(BaseModel):
    name: str
    test_type_id: int
    description: Optional[str] = None
    duration_minutes: int = Field(default=60, gt=0)
    warning_minutes: int = Field(default=5, ge=1)


class QuestionSetUpdateRequest(BaseModel):
    name: Optional[str] = None
    test_type_id: Optional[int] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    warning_minutes: Optional[int] = Field(default=None, ge=1)


class QuestionOrderRequest(BaseModel):
    question_ids: list[int]


class AssignQuestionSetRequest(BaseModel):
    question_set_id: int
    user_id: int


class StartSessionRequest(BaseModel):
    session_code: str


class ValidateSessionRequest(BaseModel):
    session_code: str


class AnswerSaveRequest(BaseModel):
    session_id: int
    question_id: int
    answer_text: Optional[str] = None
    selected_option_ids: Optional[list[int]] = None


class SubmitRequest(BaseModel):
    session_id: int


class ViolationCreateRequest(BaseModel):
    session_id: int
    event_type: ViolationType
    metadata: Optional[str] = None
    token: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        # Pre-hash long secrets to satisfy bcrypt limits without truncation.
        password = f"sha256${hashlib.sha256(password.encode('utf-8')).hexdigest()}"
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception
    return user


def require_role(role: RoleName):
    async def _role_dependency(current_user: User = Depends(get_current_user)):
        if current_user.role.name != role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user

    return _role_dependency


async def ensure_session_active(session: TestSession) -> None:
    if session.status in {SessionStatus.submitted, SessionStatus.auto_submitted}:
        raise HTTPException(status_code=400, detail="Session already submitted")
    if session.status != SessionStatus.in_progress:
        raise HTTPException(status_code=400, detail="Session not active")
    if session.end_time and session.end_time <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Session expired")


async def auto_submit_session(db: AsyncSession, session: TestSession) -> None:
    session.status = SessionStatus.auto_submitted
    session.submitted_at = datetime.utcnow()
    await db.execute(
        update(Answer)
        .where(Answer.session_id == session.id)
        .values(is_final=True, updated_at=datetime.utcnow())
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and issue access token."""
    try:
        result = await db.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.username == payload.username)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(payload.password, user.password_hash):
            return JSONResponse(
                status_code=401, content={"error": "Invalid username or password"}
            )
        token = create_access_token(
            {"sub": user.username},
            timedelta(minutes=settings.access_token_expire_minutes),
        )
        return TokenResponse(access_token=token, role=user.role.name)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/admin/test-types")
async def list_test_types(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """List test types."""
    try:
        result = await db.execute(select(TestType).order_by(TestType.name))
        types = result.scalars().all()
        return [
            {"id": test_type.id, "name": test_type.name}
            for test_type in types
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


class TestTypeCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


@router.post("/admin/test-types")
async def create_test_type(
    payload: TestTypeCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Create a test type."""
    try:
        existing_result = await db.execute(
            select(TestType).where(TestType.name == payload.name)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return JSONResponse(
                status_code=409, content={"error": "Test type already exists"}
            )
        test_type = TestType(name=payload.name, description=payload.description)
        db.add(test_type)
        await db.commit()
        await db.refresh(test_type)
        return {"id": test_type.id, "name": test_type.name}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/admin/users")
async def create_user(
    payload: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Create a new user."""
    try:
        existing_result = await db.execute(
            select(User).where(User.username == payload.username)
        )
        if existing_result.scalar_one_or_none():
            return JSONResponse(
                status_code=409, content={"error": "Username already exists"}
            )
        role_result = await db.execute(select(Role).where(Role.name == payload.role))
        role = role_result.scalar_one_or_none()
        if not role:
            return JSONResponse(status_code=400, content={"error": "Role not found"})
        user = User(
            username=payload.username,
            password_hash=get_password_hash(payload.password),
            role_id=role.id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return {"id": user.id, "username": user.username, "role": role.name}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """List all users."""
    try:
        result = await db.execute(
            select(User).options(selectinload(User.role)).order_by(User.id)
        )
        users = result.scalars().all()
        return [
            {
                "id": user.id,
                "username": user.username,
                "role": user.role.name,
                "is_active": user.is_active,
            }
            for user in users
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.patch("/admin/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Update a user."""
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return JSONResponse(status_code=404, content={"error": "User not found"})
        if payload.password:
            user.password_hash = get_password_hash(payload.password)
        if payload.is_active is not None:
            user.is_active = payload.is_active
        await db.commit()
        return {"id": user.id, "is_active": user.is_active}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/admin/tests")
async def create_test(
    payload: TestCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Create a test configuration."""
    try:
        type_result = await db.execute(
            select(TestType).where(TestType.id == payload.test_type_id)
        )
        test_type = type_result.scalar_one_or_none()
        if not test_type:
            return JSONResponse(status_code=400, content={"error": "Test type not found"})
        set_result = await db.execute(
            select(QuestionSet).where(QuestionSet.id == payload.question_set_id)
        )
        question_set = set_result.scalar_one_or_none()
        if not question_set:
            return JSONResponse(
                status_code=400, content={"error": "Question set not found"}
            )
        if question_set.test_type_id != payload.test_type_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Question set does not match test type"},
            )
        test = Test(
            title=payload.title,
            test_type_id=payload.test_type_id,
            question_set_id=payload.question_set_id,
            duration_minutes=payload.duration_minutes,
            warning_minutes=payload.warning_minutes,
        )
        db.add(test)
        await db.commit()
        await db.refresh(test)
        return {"id": test.id, "title": test.title}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/tests")
async def list_tests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """List tests."""
    try:
        result = await db.execute(
            select(Test)
            .options(selectinload(Test.test_type), selectinload(Test.question_set))
            .order_by(Test.id)
        )
        tests = result.scalars().all()
        return [
            {
                "id": test.id,
                "title": test.title,
                "test_type": test.test_type.name if test.test_type else None,
                "test_type_id": test.test_type_id,
                "question_set_id": test.question_set_id,
                "question_set_name": test.question_set.name
                if test.question_set
                else None,
                "duration_minutes": test.duration_minutes,
                "warning_minutes": test.warning_minutes,
                "is_active": test.is_active,
            }
            for test in tests
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.patch("/admin/tests/{test_id}")
async def update_test(
    test_id: int,
    payload: TestUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Update test configuration."""
    try:
        result = await db.execute(select(Test).where(Test.id == test_id))
        test = result.scalar_one_or_none()
        if not test:
            return JSONResponse(status_code=404, content={"error": "Test not found"})
        if payload.test_type_id:
            type_result = await db.execute(
                select(TestType).where(TestType.id == payload.test_type_id)
            )
            if not type_result.scalar_one_or_none():
                return JSONResponse(
                    status_code=400, content={"error": "Test type not found"}
                )
        if payload.question_set_id:
            set_result = await db.execute(
                select(QuestionSet).where(QuestionSet.id == payload.question_set_id)
            )
            question_set = set_result.scalar_one_or_none()
            if not question_set:
                return JSONResponse(
                    status_code=400, content={"error": "Question set not found"}
                )
            if payload.test_type_id and question_set.test_type_id != payload.test_type_id:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Question set does not match test type"},
                )
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(test, field, value)
        await db.commit()
        return {"id": test.id}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/admin/question-sets")
async def create_question_set(
    payload: QuestionSetCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Create a question set."""
    try:
        type_result = await db.execute(
            select(TestType).where(TestType.id == payload.test_type_id)
        )
        if not type_result.scalar_one_or_none():
            return JSONResponse(status_code=400, content={"error": "Test type not found"})
        question_set = QuestionSet(
            name=payload.name,
            test_type_id=payload.test_type_id,
            description=payload.description,
            duration_minutes=payload.duration_minutes,
            warning_minutes=payload.warning_minutes,
        )
        db.add(question_set)
        await db.commit()
        await db.refresh(question_set)
        return {"id": question_set.id, "name": question_set.name}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/question-sets")
async def list_question_sets(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """List question sets."""
    try:
        result = await db.execute(
            select(QuestionSet).options(selectinload(QuestionSet.test_type)).order_by(
                QuestionSet.id
            )
        )
        sets = result.scalars().all()
        return [
            {
                "id": question_set.id,
                "name": question_set.name,
                "description": question_set.description,
                "test_type_id": question_set.test_type_id,
                "test_type": question_set.test_type.name
                if question_set.test_type
                else None,
                "duration_minutes": question_set.duration_minutes,
                "warning_minutes": question_set.warning_minutes,
            }
            for question_set in sets
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.patch("/admin/question-sets/{set_id}")
async def update_question_set(
    set_id: int,
    payload: QuestionSetUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Update a question set."""
    try:
        result = await db.execute(select(QuestionSet).where(QuestionSet.id == set_id))
        question_set = result.scalar_one_or_none()
        if not question_set:
            return JSONResponse(status_code=404, content={"error": "Question set not found"})
        if payload.test_type_id:
            type_result = await db.execute(
                select(TestType).where(TestType.id == payload.test_type_id)
            )
            if not type_result.scalar_one_or_none():
                return JSONResponse(
                    status_code=400, content={"error": "Test type not found"}
                )
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(question_set, field, value)
        await db.commit()
        return {"id": question_set.id}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.delete("/admin/question-sets/{set_id}")
async def delete_question_set(
    set_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Delete a question set if not in use."""
    try:
        test_result = await db.execute(select(Test).where(Test.question_set_id == set_id))
        if test_result.scalar_one_or_none():
            return JSONResponse(
                status_code=400, content={"error": "Question set is in use"}
            )
        await db.execute(
            delete(QuestionSetQuestion).where(QuestionSetQuestion.question_set_id == set_id)
        )
        result = await db.execute(delete(QuestionSet).where(QuestionSet.id == set_id))
        if result.rowcount == 0:
            return JSONResponse(status_code=404, content={"error": "Question set not found"})
        await db.commit()
        return {"status": "deleted"}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/question-sets/{set_id}/questions")
async def list_question_set_questions(
    set_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """List questions in a question set."""
    try:
        result = await db.execute(
            select(QuestionSetQuestion, Question)
            .join(Question)
            .where(QuestionSetQuestion.question_set_id == set_id)
            .order_by(QuestionSetQuestion.order)
        )
        rows = result.all()
        question_ids = [question.id for _, question in rows]
        options = []
        if question_ids:
            options_result = await db.execute(
                select(QuestionOption).where(QuestionOption.question_id.in_(question_ids))
            )
            options = options_result.scalars().all()
        options_map = {}
        for option in options:
            options_map.setdefault(option.question_id, []).append(option)
        return [
            {
                "id": question.id,
                "title": question.title,
                "body": question.body,
                "sections": question.sections,
                "answer_type": question.answer_type,
                "allow_multiple": question.allow_multiple,
                "order": set_link.order,
                "options": [
                    {
                        "id": option.id,
                        "option_text": option.option_text,
                        "is_correct": option.is_correct,
                        "order": option.order,
                    }
                    for option in sorted(
                        options_map.get(question.id, []), key=lambda o: o.order
                    )
                ],
            }
            for set_link, question in rows
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/admin/question-sets/{set_id}/questions")
async def create_question_in_set(
    set_id: int,
    payload: QuestionCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Create a question inside a question set."""
    try:
        set_result = await db.execute(select(QuestionSet).where(QuestionSet.id == set_id))
        if not set_result.scalar_one_or_none():
            return JSONResponse(status_code=404, content={"error": "Question set not found"})
        if payload.answer_type not in {"long_text", "short_text", "multiple_choice"}:
            return JSONResponse(status_code=400, content={"error": "Invalid answer type"})
        if payload.answer_type == "multiple_choice" and not payload.options:
            return JSONResponse(
                status_code=400, content={"error": "Options required for multiple choice"}
            )
        question = Question(
            title=payload.title,
            body=payload.body,
            sections=payload.sections,
            answer_type=payload.answer_type,
            allow_multiple=payload.allow_multiple,
        )
        db.add(question)
        await db.flush()
        if payload.options:
            for idx, option in enumerate(payload.options):
                db.add(
                    QuestionOption(
                        question_id=question.id,
                        option_text=option.option_text,
                        is_correct=option.is_correct,
                        order=idx,
                    )
                )
        link_result = await db.execute(
            select(func.count(QuestionSetQuestion.id)).where(
                QuestionSetQuestion.question_set_id == set_id
            )
        )
        order_index = link_result.scalar_one() or 0
        db.add(
            QuestionSetQuestion(
                question_set_id=set_id, question_id=question.id, order=order_index
            )
        )
        await db.commit()
        return {"id": question.id}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.patch("/admin/question-sets/{set_id}/questions/{question_id}")
async def update_question_in_set(
    set_id: int,
    question_id: int,
    payload: QuestionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Update a question within a set."""
    try:
        link_result = await db.execute(
            select(QuestionSetQuestion).where(
                QuestionSetQuestion.question_set_id == set_id,
                QuestionSetQuestion.question_id == question_id,
            )
        )
        if not link_result.scalar_one_or_none():
            return JSONResponse(status_code=404, content={"error": "Question not found"})
        result = await db.execute(select(Question).where(Question.id == question_id))
        question = result.scalar_one_or_none()
        if not question:
            return JSONResponse(status_code=404, content={"error": "Question not found"})
        update_data = payload.model_dump(exclude_unset=True)
        if "answer_type" in update_data and update_data["answer_type"] not in {
            "long_text",
            "short_text",
            "multiple_choice",
        }:
            return JSONResponse(status_code=400, content={"error": "Invalid answer type"})
        if "options" in update_data:
            options = update_data.pop("options")
            await db.execute(
                delete(QuestionOption).where(QuestionOption.question_id == question.id)
            )
            if options:
                for idx, option in enumerate(options):
                    db.add(
                        QuestionOption(
                            question_id=question.id,
                            option_text=option.option_text,
                            is_correct=option.is_correct,
                            order=idx,
                        )
                    )
        for field, value in update_data.items():
            setattr(question, field, value)
        await db.commit()
        return {"id": question.id}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.delete("/admin/question-sets/{set_id}/questions/{question_id}")
async def delete_question_from_set(
    set_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Remove question from set."""
    try:
        answer_result = await db.execute(
            select(Answer).where(Answer.question_id == question_id)
        )
        if answer_result.scalar_one_or_none():
            return JSONResponse(
                status_code=400,
                content={"error": "Question has submissions and cannot be deleted"},
            )
        await db.execute(
            delete(QuestionSetQuestion).where(
                QuestionSetQuestion.question_set_id == set_id,
                QuestionSetQuestion.question_id == question_id,
            )
        )
        await db.execute(delete(QuestionOption).where(QuestionOption.question_id == question_id))
        await db.execute(delete(Question).where(Question.id == question_id))
        await db.commit()
        return {"status": "deleted"}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/admin/question-sets/{set_id}/order")
async def reorder_questions_in_set(
    set_id: int,
    payload: QuestionOrderRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Reorder questions within a set."""
    try:
        await db.execute(
            delete(QuestionSetQuestion).where(QuestionSetQuestion.question_set_id == set_id)
        )
        for idx, question_id in enumerate(payload.question_ids):
            db.add(
                QuestionSetQuestion(
                    question_set_id=set_id, question_id=question_id, order=idx
                )
            )
        await db.commit()
        return {"status": "reordered"}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/admin/assignments")
async def assign_test_to_user(
    payload: AssignQuestionSetRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Assign a question set to a user."""
    try:
        set_result = await db.execute(
            select(QuestionSet).where(QuestionSet.id == payload.question_set_id)
        )
        question_set = set_result.scalar_one_or_none()
        if not question_set:
            return JSONResponse(
                status_code=400, content={"error": "Question set not found"}
            )
        code = secrets.token_urlsafe(8)
        assignment = TestAssignment(
            test_id=None,
            question_set_id=payload.question_set_id,
            user_id=payload.user_id,
            session_code=code,
        )
        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)
        return {"id": assignment.id, "session_code": assignment.session_code}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/admin/assignments/{assignment_id}/session-code")
async def regenerate_session_code(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Create a new assignment with a fresh session code."""
    try:
        result = await db.execute(
            select(TestAssignment).where(TestAssignment.id == assignment_id)
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return JSONResponse(status_code=404, content={"error": "Assignment not found"})
        latest_session_result = await db.execute(
            select(TestSession)
            .where(TestSession.assignment_id == assignment.id)
            .order_by(TestSession.created_at.desc())
            .limit(1)
        )
        latest_session = latest_session_result.scalar_one_or_none()
        if latest_session and latest_session.status == SessionStatus.in_progress:
            return JSONResponse(
                status_code=400,
                content={"error": "Session already in progress"},
            )
        new_assignment = TestAssignment(
            test_id=assignment.test_id,
            question_set_id=assignment.question_set_id,
            user_id=assignment.user_id,
            session_code=secrets.token_urlsafe(8),
        )
        db.add(new_assignment)
        await db.commit()
        await db.refresh(new_assignment)
        return {"id": new_assignment.id, "session_code": new_assignment.session_code}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/monitoring")
async def monitoring(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """View active tests and violations."""
    try:
        active_result = await db.execute(
            select(TestSession).where(TestSession.status == SessionStatus.in_progress)
        )
        active_sessions = active_result.scalars().all()
        violations_result = await db.execute(
            select(
                Violation.session_id, func.count(Violation.id).label("count")
            ).group_by(Violation.session_id)
        )
        violations = {row.session_id: row.count for row in violations_result.all()}
        auto_result = await db.execute(
            select(TestSession).where(TestSession.status == SessionStatus.auto_submitted)
        )
        auto_sessions = auto_result.scalars().all()
        return {
            "active_sessions": [
                {
                    "session_id": session.id,
                    "user_id": session.user_id,
                    "question_set_id": session.question_set_id,
                    "end_time": session.end_time,
                    "violations": violations.get(session.id, 0),
                }
                for session in active_sessions
            ],
            "auto_submitted": [
                {
                    "session_id": session.id,
                    "user_id": session.user_id,
                    "question_set_id": session.question_set_id,
                    "submitted_at": session.submitted_at,
                }
                for session in auto_sessions
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/dashboard")
async def dashboard(
    test_type: Optional[str] = None,
    status: Optional[str] = None,
    violations_only: Optional[bool] = False,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """Summary dashboard for assignments and sessions."""
    try:
        assignment_result = await db.execute(
            select(TestAssignment)
            .options(
                selectinload(TestAssignment.user),
                selectinload(TestAssignment.question_set).selectinload(
                    QuestionSet.test_type
                ),
                selectinload(TestAssignment.sessions),
            )
            .order_by(TestAssignment.assigned_at.desc())
        )
        assignments = assignment_result.scalars().all()
        violations_result = await db.execute(
            select(
                Violation.session_id, func.count(Violation.id).label("count")
            ).group_by(Violation.session_id)
        )
        violations_map = {row.session_id: row.count for row in violations_result.all()}

        def to_status_label(session: Optional[TestSession]) -> str:
            if not session:
                return "Not Started"
            if session.status == SessionStatus.in_progress:
                return "In Progress"
            if session.status == SessionStatus.submitted:
                return "Submitted"
            if session.status == SessionStatus.auto_submitted:
                return "Auto-Submitted"
            if session.status == SessionStatus.expired:
                return "Expired"
            return "Not Started"

        status_priority = [
            "In Progress",
            "Not Started",
            "Auto-Submitted",
            "Submitted",
            "Expired",
        ]

        def aggregate_status(statuses: list[str]) -> str:
            for status_value in status_priority:
                if status_value in statuses:
                    return status_value
            return "Not Started"

        candidates_map = {}
        for assignment in assignments:
            user = assignment.user
            question_set = assignment.question_set
            test_type_name = (
                question_set.test_type.name
                if question_set and question_set.test_type
                else "Custom"
            )
            sessions_sorted = sorted(
                assignment.sessions or [], key=lambda s: s.created_at, reverse=True
            )
            latest_session = sessions_sorted[0] if sessions_sorted else None
            session_status = to_status_label(latest_session)
            time_remaining = None
            time_taken = None
            violation_count = 0
            session_id = None
            if latest_session:
                session_id = latest_session.id
                violation_count = violations_map.get(latest_session.id, 0)
                if latest_session.status == SessionStatus.in_progress:
                    if latest_session.end_time:
                        remaining = latest_session.end_time - datetime.utcnow()
                        time_remaining = max(int(remaining.total_seconds()), 0)
                if latest_session.start_time and latest_session.submitted_at:
                    time_taken = int(
                        (
                            latest_session.submitted_at - latest_session.start_time
                        ).total_seconds()
                    )

            history = []
            for index, session in enumerate(sessions_sorted):
                history_status = to_status_label(session)
                history_time_taken = None
                if session.start_time and session.submitted_at:
                    history_time_taken = int(
                        (session.submitted_at - session.start_time).total_seconds()
                    )
                history.append(
                    {
                        "session_id": session.id,
                        "status": history_status,
                        "time_taken_seconds": history_time_taken,
                        "violation_count": violations_map.get(session.id, 0),
                        "created_at": session.created_at.isoformat()
                        if session.created_at
                        else None,
                        "attempt": index + 1,
                    }
                )

            test_row = {
                "test_id": assignment.id,
                "assignment_id": assignment.id,
                "test_name": question_set.name if question_set else None,
                "question_set": question_set.name if question_set else None,
                "test_type": test_type_name,
                "status": session_status,
                "time_remaining_seconds": time_remaining,
                "time_taken_seconds": time_taken,
                "violations": violation_count,
                "session_id": session_id,
                "history": history,
                "session_code": assignment.session_code,
            }

            candidate_entry = candidates_map.setdefault(
                user.id,
                {
                    "user_id": user.id,
                    "username": user.username,
                    "is_active": user.is_active,
                    "tests": [],
                },
            )
            candidate_entry["tests"].append(test_row)

        candidates = []
        for candidate in candidates_map.values():
            tests = candidate["tests"]
            if test_type:
                tests = [test for test in tests if test["test_type"] == test_type]
            if status:
                tests = [test for test in tests if test["status"] == status]
            if violations_only:
                tests = [test for test in tests if test["violations"] > 0]
            if not tests:
                continue
            candidate["tests"] = tests
            candidate["total_tests_assigned"] = len(tests)
            candidate["total_violations"] = sum(
                test["violations"] for test in tests
            )
            candidate["overall_status"] = aggregate_status(
                [test["status"] for test in tests]
            )
            candidates.append(candidate)

        return {"candidates": candidates}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/sessions/{session_id}/answers")
async def session_answers(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """View submissions for a session."""
    try:
        result = await db.execute(
            select(Answer)
            .options(
                selectinload(Answer.question).selectinload(Question.options),
                selectinload(Answer.selected_options),
            )
            .where(Answer.session_id == session_id)
        )
        answers = result.scalars().all()
        return [
            {
                "question_id": answer.question_id,
                "question_title": answer.question.title,
                "answer_type": answer.question.answer_type,
                "answer_text": answer.answer_text,
                "selected_option_ids": [
                    option.option_id for option in answer.selected_options
                ],
                "options": [
                    {
                        "id": option.id,
                        "option_text": option.option_text,
                        "is_correct": option.is_correct,
                    }
                    for option in sorted(
                        answer.question.options, key=lambda o: o.order
                    )
                ],
            }
            for answer in answers
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/sessions/{session_id}/violations")
async def session_violations(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """View violations for a session."""
    try:
        result = await db.execute(
            select(Violation)
            .where(Violation.session_id == session_id)
            .order_by(Violation.created_at.desc())
        )
        violations = result.scalars().all()
        return [
            {
                "id": violation.id,
                "event_type": violation.event_type,
                "metadata": violation.metadata_json,
                "created_at": violation.created_at,
            }
            for violation in violations
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/admin/violations")
async def list_violations(
    test_id: Optional[int] = None,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(RoleName.admin)),
):
    """List violations with optional filtering."""
    try:
        query = select(Violation).join(TestSession)
        if test_id:
            query = query.where(TestSession.test_id == test_id)
        if user_id:
            query = query.where(TestSession.user_id == user_id)
        result = await db.execute(query.order_by(Violation.created_at.desc()))
        violations = result.scalars().all()
        return [
            {
                "id": violation.id,
                "session_id": violation.session_id,
                "event_type": violation.event_type,
                "metadata": violation.metadata_json,
                "created_at": violation.created_at,
            }
            for violation in violations
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/candidate/assignments")
async def candidate_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.candidate)),
):
    """List assigned question sets for candidate."""
    try:
        result = await db.execute(
            select(TestAssignment, QuestionSet, TestType)
            .join(QuestionSet, TestAssignment.question_set_id == QuestionSet.id)
            .join(TestType, QuestionSet.test_type_id == TestType.id)
            .where(
                TestAssignment.user_id == current_user.id,
                TestAssignment.is_active.is_(True),
            )
        )
        assignments = result.all()
        session_result = await db.execute(
            select(TestSession).where(TestSession.user_id == current_user.id)
        )
        sessions = session_result.scalars().all()
        latest_by_assignment = {}
        for session in sessions:
            latest = latest_by_assignment.get(session.assignment_id)
            if not latest or session.created_at > latest.created_at:
                latest_by_assignment[session.assignment_id] = session
        return [
            {
                "assignment_id": assignment.id,
                "question_set_id": question_set.id,
                "test_title": question_set.name,
                "test_type": test_type.name,
                "duration_minutes": question_set.duration_minutes,
                "warning_minutes": question_set.warning_minutes,
                "status": latest_by_assignment.get(assignment.id).status
                if latest_by_assignment.get(assignment.id)
                else "Not Started",
                "session_code": assignment.session_code,
            }
            for assignment, question_set, test_type in assignments
        ]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/candidate/sessions/start")
async def start_session(
    payload: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.candidate)),
):
    """Start a test session and return test details."""
    try:
        assignment_result = await db.execute(
            select(TestAssignment)
            .options(
                selectinload(TestAssignment.question_set).selectinload(
                    QuestionSet.test_type
                )
            )
            .where(
                TestAssignment.session_code == payload.session_code.strip(),
                TestAssignment.user_id == current_user.id,
                TestAssignment.is_active.is_(True),
            )
        )
        assignment = assignment_result.scalar_one_or_none()
        if not assignment:
            return JSONResponse(status_code=404, content={"error": "Invalid session code"})
        if not assignment.question_set_id:
            return JSONResponse(
                status_code=400, content={"error": "Assignment has no question set"}
            )
        session_result = await db.execute(
            select(TestSession)
            .where(TestSession.assignment_id == assignment.id)
            .order_by(TestSession.created_at.desc())
            .limit(1)
        )
        existing_session = session_result.scalar_one_or_none()
        if existing_session and existing_session.status == SessionStatus.in_progress:
            if existing_session.end_time and existing_session.end_time <= datetime.utcnow():
                await auto_submit_session(db, existing_session)
                await db.commit()
                return JSONResponse(status_code=400, content={"error": "Session expired"})
            return JSONResponse(
                status_code=400, content={"error": "Session already in progress"}
            )
        if existing_session and existing_session.status in {
            SessionStatus.submitted,
            SessionStatus.auto_submitted,
            SessionStatus.expired,
        }:
            return JSONResponse(status_code=400, content={"error": "Session already used"})
        session = TestSession(
            test_id=assignment.test_id,
            question_set_id=assignment.question_set_id,
            user_id=current_user.id,
            assignment_id=assignment.id,
            status=SessionStatus.in_progress,
            start_time=datetime.utcnow(),
            violation_token=secrets.token_hex(16),
        )
        db.add(session)
        question_set = assignment.question_set
        if not question_set:
            set_result = await db.execute(
                select(QuestionSet).where(QuestionSet.id == assignment.question_set_id)
            )
            question_set = set_result.scalar_one_or_none()
        if not question_set:
            return JSONResponse(
                status_code=404, content={"error": "Question set not found"}
            )
        if session.end_time is None:
            duration = question_set.duration_minutes or 60
            if duration <= 0:
                duration = 60
            session.end_time = session.start_time + timedelta(minutes=duration)
        await db.commit()
        await db.refresh(session)

        questions_result = await db.execute(
            select(Question)
            .options(selectinload(Question.options))
            .join(QuestionSetQuestion)
            .where(QuestionSetQuestion.question_set_id == question_set.id)
            .order_by(QuestionSetQuestion.order)
        )
        questions = questions_result.scalars().all()
        end_time_iso = (
            session.end_time.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            if session.end_time
            else None
        )
        return {
            "session_id": session.id,
            "test": {
                "id": None,
                "title": question_set.name,
                "test_type": question_set.test_type.name
                if question_set.test_type
                else None,
                "question_set": question_set.name,
                "duration_minutes": question_set.duration_minutes,
                "warning_minutes": question_set.warning_minutes,
            },
            "end_time": end_time_iso,
            "violation_token": session.violation_token,
            "questions": [
                {
                    "id": question.id,
                    "title": question.title,
                    "body": question.body,
                    "sections": question.sections,
                    "answer_type": question.answer_type,
                    "allow_multiple": question.allow_multiple,
                    "options": [
                        {
                            "id": option.id,
                            "option_text": option.option_text,
                            "order": option.order,
                        }
                        for option in sorted(question.options, key=lambda o: o.order)
                    ],
                }
                for question in questions
            ],
        }
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/sessions/validate")
async def validate_session_code(
    payload: ValidateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.candidate)),
):
    """Validate a session code for the current candidate."""
    try:
        assignment_result = await db.execute(
            select(TestAssignment).where(
                TestAssignment.session_code == payload.session_code.strip()
            )
        )
        assignment = assignment_result.scalar_one_or_none()
        if not assignment:
            return {"valid": False, "reason": "invalid"}
        if assignment.user_id != current_user.id:
            return {"valid": False, "reason": "wrong_user"}
        if not assignment.is_active:
            return {"valid": False, "reason": "inactive"}
        session_result = await db.execute(
            select(TestSession)
            .where(TestSession.assignment_id == assignment.id)
            .order_by(TestSession.created_at.desc())
            .limit(1)
        )
        existing_session = session_result.scalar_one_or_none()
        if existing_session:
            if existing_session.status == SessionStatus.in_progress:
                return {"valid": False, "reason": "in_progress"}
            if existing_session.status in {
                SessionStatus.submitted,
                SessionStatus.auto_submitted,
                SessionStatus.expired,
            }:
                return {"valid": False, "reason": "used"}
        return {"valid": True}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/candidate/answers/save")
async def save_answer(
    payload: AnswerSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.candidate)),
):
    """Autosave answer content."""
    try:
        session_result = await db.execute(
            select(TestSession).where(
                TestSession.id == payload.session_id,
                TestSession.user_id == current_user.id,
            )
        )
        session = session_result.scalar_one_or_none()
        if not session:
            return JSONResponse(status_code=404, content={"error": "Session not found"})
        if session.end_time and session.end_time <= datetime.utcnow():
            await auto_submit_session(db, session)
            await db.commit()
            return JSONResponse(status_code=400, content={"error": "Session expired"})
        await ensure_session_active(session)
        if not session.question_set_id:
            return JSONResponse(status_code=400, content={"error": "Invalid assignment"})
        question_result = await db.execute(
            select(Question)
            .join(QuestionSetQuestion)
            .where(
                Question.id == payload.question_id,
                QuestionSetQuestion.question_set_id == session.question_set_id,
            )
        )
        question = question_result.scalar_one_or_none()
        if not question:
            return JSONResponse(
                status_code=404, content={"error": "Question not found in set"}
            )
        answer_result = await db.execute(
            select(Answer).where(
                Answer.session_id == session.id, Answer.question_id == payload.question_id
            )
        )
        answer = answer_result.scalar_one_or_none()
        if answer and answer.is_final:
            return JSONResponse(status_code=400, content={"error": "Answer locked"})
        if not answer:
            answer = Answer(
                session_id=session.id,
                question_id=payload.question_id,
                answer_text=payload.answer_text,
            )
            db.add(answer)
            await db.flush()
        else:
            answer.last_saved_at = datetime.utcnow()

        if question.answer_type == "multiple_choice":
            selected_ids = payload.selected_option_ids or []
            await db.execute(
                delete(AnswerOption).where(AnswerOption.answer_id == answer.id)
            )
            if selected_ids:
                option_result = await db.execute(
                    select(QuestionOption).where(
                        QuestionOption.question_id == question.id,
                        QuestionOption.id.in_(selected_ids),
                    )
                )
                options = option_result.scalars().all()
                for option in options:
                    db.add(AnswerOption(answer_id=answer.id, option_id=option.id))
            answer.answer_text = None
        else:
            answer.answer_text = payload.answer_text
        await db.commit()
        return {"status": "saved"}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/candidate/submit")
async def submit_test(
    payload: SubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.candidate)),
):
    """Final submission of test."""
    try:
        session_result = await db.execute(
            select(TestSession).where(
                TestSession.id == payload.session_id,
                TestSession.user_id == current_user.id,
            )
        )
        session = session_result.scalar_one_or_none()
        if not session:
            return JSONResponse(status_code=404, content={"error": "Session not found"})
        if session.end_time and session.end_time <= datetime.utcnow():
            await auto_submit_session(db, session)
            await db.commit()
            return JSONResponse(status_code=400, content={"error": "Session expired"})
        await ensure_session_active(session)
        session.status = SessionStatus.submitted
        session.submitted_at = datetime.utcnow()
        await db.execute(
            update(Answer)
            .where(Answer.session_id == session.id)
            .values(is_final=True, updated_at=datetime.utcnow())
        )
        await db.commit()
        return {"status": "submitted"}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/candidate/violations")
async def log_violation(
    payload: ViolationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.candidate)),
):
    """Record a violation event."""
    try:
        session_result = await db.execute(
            select(TestSession).where(
                TestSession.id == payload.session_id,
                TestSession.user_id == current_user.id,
            )
        )
        session = session_result.scalar_one_or_none()
        if not session:
            return JSONResponse(status_code=404, content={"error": "Session not found"})
        if payload.token != session.violation_token:
            return JSONResponse(status_code=401, content={"error": "Invalid token"})
        violation = Violation(
            session_id=session.id,
            event_type=payload.event_type,
            metadata_json=payload.metadata,
        )
        db.add(violation)
        await db.commit()
        return {"status": "logged"}
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        return JSONResponse(status_code=500, content={"error": str(exc)})


async def sweep_expired_sessions(db: AsyncSession) -> None:
    now = datetime.utcnow()
    result = await db.execute(
        select(TestSession).where(
            TestSession.status == SessionStatus.in_progress,
            TestSession.end_time <= now,
        )
    )
    sessions = result.scalars().all()
    for session in sessions:
        await auto_submit_session(db, session)


async def start_sweeper(stop_event: asyncio.Event):
    """Background task to auto-submit expired sessions."""
    while not stop_event.is_set():
        async for db in get_db():
            try:
                await sweep_expired_sessions(db)
                await db.commit()
            except Exception:  # noqa: BLE001
                await db.rollback()
        await asyncio.sleep(30)


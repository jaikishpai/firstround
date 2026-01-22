import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.config import settings
from app.database import Base, engine, get_db
from app.models import Role, RoleName, User, TestType
from app.routes import router, get_password_hash, start_sweeper


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "ALTER TABLE questions "
                "ADD COLUMN IF NOT EXISTS answer_type VARCHAR(50) DEFAULT 'long_text' NOT NULL"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE questions "
                "ADD COLUMN IF NOT EXISTS allow_multiple BOOLEAN DEFAULT FALSE NOT NULL"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE tests "
                "ADD COLUMN IF NOT EXISTS test_type_id INTEGER"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE tests "
                "ADD COLUMN IF NOT EXISTS question_set_id INTEGER"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS test_types ("
                "id SERIAL PRIMARY KEY, "
                "name VARCHAR(100) UNIQUE NOT NULL, "
                "description TEXT, "
                "created_at TIMESTAMP NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS question_sets ("
                "id SERIAL PRIMARY KEY, "
                "name VARCHAR(200) NOT NULL, "
                "description TEXT, "
                "test_type_id INTEGER NOT NULL REFERENCES test_types(id), "
                "duration_minutes INTEGER NOT NULL DEFAULT 60, "
                "warning_minutes INTEGER NOT NULL DEFAULT 5, "
                "created_at TIMESTAMP NOT NULL DEFAULT NOW(), "
                "updated_at TIMESTAMP NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE question_sets "
                "ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 60"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE question_sets "
                "ADD COLUMN IF NOT EXISTS warning_minutes INTEGER DEFAULT 5"
            )
        )
        await conn.execute(
            text(
                "UPDATE question_sets "
                "SET duration_minutes = 60 "
                "WHERE duration_minutes IS NULL"
            )
        )
        await conn.execute(
            text(
                "UPDATE question_sets "
                "SET warning_minutes = 5 "
                "WHERE warning_minutes IS NULL"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS question_set_questions ("
                "id SERIAL PRIMARY KEY, "
                "question_set_id INTEGER NOT NULL REFERENCES question_sets(id), "
                "question_id INTEGER NOT NULL REFERENCES questions(id), "
                "\"order\" INTEGER NOT NULL DEFAULT 0, "
                "UNIQUE(question_set_id, question_id), "
                "UNIQUE(question_id)"
                ")"
            )
        )
        await conn.execute(
            text(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS ("
                "SELECT 1 FROM pg_constraint WHERE conname = 'tests_test_type_fk'"
                ") THEN "
                "ALTER TABLE tests "
                "ADD CONSTRAINT tests_test_type_fk "
                "FOREIGN KEY (test_type_id) REFERENCES test_types(id); "
                "END IF; "
                "END $$;"
            )
        )
        await conn.execute(
            text(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS ("
                "SELECT 1 FROM pg_constraint WHERE conname = 'tests_question_set_fk'"
                ") THEN "
                "ALTER TABLE tests "
                "ADD CONSTRAINT tests_question_set_fk "
                "FOREIGN KEY (question_set_id) REFERENCES question_sets(id); "
                "END IF; "
                "END $$;"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE test_assignments "
                "ADD COLUMN IF NOT EXISTS question_set_id INTEGER"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE test_assignments "
                "ADD COLUMN IF NOT EXISTS session_code VARCHAR(32)"
            )
        )
        await conn.execute(
            text(
                "DO $$ "
                "DECLARE r RECORD; "
                "BEGIN "
                "FOR r IN "
                "SELECT c.conname "
                "FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey) "
                "WHERE t.relname = 'test_assignments' AND c.contype = 'u' "
                "GROUP BY c.conname "
                "HAVING array_agg(a.attname::text ORDER BY a.attname) = ARRAY['question_set_id','user_id']::text[] "
                "LOOP "
                "EXECUTE 'ALTER TABLE test_assignments DROP CONSTRAINT ' || r.conname; "
                "END LOOP; "
                "END $$;"
            )
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_test_assignments_session_code "
                "ON test_assignments (session_code)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE test_assignments "
                "ALTER COLUMN test_id DROP NOT NULL"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE test_sessions "
                "ADD COLUMN IF NOT EXISTS question_set_id INTEGER"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE test_sessions "
                "ALTER COLUMN test_id DROP NOT NULL"
            )
        )
        await conn.execute(
            text(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS ("
                "SELECT 1 FROM pg_constraint WHERE conname = 'assignments_question_set_fk'"
                ") THEN "
                "ALTER TABLE test_assignments "
                "ADD CONSTRAINT assignments_question_set_fk "
                "FOREIGN KEY (question_set_id) REFERENCES question_sets(id); "
                "END IF; "
                "END $$;"
            )
        )
        await conn.execute(
            text(
                "UPDATE test_assignments "
                "SET session_code = substr(md5(random()::text), 1, 12) "
                "WHERE session_code IS NULL"
            )
        )
        await conn.execute(
            text(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS ("
                "SELECT 1 FROM pg_constraint WHERE conname = 'sessions_question_set_fk'"
                ") THEN "
                "ALTER TABLE test_sessions "
                "ADD CONSTRAINT sessions_question_set_fk "
                "FOREIGN KEY (question_set_id) REFERENCES question_sets(id); "
                "END IF; "
                "END $$;"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS question_options ("
                "id SERIAL PRIMARY KEY, "
                "question_id INTEGER NOT NULL REFERENCES questions(id), "
                "option_text TEXT NOT NULL, "
                "is_correct BOOLEAN NOT NULL DEFAULT FALSE, "
                "\"order\" INTEGER NOT NULL DEFAULT 0"
                ")"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS answer_options ("
                "id SERIAL PRIMARY KEY, "
                "answer_id INTEGER NOT NULL REFERENCES answers(id), "
                "option_id INTEGER NOT NULL REFERENCES question_options(id)"
                ")"
            )
        )

        await conn.execute(
            text(
                "DO $$ "
                "DECLARE rec RECORD; "
                "DECLARE set_id INTEGER; "
                "BEGIN "
                "FOR rec IN SELECT id, title, test_type_id FROM tests WHERE question_set_id IS NULL LOOP "
                "INSERT INTO question_sets (name, description, test_type_id, created_at, updated_at) "
                "VALUES (rec.title || ' Set', 'Migrated from legacy test questions', rec.test_type_id, NOW(), NOW()) "
                "RETURNING id INTO set_id; "
                "UPDATE tests SET question_set_id = set_id WHERE id = rec.id; "
                "UPDATE test_assignments SET question_set_id = set_id WHERE test_id = rec.id; "
                "UPDATE test_sessions SET question_set_id = set_id WHERE test_id = rec.id; "
                "IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'test_questions') THEN "
                "INSERT INTO question_set_questions (question_set_id, question_id, \"order\") "
                "SELECT set_id, question_id, \"order\" FROM test_questions WHERE test_id = rec.id "
                "ON CONFLICT DO NOTHING; "
                "END IF; "
                "END LOOP; "
                "END $$;"
            )
        )

    async for db in get_db():
        for role_name in RoleName:
            result = await db.execute(select(Role).where(Role.name == role_name))
            if not result.scalar_one_or_none():
                db.add(Role(name=role_name))
        await db.commit()

        default_types = ["QA", "Java", "Python", "Custom"]
        for type_name in default_types:
            result = await db.execute(select(TestType).where(TestType.name == type_name))
            if not result.scalar_one_or_none():
                db.add(TestType(name=type_name))
        await db.commit()

        result = await db.execute(select(TestType).where(TestType.name == "QA"))
        qa_type = result.scalar_one_or_none()
        if qa_type:
            await db.execute(
                text(
                    "UPDATE tests SET test_type_id = :type_id "
                    "WHERE test_type_id IS NULL"
                ),
                {"type_id": qa_type.id},
            )
            await db.commit()

        if settings.admin_seed_username and settings.admin_seed_password:
            result = await db.execute(
                select(User).where(User.username == settings.admin_seed_username)
            )
            existing = result.scalar_one_or_none()
            if not existing:
                role_result = await db.execute(
                    select(Role).where(Role.name == RoleName.admin)
                )
                admin_role = role_result.scalar_one()
                admin_user = User(
                    username=settings.admin_seed_username,
                    password_hash=get_password_hash(settings.admin_seed_password),
                    role_id=admin_role.id,
                )
                db.add(admin_user)
                await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    stop_event = asyncio.Event()
    sweeper_task = asyncio.create_task(start_sweeper(stop_event))
    yield
    stop_event.set()
    await sweeper_task


app = FastAPI(title="QA Assessment Platform", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


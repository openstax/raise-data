from uuid import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import UniqueConstraint
from datetime import datetime, date


class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class Course(Base):
    __tablename__ = 'course'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str]
    term: Mapped[str]


class EventUserEnrollment(Base):
    __tablename__ = 'event_user_enrollment'
    __table_args__ = (
        UniqueConstraint('user_uuid_md5', 'course_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_uuid_md5: Mapped[str]
    course_id: Mapped[int]
    role: Mapped[str]


class CourseActivityStat(Base):
    __tablename__ = 'course_activity_stat'
    __table_args__ = (
        UniqueConstraint('course_id', 'date'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int]
    date: Mapped[date]
    enrolled_students: Mapped[int]
    weekly_active_users: Mapped[int]
    daily_active_users: Mapped[int]


class CourseQuizStat(Base):
    __tablename__ = 'course_quiz_stat'
    __table_args__ = (
        UniqueConstraint('course_id', 'date', 'quiz_name'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int]
    date: Mapped[date]
    quiz_name: Mapped[str]
    quiz_attempts: Mapped[int]


class ContentLoadedEvent(Base):
    __tablename__ = 'content_loaded_event'
    __table_args__ = (
        UniqueConstraint('impression_id', 'content_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_uuid_md5: Mapped[str]
    course_id: Mapped[int]
    impression_id: Mapped[UUID]
    timestamp: Mapped[datetime]
    content_id: Mapped[UUID]
    variant: Mapped[str]


class PsetProblemAttemptedEvent(Base):
    __tablename__ = 'pset_problem_attempted_event'
    __table_args__ = (
        UniqueConstraint(
            'impression_id', 'pset_problem_content_id', 'attempt'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_uuid_md5: Mapped[str]
    course_id: Mapped[int]
    impression_id: Mapped[UUID]
    timestamp: Mapped[datetime]
    content_id: Mapped[UUID]
    variant: Mapped[str]
    pset_content_id: Mapped[UUID]
    pset_problem_content_id: Mapped[UUID]
    problem_type: Mapped[str]
    correct: Mapped[bool]
    attempt: Mapped[int]
    final_attempt: Mapped[bool]


class InputSubmittedEvent(Base):
    __tablename__ = 'input_submitted_event'
    __table_args__ = (
        UniqueConstraint('impression_id', 'input_content_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_uuid_md5: Mapped[str]
    course_id: Mapped[int]
    impression_id: Mapped[UUID]
    timestamp: Mapped[datetime]
    content_id: Mapped[UUID]
    variant: Mapped[str]
    input_content_id: Mapped[UUID]

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------- 认证 ----------------
class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)
    nickname: str = Field(min_length=1, max_length=50)
    role: Literal["student", "coach"] = "student"
    phone: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class ProfileUpdateIn(BaseModel):
    nickname: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = None
    gender: Optional[int] = None
    avatar: Optional[str] = None
    reminder_time: Optional[str] = None
    anonymous_rank: Optional[int] = None
    coach_bio: Optional[str] = None
    coach_specialty: Optional[str] = None


class PasswordChangeIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=72)


# ---------------- 打卡 ----------------
class CheckinDetailIn(BaseModel):
    exercise_name: str
    sets: int = 0
    reps: int = 0
    weight: float = 0
    rpe: Optional[int] = None
    heart_rate: Optional[int] = None
    rest_sec: Optional[int] = None


class CheckinIn(BaseModel):
    checkin_date: date
    content: str = ""
    plan_id: Optional[int] = None
    duration_min: int = 0
    intensity: int = Field(default=1, ge=1, le=5)
    vas_before: Optional[int] = Field(default=None, ge=0, le=10)
    vas_after: Optional[int] = Field(default=None, ge=0, le=10)
    media_paths: List[str] = []
    details: List[CheckinDetailIn] = []


class MakeupRequestIn(BaseModel):
    checkin_date: date
    reason: str = ""


# ---------------- 身体数据 ----------------
class BodyRecordIn(BaseModel):
    record_date: date
    weight: Optional[float] = None
    body_fat: Optional[float] = None
    chest: Optional[float] = None
    waist: Optional[float] = None
    hip: Optional[float] = None
    arm: Optional[float] = None
    thigh: Optional[float] = None
    photo_path: Optional[str] = None


# ---------------- 计划 ----------------
class PlanItemIn(BaseModel):
    day_date: date
    exercise_name: str
    sets: int = 3
    reps: int = 12
    weight_suggest: float = 0
    rest_sec: int = 90
    note: str = ""
    sort_order: int = 0


class PlanIn(BaseModel):
    student_id: int
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    start_date: date
    end_date: date
    items: List[PlanItemIn] = []


class ExerciseIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str
    equipment: str = "自重"
    difficulty: int = Field(default=1, ge=1, le=3)
    default_sets: int = 3
    default_reps: int = 12
    default_weight: float = 0


# ---------------- 社区动态 ----------------
class PostIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    media_paths: List[str] = []
    visibility: Literal["public", "coach", "private"] = "public"


class PostCommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


# ---------------- 消息 ----------------
class MessageIn(BaseModel):
    receiver_id: int
    msg_type: Literal["text", "image", "voice", "video"] = "text"
    content: str = ""
    media_path: str = ""


class BatchMessageIn(BaseModel):
    target: Literal["all", "student_ids"] = "all"
    student_ids: List[int] = []
    msg_type: Literal["text", "image", "voice"] = "text"
    content: str = Field(min_length=1, max_length=2000)
    media_path: str = ""


class TemplateIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=1000)
    category: str = "通用"


class UrgeIn(BaseModel):
    message: str = "今天还没打卡哦，训练完记得打卡！"


# ---------------- 训练营 ----------------
class CampIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    start_date: date
    end_date: date
    capacity: int = Field(default=30, ge=1, le=500)


class CampJoinIn(BaseModel):
    invite_code: str = Field(min_length=4, max_length=20)


class CampMemberIn(BaseModel):
    user_id: int


class CampPlanGenIn(BaseModel):
    template_plan_id: int
    title: str = Field(min_length=1, max_length=100)


class CampUrgeIn(BaseModel):
    message: str = "【营期催打卡】今天还没打卡哦，坚持就是胜利！"


# ---------------- 指导 ----------------
class CheckinCommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    voice_path: str = ""


class MakeupReviewIn(BaseModel):
    approve: bool
    review_note: str = ""


# ---------------- 管理 ----------------
class CoachReviewIn(BaseModel):
    approve: bool
    review_note: str = ""


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    is_pinned: int = 0
    status: Literal["published", "draft", "offline"] = "published"
    target_role: Literal["all", "student", "coach"] = "all"


class RecommendIn(BaseModel):
    weight: int = 0


class ConfigUpdateIn(BaseModel):
    configs: dict


class UserStatusIn(BaseModel):
    status: int  # 1启用 0禁用


class UserRoleIn(BaseModel):
    role: Literal["student", "coach", "admin"]


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=6, max_length=72)

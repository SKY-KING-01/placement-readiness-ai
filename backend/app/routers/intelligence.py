from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.models import LearningRoadmap, RoadmapTask
from app.routers.dependencies import DB, CurrentStudent, Limit, Offset
from app.schemas.roadmap import RoadmapRequest, TaskChange
from app.services import roadmap
from app.services.prediction import predict, prediction_history

router = APIRouter(prefix="/students/me", tags=["Predictions and learning"])


@router.get("/predictions")
def predictions(db: DB, student: CurrentStudent):
    response = predict(db, student)
    db.commit()
    return response


@router.get("/prediction-history")
def predictions_history(db: DB, student: CurrentStudent, limit: Limit = 30, offset: Offset = 0):
    return prediction_history(db, student.id, limit, offset)


@router.post("/roadmap")
def generate(data: RoadmapRequest, db: DB, student: CurrentStudent):
    result = roadmap.public(db, roadmap.create(db, student, data.weekly_hours))
    db.commit()
    return result


@router.get("/roadmap")
def get(db: DB, student: CurrentStudent):
    return roadmap.public(db, roadmap.latest(db, student.id))


@router.patch("/roadmap/tasks/{key}")
def update(key: str, data: TaskChange, db: DB, student: CurrentStudent):
    task = db.scalar(
        select(RoadmapTask)
        .join(LearningRoadmap, LearningRoadmap.id == RoadmapTask.roadmap_id)
        .where(RoadmapTask.id == key, LearningRoadmap.student_id == student.id)
        .with_for_update()
    )
    if task is None:
        raise HTTPException(404, "Task not found")
    task.completed = data.completed
    db.commit()
    return {"id": key, "completed": data.completed}

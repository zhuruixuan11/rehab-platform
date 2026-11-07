from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.deps import get_current_user
from app.utils.helpers import save_upload_file

router = APIRouter(prefix="/api/upload", tags=["文件上传"])


@router.post("/image")
async def upload_image(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    rel_path, err = await save_upload_file(file, "checkin", "image")
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"path": rel_path, "url": f"/uploads/{rel_path}", "type": "image"}


@router.post("/video")
async def upload_video(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    rel_path, err = await save_upload_file(file, "checkin", "video")
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"path": rel_path, "url": f"/uploads/{rel_path}", "type": "video"}


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    rel_path, err = await save_upload_file(file, "avatars", "image")
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"path": rel_path, "url": f"/uploads/{rel_path}"}

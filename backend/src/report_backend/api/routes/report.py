from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ..dependencies import report_service, task_store


router = APIRouter(prefix="/api/v1", tags=["report"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/report/generate")
async def generate_report(
    title: str = Form(...),
    extra_info: str = Form(""),
    template_file: UploadFile = File(...),
    background_files: list[UploadFile] | None = File(default=None),
) -> dict[str, object]:
    if not template_file.filename or not template_file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="template_file must be a .docx file.")
    if not await is_valid_docx_upload(template_file):
        raise HTTPException(status_code=400, detail="Uploaded template is not a valid .docx file.")

    task_id = await report_service.submit(
        title=title,
        extra_info=extra_info,
        template_file=template_file,
        background_files=background_files or [],
    )
    return {
        "code": 200,
        "message": "Task submitted successfully",
        "data": {"task_id": task_id},
    }


@router.get("/report/events/{task_id}")
async def stream_report_events(task_id: str) -> StreamingResponse:
    snapshot = task_store.get(task_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="task_id does not exist.")

    async def event_generator():
        last_version = -1
        keepalive_ticks = 0
        while True:
            current = task_store.get(task_id)
            version = task_store.get_version(task_id)
            if current is None or version is None:
                break
            if version != last_version:
                yield f"data: {json.dumps(current.as_event(), ensure_ascii=False)}\n\n"
                last_version = version
                keepalive_ticks = 0
                if current.status.value in {"SUCCESS", "FAILED"}:
                    break
            else:
                keepalive_ticks += 1
                if keepalive_ticks >= 30:
                    yield ": keep-alive\n\n"
                    keepalive_ticks = 0
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/report/download/{task_id}")
async def download_report(task_id: str) -> FileResponse:
    snapshot = task_store.get(task_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="task_id does not exist.")
    if snapshot.output_docx_path is None:
        raise HTTPException(status_code=409, detail="Report has not finished generating.")

    output_path = Path(snapshot.output_docx_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Generated report file does not exist.")

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=snapshot.file_name or output_path.name,
    )


async def is_valid_docx_upload(upload: UploadFile) -> bool:
    content = await upload.read()
    await upload.seek(0)
    return zipfile.is_zipfile(io.BytesIO(content))

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import uuid
import shutil
import json

app = FastAPI()

# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# STORAGE
# =========================

os.makedirs("storage/projects", exist_ok=True)
os.makedirs("storage/profile_logos", exist_ok=True)
os.makedirs("storage/project_files", exist_ok=True)

# =========================
# STATIC
# =========================

app.mount("/storage", StaticFiles(directory="storage"), name="storage")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# =========================
# DATABASE
# =========================

users = {}
projects = {}
rooms = {}

# =========================
# MODELS
# =========================

class RegisterModel(BaseModel):
    username: str
    bio: str

class ProjectModel(BaseModel):
    name: str
    purpose: str
    description: str
    visibility: str
    owner: str

# =========================
# USER REGISTER
# =========================

@app.post("/api/register")

async def register(
    username: str = Form(...),
    bio: str = Form(...),
    logo: UploadFile = File(...)
):

    social_id = "CRN-" + str(uuid.uuid4())[:6].upper()

    logo_name = f"{uuid.uuid4()}_{logo.filename}"

    logo_path = f"storage/profile_logos/{logo_name}"

    with open(logo_path, "wb") as buffer:
        shutil.copyfileobj(logo.file, buffer)

    user = {
        "username": username,
        "bio": bio,
        "social_id": social_id,
        "logo": "/" + logo_path
    }

    users[social_id] = user

    return user

# =========================
# CREATE PROJECT
# =========================

@app.post("/api/create-project")

async def create_project(data: ProjectModel):

    project_id = str(uuid.uuid4())[:8]

    projects[project_id] = {
        "id": project_id,
        "name": data.name,
        "purpose": data.purpose,
        "description": data.description,
        "visibility": data.visibility,
        "owner": data.owner,
        "files": [],
        "team": []
    }

    os.makedirs(f"storage/project_files/{project_id}", exist_ok=True)

    return {
        "message": "Project Created",
        "project_id": project_id
    }

# =========================
# GET PROJECT
# =========================

@app.get("/api/project/{project_id}")

async def get_project(project_id: str):

    if project_id not in projects:
        return JSONResponse(
            status_code=404,
            content={"message": "Project Not Found"}
        )

    return projects[project_id]

# =========================
# UPLOAD FILES
# =========================

@app.post("/api/upload-file/{project_id}")

async def upload_file(
    project_id: str,
    file: UploadFile = File(...)
):

    if project_id not in projects:
        return JSONResponse(
            status_code=404,
            content={"message": "Project Not Found"}
        )

    file_path = f"storage/project_files/{project_id}/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    projects[project_id]["files"].append(file.filename)

    return {
        "message": "File Uploaded",
        "filename": file.filename
    }

# =========================
# LIST FILES
# =========================

@app.get("/api/files/{project_id}")

async def list_files(project_id: str):

    if project_id not in projects:
        return []

    return projects[project_id]["files"]

# =========================
# SAVE FILE CONTENT
# =========================

@app.post("/api/save-file/{project_id}/{filename}")

async def save_file(
    project_id: str,
    filename: str,
    content: str = Form(...)
):

    folder = f"storage/project_files/{project_id}"

    os.makedirs(folder, exist_ok=True)

    path = f"{folder}/{filename}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "message": "Saved"
    }

# =========================
# LOAD FILE CONTENT
# =========================

@app.get("/api/load-file/{project_id}/{filename}")

async def load_file(project_id: str, filename: str):

    path = f"storage/project_files/{project_id}/{filename}"

    if not os.path.exists(path):
        return {
            "content": ""
        }

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "content": content
    }

# =========================
# GENERATE PUBLIC LINK
# =========================

@app.post("/api/generate-link/{project_id}")

async def generate_link(project_id: str):

    if project_id not in projects:
        return JSONResponse(
            status_code=404,
            content={"message": "Project Not Found"}
        )

    public_link = f"/project-{project_id}"

    projects[project_id]["public_link"] = public_link

    return {
        "public_link": public_link
    }

# =========================
# PUBLIC PROJECT PAGE
# =========================

@app.get("/project-{project_id}")

async def public_project(project_id: str):

    if project_id not in projects:
        return JSONResponse(
            status_code=404,
            content={"message": "Project Not Found"}
        )

    return projects[project_id]

# =========================
# SOCIALS
# =========================

@app.get("/api/users")

async def get_users():
    return list(users.values())

# =========================
# WEBSOCKET MULTIPLAYER
# =========================

@app.websocket("/ws/{room}")

async def websocket_endpoint(websocket: WebSocket, room: str):

    await websocket.accept()

    if room not in rooms:
        rooms[room] = []

    rooms[room].append(websocket)

    try:

        while True:

            data = await websocket.receive_text()

            for connection in rooms[room]:

                await connection.send_text(data)

    except WebSocketDisconnect:

        rooms[room].remove(websocket)

# =========================
# MEETING ROOM
# =========================

@app.websocket("/meet/{room}")

async def meeting_room(websocket: WebSocket, room: str):

    await websocket.accept()

    if room not in rooms:
        rooms[room] = []

    rooms[room].append(websocket)

    try:

        while True:

            data = await websocket.receive_text()

            for user in rooms[room]:

                if user != websocket:
                    await user.send_text(data)

    except WebSocketDisconnect:

        rooms[room].remove(websocket)

# =========================
# TERMINAL COMPILER
# =========================

@app.post("/api/compile")

async def compile_code(code: str = Form(...)):

    errors = []

    if "error" in code.lower():
        errors.append("Syntax Error Found")

    return {
        "success": len(errors) == 0,
        "errors": errors,
        "output": "Compilation Finished"
    }

# =========================
# SETTINGS
# =========================

@app.get("/api/settings")

async def settings():

    return {
        "app": "CODE REALME NONSTOP",
        "version": "ULTRA MAX",
        "status": "ONLINE"
    }

# =========================
# RUN
# =========================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

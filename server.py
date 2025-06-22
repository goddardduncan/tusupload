from fastapi import FastAPI, Request
from tusserver.tus import create_api_router
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi import HTTPException

import uvicorn
import os
import shutil
import subprocess

app = FastAPI()

# Enable required CORS headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Location",
        "Upload-Offset",
        "Tus-Resumable",
        "Tus-Version",
        "Tus-Extension",
        "Tus-Max-Size",
        "Upload-Expires",
    ],
)

# Live upload handler
def on_upload_complete(file_path: str, metadata: dict):
    filename = metadata.get("name", "uploaded_file")
    final_path = os.path.join("./uploads", filename)
    try:
        shutil.copyfile(file_path, final_path)
        print(f"✅ Reassembled to: {final_path}")
    except Exception as e:
        print(f"❌ Error reassembling file: {e}")

# Mount TUS upload handler
tus_router = create_api_router(
    files_dir="./uploads",
    prefix="files",
    on_upload_complete=on_upload_complete
)
app.include_router(tus_router)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve frontend
@app.get("/")
def serve_index():
    return FileResponse("templates/index.html")

# List uploaded files
@app.get("/uploads")
def list_uploaded_files():
    upload_dir = "./uploads"
    files = []
    for f in sorted(os.listdir(upload_dir)):
        if f.endswith(".info"):
            continue
        full_path = os.path.join(upload_dir, f)
        if os.path.isfile(full_path):
            size_bytes = os.path.getsize(full_path)
            files.append({
                "name": f,
                "size": size_bytes
            })
    return JSONResponse(content=files)

# Download files
@app.get("/uploads/{filename}")
def download_file(filename: str):
    path = os.path.join("uploads", filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)

# Manual finalize for resumed uploads
@app.post("/finalize")
async def finalize_upload(request: Request):
    data = await request.json()
    upload_id = data.get("upload_id")
    filename = data.get("filename")
    if not upload_id or not filename:
        return JSONResponse({"error": "Missing fields"}, status_code=400)

    try:
        src = os.path.join("uploads", upload_id)
        dst = os.path.join("uploads", filename)
        shutil.copyfile(src, dst)
        print(f"🔧 Finalized {upload_id} → {filename}")
        return {"status": "✅ File finalized"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
# Drive space info
@app.get("/lsblk")
def get_lsblk_output():
    try:
        output = subprocess.check_output(["df", "-h", "/dev/nvme0n1p1"], text=True)
        return {"output": output}
    except subprocess.CalledProcessError as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8200, reload=True)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import ROOT_DIR, settings
from app.database import Base, engine

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(router)
app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT_DIR / "static" / "new.html")


@app.get("/new.html", include_in_schema=False)
def new_index():
    return FileResponse(ROOT_DIR / "static" / "new.html")


@app.get("/styles.css", include_in_schema=False)
def styles():
    return FileResponse(ROOT_DIR / "static" / "styles.css")


@app.get("/app.js", include_in_schema=False)
def app_js():
    return FileResponse(ROOT_DIR / "static" / "app.js")

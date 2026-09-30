from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.db.database import Base,engine
from app.api.routes import router
Base.metadata.create_all(bind=engine)
app=FastAPI(title='Hinglish MedCare')
app.include_router(router)
app.mount('/static',StaticFiles(directory='app/static'),name='static')
templates=Jinja2Templates(directory='app/templates')
@app.get('/',response_class=HTMLResponse)
def chat(request:Request):return templates.TemplateResponse('chat.html',{'request':request})

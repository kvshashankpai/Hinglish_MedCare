from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Call
from app.services.conversation_service import new_call,process
router=APIRouter(prefix='/api')
class Message(BaseModel): message:str
@router.post('/calls')
def create(db:Session=Depends(get_db)):
    c=new_call(db);return {'call_uid':c.call_uid,'stage':c.current_stage,'condition':c.condition}
@router.post('/calls/{call_uid}/message')
def send(call_uid:str,payload:Message,db:Session=Depends(get_db)):
    c=db.query(Call).filter(Call.call_uid==call_uid).first()
    if not c:raise HTTPException(404,'Call not found')
    return process(db,c,payload.message.strip())

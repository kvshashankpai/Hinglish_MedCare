from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import Base

class Patient(Base):
    __tablename__='patients'
    id=Column(Integer,primary_key=True); patient_uid=Column(String(40),unique=True,index=True,nullable=False)
    name=Column(String(120)); age=Column(Integer); gender=Column(String(40)); phone=Column(String(40)); location=Column(String(160)); preferred_language=Column(String(40),default='hinglish')
    created_at=Column(DateTime,default=datetime.utcnow); updated_at=Column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    calls=relationship('Call',back_populates='patient')

class Call(Base):
    __tablename__='calls'
    id=Column(Integer,primary_key=True); call_uid=Column(String(40),unique=True,index=True,nullable=False); patient_id=Column(Integer,ForeignKey('patients.id'))
    condition=Column(String(80),default='unknown'); status=Column(String(30),default='active'); current_stage=Column(String(60),default='IDENTIFY_CONDITION')
    is_returning_user=Column(Boolean,default=False); severity=Column(String(20),default='UNKNOWN'); severity_reasons=Column(JSON,default=list)
    requires_follow_up=Column(String(30),default='unknown'); follow_up_status=Column(String(30),default='not_started'); summary=Column(Text)
    started_at=Column(DateTime,default=datetime.utcnow); ended_at=Column(DateTime); updated_at=Column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    patient=relationship('Patient',back_populates='calls'); messages=relationship('ConversationMessage',back_populates='call',cascade='all, delete-orphan'); assessment=relationship('Assessment',back_populates='call',uselist=False,cascade='all, delete-orphan')

class ConversationMessage(Base):
    __tablename__='conversation_messages'
    id=Column(Integer,primary_key=True); call_id=Column(Integer,ForeignKey('calls.id'),nullable=False); role=Column(String(20),nullable=False); message=Column(Text,nullable=False); input_type=Column(String(20),default='text'); language=Column(String(40),default='hinglish'); timestamp=Column(DateTime,default=datetime.utcnow)
    call=relationship('Call',back_populates='messages')

class Assessment(Base):
    __tablename__='assessments'
    id=Column(Integer,primary_key=True); call_id=Column(Integer,ForeignKey('calls.id'),unique=True,nullable=False)
    age=Column(String(30),default='unknown'); cause_of_burn=Column(String(100),default='unknown'); time_since_burn=Column(String(100),default='unknown'); first_aid_given=Column(String(200),default='unknown'); body_part_affected=Column(String(160),default='unknown'); approximate_size=Column(String(160),default='unknown'); blistering_or_skin_appearance=Column(String(160),default='unknown'); pain_level=Column(String(80),default='unknown'); circumferential=Column(String(80),default='unknown'); smoke_or_enclosed_space_exposure=Column(String(160),default='unknown'); missing_information=Column(JSON,default=list); other_relevant_details=Column(Text,default='')
    updated_at=Column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow); call=relationship('Call',back_populates='assessment')

class FollowUp(Base):
    __tablename__='follow_ups'
    id=Column(Integer,primary_key=True); call_id=Column(Integer,ForeignKey('calls.id')); required=Column(Boolean,default=False); follow_up_type=Column(String(50)); reason=Column(Text); status=Column(String(30),default='pending'); created_at=Column(DateTime,default=datetime.utcnow)

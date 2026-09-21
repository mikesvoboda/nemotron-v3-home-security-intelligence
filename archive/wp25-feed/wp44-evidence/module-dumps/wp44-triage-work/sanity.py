from enum import Enum
from sqlalchemy import Column, DateTime, Integer, Text, Boolean, desc, func, select
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import declarative_base
Base = declarative_base()

class AIModel(str, Enum):
    NEMOTRON = "nemotron"

class PV(Base):
    __tablename__ = "prompt_versions"
    id = Column(Integer, primary_key=True)
    model = Column(SQLEnum(AIModel, values_callable=lambda x: [e.value for e in x]), nullable=False)
    version = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)

def try_(label, fn):
    try:
        r = fn()
        print(f"OK  {label}: {r}")
    except Exception as e:
        print(f"RAISE {label}: {type(e).__name__}: {e}")

def comp(s):
    return str(s.compile(compile_kwargs={"literal_binds": True}))

m = AIModel.NEMOTRON
try_("select(None)", lambda: comp(select(None)))
try_("where(None) in 2-clause", lambda: comp(select(PV).where(PV.model==m, None)))
try_("limit(None)", lambda: comp(select(PV).limit(None)))
try_("offset(None)", lambda: comp(select(PV).offset(None)))
try_("order_by(None)", lambda: comp(select(PV).order_by(None)))
try_("desc(None)", lambda: comp(select(PV).order_by(desc(None))))
try_("where model==None literal", lambda: comp(select(PV).where(PV.model==None)))
try_("orig active filter", lambda: comp(select(PV).where(PV.model==m, PV.is_active==True)))
try_("flip != active", lambda: comp(select(PV).where(PV.model==m, PV.is_active != True)))
try_("is_active == False", lambda: comp(select(PV).where(PV.model==m, PV.is_active == False)))
try_("model != ", lambda: comp(select(PV).where(PV.model != m)))
try_("by-id", lambda: comp(select(PV).where(PV.id==7)))
try_("by-id !=", lambda: comp(select(PV).where(PV.id!=7)))
try_("history paged", lambda: comp(select(PV).order_by(desc(PV.created_at)).limit(10).offset(20)))
try_("count scoped", lambda: comp(select(func.count()).select_from(PV).where(PV.model==m)))
try_("keep q", lambda: comp(select(PV.id).where(PV.model==m).order_by(desc(PV.created_at)).limit(50)))
try_("delete q", lambda: comp(select(PV).where(PV.model==m, ~PV.id.in_({1,2,3}))))
try_("delete q inverted", lambda: comp(select(PV).where(PV.model==m, PV.id.in_({1,2,3}))))
try_("delete no model", lambda: comp(select(PV).where(None, ~PV.id.in_({1,2}))))
print("enum roundtrip:", AIModel(AIModel.NEMOTRON) is AIModel.NEMOTRON, AIModel.NEMOTRON == "nemotron", isinstance("nemotron", AIModel))
import json
print("indent eq via loads:", json.loads(json.dumps({"a":1})) == json.loads(json.dumps({"a":1}, indent=None)))

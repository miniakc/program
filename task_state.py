"""UI-independent task state; progress counts completed pages/chunks, never elapsed estimates."""
from dataclasses import dataclass
from time import monotonic

@dataclass
class TaskState:
    name: str = '준비됨'
    filename: str = ''
    phase: str = '교재를 등록해 수업을 준비하세요.'
    detail: str = ''
    current: int = 0
    total: int = 0
    unit: str = '쪽'
    state: str = 'idle'
    started: float = 0
    ended: float = 0
    def begin(self,name,filename=''):
        self.name=name;self.filename=filename;self.phase='작업 준비 중';self.detail='';self.current=0;self.total=0;self.unit='쪽';self.state='running';self.started=monotonic();self.ended=0
    def update(self,payload):
        if self.state not in ('running','stopping'):return
        if isinstance(payload,str):self.detail=payload;return
        if 'total' in payload:self.total=max(0,int(payload['total']))
        if 'current' in payload:self.current=max(0,int(payload['current']))
        if self.total:self.current=min(self.current,self.total)
        for key in ('phase','detail','unit'):
            if key in payload:setattr(self,key,str(payload[key]))
    @property
    def percent(self):return round(100*self.current/self.total) if self.total else None
    @property
    def elapsed(self):return max(0,int((self.ended or monotonic())-self.started)) if self.started else 0
    def finish(self,detail):
        self.state='done';self.phase='완료';self.detail=detail;self.ended=monotonic()
        if self.total:self.current=self.total
    def stop(self):
        if self.state=='running':self.state='stopping';self.detail='중단 요청을 전달했습니다. 현재 처리 구간이 정리될 때까지 기다려주세요.'
    def end(self,state,detail):
        self.state=state;self.phase='중단됨' if state=='cancelled' else '작업 실패';self.detail=detail;self.ended=monotonic()

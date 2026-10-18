"""Offline, auditable source checks. No claim of semantic/clinical validation."""
import hashlib,json,re
from pathlib import Path
from core import validate,now

SCOPE='문제 형식·교재 연결·원본 페이지·챕터 범위·원문 인용·이미지 파일 연결을 대조합니다. 정답의 의미·의학적 정확성은 자동 확정하지 않습니다.'

def norm(value):return re.sub(r'\s+','',str(value or '')).casefold()
def source_name(value):return re.sub(r'[^\w가-힣]','',Path(str(value or '')).stem).casefold()
def category(q):return q.get('category') or q.get('topic') or '기타'
def status_label(q):
    if q.get('approved'):
        return '직접 검토 완료' if q.get('review_origin','manual') in ('manual','manual_legacy') else '자동 대조 완료'
    return '확인 필요'

class SourceReview:
    def __init__(self,store,assets):self.store=store;self.assets=assets;self._cache=None;self._chapter_cache=None
    def doc(self,id):
        if self._cache is None:return self.store.document(id)
        if id not in self._cache:self._cache[id]=self.store.document(id)
        return self._cache[id]
    def chapters(self,id):
        if self._chapter_cache is None:return self.store.chapters(id)
        if id not in self._chapter_cache:self._chapter_cache[id]=self.store.chapters(id)
        return self._chapter_cache[id]
    def prepare(self,questions,target_doc=None,target_chapter=None,preserve_manual=False):
        self._cache={};self._chapter_cache={}
        try:return self._prepare(questions,target_doc,target_chapter,preserve_manual)
        finally:self._cache=None;self._chapter_cache=None
    def identify(self,q):
        docs=self.store.documents();fingerprint=q.get('source_digest');ids=set()
        if fingerprint:
            exact=[d['id'] for d in docs if d['digest']==fingerprint]
            if len(exact)==1:return exact[0]
            ids={d['id'] for d in docs if any(('EMS_SOURCE_SHA256: '+str(fingerprint)) in p['text'] for p in self.doc(d['id'])['pages'][:1])}
            return next(iter(ids)) if len(ids)==1 else None
        if q.get('doc_id') in {d['id'] for d in docs}:return q['doc_id']
        prefixes={name.split('_p')[0] for name in q.get('images',[]) if '_p' in name}
        if prefixes:
            ids={d['id'] for d in docs if d['digest'][:16] in prefixes}
            if len(ids)==1:return next(iter(ids))
        name=source_name(q.get('source'))
        if name:
            ids={d['id'] for d in docs if source_name(d['name'])==name}
            if len(ids)==1:return next(iter(ids))
        return None
    def _prepare(self,questions,target_doc=None,target_chapter=None,preserve_manual=False):
        qs=[dict(q) for q in questions];resolved=[self.identify(q) for q in qs]
        by_source={}
        for q,doc in zip(qs,resolved):
            if doc and q.get('source'):by_source.setdefault(norm(q['source']),set()).add(doc)
        for q,doc in zip(qs,resolved):
            if not doc and len(by_source.get(norm(q.get('source')),set()))==1:doc=next(iter(by_source[norm(q.get('source'))]))
            doc=doc or target_doc
            old_chapter=q.get('chapter_id');q.pop('doc_id',None);q.pop('chapter_id',None)
            if doc:
                q['doc_id']=doc;d=self.doc(doc);chapters=self.chapters(doc)
                if not q.get('source'):q['source']=d['name']
                if target_chapter and target_doc==doc:q['chapter_id']=target_chapter
                elif old_chapter in {c['id'] for c in chapters}:q['chapter_id']=old_chapter
                else:
                    page=q.get('page');matches=[c for c in chapters if type(page) is int and c['start']<=page<=c['end']]
                    if len(matches)==1:q['chapter_id']=matches[0]['id']
            q['category']=category(q)
            self.check(q,preserve_manual=preserve_manual)
        return qs
    def check(self,q,preserve_manual=False):
        validate(q);checks={};issues=[]
        def check(name,ok,reason):checks[name]=bool(ok);issues.extend([] if ok else [reason])
        check('문제·정답 형식',True,'')
        doc=q.get('doc_id');d=None
        if doc:
            try:d=self.doc(doc)
            except ValueError:pass
        check('교재 연결',d is not None,'등록된 교재를 연결하세요.')
        if d:
            digest=q.get('source_digest')
            matches=not digest or digest==d['digest'] or any(('EMS_SOURCE_SHA256: '+str(digest)) in p['text'] for p in d['pages'][:1])
            check('교재 식별값',matches,'JSON의 교재 식별값과 연결한 교재가 다릅니다.')
            page=q.get('page');p=next((p for p in d['pages'] if type(page) is int and p['page']==page),None)
            check('원본 페이지',p is not None,'해당 원본 PDF 페이지를 찾을 수 없습니다.')
            check('원문 인용',p is not None and bool(norm(q.get('quote'))) and norm(q['quote']) in norm(p['text']),'인용문이 지정 페이지의 원문과 일치하지 않습니다.')
            chapters=self.chapters(doc)
            if not q.get('chapter_id'):
                matches=[c for c in chapters if type(page) is int and c['start']<=page<=c['end']]
                if len(matches)==1:q['chapter_id']=matches[0]['id']
            chapter=next((c for c in chapters if c['id']==q.get('chapter_id')),None)
            in_scope=not chapters or chapter is not None and type(page) is int and chapter['start']<=page<=chapter['end']
            check('챕터 범위',in_scope,'페이지에 맞는 챕터를 연결하거나 챕터 범위를 확인하세요.')
            for r in q.get('refs',[]):
                if isinstance(r,dict) and r.get('quote'):
                    rp=next((p for p in d['pages'] if p['page']==r.get('page')),None)
                    check('추가 인용 '+str(r.get('page')),bool(rp) and norm(r['quote']) in norm(rp['text']),'추가 인용문이 원문과 일치하지 않습니다.')
            for name in q.get('images',[]):
                prefixes={d['digest'][:16]}|{v[:16] for p in d['pages'][:1] for v in re.findall(r'EMS_SOURCE_SHA256: ([a-f0-9]{64})',p['text'])}
                if '_p' in name and name.split('_p')[0] not in prefixes:
                    check('이미지 출처 '+name,False,'다른 교재의 이미지 ID가 포함되어 있습니다: '+name)
        for name in q.get('images',[]):check('이미지 파일 '+name,self.assets.resolve(name) is not None,'이미지 파일이 없습니다: '+name)
        fingerprint=hashlib.sha256(json.dumps({k:v for k,v in q.items() if k not in ('review_report','approved','review_origin')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        q['review_report']={'status':'passed' if not issues else 'needs_review','checks':checks,'issues':issues,'scope':SCOPE,'semantic_validation':False,'checked_at':now(),'fingerprint':fingerprint}
        manual=preserve_manual and q.get('approved') and q.get('review_origin','manual_legacy') in ('manual','manual_legacy')
        q['approved']=bool(manual or not issues);q['review_origin']='manual' if manual else 'automatic'
        q['organization_version']=1
        return q
    def reconcile(self):
        qs=self.store.questions();prepared=self.prepare(qs,preserve_manual=True)
        for old,q in zip(qs,prepared):
            # Re-run on meaningful changes, not on every refresh/timer tick.
            self.store.put(q)
        return prepared

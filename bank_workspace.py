"""Textbook/chapter question bank and textbook-linked category classroom."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from question_list import QuestionList
from review import category,status_label,SCOPE
from core import parse_questions

UNLINKED='__unlinked__';UNASSIGNED='__unassigned__'

class BankWorkspace:
    def setup_bank(self):
        self.bank_doc_id=None;self.bank_chapter_id=None;self.bank_level='books'
        title=ttk.Frame(self.bank);title.pack(fill='x',pady=(0,10))
        ttk.Label(title,text='문제은행',font=('맑은 고딕',20,'bold')).pack(side='left')
        ttk.Label(title,text='교재 → 하위 챕터 → 문제 선택·관리',style='Muted.TLabel').pack(side='left',padx=16)
        self.bank_breadcrumb=ttk.Frame(self.bank);self.bank_breadcrumb.pack(fill='x',pady=(0,8))
        self.bank_toolbar=ttk.Frame(self.bank);self.bank_toolbar.pack(fill='x',pady=(0,10))
        self.action(self.bank_toolbar,'JSON 가져오기',self.import_bank,True,lock=True);self.action(self.bank_toolbar,'직접 작성',lambda:self.editor(None));self.action(self.bank_toolbar,'교재 자료 관리',lambda:self.navigate('docs'),side='right')
        self.bank_bottom=ttk.Frame(self.bank);self.bank_bottom.pack(side='bottom',fill='x',pady=(10,0));self.bank_quiz_button=self.action(self.bank_bottom,'선택 / 현재 챕터 퀴즈 →',self.start_quiz,True,side='right')
        self.bank_count=ttk.Label(self.bank_bottom,text='',style='Muted.TLabel');self.bank_count.pack(side='left')
        self.bank_browser_host=ttk.Frame(self.bank);self.bank_browser_host.pack(fill='both',expand=True)
        self.bank_browser_canvas=tk.Canvas(self.bank_browser_host,bg='#f6f8f8',highlightthickness=0);sc=ttk.Scrollbar(self.bank_browser_host,orient='vertical',command=self.bank_browser_canvas.yview);sc.pack(side='right',fill='y');self.bank_browser_canvas.pack(fill='both',expand=True);self.bank_browser_canvas.configure(yscrollcommand=sc.set)
        self.bank_browser=ttk.Frame(self.bank_browser_canvas);item=self.bank_browser_canvas.create_window((0,0),window=self.bank_browser,anchor='nw');self.bank_browser_canvas.bind('<Configure>',lambda e:self.bank_browser_canvas.itemconfigure(item,width=e.width));self.bank_browser.bind('<Configure>',lambda e:self.bank_browser_canvas.configure(scrollregion=self.bank_browser_canvas.bbox('all')))
        self.bank_questions=ttk.Frame(self.bank)
        tools=ttk.Frame(self.bank_questions);tools.pack(fill='x',pady=(0,8));self.select_all_var=tk.BooleanVar();ttk.Checkbutton(tools,text='전체 선택',variable=self.select_all_var,command=self.select_all_questions).pack(side='left')
        self.action(tools,'선택 삭제',self.delete_selected,lock=True);self.action(tools,'교재·챕터 이동',self.move_questions);self.action(tools,'원문 다시 대조',self.recheck_questions)
        exports=ttk.Frame(self.bank_questions);exports.pack(fill='x',pady=(0,8));self.action(exports,'Excel 저장',self.export_excel);self.action(exports,'JSON 저장',self.export_bank);self.action(exports,'이미지 ZIP',self.import_assets)
        filters=ttk.Frame(self.bank_questions);filters.pack(fill='x',pady=(0,8));self.search=tk.StringVar();ttk.Entry(filters,textvariable=self.search).pack(side='left',fill='x',expand=True);self.search.trace_add('write',lambda *a:self.refresh_bank())
        self.topic_filter=tk.StringVar(value='전체');self.topic_pick=ttk.Combobox(filters,textvariable=self.topic_filter,values=['전체'],state='readonly',width=15);self.topic_pick.pack(side='left',padx=8);self.topic_pick.bind('<<ComboboxSelected>>',lambda e:self.refresh_bank())
        self.onlydraft=tk.BooleanVar();ttk.Checkbutton(filters,text='확인 필요',variable=self.onlydraft,command=self.refresh_bank).pack(side='right')
        self.qlist=QuestionList(self.bank_questions,self.editor,self.update_bank_selection);self.qlist.pack(fill='both',expand=True)
        ttk.Label(self.play,text='함께 풀며 배우는 시간.',font=('맑은 고딕',18,'bold')).pack(anchor='w',pady=(0,6))
        ttk.Label(self.play,text='자동 10초 · Space 정답 / 방향키 이전·다음',style='Muted.TLabel').pack(anchor='w',pady=(0,10))
        row=ttk.Frame(self.play);row.pack(fill='x');self.action(row,'카테고리 선택',lambda:self.open_catalog(),True);self.action(row,'전체화면',self.toggle_fullscreen,side='right')
        self.quiz_count=tk.StringVar(value='전체');ttk.Label(row,text='문항 수').pack(side='left',padx=8);ttk.Combobox(row,textvariable=self.quiz_count,values=['전체','10','20','30','50'],state='readonly',width=7).pack(side='left')
        self.quiz_shuffle=tk.BooleanVar(value=False);ttk.Checkbutton(row,text='무작위',variable=self.quiz_shuffle).pack(side='left',padx=8)
        self.quizframe=ttk.Frame(self.play,style='Card.TFrame',padding=20);self.quizframe.pack(fill='both',expand=True,pady=12)
    def bank_scope(self,q):
        if self.bank_doc_id==UNLINKED and q.get('doc_id'):return False
        if self.bank_doc_id not in (None,UNLINKED) and q.get('doc_id')!=self.bank_doc_id:return False
        if self.bank_chapter_id==UNASSIGNED and q.get('chapter_id'):return False
        if self.bank_chapter_id not in (None,UNASSIGNED) and q.get('chapter_id')!=self.bank_chapter_id:return False
        return True
    def open_bank(self,doc=None,chapter=None):
        self.bank_doc_id=doc;self.bank_chapter_id=chapter;self.bank_level='questions' if chapter is not None or doc==UNLINKED else ('chapters' if doc else 'books')
        self.search.set('');self.topic_filter.set('전체');self.onlydraft.set(False);self.refresh_bank();self.navigate('bank')
    def refresh_bank(self):
        if not hasattr(self,'qlist'):return
        if self.bank_doc_id not in (None,UNLINKED) and self.bank_doc_id not in {d['id'] for d in self.store.documents()}:self.bank_doc_id=None;self.bank_chapter_id=None;self.bank_level='books'
        chosen=set(self.qlist.selection());self.qrows=self.store.questions();self.qlist.delete(*self.qlist.get_children())
        self.topic_pick['values']=['전체']+list(dict.fromkeys(category(q) for q in self.qrows if self.bank_scope(q)))
        for q in self.qrows:
            if not self.bank_scope(q) or self.onlydraft.get() and q['approved']:continue
            if self.topic_filter.get() not in ('전체',category(q)):continue
            if self.search.get().casefold() not in (q['stem']+' '+category(q)+' '+q['concept']).casefold():continue
            self.qlist.add_question(q,self.question_location(q))
        self.qlist.selection_set(chosen)
        self.refresh_bank_browser();self.update_bank_selection()
    def question_location(self,q):
        doc=next((d for d in self.store.documents() if d['id']==q.get('doc_id')),None)
        chapter=next((c for c in self.store.chapters(doc['id']) if c['id']==q.get('chapter_id')),None) if doc else None
        return (doc['name'] if doc else '교재 미연결')+' · '+(chapter['title'] if chapter else '미분류' if doc and self.store.chapters(doc['id']) else '전체 범위')+' · '+category(q)+f" · PDF {q.get('page','미상')}쪽"
    def update_bank_selection(self):
        if not hasattr(self,'qlist'):return
        total=len(self.qlist.get_children());chosen=len(self.qlist.selection());self.bank_count.configure(text=f'{total}문제 · {chosen}개 선택');self.select_all_var.set(bool(total) and chosen==total);self.bank_quiz_button.configure(state='normal' if self.bank_level=='questions' and total else 'disabled')
    def select_all_questions(self):self.qlist.selection_set(self.qlist.get_children() if self.select_all_var.get() else [])
    def refresh_bank_browser(self):
        for w in self.bank_breadcrumb.winfo_children():w.destroy()
        self.action(self.bank_breadcrumb,'교재 목록',lambda:self.open_bank())
        doc=next((d for d in self.store.documents() if d['id']==self.bank_doc_id),None)
        if doc:self.action(self.bank_breadcrumb,doc['name'],lambda:self.open_bank(doc['id']))
        if self.bank_chapter_id:
            title=next((c['title'] for c in self.store.chapters(doc['id']) if c['id']==self.bank_chapter_id),'전체 범위' if self.bank_chapter_id==UNASSIGNED else '') if doc else '미연결 문제'
            ttk.Label(self.bank_breadcrumb,text=' / '+title).pack(side='left')
        self.bank_browser_host.pack_forget();self.bank_questions.pack_forget()
        if self.bank_level=='questions':self.bank_questions.pack(fill='both',expand=True);return
        self.bank_browser_host.pack(fill='both',expand=True)
        for w in self.bank_browser.winfo_children():w.destroy()
        if self.bank_level=='books':
            groups=[(d['id'],d['name'],f"챕터 {len(self.store.chapters(d['id']))}개",lambda id=d['id']:self.open_bank(id)) for d in self.store.documents()]
            if any(not q.get('doc_id') for q in self.qrows):groups.append((UNLINKED,'교재 미연결','연결할 교재를 지정하세요.',lambda:self.open_bank(UNLINKED,UNASSIGNED)))
        elif doc:
            groups=[(c['id'],c['title'],f"PDF {c['start']}–{c['end']}쪽",lambda id=c['id']:self.open_bank(doc['id'],id)) for c in self.store.chapters(doc['id'])]
            if not groups or any(q.get('doc_id')==doc['id'] and not q.get('chapter_id') for q in self.qrows):groups.append((UNASSIGNED,'전체 범위' if not groups else '미분류 문제','페이지·챕터를 확인하세요.' if groups else '교재 전체의 문제',lambda:self.open_bank(doc['id'],UNASSIGNED)))
            row=ttk.Frame(self.bank_browser);row.pack(fill='x',pady=(0,10));self.action(row,'이 교재 카테고리 퀴즈 →',lambda:self.open_catalog(doc['id']),True);self.action(row,'챕터 범위 설정',lambda:self.open_document(doc['id']))
        else:self.bank_doc_id=None;self.bank_level='books';return self.refresh_bank_browser()
        grid=ttk.Frame(self.bank_browser);grid.pack(fill='x')
        for i,(id,title,detail,fn) in enumerate(groups):
            qs=[q for q in self.qrows if (q.get('doc_id')==id if self.bank_level=='books' and id!=UNLINKED else not q.get('doc_id') if id==UNLINKED else q.get('doc_id')==self.bank_doc_id and (q.get('chapter_id')==id if id!=UNASSIGNED else not q.get('chapter_id')))]
            host=ttk.Frame(grid);host.grid(row=i//2,column=i%2,sticky='nsew',padx=(0,10 if i%2==0 else 0),pady=6);grid.columnconfigure(i%2,weight=1)
            c=self.card(host,fill='both',expand=True);self.label(c,'TEXTBOOK' if self.bank_level=='books' else 'CHAPTER','CardMuted.TLabel');self.label(c,title,'CardTitle.TLabel',wraplength=400);self.label(c,detail,'CardMuted.TLabel',wraplength=400);self.label(c,f"{len(qs)}문제 · 대조 / 검토 완료 {sum(q.get('approved',False) for q in qs)}개",'CardMuted.TLabel')
            row=ttk.Frame(c,style='Card.TFrame');row.pack(fill='x',pady=(12,0));self.action(row,'교재 열기 →' if self.bank_level=='books' else '챕터 문제 보기 →',fn,True)
        if not groups:self.label(self.bank_browser,'아직 교재가 없습니다. 교재 자료에서 PDF를 먼저 등록하세요.','Muted.TLabel',wraplength=650)
    def choose_destination(self,initial_doc=None,initial_chapter=None):
        docs=self.store.documents();win=tk.Toplevel(self);win.title('교재·챕터 연결');win.geometry('540x320');win.transient(self);win.grab_set();result=[None]
        body=ttk.Frame(win,padding=24);body.pack(fill='both',expand=True);ttk.Label(body,text='어느 교재에 저장할까요?',font=('맑은 고딕',17,'bold')).pack(anchor='w')
        ttk.Label(body,text='교재와 챕터를 연결하면 원문을 자동으로 대조합니다.',wraplength=470).pack(anchor='w',pady=10)
        dv=tk.StringVar();cv=tk.StringVar();dc=ttk.Combobox(body,textvariable=dv,values=['교재 미연결']+[d['name'] for d in docs],state='readonly');dc.pack(fill='x',pady=8)
        cc=ttk.Combobox(body,textvariable=cv,state='readonly');cc.pack(fill='x',pady=8);chapters=[]
        def changed(e=None):
            nonlocal chapters
            index=dc.current()-1;chapters=self.store.chapters(docs[index]['id']) if index>=0 else [];cc['values']=['페이지로 자동 배치']+[c['title'] for c in chapters];cc.current(0)
            if initial_chapter:
                for i,c in enumerate(chapters,1):
                    if c['id']==initial_chapter:cc.current(i)
        dc.bind('<<ComboboxSelected>>',changed);dc.current(next((i+1 for i,d in enumerate(docs) if d['id']==initial_doc),0));changed()
        def save():
            i=dc.current()-1;j=cc.current()-1;result[0]=(docs[i]['id'] if i>=0 else None,chapters[j]['id'] if j>=0 else None);win.destroy()
        row=ttk.Frame(body);row.pack(side='bottom',fill='x');ttk.Button(row,text='취소',command=win.destroy).pack(side='right');ttk.Button(row,text='연결·저장',style='Primary.TButton',command=save).pack(side='right',padx=8)
        self.wait_window(win);return result[0]
    def import_bank(self):
        if self.working:return self.show_busy()
        path=filedialog.askopenfilename(filetypes=[('JSON 문제 파일','*.json *.md')])
        if not path:return
        qs=parse_questions(Path(path).read_text(encoding='utf-8-sig'));doc=self.bank_doc_id if self.bank_doc_id not in (None,UNLINKED) else None;chapter=self.bank_chapter_id if self.bank_chapter_id not in (None,UNASSIGNED) else None
        prepared=self.reviewer.prepare(qs,doc,chapter)
        if any(not q.get('doc_id') for q in prepared) and self.store.documents() and not doc:
            destination=self.choose_destination()
            if destination is None:return
            doc,chapter=destination
        old={q['id'] for q in self.store.questions()};n=self.store.import_questions(qs,self.reviewer,doc,chapter)
        incoming=[q for q in self.store.questions() if q['id'] not in old]
        first=incoming[0] if incoming else None
        if first:self.open_bank(first.get('doc_id') or UNLINKED,first.get('chapter_id') or UNASSIGNED)
        else:self.refresh_bank();self.navigate('bank')
        self.search.set('');self.onlydraft.set(False);self.topic_filter.set('전체');self.refresh_bank();self.qlist.selection_set([q['id'] for q in incoming]);self.refresh_home();self.refresh_catalog()
        ready=sum(q['approved'] for q in incoming);self.status.set(f'{n}문제 저장 · 원문 자동 대조 완료 {ready}개 · 확인 필요 {n-ready}개 · 중복 {len(qs)-n}개 제외');self.draw_task()
    def move_questions(self):
        ids=self.qlist.selection()
        if not ids:raise ValueError('이동할 문제의 체크박스를 선택하세요.')
        target=self.choose_destination(self.bank_doc_id,self.bank_chapter_id)
        if target is None:return
        doc,chapter=target
        for q in self.qrows:
            if q['id'] not in ids:continue
            q=dict(q);q.pop('doc_id',None);q.pop('chapter_id',None)
            if doc:q['doc_id']=doc
            if chapter:q['chapter_id']=chapter
            self.reviewer.check(q);self.store.put(q)
        self.open_bank(doc or UNLINKED,chapter or UNASSIGNED);self.refresh_home();self.refresh_catalog()
    def recheck_questions(self):
        ids=set(self.qlist.selection() or self.qlist.get_children())
        for q in self.reviewer.prepare([q for q in self.qrows if q['id'] in ids],preserve_manual=True):self.store.put(q)
        self.refresh_bank();self.refresh_home();self.refresh_catalog();self.status.set('선택 / 현재 범위의 원문 대조를 완료했습니다.');self.draw_task()
    def delete_selected(self):
        ids=self.qlist.selection()
        if not ids:raise ValueError('삭제할 문제의 체크박스를 선택하세요.')
        if not self.confirm_action('선택 문제 삭제',f'체크한 {len(ids)}개 문제를 삭제할까요? 교재와 다른 문제는 유지합니다.','선택 삭제'):return
        self.store.delete(ids);self.refresh_bank();self.refresh_home();self.refresh_catalog()
    def setup_catalog(self):
        self.heading(self.catalog,'CLASSROOM LIBRARY','어떤 교재로 시작할까요?','교재와 카테고리를 선택하면 연결된 문제로 수업을 시작합니다.')
        filters=ttk.Frame(self.catalog);filters.pack(fill='x',pady=(0,12));self.catalog_doc=ttk.Combobox(filters,state='readonly');self.catalog_doc.pack(side='left',fill='x',expand=True);self.catalog_doc.bind('<<ComboboxSelected>>',lambda e:self.catalog_document_changed())
        self.catalog_chapter=ttk.Combobox(filters,state='readonly',width=18);self.catalog_chapter.pack(side='left',padx=8);self.catalog_chapter.bind('<<ComboboxSelected>>',lambda e:self.refresh_catalog_cards())
        self.catalog_pending=tk.BooleanVar(value=False);ttk.Checkbutton(self.catalog,text='확인 필요 문제도 포함',variable=self.catalog_pending,command=self.refresh_catalog_cards).pack(anchor='w')
        self.catalog_cards=ttk.Frame(self.catalog);self.catalog_cards.pack(fill='both',expand=True,pady=12)
    def open_catalog(self,doc=None):
        self.refresh_catalog(doc);self.navigate('catalog')
    def refresh_catalog(self,doc=None):
        if not hasattr(self,'catalog_doc'):return
        previous=self.catalog_docs[self.catalog_doc.current()]['id'] if hasattr(self,'catalog_docs') and 0<=self.catalog_doc.current()<len(self.catalog_docs) else None
        self.catalog_docs=self.store.documents()
        if any(not q.get('doc_id') for q in self.store.questions()):self.catalog_docs.append({'id':UNLINKED,'name':'교재 미연결 문제'})
        self.catalog_doc['values']=[d['name'] for d in self.catalog_docs]
        if self.catalog_docs:self.catalog_doc.current(next((i for i,d in enumerate(self.catalog_docs) if d['id']==(doc or previous)),0))
        else:self.catalog_doc.set('')
        self.catalog_document_changed()
    def catalog_document_changed(self):
        i=self.catalog_doc.current();self.catalog_chapters=self.store.chapters(self.catalog_docs[i]['id']) if 0<=i<len(self.catalog_docs) and self.catalog_docs[i]['id']!=UNLINKED else []
        self.catalog_chapter['values']=['전체 챕터']+[c['title'] for c in self.catalog_chapters];self.catalog_chapter.current(1 if self.catalog_chapters else 0);self.refresh_catalog_cards()
    def catalog_pool(self):
        i=self.catalog_doc.current()
        if i<0 or i>=len(self.catalog_docs):return []
        doc=self.catalog_docs[i]['id'];j=self.catalog_chapter.current()-1;chapter=self.catalog_chapters[j]['id'] if j>=0 else None
        return [q for q in self.store.questions() if (not q.get('doc_id') if doc==UNLINKED else q.get('doc_id')==doc) and (not chapter or q.get('chapter_id')==chapter)]
    def refresh_catalog_cards(self):
        for w in self.catalog_cards.winfo_children():w.destroy()
        pool=self.catalog_pool();groups=list(dict.fromkeys(category(q) for q in pool))
        for i,topic in enumerate(groups):
            qs=[q for q in pool if category(q)==topic];ready=[q for q in qs if q['approved'] or self.catalog_pending.get()]
            host=ttk.Frame(self.catalog_cards);host.grid(row=i//2,column=i%2,sticky='nsew',padx=(0,12 if i%2==0 else 0),pady=7);self.catalog_cards.columnconfigure(i%2,weight=1)
            c=self.card(host,fill='both',expand=True);self.label(c,'CLASSROOM CATEGORY','CardMuted.TLabel');self.label(c,topic,'CardTitle.TLabel',wraplength=400);self.label(c,f'전체 {len(qs)}문제 · 바로 풀기 {len(ready)}개','CardMuted.TLabel')
            row=ttk.Frame(c,style='Card.TFrame');row.pack(fill='x',pady=(12,0));button=self.action(row,'퀴즈 시작 →',lambda qs=ready:self.launch_quiz(qs),True);button.configure(state='normal' if ready else 'disabled')
        if not groups:self.label(self.catalog_cards,'아직 연결된 문제가 없습니다. 문제은행에서 JSON을 등록하세요.','Muted.TLabel',wraplength=650)
        self.after_idle(self.fit_scroll_pages)

"""Desktop layout based on the original EMS QUIZ workspace: white sidebar, teal hero and cards."""
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

BG='#f6f8f8';WHITE='#ffffff';INK='#20343e';MUTED='#73878a';TEAL='#0c8476';DEEP='#143e3d';LINE='#e2eae7';PALE='#e9f4ef'

class WorkspaceUI:
    def configure_style(self):
        self.configure(bg=BG)
        st=ttk.Style(self);st.theme_use('clam')
        st.configure('.',font=('맑은 고딕',10),background=BG,foreground=INK)
        st.configure('TFrame',background=BG);st.configure('Card.TFrame',background=WHITE)
        st.configure('TLabel',background=BG,foreground=INK);st.configure('Card.TLabel',background=WHITE)
        st.configure('Muted.TLabel',foreground=MUTED);st.configure('CardMuted.TLabel',background=WHITE,foreground=MUTED,font=('맑은 고딕',9))
        st.configure('Title.TLabel',font=('맑은 고딕',23,'bold'));st.configure('CardTitle.TLabel',background=WHITE,font=('맑은 고딕',12,'bold'))
        st.configure('TButton',background=WHITE,foreground=INK,bordercolor=LINE,padding=(12,9),font=('맑은 고딕',10),relief='flat')
        st.map('TButton',background=[('active','#edf5f2'),('disabled','#f1f4f2')],foreground=[('disabled','#9caaa6')])
        st.configure('Primary.TButton',background=TEAL,foreground=WHITE,bordercolor=TEAL,font=('맑은 고딕',10,'bold'))
        st.map('Primary.TButton',background=[('active','#076c60'),('disabled','#d4e8df')],foreground=[('disabled','#829e94')])
        st.configure('Danger.TButton',foreground='#b35b4c')
        st.configure('TEntry',fieldbackground=WHITE,bordercolor=LINE,padding=7)
        st.configure('TCombobox',fieldbackground=WHITE,background=WHITE,bordercolor=LINE,padding=6)
        st.map('TCombobox',fieldbackground=[('readonly',WHITE),('disabled','#f1f4f2')])
        st.configure('TCheckbutton',background=WHITE,padding=4)
        st.configure('TRadiobutton',background=WHITE,padding=6)
        st.configure('Treeview',background=WHITE,fieldbackground=WHITE,bordercolor=LINE,rowheight=39,font=('맑은 고딕',10))
        st.configure('Treeview.Heading',background='#eff5f1',foreground='#55786b',font=('맑은 고딕',9,'bold'),padding=9,relief='flat')
        st.map('Treeview',background=[('selected','#e0f1e7')],foreground=[('selected','#126851')])
        st.configure('Workspace.TNotebook',background=BG,borderwidth=0,bordercolor=BG,lightcolor=BG,darkcolor=BG);st.layout('Workspace.TNotebook.Tab',[])
        st.configure('Job.Horizontal.TProgressbar',background=TEAL,troughcolor='#e7efeb',bordercolor='#e7efeb',lightcolor=TEAL,darkcolor=TEAL,thickness=8)
    def action(self,parent,text,fn,primary=False,lock=False,side='left'):
        b=ttk.Button(parent,text=text,style='Primary.TButton' if primary else 'TButton',command=lambda:self.safe(fn))
        b.pack(side=side,padx=(0,8))
        if lock:self.task_controls.append(b)
        return b
    def label(self,parent,text,style='Card.TLabel',**kw):
        w=ttk.Label(parent,text=text,style=style,**kw);w.pack(anchor='w')
        if 'wraplength' in kw:
            parent.bind('<Configure>',lambda e,l=w,limit=kw['wraplength']:l.configure(wraplength=max(180,min(limit,e.width-25))),add='+')
        return w
    def card(self,parent,**pack):
        w=ttk.Frame(parent,style='Card.TFrame',padding=18);w.pack(**pack);return w
    def heading(self,parent,tag,title,description,button=None):
        area=ttk.Frame(parent);area.pack(fill='x',pady=(0,18))
        self.label(area,tag,'Muted.TLabel',font=('맑은 고딕',9,'bold'))
        line=ttk.Frame(area);line.pack(fill='x',pady=(7,4))
        ttk.Label(line,text=title,style='Title.TLabel').pack(side='left')
        if button:self.action(line,button[0],button[1],True,lock=button[2],side='right')
        self.label(area,description,'Muted.TLabel',wraplength=900)
    def setup_shell(self):
        self.task_controls=[];self.current_view=None
        side=tk.Frame(self,bg=WHITE,width=200,highlightbackground=LINE,highlightthickness=1);side.pack(side='left',fill='y');side.pack_propagate(False)
        brand=tk.Frame(side,bg=WHITE);brand.pack(fill='x',padx=20,pady=(28,35))
        tk.Label(brand,text='✚',bg=TEAL,fg=WHITE,font=('Segoe UI Symbol',22,'bold'),width=2).pack(side='left',padx=(0,9))
        names=tk.Frame(brand,bg=WHITE);names.pack(side='left')
        tk.Label(names,text='EMS QUIZ',bg=WHITE,fg=DEEP,font=('맑은 고딕',15,'bold')).pack(anchor='w')
        tk.Label(names,text='응급의료 교육 플랫폼',bg=WHITE,fg=MUTED,font=('맑은 고딕',8)).pack(anchor='w')
        tk.Label(side,text='WORKSPACE',bg=WHITE,fg='#97a8a6',font=('Segoe UI',8,'bold')).pack(anchor='w',padx=25,pady=(0,14))
        self.nav={}
        for key,text in [('home','▦  대시보드'),('docs','▤  자료 관리'),('bank','☷  문제은행'),('play','▷  퀴즈 실행'),('settings','⚙  연결 및 사용안내')]:
            b=tk.Button(side,text=text,anchor='w',bg=WHITE,fg=MUTED,activebackground=PALE,activeforeground=TEAL,relief='flat',bd=0,padx=16,pady=13,font=('맑은 고딕',10),cursor='hand2',command=lambda k=key:self.navigate(k));b.pack(fill='x',padx=12,pady=3);self.nav[key]=b
        tk.Label(side,text='EMS QUIZ  ·  v0.3.0\n강사 워크스페이스',bg=WHITE,fg=MUTED,font=('맑은 고딕',9),justify='left').pack(side='bottom',anchor='w',padx=22,pady=22)
        note=tk.Frame(side,bg='#f0f6f2',padx=13,pady=16);note.pack(side='bottom',fill='x',padx=15,pady=8)
        tk.Label(note,text='교재에서 수업까지',bg='#f0f6f2',fg='#437463',font=('맑은 고딕',10,'bold')).pack(anchor='w')
        tk.Label(note,text='교재 등록 → 문제 만들기\n원문 검토 → 퀴즈 실행',bg='#f0f6f2',fg=MUTED,font=('맑은 고딕',9),justify='left').pack(anchor='w',pady=(8,0))
        self.main=ttk.Frame(self);self.main.pack(side='left',fill='both',expand=True)
        top=tk.Frame(self.main,bg=WHITE,height=57);top.pack(fill='x');top.pack_propagate(False)
        self.breadcrumb=tk.Label(top,text='내 워크스페이스  /  대시보드',bg=WHITE,fg=MUTED,font=('맑은 고딕',9));self.breadcrumb.pack(side='left',padx=26)
        tk.Label(top,text='●  내 PC에 저장됨',bg=WHITE,fg='#51977a',font=('맑은 고딕',9)).pack(side='right',padx=26)
        self.setup_job_panel()
        self.tabs=ttk.Notebook(self.main,style='Workspace.TNotebook');self.tabs.pack(fill='both',expand=True,padx=24,pady=(22,6))
        self.views={};self.page_canvases={}
        for key,title in [('home','대시보드'),('docs','자료 관리'),('bank','문제은행'),('play','퀴즈 실행'),('settings','연결 및 사용안내')]:
            frame=ttk.Frame(self.tabs);self.tabs.add(frame,text=title);self.views[key]=(frame,title)
            if key in ('home','docs','settings'):
                canvas=tk.Canvas(frame,bg=BG,highlightthickness=0,bd=0);scroll=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
                inner=ttk.Frame(canvas);window=canvas.create_window((0,0),window=inner,anchor='nw');self.page_canvases[key]=canvas
                def resize(event,c=canvas,w=window,f=inner):
                    c.itemconfigure(w,width=event.width,height=max(event.height,f.winfo_reqheight()));c.configure(scrollregion=c.bbox('all'))
                canvas.bind('<Configure>',resize);inner.bind('<Configure>',lambda e,c=canvas:c.configure(scrollregion=c.bbox('all')))
                setattr(self,key,inner)
            else:setattr(self,key,frame)
        self.tabs.bind('<<NotebookTabChanged>>',lambda e:self.sync_navigation())
        def wheel(event):
            canvas=self.page_canvases.get(self.current_view)
            target=self.winfo_containing(event.x_root,event.y_root)
            if canvas and target and str(target).startswith(str(canvas)) and not isinstance(target,(tk.Text,ttk.Treeview,ttk.Combobox)):
                delta=-int(event.delta/120) if event.delta else (1 if getattr(event,'num',None)==5 else -1);canvas.yview_scroll(delta,'units')
        self.bind_all('<MouseWheel>',wheel,add='+')
    def navigate(self,key):
        self.tabs.select(self.views[key][0]);self.sync_navigation()
        if key in self.page_canvases:self.page_canvases[key].yview_moveto(0)
    def sync_navigation(self):
        current=self.tabs.select()
        for key,(frame,title) in self.views.items():
            selected=str(frame)==current;self.nav[key].configure(bg=PALE if selected else WHITE,fg=TEAL if selected else MUTED,font=('맑은 고딕',10,'bold' if selected else 'normal'))
            if selected:self.current_view=key;self.breadcrumb.configure(text='내 워크스페이스  /  '+title)
    def setup_job_panel(self):
        self.job_box=tk.Frame(self.main,bg=WHITE,highlightbackground=LINE,highlightthickness=1,padx=16,pady=10)
        self.job_box.pack(side='bottom',fill='x',padx=24,pady=(4,15))
        line=tk.Frame(self.job_box,bg=WHITE);line.pack(fill='x')
        self.job_title=tk.Label(line,text='준비됨',bg=WHITE,fg=TEAL,font=('맑은 고딕',10,'bold'),anchor='w');self.job_title.pack(side='left')
        self.stopbutton=ttk.Button(line,text='작업 중단',command=self.stop_task);self.stopbutton.pack(side='right')
        self.job_numbers=tk.Label(line,text='',bg=WHITE,fg=MUTED,font=('맑은 고딕',9));self.job_numbers.pack(side='right',padx=12)
        self.job_bar=ttk.Progressbar(self.job_box,style='Job.Horizontal.TProgressbar',maximum=100);self.job_bar.pack(fill='x',pady=(8,5))
        self.job_detail=tk.Label(self.job_box,text='',bg=WHITE,fg=MUTED,font=('맑은 고딕',9),anchor='w');self.job_detail.pack(fill='x')
        self.job_tail=tk.Label(self.job_box,text='',bg=WHITE,fg=MUTED,font=('맑은 고딕',9),anchor='w');self.job_tail.pack(fill='x',pady=(3,0));self._indeterminate=False
        self.status=tk.StringVar(value='')
    def draw_task(self):
        job=self.task;active=self.working
        color='#b16740' if job.state in ('error','cancelled','stopping') else TEAL
        self.job_title.configure(text=f'{job.name}  ·  {job.phase}' if job.state!='idle' else '준비됨',fg=color)
        elapsed=f'{job.elapsed//60:02d}:{job.elapsed%60:02d}'
        if job.total:self.job_numbers.configure(text=f'{job.current:,} / {job.total:,}{job.unit} 완료   {job.percent}%   ·   경과 {elapsed}')
        else:self.job_numbers.configure(text=f'경과 {elapsed}' if active else '')
        unknown=active and not job.total
        if unknown and not self._indeterminate:self.job_bar.configure(mode='indeterminate');self.job_bar.start(12);self._indeterminate=True
        elif not unknown:
            if self._indeterminate:self.job_bar.stop();self._indeterminate=False
            self.job_bar.configure(mode='determinate',value=job.percent or 0)
        self.job_detail.configure(text=(job.filename+'  |  ' if job.filename else '')+(job.detail or '교재를 등록하면 본문을 준비하고 다음 단계를 안내합니다.'))
        self.job_tail.configure(text=(self.status.get() or '현재 작업을 진행 중입니다. 다른 작업 버튼은 완료 후 사용할 수 있습니다.') if active else self.status.get())
        width=max(600,self.main.winfo_width()-90);self.job_detail.configure(wraplength=width,justify='left');self.job_tail.configure(wraplength=width,justify='left')
        self.stopbutton.configure(state='normal' if active and job.state=='running' else 'disabled',text='중단 대기 중' if job.state=='stopping' else '작업 중단')
        for b in self.task_controls:
            if b.winfo_exists():b.configure(state='disabled' if active else 'normal')
        if hasattr(self,'doclist'):self.doclist.configure(state='disabled' if active else 'readonly')
        if hasattr(self,'reocr_button') and not active:
            valid=bool(getattr(self,'docrows',[])) and Path(self.store.document(self.selected_doc())['original']).suffix.lower()=='.pdf'
            self.reocr_button.configure(state='normal' if valid else 'disabled')
        self.update_next_step()
    def setup_home(self):
        self.heading(self.home,'INSTRUCTOR WORKSPACE','수업의 시작, EMS QUIZ.','교재를 준비하고, 문제를 검토하고, 학생들과 함께 풀어보세요.')
        hero=tk.Frame(self.home,bg=DEEP,padx=25,pady=22);hero.pack(fill='x')
        tk.Label(hero,text='CLASSROOM QUIZ',bg=DEEP,fg='#a8cebe',font=('Segoe UI',9,'bold')).pack(anchor='w')
        tk.Label(hero,text='오늘의 수업,\n퀴즈로 시작해 볼까요?',bg=DEEP,fg=WHITE,font=('맑은 고딕',24,'bold'),justify='left').pack(anchor='w',pady=(8,8))
        tk.Label(hero,text='PDF·MD 교재를 한 번 등록하면, 저장된 본문으로 문제를 만들 수 있어요.',bg=DEEP,fg='#b0c9c0',font=('맑은 고딕',10)).pack(anchor='w')
        row=tk.Frame(hero,bg=DEEP);row.pack(fill='x',pady=(16,0))
        b=tk.Button(row,text='교재 등록하기  →',bg=WHITE,fg=DEEP,relief='flat',padx=17,pady=9,font=('맑은 고딕',10,'bold'),command=lambda:self.safe(self.import_doc));b.pack(side='left');self.task_controls.append(b)
        tk.Button(row,text='문제은행 열기  →',bg=DEEP,fg='#c3e2d2',activebackground=DEEP,activeforeground=WHITE,relief='flat',padx=20,pady=9,font=('맑은 고딕',10),command=lambda:self.navigate('bank')).pack(side='left')
        statrow=ttk.Frame(self.home);statrow.pack(fill='x',pady=16);self.stats={}
        for i,(key,title) in enumerate([('docs','등록된 교재'),('all','저장된 문제'),('draft','검토할 문제'),('approved','사용 가능한 문제')]):
            statrow.columnconfigure(i,weight=1);c=ttk.Frame(statrow,style='Card.TFrame',padding=(15,12));c.grid(row=0,column=i,sticky='nsew',padx=(0,10 if i<3 else 0))
            self.label(c,title,'CardMuted.TLabel');self.stats[key]=self.label(c,'0','CardTitle.TLabel',font=('맑은 고딕',22,'bold'))
        row=ttk.Frame(self.home);row.pack(fill='x',pady=(0,8));self.label(row,'다음 단계로 이어가세요.','TLabel',font=('맑은 고딕',13,'bold'))
        self.recent=ttk.Frame(self.home);self.recent.pack(fill='both',expand=True)
    def refresh_home(self):
        if not hasattr(self,'stats'):return
        qs=self.store.questions();docs=self.store.documents();values={'docs':len(docs),'all':len(qs),'draft':sum(not q['approved'] for q in qs),'approved':sum(q['approved'] for q in qs)}
        for k,v in values.items():self.stats[k].configure(text=str(v))
        for child in self.recent.winfo_children():child.destroy()
        if not docs:
            c=self.card(self.recent,fill='x');self.label(c,'아직 등록된 교재가 없습니다.','CardTitle.TLabel');self.label(c,'교재를 등록하면 본문 추출부터 챕터 설정까지 순서대로 안내합니다.','CardMuted.TLabel')
        for doc in docs[:2]:
            c=self.card(self.recent,fill='x',pady=(0,8));info=ttk.Frame(c,style='Card.TFrame');info.pack(side='left',fill='x',expand=True)
            self.label(info,doc['name'],'CardTitle.TLabel',wraplength=650)
            chapters=self.store.chapters(doc['id']);self.label(info,f'본문 준비 완료  ·  챕터 {len(chapters)}개  ·  '+('문제 만들기로 이어가세요.' if chapters else '출제할 챕터 범위를 설정하세요.'),'CardMuted.TLabel')
            self.action(c,'교재 열기  →',lambda id=doc['id']:self.open_document(id),side='right')
        self.after_idle(self.fit_scroll_pages)
    def fit_scroll_pages(self):
        for key,canvas in self.page_canvases.items():
            items=canvas.find_all()
            if items:
                canvas.itemconfigure(items[0],height=max(canvas.winfo_height(),getattr(self,key).winfo_reqheight()))
                canvas.configure(scrollregion=canvas.bbox('all'))
    def open_document(self,id):
        if self.working:return self.show_busy()
        for i,d in enumerate(self.docrows):
            if d['id']==id:self.doclist.current(i);self.show_doc();break
        self.navigate('docs')
    def setup_docs(self):
        self.heading(self.docs,'SOURCE LIBRARY','문제의 시작은, 좋은 자료.','등록한 본문은 자동 저장됩니다. 별도 MD 파일을 다시 올리지 않아도 됩니다.',('교재 추가 (PDF·MD)',self.import_doc,True))
        rail=ttk.Frame(self.docs);rail.pack(fill='x',pady=(0,12))
        for i,text in enumerate(['교재 등록','본문 확인','챕터 설정','문제 만들기']):
            rail.columnconfigure(i,weight=1);ttk.Label(rail,text=f'0{i+1}   {text}',background=PALE,foreground='#377963',padding=(12,9),font=('맑은 고딕',10,'bold')).grid(row=0,column=i,sticky='ew',padx=(0,6 if i<3 else 0))
        line=ttk.Frame(self.docs);line.pack(fill='x',pady=(0,8));self.doclist=ttk.Combobox(line,state='readonly');self.doclist.pack(side='left',fill='x',expand=True);self.doclist.bind('<<ComboboxSelected>>',lambda e:self.show_doc())
        self.action(line,'원본 열기',self.open_original,side='right')
        self.doc_summary=ttk.Label(self.docs,text='교재를 추가해 주세요.',style='Muted.TLabel',wraplength=1000);self.doc_summary.pack(anchor='w',pady=(0,10));self.docs.bind('<Configure>',lambda e:self.doc_summary.configure(wraplength=max(250,e.width-25)),add='+')
        pan=ttk.Panedwindow(self.docs,orient='horizontal');pan.pack(fill='both',expand=True)
        def size_pan(event):
            if event.width>400 and not getattr(pan,'initialized',False):
                pan.initialized=True;pan.sashpos(0,int(event.width*.57))
        pan.bind('<Configure>',size_pan)
        left=ttk.Frame(pan,style='Card.TFrame',padding=14);right=ttk.Frame(pan,style='Card.TFrame',padding=14);pan.add(left,weight=3);pan.add(right,weight=2)
        row=ttk.Frame(left,style='Card.TFrame');row.pack(fill='x');self.label(row,'추출한 본문','CardTitle.TLabel')
        pager=ttk.Frame(left,style='Card.TFrame');pager.pack(fill='x',pady=8);ttk.Label(pager,text='확인할 페이지',style='CardMuted.TLabel').pack(side='left')
        self.pagepick=ttk.Combobox(pager,state='readonly',width=14);self.pagepick.pack(side='right');self.pagepick.bind('<<ComboboxSelected>>',lambda e:self.show_page())
        self.body=ScrolledText(left,wrap='word',font=('맑은 고딕',10),bg=WHITE,fg=INK,relief='flat',borderwidth=0,spacing1=4,spacing3=6,state='disabled',height=9);self.body.pack(fill='both',expand=True)
        tools=ttk.Frame(left,style='Card.TFrame');tools.pack(fill='x',pady=(10,0))
        self.reocr_button=self.action(tools,'글자 다시 인식 (OCR)',self.reocr,lock=True)
        self.action(tools,'본문 파일 저장',self.export_md,lock=True)
        self.label(right,'챕터와 출제 범위','CardTitle.TLabel')
        self.label(right,'PDF 뷰어의 페이지 번호를 입력하세요.','CardMuted.TLabel')
        chapterbox=ttk.Frame(right,style='Card.TFrame');chapterbox.pack(fill='both',expand=True,pady=8)
        self.chapters=ttk.Treeview(chapterbox,columns=('title','range'),show='headings',height=3);self.chapters.heading('title',text='챕터');self.chapters.heading('range',text='PDF 페이지');self.chapters.column('title',width=150,stretch=True);self.chapters.column('range',width=85,stretch=False);self.chapters.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(chapterbox,orient='vertical',command=self.chapters.yview);scroll.pack(side='right',fill='y');self.chapters.configure(yscrollcommand=scroll.set)
        self.chapters.bind('<<TreeviewSelect>>',lambda e:self.update_next_step())
        self.ct=tk.StringVar();self.cs=tk.StringVar(value='1');self.ce=tk.StringVar(value='40')
        self.label(right,'새 챕터 제목','CardMuted.TLabel');self.chapter_entry=ttk.Entry(right,textvariable=self.ct);self.chapter_entry.pack(fill='x',pady=(3,7))
        bounds=ttk.Frame(right,style='Card.TFrame');bounds.pack(fill='x')
        for i,(title,var) in enumerate([('시작 페이지',self.cs),('끝 페이지',self.ce)]):
            bounds.columnconfigure(i,weight=1);f=ttk.Frame(bounds,style='Card.TFrame');f.grid(row=0,column=i,sticky='ew',padx=(0,8 if i==0 else 0));self.label(f,title,'CardMuted.TLabel');ttk.Entry(f,textvariable=var,width=7).pack(fill='x',pady=(3,5))
        self.chapter_add_button=self.action(right,'챕터 추가',self.add_chapter,lock=True)
        self.nextstep=ttk.Frame(self.docs);self.nextstep.pack(fill='x',pady=(0,12),before=pan);self.next_hint=ttk.Label(self.nextstep,text='다음 단계: 교재를 추가하세요.',foreground=TEAL,wraplength=700);self.next_hint.pack(side='left')
        self.generate_button=self.action(self.nextstep,'문제 만들기  →',self.generate_dialog,True,lock=True,side='right')
        self.nextstep.bind('<Configure>',lambda e:self.next_hint.configure(wraplength=max(180,e.width-200)))
    def update_next_step(self):
        if not hasattr(self,'next_hint'):return
        ready=bool(self.chapters.selection());hasdoc=bool(getattr(self,'docrows',[]))
        mapped=getattr(self,'has_page_mapping',False)
        self.next_hint.configure(text=('다음 단계: 선택한 챕터로 문제를 만드세요.' if ready else '다음 단계: 챕터 제목과 시작·끝 페이지를 입력하고 추가하세요.') if hasdoc else '다음 단계: PDF·MD 교재를 추가하세요.')
        if hasdoc and not mapped:self.next_hint.configure(text='이 MD에는 원본 페이지 정보가 없습니다. 챕터를 설정하려면 원본 PDF를 등록하세요.')
        self.generate_button.configure(state='normal' if ready and not self.working else 'disabled')
        self.chapter_add_button.configure(state='normal' if hasdoc and mapped and not self.working else 'disabled')
    def show_page(self):
        pages=getattr(self,'visible_pages',[]);i=self.pagepick.current()
        self.body.configure(state='normal');self.body.delete('1.0','end')
        if 0<=i<len(pages):
            p=pages[i];self.body.insert('1.0',p['text'] or '추출된 본문이 없습니다. 원본을 확인하거나 글자 다시 인식(OCR)을 실행하세요.')
        self.body.configure(state='disabled')
    def setup_bank(self):
        self.heading(self.bank,'QUESTION BANK','수업의 자산이 쌓이는 곳.','원문과 정답을 확인한 뒤 승인한 문제를 수업에 사용하세요.')
        bar=ttk.Frame(self.bank);bar.pack(fill='x',pady=(0,12))
        self.action(bar,'문제 가져오기 (JSON·MD)',self.import_bank,lock=True);self.action(bar,'직접 작성',lambda:self.editor(None),lock=True)
        self.action(bar,'선택 검토',self.edit_selected);self.action(bar,'선택 삭제',self.delete_selected,lock=True);self.action(bar,'JSON 저장',self.export_bank)
        filters=ttk.Frame(self.bank);filters.pack(fill='x',pady=(0,12));ttk.Label(filters,text='문제 검색',style='Muted.TLabel').pack(side='left',padx=(0,10));self.search=tk.StringVar();ttk.Entry(filters,textvariable=self.search).pack(side='left',fill='x',expand=True);self.search.trace_add('write',lambda *a:self.refresh_bank());self.onlydraft=tk.BooleanVar();ttk.Checkbutton(filters,text='검토 전만 보기',variable=self.onlydraft,command=self.refresh_bank).pack(side='right',padx=12)
        self.bank_count=ttk.Label(self.bank,text='',style='Muted.TLabel');self.bank_count.pack(anchor='w',pady=(0,8))
        frame=ttk.Frame(self.bank);frame.pack(fill='both',expand=True)
        self.qlist=ttk.Treeview(frame,columns=('state','topic','stem'),show='headings',selectmode='extended')
        for key,title,width in [('state','상태',80),('topic','챕터 / 주제',140),('stem','문제',550)]:self.qlist.heading(key,text=title);self.qlist.column(key,width=width,stretch=key=='stem')
        self.qlist.pack(side='left',fill='both',expand=True);scroll=ttk.Scrollbar(frame,orient='vertical',command=self.qlist.yview);scroll.pack(side='right',fill='y');self.qlist.configure(yscrollcommand=scroll.set);self.qlist.bind('<Double-1>',lambda e:self.safe(self.edit_selected))
        row=ttk.Frame(self.bank);row.pack(side='bottom',fill='x',pady=(10,0),before=frame);self.bank_quiz_button=self.action(row,'승인된 문제로 퀴즈 시작  →',self.start_quiz,True,side='right')
        self.heading(self.play,'CLASSROOM QUIZ','함께 풀며 배우는 시간.','검토를 마친 객관식 문제 중 최대 10개로 수업을 시작합니다.')
        row=ttk.Frame(self.play);row.pack(fill='x');self.action(row,'퀴즈 시작',self.start_quiz,True)
        self.quizframe=ttk.Frame(self.play,style='Card.TFrame',padding=20);self.quizframe.pack(fill='both',expand=True,pady=15)
    def setup_settings(self):
        self.heading(self.settings,'WORKSPACE GUIDE','연결하고, 바로 시작하세요.','AI 연결은 문제 생성에 사용합니다. 교재·문제은행·퀴즈는 이 PC에서 관리합니다.')
        c=self.card(self.settings,fill='x',pady=(0,14));self.label(c,'AI 자동 생성 연결','CardTitle.TLabel')
        self.label(c,'OpenAI API 키 · 현재 실행 중에만 보관합니다.','CardMuted.TLabel')
        self.apikey=tk.StringVar();self.model=tk.StringVar(value='gpt-5-mini');ttk.Entry(c,textvariable=self.apikey,show='•',width=60).pack(fill='x',pady=(7,12))
        self.label(c,'모델','CardMuted.TLabel');ttk.Entry(c,textvariable=self.model,width=35).pack(anchor='w',pady=(5,12))
        self.label(c,'ChatGPT 구독과 API 요금은 별도입니다. 선택한 챕터 본문만 API로 전송합니다.','CardMuted.TLabel',wraplength=900)
        row=ttk.Frame(c,style='Card.TFrame');row.pack(fill='x',pady=(12,0));self.action(row,'자료 관리로 돌아가기  →',lambda:self.navigate('docs'),True)
        c=self.card(self.settings,fill='x',pady=(0,14));self.label(c,'수업 준비 순서','CardTitle.TLabel')
        self.label(c,'1. 자료 관리에서 교재를 등록합니다. 필요한 페이지의 글자는 자동 인식합니다.\n2. 본문을 확인하고 챕터 제목·페이지 범위를 설정합니다.\n3. 챕터를 선택해 문제를 만들고, 문제은행에서 검토·승인합니다.\n4. 퀴즈를 실행합니다. MD 파일을 직접 변환하거나 다시 올릴 필요는 없습니다.','Card.TLabel',wraplength=900,justify='left')
        c=self.card(self.settings,fill='x');self.label(c,'자료 보관과 백업','CardTitle.TLabel');self.label(c,'본문 추출·OCR을 중단해도 완료한 페이지는 다음 실행에서 재사용합니다.\n표·그림·수식과 다단 편집은 원본과 비교해 확인하세요.','CardMuted.TLabel',wraplength=900)
        row=ttk.Frame(c,style='Card.TFrame');row.pack(fill='x',pady=(12,0));self.action(row,'전체 백업 ZIP 저장',self.backup,lock=True);self.action(row,'외부 AI용 출제 요청 저장',self.export_prompt,lock=True)

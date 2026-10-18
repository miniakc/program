import json, os, queue, random, shutil, sys, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core import Store, parse_md, parse_questions, uid
from pipeline import extract_pdf, generate, Cancelled

ROOT=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'EMSQuiz'

class App(tk.Tk):
    def __init__(self):
        super().__init__();self.title('EMS QUIZ · Windows 0.2');self.geometry('1180x780');self.minsize(950,650)
        self.store=Store(ROOT/'bank.sqlite3');self.events=queue.Queue();self.working=False;self.cancel=threading.Event()
        style=ttk.Style(self);style.theme_use('clam');style.configure('.',font=('맑은 고딕',11));style.configure('TButton',padding=8);style.configure('Treeview',rowheight=32)
        head=ttk.Frame(self,padding=18);head.pack(fill='x');ttk.Label(head,text='EMS QUIZ',font=('맑은 고딕',23,'bold')).pack(side='left');ttk.Label(head,text='교재 → 문제 검토 → 퀴즈 · PC 로컬 저장').pack(side='right')
        self.tabs=ttk.Notebook(self);self.tabs.pack(fill='both',expand=True,padx=18,pady=5)
        self.docs=ttk.Frame(self.tabs,padding=15);self.bank=ttk.Frame(self.tabs,padding=15);self.play=ttk.Frame(self.tabs,padding=15);self.settings=ttk.Frame(self.tabs,padding=15)
        for frame,title in [(self.docs,'교재 관리'),(self.bank,'검토함 · 문제은행'),(self.play,'퀴즈 실행'),(self.settings,'설정 · 백업')]:self.tabs.add(frame,text=title)
        self.status=tk.StringVar(value='준비됨 · 인터넷 연결 없이 교재와 문제은행을 관리합니다.');ttk.Label(self,textvariable=self.status,padding=12).pack(fill='x');ttk.Button(self,text='작업 중단 요청',command=lambda:self.cancel.set()).pack(anchor='e',padx=18)
        self.setup_docs();self.setup_bank();self.setup_settings();self.refresh();self.after(100,self.poll)
        self.protocol('WM_DELETE_WINDOW',self.close)
    def close(self):
        if self.working:
            messagebox.showinfo('처리 중','교재 작업이 완료된 후 종료해주세요.');return
        self.store.db.close();self.destroy()
    def safe(self,fn):
        try:return fn()
        except Exception as e:messagebox.showerror('확인 필요',str(e))
    def button(self,parent,text,fn):
        b=ttk.Button(parent,text=text,command=lambda:self.safe(fn));b.pack(side='left',padx=3);return b
    def setup_docs(self):
        bar=ttk.Frame(self.docs);bar.pack(fill='x');self.button(bar,'PDF / MD 등록',self.import_doc);self.button(bar,'선택 교재 전체 OCR',self.reocr);self.button(bar,'본문 MD 내보내기',self.export_md);self.button(bar,'출제 요청 내보내기',self.export_prompt);self.button(bar,'AI 문제 생성',self.generate_dialog)
        self.doclist=ttk.Combobox(self.docs,state='readonly');self.doclist.pack(fill='x',pady=12);self.doclist.bind('<<ComboboxSelected>>',lambda e:self.show_doc())
        pan=ttk.Panedwindow(self.docs,orient='horizontal');pan.pack(fill='both',expand=True)
        left=ttk.Frame(pan);right=ttk.Frame(pan,padding=10);pan.add(left,weight=3);pan.add(right,weight=2)
        self.body=tk.Text(left,wrap='word',font=('맑은 고딕',11));self.body.pack(fill='both',expand=True)
        ttk.Label(right,text='챕터 설정 · PDF 뷰어 페이지 기준',font=('맑은 고딕',12,'bold')).pack(anchor='w')
        self.chapters=ttk.Treeview(right,columns=('title','range'),show='headings',height=10);self.chapters.heading('title',text='챕터');self.chapters.heading('range',text='PDF 페이지');self.chapters.column('title',width=190);self.chapters.column('range',width=100);self.chapters.pack(fill='both',expand=True,pady=10)
        self.ct=tk.StringVar();self.cs=tk.StringVar(value='1');self.ce=tk.StringVar(value='40')
        for label,var in [('챕터 제목',self.ct),('시작 페이지',self.cs),('끝 페이지',self.ce)]:ttk.Label(right,text=label).pack(anchor='w');ttk.Entry(right,textvariable=var).pack(fill='x',pady=3)
        ttk.Button(right,text='챕터 추가',command=lambda:self.safe(self.add_chapter)).pack(fill='x',pady=10)
        ttk.Label(right,text='MD에 페이지 표시가 없으면 페이지를 추정하지 않습니다.\n형식: <!-- PDF_PAGE: 1 -->',wraplength=330).pack(anchor='w')
    def selected_doc(self):
        i=self.doclist.current()
        if i<0:raise ValueError('교재를 먼저 선택하세요.')
        return self.docrows[i]['id']
    def selected_chapter(self):
        ids=self.chapters.selection()
        if not ids:raise ValueError('챕터를 선택하세요.')
        return next(c for c in self.store.chapters(self.selected_doc()) if c['id']==ids[0])
    def refresh(self):
        old=self.doclist.current();self.docrows=self.store.documents();self.doclist['values']=[r['name'] for r in self.docrows]
        if self.docrows:self.doclist.current(min(max(old,0),len(self.docrows)-1));self.show_doc()
        self.refresh_bank()
    def show_doc(self):
        d=self.store.document(self.selected_doc());self.body.delete('1.0','end');self.body.insert('1.0','\n\n'.join(f"[PDF {p['page'] if p['page'] else '페이지 미상'}쪽]\n{p['text']}" for p in d['pages']))
        self.chapters.delete(*self.chapters.get_children())
        for c in self.store.chapters(d['id']):self.chapters.insert('', 'end',iid=c['id'],values=(c['title'],f"{c['start']}–{c['end']}"))
    def add_chapter(self):self.store.add_chapter(self.selected_doc(),self.ct.get(),int(self.cs.get()),int(self.ce.get()));self.show_doc()
    def import_doc(self):
        if self.working:raise ValueError('현재 교재 작업이 완료된 후 등록하세요.')
        path=filedialog.askopenfilename(filetypes=[('교재','*.pdf *.md')])
        if not path:return
        self.working=True;self.cancel.clear();self.status.set('교재 읽는 중…')
        def run():
            try:
                p=Path(path);raw=p.read_bytes()
                if p.suffix.lower()=='.md':pages=parse_md(raw.decode('utf-8-sig'))
                else:
                    pages=extract_pdf(p,ROOT/'jobs'/'extract',self.cancel,lambda msg:self.events.put(('status',msg)))
                if not pages:raise ValueError('페이지가 없습니다.')
                self.events.put(('doc',(p.name,raw,pages,path)))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=run,daemon=True).start()
    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if kind=='status':self.status.set(data)
                elif kind=='error':self.working=False;self.status.set('작업 실패');messagebox.showerror('등록 실패',data)
                elif kind=='generated':
                    try:
                        qs,usage,doc,chapter=data
                        for q in qs:q.update(doc_id=doc,chapter_id=chapter)
                        n=self.store.import_questions(qs);self.refresh_bank();self.tabs.select(self.bank)
                        self.status.set(f'{n}문제 검토함 등록 · 입력 {usage.get("input_tokens",0)} / 출력 {usage.get("output_tokens",0)}토큰 (재사용 구간 포함)')
                        messagebox.showinfo('생성 완료',f'{n}문제를 검토 전 상태로 등록했습니다. 자료 부족 또는 중복 제외로 요청 수보다 적을 수 있습니다.')
                    except Exception as e:messagebox.showerror('문제 저장 실패',str(e))
                    finally:self.working=False
                elif kind=='reocr':
                    try:
                        doc,pages=data;self.store.update_pages(doc,pages);self.show_doc();self.refresh_bank();self.status.set('OCR 완료 · 연결된 문제는 근거 재검토 대상으로 변경했습니다.')
                    except Exception as e:messagebox.showerror('OCR 저장 실패',str(e))
                    finally:self.working=False
                elif kind=='doc':
                    try:
                        name,raw,pages,path=data
                        # Keep the original in a content-addressed location; never replace the user's file.
                        import hashlib
                        original=ROOT/'originals'/(hashlib.sha256(raw).hexdigest()+Path(name).suffix.lower());original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(raw)
                        _,added=self.store.add_document(name,raw,pages,str(original));self.refresh()
                        blank=sum(not p['text'].strip() for p in pages)
                        self.status.set('교재 등록 완료' if added else '이미 등록된 교재입니다.')
                        if blank:messagebox.showinfo('본문 확인 필요',f'{blank}쪽의 본문이 비어 있습니다. 원본을 확인하세요. 텍스트가 잘못 추출되었으면 선택 교재 전체 OCR을 실행할 수 있습니다.')
                    except Exception as e:messagebox.showerror('저장 실패',str(e))
                    finally:self.working=False
        except queue.Empty:pass
        self.after(100,self.poll)
    def reocr(self):
        if self.working:raise ValueError('현재 작업이 완료된 후 실행하세요.')
        doc=self.selected_doc();d=self.store.document(doc);path=Path(d['original'])
        if path.suffix.lower()!='.pdf':raise ValueError('원본 PDF가 등록된 교재만 OCR할 수 있습니다.')
        if not path.exists():raise ValueError('원본 PDF 사본을 찾을 수 없습니다.')
        self.working=True;self.cancel.clear()
        def run():
            try:self.events.put(('reocr',(doc,extract_pdf(path,ROOT/'jobs'/'extract',self.cancel,lambda msg:self.events.put(('status',msg)),force=True))))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=run,daemon=True).start()
    def generate_dialog(self):
        if self.working:raise ValueError('현재 작업이 완료된 후 실행하세요.')
        doc=self.selected_doc();chapter=self.selected_chapter();d=self.store.document(doc)
        if not self.apikey.get().strip():self.tabs.select(self.settings);raise ValueError('설정에서 API 키를 입력하세요. 키는 현재 실행 중에만 보관합니다.')
        pages=[p for p in d['pages'] if p['page'] is not None and chapter['start']<=p['page']<=chapter['end']]
        if not any(p['text'].strip() for p in pages):raise ValueError('선택한 챕터에 본문이 없습니다.')
        win=tk.Toplevel(self);win.title('AI 문제 생성');win.geometry('560x310');win.transient(self);win.grab_set()
        ttk.Label(win,text=f"{d['name']}\n{chapter['title']} · PDF {chapter['start']}–{chapter['end']}쪽",wraplength=520,padding=15).pack(anchor='w')
        ttk.Label(win,text='선택한 본문을 OpenAI API로 전송합니다. API 이용료가 발생합니다.\n교재 안의 내용만으로 생성하며 최신 외부 지침 검색은 수행하지 않습니다.',wraplength=520,padding=15).pack(anchor='w')
        count=tk.StringVar(value='10');ttk.Label(win,text='최대 문항 수 (1–100)').pack();ttk.Spinbox(win,from_=1,to=100,textvariable=count,width=8).pack()
        def start():
            n=int(count.get())
            if not 1<=n<=100:raise ValueError('문항 수는 1~100개입니다.')
            key=self.apikey.get().strip();model=self.model.get().strip();win.destroy();self.working=True;self.cancel.clear()
            def run():
                try:
                    qs,usage=generate(pages,n,model,key,chapter['title'],d['name'],ROOT/'jobs'/'generate',self.cancel,lambda msg:self.events.put(('status',msg)))
                    self.events.put(('generated',(qs,usage,doc,chapter['id'])))
                except Exception as e:self.events.put(('error',str(e)))
            threading.Thread(target=run,daemon=True).start()
        ttk.Button(win,text='원문 전송·문제 생성',command=lambda:self.safe(start)).pack(pady=15)
    def export_md(self):
        d=self.store.document(self.selected_doc());path=filedialog.asksaveasfilename(defaultextension='.md',initialfile=Path(d['name']).stem+'.md')
        if path:Path(path).write_text('\n\n'.join((f"<!-- PDF_PAGE: {p['page']} -->\n\n" if p['page'] else '')+p['text'] for p in d['pages']),encoding='utf-8');self.status.set('MD 내보내기 완료')
    def export_prompt(self):
        prompt=self.store.prompt(self.selected_doc(),self.selected_chapter());path=filedialog.asksaveasfilename(defaultextension='.md',initialfile='문제생성_요청.md')
        if path:Path(path).write_text(prompt,encoding='utf-8');self.status.set('출제 요청 저장 완료 · 외부 AI에서 생성한 JSON을 가져오세요.')
    def setup_bank(self):
        bar=ttk.Frame(self.bank);bar.pack(fill='x')
        for text,fn in [('JSON / MD 문제 가져오기',self.import_bank),('직접 작성',lambda:self.editor(None)),('선택 검토',self.edit_selected),('선택 삭제',self.delete_selected),('JSON 내보내기',self.export_bank)]:self.button(bar,text,fn)
        filters=ttk.Frame(self.bank);filters.pack(fill='x',pady=10);self.search=tk.StringVar();ttk.Label(filters,text='검색').pack(side='left');ttk.Entry(filters,textvariable=self.search).pack(side='left',fill='x',expand=True);self.search.trace_add('write',lambda *a:self.refresh_bank());self.onlydraft=tk.BooleanVar();ttk.Checkbutton(filters,text='검토 전만',variable=self.onlydraft,command=self.refresh_bank).pack(side='right')
        self.qlist=ttk.Treeview(self.bank,columns=('state','topic','stem'),show='headings',selectmode='extended')
        for key,title,width in [('state','상태',90),('topic','챕터 / 주제',150),('stem','문제',650)]:self.qlist.heading(key,text=title);self.qlist.column(key,width=width)
        self.qlist.pack(fill='both',expand=True);self.qlist.bind('<Double-1>',lambda e:self.safe(self.edit_selected))
        ttk.Label(self.bank,text='가져온 문제는 검토 전으로 저장됩니다. MD는 JSON 코드 블록 형식을 지원합니다.').pack(anchor='w',pady=10)
        self.button(self.play,'승인된 문제로 퀴즈 시작',self.start_quiz)
        self.quizframe=ttk.Frame(self.play,padding=20);self.quizframe.pack(fill='both',expand=True)
    def refresh_bank(self):
        if not hasattr(self,'qlist'):return
        self.qlist.delete(*self.qlist.get_children());self.qrows=self.store.questions()
        for q in self.qrows:
            if self.onlydraft.get() and q['approved']:continue
            if self.search.get().casefold() not in (q['stem']+' '+q.get('topic','')+' '+q['concept']).casefold():continue
            self.qlist.insert('','end',iid=q['id'],values=('승인' if q['approved'] else '검토 전',q.get('topic',''),q['stem']))
    def import_bank(self):
        path=filedialog.askopenfilename(filetypes=[('문제 파일','*.json *.md')])
        if not path:return
        qs=parse_questions(Path(path).read_text(encoding='utf-8-sig'))
        if self.docrows and messagebox.askyesno('근거 연결','교재 관리에서 현재 선택한 교재·챕터를 근거로 연결할까요?'):
            doc=self.selected_doc();chapter=self.selected_chapter()
            for q in qs:q.update(doc_id=doc,chapter_id=chapter['id'])
        n=self.store.import_questions(qs);self.refresh_bank();self.status.set(f'{n}문제 등록 · {len(qs)-n}개 동일 지문 제외')
    def edit_selected(self):
        ids=self.qlist.selection()
        if len(ids)!=1:raise ValueError('검토할 문제 하나를 선택하세요.')
        self.editor(next(q for q in self.qrows if q['id']==ids[0]))
    def delete_selected(self):
        ids=self.qlist.selection()
        if not ids:raise ValueError('삭제할 문제를 선택하세요.')
        if messagebox.askyesno('선택 삭제',f'{len(ids)}개 문제를 삭제할까요?'):self.store.delete(ids);self.refresh_bank()
    def export_bank(self):
        ids=self.qlist.selection();qs=[q for q in self.qrows if not ids or q['id'] in ids]
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='EMS_문제은행.json')
        if path:Path(path).write_text(json.dumps({'questions':qs},ensure_ascii=False,indent=2),encoding='utf-8')
    def editor(self,question):
        q=dict(question or {'id':uid(),'stem':'','concept':'','topic':'','options':['']*4,'correct':0,'explanation':'','approved':False})
        win=tk.Toplevel(self);win.title('문제 검토·수정');win.geometry('1000x700');win.transient(self);win.grab_set()
        panes=ttk.Panedwindow(win,orient='horizontal');panes.pack(fill='both',expand=True,padx=15,pady=15);left=ttk.Frame(panes);right=ttk.Frame(panes);panes.add(left,weight=1);panes.add(right,weight=1)
        ttk.Label(left,text='근거 원문',font=('맑은 고딕',14,'bold')).pack(anchor='w');evidence=tk.Text(left,wrap='word');evidence.pack(fill='both',expand=True)
        text=self.store.evidence(q)
        if q.get('doc_id'):
            d=self.store.document(q['doc_id']);p=next((p for p in d['pages'] if p['page']==q.get('page')),None)
            text+=f"\n\n교재: {d['name']}\nPDF {q.get('page','미상')}쪽\n\n"+(p['text'] if p else '')
        evidence.insert('1.0',text);evidence.configure(state='disabled')
        fields={}
        for key,label in [('topic','챕터 / 주제'),('concept','학습목표'),('stem','문제')]:
            ttk.Label(right,text=label).pack(anchor='w');v=tk.StringVar(value=q.get(key,''));fields[key]=v;ttk.Entry(right,textvariable=v).pack(fill='x',pady=3)
        answer=tk.IntVar(value=q['correct']);options=[]
        for i,opt in enumerate(q['options']):
            row=ttk.Frame(right);row.pack(fill='x',pady=3);ttk.Radiobutton(row,text=str(i+1),variable=answer,value=i).pack(side='left');v=tk.StringVar(value=opt);options.append(v);ttk.Entry(row,textvariable=v).pack(fill='x',expand=True)
        ttk.Label(right,text='정답·오답 해설').pack(anchor='w');ex=tk.Text(right,height=8,wrap='word');ex.insert('1.0',q['explanation']);ex.pack(fill='both',expand=True)
        approved=tk.BooleanVar(value=q['approved']);ttk.Checkbutton(right,text='정답·해설·원문을 검토했고 퀴즈 사용을 승인합니다.',variable=approved).pack(pady=10)
        def save():
            q.update({k:v.get() for k,v in fields.items()});q.update(options=[v.get() for v in options],correct=answer.get(),explanation=ex.get('1.0','end').strip(),approved=approved.get(),type='객관식');self.store.put(q);self.refresh_bank();win.destroy()
        ttk.Button(right,text='저장',command=lambda:self.safe(save)).pack(fill='x')
    def start_quiz(self):
        qs=[q for q in self.store.questions() if q['approved']]
        if not qs:raise ValueError('승인된 문제가 없습니다. 문제를 검토한 뒤 승인하세요.')
        random.shuffle(qs);self.quiz=qs[:10];self.index=0;self.tabs.select(self.play);self.render_quiz()
    def render_quiz(self):
        for w in self.quizframe.winfo_children():w.destroy()
        q=self.quiz[self.index];ttk.Label(self.quizframe,text=f'문제 {self.index+1} / {len(self.quiz)} · {q.get("topic","")}',font=('맑은 고딕',14)).pack(anchor='w',pady=10)
        ttk.Label(self.quizframe,text=q['stem'],font=('맑은 고딕',21,'bold'),wraplength=1000).pack(anchor='w',pady=15)
        choice=tk.IntVar(value=-1)
        for i,o in enumerate(q['options']):ttk.Radiobutton(self.quizframe,text=f'{i+1}. {o}',variable=choice,value=i).pack(anchor='w',pady=10)
        result=ttk.Label(self.quizframe,text='',wraplength=1000);result.pack(fill='x',pady=20)
        ttk.Button(self.quizframe,text='정답·해설 보기',command=lambda:result.configure(text=f"정답: {q['correct']+1}번\n\n{q['explanation']}" )).pack(anchor='w')
        def nxt():
            if self.index+1==len(self.quiz):messagebox.showinfo('퀴즈 완료','모든 문제를 확인했습니다.');return
            self.index+=1;self.render_quiz()
        ttk.Button(self.quizframe,text='다음 문제',command=nxt).pack(anchor='e',pady=10)
    def setup_settings(self):
        ttk.Label(self.settings,text='EMS QUIZ · Windows 0.2',font=('맑은 고딕',18,'bold')).pack(anchor='w',pady=15)
        ttk.Label(self.settings,text='교재·문제은행·OCR은 PC에서 처리합니다. AI 생성은 OpenAI API 연결이 필요합니다.\nOCR 엔진과 한국어·영어 데이터는 설치 파일에 포함합니다. Marker는 사용하지 않습니다.\n키는 디스크에 저장하지 않고 프로그램을 닫으면 지워집니다.',wraplength=1000).pack(anchor='w',pady=10)
        self.apikey=tk.StringVar();self.model=tk.StringVar(value='gpt-5-mini')
        ttk.Label(self.settings,text='OpenAI API 키 (ChatGPT 구독과 별도)').pack(anchor='w');ttk.Entry(self.settings,textvariable=self.apikey,show='•',width=75).pack(anchor='w',pady=5)
        ttk.Label(self.settings,text='모델 ID (계정에서 사용 가능한 Structured Outputs 지원 모델)').pack(anchor='w');ttk.Entry(self.settings,textvariable=self.model,width=40).pack(anchor='w',pady=5)
        ttk.Label(self.settings,text='사용 흐름: 교재 등록 → 챕터 설정·선택 → AI 문제 생성 → 원문 검토·승인 → 퀴즈 실행.\n선택 범위를 작은 구간으로 나눠 요청합니다. 완료 구간은 같은 설정으로 재실행할 때 재사용합니다.\n중단은 OCR 처리 중 또는 다음 AI 요청 전 반영됩니다. 진행 중인 AI 응답은 최대 180초 기다릴 수 있습니다.\n표·수식·그림·다단 배치의 완전한 복원은 지원하지 않습니다. 생성된 문제는 직접 검토하세요.',wraplength=1000).pack(anchor='w',pady=20)
        ttk.Button(self.settings,text='전체 백업 ZIP 저장',command=lambda:self.safe(self.backup)).pack(anchor='w',pady=10)
    def backup(self):
        if self.working:raise ValueError('교재 등록 완료 후 백업하세요.')
        path=filedialog.asksaveasfilename(defaultextension='.zip',initialfile='EMSQuiz_전체백업.zip')
        if not path:return
        import tempfile,zipfile
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'bank.sqlite3';self.store.backup(db)
            with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                z.write(db,'bank.sqlite3')
                for p in (ROOT/'originals').glob('*'):z.write(p,'originals/'+p.name)
        self.status.set('전체 백업 완료')

def self_test(report):
    global ROOT
    import tempfile
    from pypdf import PdfReader, PdfWriter
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);pdf=root/'sample.pdf';writer=PdfWriter();writer.add_blank_page(width=100,height=100)
        with pdf.open('wb') as f:writer.write(f)
        assert len(PdfReader(pdf).pages)==1
        import pypdfium2 as pdfium
        document=pdfium.PdfDocument(pdf);page=document[0];bitmap=page.render(scale=1);assert bitmap.width>0;bitmap.close();page.close();document.close()
        from PIL import Image, ImageDraw, ImageFont
        from pipeline import ocr_image
        image=Image.new('RGB',(1200,250),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',64)
        draw.text((30,70),'EMS QUIZ 12345',font=font,fill='black');image.save(root/'ocr.png')
        recognized=ocr_image(root/'ocr.png',root/'result',threading.Event())
        assert '12345' in recognized, recognized
        db=Store(root/'bank.sqlite3');assert db.questions()==[];db.db.close()
        # Start and destroy a real Tk window to verify Tcl/Tk resources in the bundle.
        ROOT=root/'app-data'
        window=App();window.withdraw();window.update()
        doc,_=window.store.add_document('Example.pdf',b'example',[{'page':1,'text':'Example source for the UI test.'}])
        window.store.add_chapter(doc,'Example',1,1)
        q={'id':uid(),'type':'객관식','topic':'Example','concept':'Example objective','stem':'Example question?','options':['A','B','C','D'],'correct':0,'explanation':'Example explanation.','approved':True}
        window.store.put(q);window.refresh();window.start_quiz();window.update();window.editor(q);window.update();window.store.db.close();window.destroy()
    Path(report).write_text(json.dumps({'ok':True,'python':sys.version,'frozen':bool(getattr(sys,'frozen',False))}),encoding='utf-8')

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--self-test':self_test(sys.argv[2])
    else:App().mainloop()


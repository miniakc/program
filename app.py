import json, os, queue, random, shutil, sys, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core import Store, parse_md, parse_questions, uid
from pipeline import extract_pdf, generate, Cancelled, validate_api_key
from desktop_ui import WorkspaceUI
from task_state import TaskState

ROOT=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'EMSQuiz'

class App(WorkspaceUI, tk.Tk):
    def __init__(self):
        super().__init__();self.title('EMS QUIZ · Windows 0.3.1')
        width=max(980,min(1320,self.winfo_screenwidth()-40));height=max(680,min(890,self.winfo_screenheight()-70));self.geometry(f'{width}x{height}');self.minsize(980,680)
        self.store=Store(ROOT/'bank.sqlite3');self.events=queue.Queue();self.working=False;self.cancel=threading.Event();self.task=TaskState()
        self.configure_style();self.setup_shell();self.setup_home();self.setup_docs();self.setup_bank();self.setup_settings();self.refresh();self.navigate('home');self.draw_task();self.after(100,self.poll)
        self.protocol('WM_DELETE_WINDOW',self.close)
    def begin_task(self,name,filename=''):
        if self.working:self.show_busy();return False
        self.working=True;self.cancel.clear();self.status.set('');self.task.begin(name,filename);self.draw_task();self.update_idletasks();return True
    def finish_task(self,detail):
        self.working=False;self.task.finish(detail);self.status.set('')
        self.status.set('다음 단계: 자료 관리에서 챕터를 설정하고 문제를 만드세요.' if self.task.name in ('교재 등록','글자 다시 인식') else '문제은행에서 정답·해설을 검토하고 승인하세요.')
        self.draw_task();self.update_next_step()
    def show_busy(self):
        self.status.set(f'진행 중인 작업: {self.task.name} · {self.task.filename} · {self.task.phase}. 아래 진행 상태를 확인하세요.');self.draw_task()
    def stop_task(self):
        if self.working:self.cancel.set();self.task.stop();self.draw_task()
    def close(self):
        if self.working:
            self.show_busy();self.status.set('종료하려면 아래 작업 중단 버튼을 누르고 중단 완료 후 닫아주세요.');self.draw_task();return
        self.store.db.close();self.destroy()
    def safe(self,fn):
        try:return fn()
        except Exception as e:messagebox.showerror('확인 필요',str(e))
    def button(self,parent,text,fn):
        b=ttk.Button(parent,text=text,command=lambda:self.safe(fn));b.pack(side='left',padx=3);return b
    def selected_doc(self):
        i=self.doclist.current()
        if i<0:raise ValueError('교재를 먼저 선택하세요.')
        return self.docrows[i]['id']
    def selected_chapter(self):
        ids=self.chapters.selection()
        if not ids:raise ValueError('챕터를 선택하세요.')
        return next(c for c in self.store.chapters(self.selected_doc()) if c['id']==ids[0])
    def refresh(self,select_doc=None):
        old=self.doclist.current();prior=self.docrows[old]['id'] if hasattr(self,'docrows') and 0<=old<len(self.docrows) else None
        self.docrows=self.store.documents();self.doclist['values']=[r['name'] for r in self.docrows]
        if self.docrows:
            target=select_doc or prior;index=next((i for i,d in enumerate(self.docrows) if d['id']==target),0);self.doclist.current(index);self.show_doc()
        self.refresh_bank();self.refresh_home();self.update_next_step()
    def show_doc(self):
        d=self.store.document(self.selected_doc());self.visible_pages=d['pages'];self.has_page_mapping=all(p['page'] is not None for p in d['pages']);self.pagepick['values']=[f"PDF {p['page']}쪽" if p['page'] is not None else f'본문 {i+1} (페이지 정보 없음)' for i,p in enumerate(d['pages'])]
        if d['pages']:self.pagepick.current(0)
        self.show_page();blank=sum(not p['text'].strip() for p in d['pages']);ocr=sum(p.get('method')=='ocr' for p in d['pages'])
        self.doc_summary.configure(text=f"본문 {len(d['pages'])}쪽 저장됨 · OCR 인식 {ocr}쪽 · 빈 본문 {blank}쪽. 본문을 확인하고 오른쪽에서 챕터를 설정하세요.")
        selected=self.chapters.selection();self.chapters.delete(*self.chapters.get_children())
        for c in self.store.chapters(d['id']):self.chapters.insert('', 'end',iid=c['id'],values=(c['title'],f"{c['start']}–{c['end']}"))
        ids=self.chapters.get_children()
        if ids:self.chapters.selection_set(selected[0] if selected and selected[0] in ids else ids[0])
        if not self.ct.get() and not ids:
            nums=[p['page'] for p in d['pages'] if p['page'] is not None]
            self.cs.set(str(min(nums) if nums else 1));self.ce.set(str(max(nums) if nums else 1))
        self.update_next_step();self.draw_task()
    def add_chapter(self):
        if self.working:return self.show_busy()
        doc=self.selected_doc();title=self.ct.get();start=int(self.cs.get());end=int(self.ce.get())
        self.store.add_chapter(doc,title,start,end);self.ct.set('');self.show_doc()
        c=next(c for c in self.store.chapters(doc) if c['title']==title.strip() and c['start']==start and c['end']==end)
        self.chapters.selection_set(c['id']);self.update_next_step();self.refresh_home();self.status.set('챕터를 추가했습니다. 오른쪽 아래 문제 만들기로 이어가세요.');self.draw_task()
    def open_original(self):
        d=self.store.document(self.selected_doc());path=Path(d['original'])
        if not path.is_file():raise ValueError('원본 파일을 찾을 수 없습니다.')
        if sys.platform=='win32':os.startfile(str(path))
        else:raise ValueError('원본 열기는 Windows 설치 버전에서 사용할 수 있습니다.')
    def import_doc(self):
        if self.working:return self.show_busy()
        path=filedialog.askopenfilename(filetypes=[('교재','*.pdf *.md')])
        if not path:return
        self.navigate('docs')
        if not self.begin_task('교재 등록',Path(path).name):return
        def run():
            try:
                p=Path(path);raw=p.read_bytes()
                if p.suffix.lower()=='.md':
                    self.events.put(('status',{'phase':'Markdown 본문 읽기','detail':'페이지 정보와 본문을 확인하고 있습니다.'}))
                    pages=parse_md(raw.decode('utf-8-sig'));self.events.put(('status',{'phase':'본문 준비 완료','current':len(pages),'total':len(pages),'unit':'쪽','detail':'등록한 본문을 프로그램에 저장합니다.'}))
                else:pages=extract_pdf(p,ROOT/'jobs'/'extract',self.cancel,lambda msg:self.events.put(('status',msg)))
                if not pages:raise ValueError('페이지가 없습니다.')
                if self.cancel.is_set():raise Cancelled('교재 등록을 중단했습니다. 완료한 PDF 페이지는 다시 등록할 때 재사용합니다.')
                self.events.put(('doc',(p.name,raw,pages,path)))
            except Cancelled as e:self.events.put(('cancelled',str(e)))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=run,daemon=True).start()
    def handle_event(self,kind,data):
        if kind=='status':self.task.update(data)
        elif kind in ('error','cancelled'):
            self.working=False;self.task.end(kind,data);self.status.set('완료 구간은 저장되어 있습니다. 같은 작업을 다시 실행하면 재사용합니다.' if kind=='cancelled' else '아래 오류 내용을 확인한 뒤 같은 작업을 다시 실행할 수 있습니다.')
            if kind=='error':messagebox.showerror(self.task.name+' 실패',data)
        elif kind=='generated':
            qs,usage,doc,chapter=data
            for q in qs:q.update(doc_id=doc,chapter_id=chapter,source=self.store.document(doc)['name'])
            n=self.store.import_questions(qs);self.refresh_bank();self.refresh_home();self.navigate('bank')
            self.finish_task(f'{n}문제를 검토함에 저장했습니다. 원문·정답·해설을 확인하고 승인하세요.');self.status.set(f'입력 {usage.get("input_tokens",0):,} / 출력 {usage.get("output_tokens",0):,}토큰 · 완료 구간 재사용 포함')
        elif kind=='reocr':
            doc,pages=data;self.store.update_pages(doc,pages);self.show_doc();self.refresh_bank();self.refresh_home()
            self.finish_task('인식한 본문을 저장했습니다. 연결된 문제는 근거 재검토 대상으로 변경했습니다.')
        elif kind=='doc':
            name,raw,pages,path=data
            self.task.update({'phase':'교재 저장','detail':'원본과 추출한 본문을 저장하고 있습니다.'});self.draw_task();self.update_idletasks()
            import hashlib
            original=ROOT/'originals'/(hashlib.sha256(raw).hexdigest()+Path(name).suffix.lower());original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(raw)
            id,added=self.store.add_document(name,raw,pages,str(original));self.refresh(select_doc=id);self.navigate('docs')
            blank=sum(not p['text'].strip() for p in pages)
            self.finish_task(('교재를 등록했습니다.' if added else '이미 등록된 교재를 열었습니다.')+' 본문은 자동 저장되며 MD를 다시 올릴 필요가 없습니다.')
            self.status.set(f'다음: 본문 확인 → 오른쪽 챕터 범위 설정 → 문제 만들기.{f" 빈 본문 {blank}쪽은 원본을 확인하세요." if blank else ""}')
        self.draw_task();self.update_next_step()
    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                try:self.handle_event(kind,data)
                except Exception as e:
                    self.working=False;self.task.end('error',str(e));self.draw_task();messagebox.showerror('처리 실패',str(e))
        except queue.Empty:pass
        self.draw_task();self.update_next_step();self.after(200,self.poll)
    def reocr(self):
        if self.working:return self.show_busy()
        doc=self.selected_doc();d=self.store.document(doc);path=Path(d['original'])
        if path.suffix.lower()!='.pdf':raise ValueError('원본 PDF가 등록된 교재만 OCR할 수 있습니다.')
        if not path.exists():raise ValueError('원본 PDF 사본을 찾을 수 없습니다.')
        if not self.begin_task('글자 다시 인식',d['name']):return
        def run():
            try:self.events.put(('reocr',(doc,extract_pdf(path,ROOT/'jobs'/'extract',self.cancel,lambda msg:self.events.put(('status',msg)),force=True))))
            except Cancelled as e:self.events.put(('cancelled',str(e)))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=run,daemon=True).start()
    def update_api_key_hint(self,*args):
        value=self.apikey.get()
        if not value.strip():
            self.key_feedback.set('발급받은 키 값을 붙여넣으세요. 키 이름·설명·ChatGPT 로그인 비밀번호를 넣는 칸이 아닙니다.')
            self.key_feedback_label.configure(foreground='#73878a');return
        try:validate_api_key(value)
        except ValueError as e:
            self.key_feedback.set(str(e));self.key_feedback_label.configure(foreground='#b35b4c')
        else:
            self.key_feedback.set('문자 입력 형식이 확인되었습니다. 실제 키의 유효성·사용 권한은 API 요청 시 확인합니다.')
            self.key_feedback_label.configure(foreground='#0c8476')
    def generate_dialog(self):
        if self.working:return self.show_busy()
        doc=self.selected_doc();chapter=self.selected_chapter();d=self.store.document(doc)
        try:validate_api_key(self.apikey.get())
        except ValueError as e:
            self.navigate('settings');self.update_api_key_hint();self.status.set(str(e));self.draw_task();self.key_entry.focus_set();return
        pages=[p for p in d['pages'] if p['page'] is not None and chapter['start']<=p['page']<=chapter['end']]
        if not any(p['text'].strip() for p in pages):raise ValueError('선택한 챕터에 본문이 없습니다.')
        win=tk.Toplevel(self);win.title('AI 문제 생성');win.geometry('560x310');win.transient(self);win.grab_set()
        ttk.Label(win,text=f"{d['name']}\n{chapter['title']} · PDF {chapter['start']}–{chapter['end']}쪽",wraplength=520,padding=15).pack(anchor='w')
        ttk.Label(win,text='선택한 본문을 OpenAI API로 전송합니다. API 이용료가 발생합니다.\n교재 안의 내용만으로 생성하며 최신 외부 지침 검색은 수행하지 않습니다.',wraplength=520,padding=15).pack(anchor='w')
        count=tk.StringVar(value='10');ttk.Label(win,text='최대 문항 수 (1–100)').pack();ttk.Spinbox(win,from_=1,to=100,textvariable=count,width=8).pack()
        def start():
            n=int(count.get())
            if not 1<=n<=100:raise ValueError('문항 수는 1~100개입니다.')
            key=validate_api_key(self.apikey.get());model=self.model.get().strip();win.destroy()
            if not self.begin_task('AI 문제 생성',d['name']+' · '+chapter['title']):return
            def run():
                try:
                    qs,usage=generate(pages,n,model,key,chapter['title'],d['name'],ROOT/'jobs'/'generate',self.cancel,lambda msg:self.events.put(('status',msg)))
                    self.events.put(('generated',(qs,usage,doc,chapter['id'])))
                except Cancelled as e:self.events.put(('cancelled',str(e)))
                except Exception as e:self.events.put(('error',str(e)))
            threading.Thread(target=run,daemon=True).start()
        ttk.Button(win,text='원문 전송·문제 생성',command=lambda:self.safe(start)).pack(pady=15)
    def export_md(self):
        d=self.store.document(self.selected_doc());path=filedialog.asksaveasfilename(defaultextension='.md',initialfile=Path(d['name']).stem+'.md')
        if path:Path(path).write_text('\n\n'.join((f"<!-- PDF_PAGE: {p['page']} -->\n\n" if p['page'] else '')+p['text'] for p in d['pages']),encoding='utf-8');self.status.set('MD 내보내기 완료')
    def export_prompt(self):
        prompt=self.store.prompt(self.selected_doc(),self.selected_chapter());path=filedialog.asksaveasfilename(defaultextension='.md',initialfile='문제생성_요청.md')
        if path:Path(path).write_text(prompt,encoding='utf-8');self.status.set('출제 요청 저장 완료 · 외부 AI에서 생성한 JSON을 가져오세요.')
    def refresh_bank(self):
        if not hasattr(self,'qlist'):return
        self.qlist.delete(*self.qlist.get_children());self.qrows=self.store.questions()
        for q in self.qrows:
            if self.onlydraft.get() and q['approved']:continue
            if self.search.get().casefold() not in (q['stem']+' '+q.get('topic','')+' '+q['concept']).casefold():continue
            self.qlist.insert('','end',iid=q['id'],values=('사용 가능' if q['approved'] else '검토 전',q.get('topic',''),q['stem']))
        if hasattr(self,'bank_count'):self.bank_count.configure(text=f'전체 {len(self.qrows)}문제 · 검색 결과 {len(self.qlist.get_children())}문제')
    def import_bank(self):
        path=filedialog.askopenfilename(filetypes=[('문제 파일','*.json *.md')])
        if not path:return
        qs=parse_questions(Path(path).read_text(encoding='utf-8-sig'))
        if self.docrows and messagebox.askyesno('근거 연결','교재 관리에서 현재 선택한 교재·챕터를 근거로 연결할까요?'):
            doc=self.selected_doc();chapter=self.selected_chapter()
            for q in qs:q.update(doc_id=doc,chapter_id=chapter['id'])
        n=self.store.import_questions(qs);self.refresh_bank();self.refresh_home();self.status.set(f'{n}문제 등록 · {len(qs)-n}개 동일 지문 제외')
    def edit_selected(self):
        ids=self.qlist.selection()
        if len(ids)!=1:raise ValueError('검토할 문제 하나를 선택하세요.')
        self.editor(next(q for q in self.qrows if q['id']==ids[0]))
    def delete_selected(self):
        ids=self.qlist.selection()
        if not ids:raise ValueError('삭제할 문제를 선택하세요.')
        if messagebox.askyesno('선택 삭제',f'{len(ids)}개 문제를 삭제할까요?'):self.store.delete(ids);self.refresh_bank();self.refresh_home()
    def export_bank(self):
        ids=self.qlist.selection();qs=[q for q in self.qrows if not ids or q['id'] in ids]
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='EMS_문제은행.json')
        if path:Path(path).write_text(json.dumps({'questions':qs},ensure_ascii=False,indent=2),encoding='utf-8')
    def editor(self,question):
        q=dict(question or {'id':uid(),'stem':'','concept':'','topic':'','options':['']*4,'correct':0,'explanation':'','approved':False})
        win=tk.Toplevel(self);win.title('문제 검토·수정');win.geometry('1000x700');win.transient(self);win.grab_set()
        panes=ttk.Panedwindow(win,orient='horizontal');panes.pack(fill='both',expand=True,padx=15,pady=15);left=ttk.Frame(panes);right=ttk.Frame(panes);panes.add(left,weight=1);panes.add(right,weight=1)
        ttk.Label(left,text='근거 원문',font=('맑은 고딕',14,'bold')).pack(anchor='w');evidence=tk.Text(left,wrap='word',bg='white',fg='#20343e',font=('맑은 고딕',10),relief='flat');evidence.pack(fill='both',expand=True)
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
        ttk.Label(right,text='정답·오답 해설').pack(anchor='w');ex=tk.Text(right,height=8,wrap='word',bg='white',fg='#20343e',font=('맑은 고딕',10),relief='flat');ex.insert('1.0',q['explanation']);ex.pack(fill='both',expand=True)
        approved=tk.BooleanVar(value=q['approved']);ttk.Checkbutton(right,text='정답·해설·원문을 검토했고 퀴즈 사용을 승인합니다.',variable=approved).pack(pady=10)
        def save():
            q.update({k:v.get() for k,v in fields.items()});q.update(options=[v.get() for v in options],correct=answer.get(),explanation=ex.get('1.0','end').strip(),approved=approved.get(),type='객관식');self.store.put(q);self.refresh_bank();self.refresh_home();win.destroy()
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
    def backup(self):
        if self.working:return self.show_busy()
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
        image=Image.new('RGB',(1200,350),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',64)
        draw.text((30,40),'EMS QUIZ 12345',font=font,fill='black')
        korean=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',64)
        draw.text((30,160),'응급의료 119',font=korean,fill='black');image.save(root/'ocr.png')
        recognized=ocr_image(root/'ocr.png',root/'result',threading.Event())
        assert '12345' in recognized and '응급' in recognized.replace(' ',''), recognized
        image.save(root/'scan.pdf','PDF',resolution=150)
        extracted=extract_pdf(root/'scan.pdf',root/'cache',threading.Event(),lambda msg:None,force=True)
        assert '12345' in extracted[0]['text'] and '응급' in extracted[0]['text'].replace(' ',''), extracted
        db=Store(root/'bank.sqlite3');assert db.questions()==[];db.db.close()
        # Start and destroy a real Tk window to verify Tcl/Tk resources in the bundle.
        ROOT=root/'app-data'
        window=App();window.withdraw();window.update()
        doc,_=window.store.add_document('Example.pdf',b'example',[{'page':1,'text':'Example source for the UI test.'}])
        window.store.add_chapter(doc,'Example',1,1)
        q={'id':uid(),'type':'객관식','topic':'Example','concept':'Example objective','stem':'Example question?','options':['A','B','C','D'],'correct':0,'explanation':'Example explanation.','approved':True}
        window.store.put(q);window.refresh();window.deiconify();window.geometry('+10+10');window.update()
        screenshots=Path(report).parent/'qa'/Path(report).stem;screenshots.mkdir(parents=True,exist_ok=True)
        def capture(name):
            from PIL import ImageGrab
            window.update_idletasks();window.update()
            x,y=window.winfo_rootx(),window.winfo_rooty();ImageGrab.grab(bbox=(x,y,x+window.winfo_width(),y+window.winfo_height())).save(screenshots/(name+'.png'))
        window.navigate('home');window.update();capture('dashboard')
        window.navigate('docs');window.update();capture('source-library')
        window.begin_task('글자 다시 인식','진행 상태 검사.pdf');window.handle_event('status',{'phase':'한국어·영어 글자 인식 (OCR)','current':10,'total':40,'unit':'쪽','detail':'PDF 11쪽 인식 중 · 현재 페이지 완료 후 진행률이 올라갑니다.'})
        assert '25%' in window.job_numbers.cget('text');assert '진행 상태 검사.pdf' in window.job_detail.cget('text')
        assert all(str(b.cget('state'))=='disabled' for b in window.task_controls)
        capture('ocr-progress');window.handle_event('cancelled','검사용 작업을 중단했습니다.')
        window.navigate('bank');window.update();capture('question-bank')
        window.start_quiz();window.update();capture('quiz');window.editor(q);window.update();window.store.db.close();window.destroy()
    Path(report).write_text(json.dumps({'ok':True,'python':sys.version,'frozen':bool(getattr(sys,'frozen',False)),'checks':['pdf_render','korean_english_ocr','scanned_pdf_to_text','database','gui','question_editor','quiz','sidebar_dashboard','visible_progress','busy_button_lock','completion_next_step']}),encoding='utf-8')

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--self-test':
        try:self_test(sys.argv[2])
        except Exception:
            import traceback
            Path(sys.argv[2]).write_text(json.dumps({'ok':False,'error':traceback.format_exc()}),encoding='utf-8')
            sys.exit(1)
    else:App().mainloop()


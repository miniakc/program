import json, os, queue, random, shutil, sys, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core import Store, parse_md, parse_questions, uid
from pipeline import extract_pdf, Cancelled
from exchange import AssetStore, QuizCountdown, PROMPT, markdown, export_bundle, export_xlsx, answer_text
from desktop_ui import WorkspaceUI
from task_state import TaskState
from review import SourceReview,category,status_label,SCOPE
from bank_workspace import BankWorkspace,UNLINKED,UNASSIGNED

ROOT=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'EMSQuiz'

class App(BankWorkspace, WorkspaceUI, tk.Tk):
    def __init__(self):
        super().__init__();self.title('EMS QUIZ · Windows 0.6.0')
        width=max(980,min(1320,self.winfo_screenwidth()-40));height=max(680,min(890,self.winfo_screenheight()-70));self.geometry(f'{width}x{height}');self.minsize(980,680)
        self.store=Store(ROOT/'bank.sqlite3');self.events=queue.Queue();self.working=False;self.cancel=threading.Event();self.task=TaskState()
        self.cleanup_pending();self.assets=AssetStore(ROOT/'assets');self.countdown=QuizCountdown();self.timer_job=None;self.reviewer=SourceReview(self.store,self.assets);self.reviewer.reconcile()
        self.configure_style();self.setup_shell();self.setup_home();self.setup_docs();self.setup_bank();self.setup_catalog();self.setup_settings();self.refresh();self.navigate('home');self.draw_task();self.after(100,self.poll)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<F11>',lambda e:self.toggle_fullscreen());self.bind('<Escape>',lambda e:self.attributes('-fullscreen',False))
        self.bind('<Left>',lambda e:self.quiz_key(e,-1));self.bind('<Right>',lambda e:self.quiz_key(e,1));self.bind('<space>',lambda e:self.quiz_key(e,0))
    def begin_task(self,name,filename=''):
        if self.working:self.show_busy();return False
        self.working=True;self.cancel.clear();self.status.set('');self.task.begin(name,filename);self.draw_task();self.update_idletasks();return True
    def finish_task(self,detail):
        self.working=False;self.task.finish(detail);self.status.set('')
        self.status.set('다음: MD·이미지 ZIP 저장 → GPT에서 출제 → JSON 가져오기 → 퀴즈 실행')
        self.draw_task();self.update_next_step()
    def show_busy(self):
        self.status.set(f'진행 중인 작업: {self.task.name} · {self.task.filename} · {self.task.phase}. 아래 진행 상태를 확인하세요.');self.draw_task()
    def stop_task(self):
        if self.working:self.cancel.set();self.task.stop();self.draw_task()
    def close(self):
        if self.working:
            self.show_busy();self.status.set('종료하려면 아래 작업 중단 버튼을 누르고 중단 완료 후 닫아주세요.');self.draw_task();return
        self.stop_countdown();self.store.db.close();self.destroy()
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
        else:
            self.doclist.set('');self.pagepick.set('');self.pagepick['values']=[];self.visible_pages=[];self.has_page_mapping=False;self.chapters.delete(*self.chapters.get_children());self.show_page();self.doc_summary.configure(text='교재를 추가해 주세요.');self.ct.set('')
        self.refresh_doc_cards();self.refresh_bank();self.refresh_home();self.refresh_catalog();self.update_next_step()
    def show_doc(self):
        d=self.store.document(self.selected_doc());self.visible_pages=d['pages'];self.has_page_mapping=all(p['page'] is not None for p in d['pages']);self.pagepick['values']=[f"PDF {p['page']}쪽" if p['page'] is not None else f'본문 {i+1} (페이지 정보 없음)' for i,p in enumerate(d['pages'])]
        if d['pages']:self.pagepick.current(0)
        self.show_page();blank=sum(not p['text'].strip() for p in d['pages']);ocr=sum(p.get('method')=='ocr' for p in d['pages'])
        self.doc_summary.configure(text=f"본문 {len(d['pages'])}쪽 저장됨 · OCR 인식 {ocr}쪽 · 빈 본문 {blank}쪽. 본문 확인 후 MD·이미지 ZIP을 저장하세요. 챕터 설정은 선택 사항입니다.")
        review=self.assets.review_pages(d['digest'])
        if review:self.doc_summary.configure(text=self.doc_summary.cget('text')+' 그림 영역 선택 필요: '+', '.join(map(str,review))+'쪽')
        selected=self.chapters.selection();self.chapters.delete(*self.chapters.get_children())
        for c in self.store.chapters(d['id']):self.chapters.insert('', 'end',iid=c['id'],values=(c['title'],f"{c['start']}–{c['end']}"))
        ids=self.chapters.get_children()
        if ids:self.chapters.selection_set(selected[0] if selected and selected[0] in ids else ids[0])
        if not self.ct.get() and not ids:
            nums=[p['page'] for p in d['pages'] if p['page'] is not None]
            self.cs.set(str(min(nums) if nums else 1));self.ce.set(str(max(nums) if nums else 1))
        self.refresh_doc_cards();self.update_next_step();self.draw_task()
    def add_chapter(self):
        if self.working:return self.show_busy()
        doc=self.selected_doc();title=self.ct.get();start=int(self.cs.get());end=int(self.ce.get())
        self.store.add_chapter(doc,title,start,end);self.reviewer.reconcile();self.refresh_bank();self.refresh_catalog();self.ct.set('');self.show_doc()
        c=next(c for c in self.store.chapters(doc) if c['title']==title.strip() and c['start']==start and c['end']==end)
        self.chapters.selection_set(c['id']);self.update_next_step();self.refresh_home();self.status.set('챕터를 추가했습니다. MD·이미지 ZIP을 저장하고 GPT에 출제 범위를 지정하세요.');self.draw_task()
    def open_original(self):
        d=self.store.document(self.selected_doc());path=Path(d['original'])
        if not path.is_file():raise ValueError('원본 파일을 찾을 수 없습니다.')
        if sys.platform=='win32':os.startfile(str(path))
        else:raise ValueError('원본 열기는 Windows 설치 버전에서 사용할 수 있습니다.')
    def cleanup_pending(self):
        registry=ROOT/'pending_delete.json'
        try:paths=json.loads(registry.read_text()) if registry.exists() else []
        except (OSError,ValueError):return
        used={d['original'] for d in self.store.documents()};remaining=[]
        for value in paths if isinstance(paths,list) else []:
            if not isinstance(value,str):continue
            p=Path(value)
            if p.parent.resolve()!=(ROOT/'originals').resolve() or value in used:continue
            try:
                if p.is_file():p.unlink()
            except OSError:remaining.append(value)
        if remaining:registry.write_text(json.dumps(remaining),encoding='utf-8')
        elif registry.exists():registry.unlink()
    def confirm_delete(self,title,text):return self.confirm_action(title,text,'교재 삭제')
    def confirm_action(self,title,text,action='확인'):
        result=[False];win=tk.Toplevel(self);win.title(title);win.geometry('510x270');win.transient(self);win.grab_set();win.configure(bg='#f6f8f8');win.resizable(False,False)
        body=ttk.Frame(win,padding=24);body.pack(fill='both',expand=True)
        ttk.Label(body,text=title,font=('맑은 고딕',18,'bold')).pack(anchor='w',pady=(0,16));ttk.Label(body,text=text,wraplength=450,justify='left').pack(anchor='w')
        row=ttk.Frame(body);row.pack(side='bottom',fill='x',pady=(15,0))
        def yes():result[0]=True;win.destroy()
        ttk.Button(row,text=action,style='Danger.TButton',command=yes).pack(side='right');ttk.Button(row,text='취소',command=win.destroy).pack(side='right',padx=8)
        self.wait_window(win);return result[0]
    def delete_doc(self,doc_id=None):
        if self.working:return self.show_busy()
        doc_id=doc_id or self.selected_doc();d=self.store.document(doc_id)
        if not self.confirm_delete('교재 삭제',d['name']+'\n\n등록된 교재·챕터·원본 사본을 삭제합니다. 이미 만든 문제는 유지하며, 문제에서 사용하는 그림도 보존합니다.'):return
        self.store.delete_document(doc_id)
        original=Path(d['original'])
        deferred=False
        if original.is_file() and original.parent.resolve()==(ROOT/'originals').resolve():
            try:original.unlink()
            except OSError:
                registry=ROOT/'pending_delete.json'
                try:pending=json.loads(registry.read_text()) if registry.exists() else []
                except (OSError,ValueError):pending=[]
                registry.write_text(json.dumps(list(dict.fromkeys(pending+[str(original)]))),encoding='utf-8');deferred=True
        used={name for q in self.store.questions() for name in q.get('images',[])}
        for path in self.assets.root.glob(d['digest'][:16]+'_*.png'):
            if path.name not in used:
                try:path.unlink()
                except OSError:pass
        for suffix in ('.json','.figures-v2.json','.regions.json'):
            path=self.assets.root/(d['digest']+suffix)
            if path.exists():path.unlink()
        for suffix in ('-auto','-ocr'):
            path=ROOT/'jobs'/'extract'/(d['digest']+suffix)
            if path.is_dir():shutil.rmtree(path,ignore_errors=True)
        self.refresh();self.status.set('교재를 삭제했습니다. 저장된 문제와 문제에서 사용하는 그림은 유지됩니다.'+(' 열려 있는 원본 사본은 PDF 창을 닫은 뒤 다음 실행 시 자동 정리합니다.' if deferred else ''));self.draw_task()
    def edit_figure_regions(self):
        if self.working:return self.show_busy()
        d=self.store.document(self.selected_doc());original=Path(d['original'])
        if original.suffix.lower()!='.pdf' or not original.is_file():raise ValueError('원본 PDF가 있는 교재를 선택하세요.')
        from figure_ui import FigureRegionEditor
        def saved(page,boxes):
            self.assets.set_regions(d['digest'],page,boxes)
            if not self.begin_task('그림 영역 반영',d['name']):return
            def run():
                try:
                    self.assets.extract(original,d['digest'],self.cancel,lambda msg:self.events.put(('status',msg)));self.events.put(('figures_saved',d['id']))
                except Cancelled as e:self.events.put(('cancelled',str(e)))
                except Exception as e:self.events.put(('error',str(e)))
            threading.Thread(target=run,daemon=True).start()
        win=FigureRegionEditor(self,original,self.assets,d['digest'],saved)
        self.figure_editor=win
    def start_topic(self,topic):
        self.search.set('');self.onlydraft.set(False)
        if hasattr(self,'topic_filter'):self.topic_filter.set('전체')
        self.refresh_bank();ids=[q['id'] for q in self.qrows if (q.get('topic') or '기타')==topic]
        if ids:self.qlist.selection_set(ids);self.start_quiz()
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
                if p.suffix.lower()=='.pdf':
                    import hashlib
                    self.assets.extract(p,hashlib.sha256(raw).hexdigest(),self.cancel,lambda msg:self.events.put(('status',msg)))
                self.events.put(('doc',(p.name,raw,pages,path)))
            except Cancelled as e:self.events.put(('cancelled',str(e)))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=run,daemon=True).start()
    def handle_event(self,kind,data):
        if kind=='status':self.task.update(data)
        elif kind in ('error','cancelled'):
            self.working=False;self.task.end(kind,data);self.status.set('완료 구간은 저장되어 있습니다. 같은 작업을 다시 실행하면 재사용합니다.' if kind=='cancelled' else '아래 오류 내용을 확인한 뒤 같은 작업을 다시 실행할 수 있습니다.')
            if kind=='error':messagebox.showerror(self.task.name+' 실패',data)
        elif kind=='figures_saved':
            self.finish_task('선택한 그림 영역을 저장했습니다. MD·이미지 ZIP을 다시 저장하면 반영됩니다.');self.show_doc()
        elif kind=='exported':
            review=self.assets.review_pages(self.store.document(self.selected_doc())['digest'])
            self.finish_task('MD·이미지 저장 완료'+(f' · 그림 영역 확인 필요 {len(review)}쪽' if review else ''));self.status.set('저장 위치: '+str(data)+' · '+('스캔 페이지 '+', '.join(map(str,review))+'쪽은 그림 확인·영역 선택에서 그림을 지정한 뒤 다시 저장하세요.' if review else 'MD와 필요한 그림을 GPT에 함께 첨부하고 완성된 JSON을 가져오세요.'))
        elif kind=='reocr':
            doc,pages=data;self.store.update_pages(doc,pages);self.reviewer.reconcile();self.show_doc();self.refresh_bank();self.refresh_home();self.refresh_catalog()
            self.finish_task('인식한 본문을 저장했습니다. 연결된 문제는 근거 재검토 대상으로 변경했습니다.')
        elif kind=='doc':
            name,raw,pages,path=data
            self.task.update({'phase':'교재 저장','detail':'원본과 추출한 본문을 저장하고 있습니다.'});self.draw_task();self.update_idletasks()
            import hashlib
            original=ROOT/'originals'/(hashlib.sha256(raw).hexdigest()+Path(name).suffix.lower());original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(raw)
            id,added=self.store.add_document(name,raw,pages,str(original));self.reviewer.reconcile();self.refresh(select_doc=id);self.navigate('docs')
            blank=sum(not p['text'].strip() for p in pages)
            self.finish_task(('교재를 등록했습니다.' if added else '이미 등록된 교재를 열었습니다.')+' MD·이미지 ZIP을 저장하여 GPT에 첨부하세요.')
            self.status.set(f'다음: MD·이미지 ZIP 저장 → 압축 해제 → MD와 필요한 이미지를 GPT에 첨부.{f" 빈 본문 {blank}쪽은 원본을 확인하세요." if blank else ""}')
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
    def export_md(self):self.export_material(md_only=True)
    def export_material(self,md_only=False):
        if self.working:return self.show_busy()
        d=self.store.document(self.selected_doc());d['chapters']=self.store.chapters(d['id']);suffix='.md' if md_only else '.zip'
        path=filedialog.asksaveasfilename(defaultextension=suffix,initialfile=Path(d['name']).stem+('_MD_이미지' if not md_only else '')+suffix,filetypes=[('Markdown' if md_only else '교재 자료 ZIP','*'+suffix)])
        if not path:return
        if not self.begin_task('MD·이미지 저장',d['name']):return
        def run():
            try:
                entries=self.assets.entries(d['digest']);original=Path(d['original'])
                if original.suffix.lower()=='.pdf':entries=self.assets.extract(original,d['digest'],self.cancel,lambda msg:self.events.put(('status',msg)))
                if self.cancel.is_set():raise Cancelled('자료 저장을 중단했습니다.')
                if md_only:
                    folder=Path(path).parent/'images';folder.mkdir(exist_ok=True)
                    for e in entries:
                        src=self.assets.resolve(e['id'])
                        if not src:raise ValueError('이미지 파일 없음: '+e['id'])
                        if src.resolve()!=(folder/e['id']).resolve():shutil.copy2(src,folder/e['id'])
                    Path(path).write_text(markdown(d,entries),encoding='utf-8')
                else:export_bundle(path,d,self.assets,entries)
                self.events.put(('exported',path))
            except Cancelled as e:self.events.put(('cancelled',str(e)))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=run,daemon=True).start()
    def export_prompt(self):
        path=filedialog.asksaveasfilename(defaultextension='.txt',initialfile='GPT_출제요청.txt')
        if path:Path(path).write_text(PROMPT,encoding='utf-8');self.status.set('출제 요청 저장 완료 · MD와 필요한 이미지를 함께 GPT에 첨부하세요.');self.draw_task()
    def import_assets(self):
        if self.working:return self.show_busy()
        path=filedialog.askopenfilename(filetypes=[('교재 자료 ZIP','*.zip')])
        if path:
            n=self.assets.import_zip(path);self.reviewer.reconcile();self.refresh_bank();self.refresh_home();self.refresh_catalog();self.status.set(f'이미지 {n}개 가져오기 완료. JSON의 파일명과 일치하면 문제에 표시됩니다.');self.draw_task()
    def selected_questions(self):
        ids=set(self.qlist.selection() or self.qlist.get_children())
        return [q for q in self.qrows if q['id'] in ids]
    def export_excel(self):
        qs=self.selected_questions()
        if not qs:raise ValueError('내보낼 문제가 없습니다.')
        path=filedialog.asksaveasfilename(defaultextension='.xlsx',initialfile='EMS_문제은행.xlsx',filetypes=[('Excel 통합 문서','*.xlsx')])
        if path:export_xlsx(path,qs,self.assets);self.status.set(f'{len(qs)}문제 Excel 저장 완료 · 그림 시트·이미지 파일명·출처 포함');self.draw_task()
    def edit_selected(self):
        ids=self.qlist.selection()
        if len(ids)!=1:raise ValueError('검토할 문제 하나를 선택하세요.')
        self.editor(next(q for q in self.qrows if q['id']==ids[0]))
    def export_bank(self):
        qs=self.selected_questions()
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='EMS_문제은행.json')
        if path:Path(path).write_text(json.dumps({'questions':qs},ensure_ascii=False,indent=2),encoding='utf-8')
    def editor(self,question):
        q=dict(question or {'id':uid(),'stem':'','concept':'','topic':'','options':['']*4,'correct':0,'explanation':'','approved':False})
        if not question and self.bank_doc_id not in (None,UNLINKED):
            q['doc_id']=self.bank_doc_id
            if self.bank_chapter_id not in (None,UNASSIGNED):q['chapter_id']=self.bank_chapter_id
        win=tk.Toplevel(self);win.title('문제 검토·수정');win.geometry('1000x700');win.transient(self);win.grab_set()
        panes=ttk.Panedwindow(win,orient='horizontal');panes.pack(fill='both',expand=True,padx=15,pady=15);left=ttk.Frame(panes);right=ttk.Frame(panes);panes.add(left,weight=1);panes.add(right,weight=1)
        right_host=right;canvas=tk.Canvas(right_host,bg='#f6f8f8',highlightthickness=0);scroll=ttk.Scrollbar(right_host,orient='vertical',command=canvas.yview);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        right=ttk.Frame(canvas);item=canvas.create_window((0,0),window=right,anchor='nw');canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));right.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        ttk.Label(left,text='근거 원문',font=('맑은 고딕',14,'bold')).pack(anchor='w');evidence=tk.Text(left,wrap='word',bg='white',fg='#20343e',font=('맑은 고딕',10),relief='flat');evidence.pack(fill='both',expand=True)
        report=q.get('review_report',{});text=status_label(q)+'\n'+SCOPE+'\n\n'+'\n'.join(('✓ ' if ok else '· ')+name for name,ok in report.get('checks',{}).items())+'\n'+'\n'.join(report.get('issues',[]))+'\n\n'+self.store.evidence(q)
        if q.get('doc_id'):
            d=self.store.document(q['doc_id']);p=next((p for p in d['pages'] if p['page']==q.get('page')),None)
            text+=f"\n\n교재: {d['name']}\nPDF {q.get('page','미상')}쪽\n\n"+(p['text'] if p else '')
        evidence.insert('1.0',text);evidence.configure(state='disabled')
        destination_label=tk.StringVar(value=self.question_location(q));ttk.Label(right,textvariable=destination_label,wraplength=420).pack(anchor='w',pady=5)
        def link():
            target=self.choose_destination(q.get('doc_id'),q.get('chapter_id'))
            if target is None:return
            doc,chapter=target;q.pop('doc_id',None);q.pop('chapter_id',None)
            if doc:q['doc_id']=doc
            if chapter:q['chapter_id']=chapter
            destination_label.set(self.question_location(q))
        ttk.Button(right,text='교재·챕터 연결 변경',command=lambda:self.safe(link)).pack(anchor='w')
        fields={}
        for key,label in [('topic','카테고리'),('concept','학습목표'),('stem','문제')]:
            ttk.Label(right,text=label).pack(anchor='w');v=tk.StringVar(value=category(q) if key=='topic' else q.get(key,''));fields[key]=v;ttk.Entry(right,textvariable=v).pack(fill='x',pady=3)
        kind=tk.StringVar(value=q.get('type','객관식'));ttk.Label(right,text='유형').pack(anchor='w');ttk.Combobox(right,textvariable=kind,values=['객관식','OX','단답형'],state='readonly').pack(fill='x')
        ttk.Label(right,text='객관식은 아래 선택지·정답 번호, OX·단답형은 정답 입력란을 사용합니다.',wraplength=440).pack(anchor='w')
        answer=tk.IntVar(value=q.get('correct',0));options=[]
        for i,opt in enumerate((q.get('options',[])+['']*4)[:4]):
            row=ttk.Frame(right);row.pack(fill='x',pady=3);ttk.Radiobutton(row,text=str(i+1),variable=answer,value=i).pack(side='left');v=tk.StringVar(value=opt);options.append(v);ttk.Entry(row,textvariable=v).pack(fill='x',expand=True)
        typed=tk.StringVar(value=q.get('answer',''));ttk.Label(right,text='OX(O 또는 X) · 단답형 정답').pack(anchor='w');ttk.Entry(right,textvariable=typed).pack(fill='x')
        images=list(q.get('images',[]));image_names=tk.StringVar(value=', '.join(images) or '첨부 이미지 없음')
        ttk.Label(left,textvariable=image_names,wraplength=420).pack(anchor='w')
        row=ttk.Frame(left);row.pack(fill='x')
        def attach():
            path=filedialog.askopenfilename(filetypes=[('이미지','*.png *.jpg *.jpeg')])
            if path:
                name=self.assets.attach(path)
                if name not in images:images.append(name)
                image_names.set(', '.join(images))
        ttk.Button(row,text='문제 그림 첨부',command=lambda:self.safe(attach)).pack(side='left')
        ttk.Button(row,text='그림 연결 모두 해제',command=lambda:(images.clear(),image_names.set('첨부 이미지 없음'))).pack(side='left')
        ttk.Label(right,text='정답·오답 해설').pack(anchor='w');ex=tk.Text(right,height=8,wrap='word',bg='white',fg='#20343e',font=('맑은 고딕',10),relief='flat');ex.insert('1.0',q['explanation']);ex.pack(fill='both',expand=True)
        ttk.Label(right,text='원본 PDF 페이지').pack(anchor='w');edit_page=tk.StringVar(value=str(q.get('page') or ''));ttk.Entry(right,textvariable=edit_page).pack(fill='x',pady=3)
        ttk.Label(right,text='원문 인용 (해당 페이지의 연속된 문장)').pack(anchor='w');edit_quote=tk.Text(right,height=4,wrap='word',font=('맑은 고딕',10));edit_quote.insert('1.0',q.get('quote',''));edit_quote.pack(fill='x',pady=3)
        approved=tk.BooleanVar(value=q.get('approved',False) and q.get('review_origin','manual') in ('manual','manual_legacy'));ttk.Checkbutton(right,text='정답·해설·원문을 직접 검토했습니다.' ,variable=approved).pack(pady=10)
        def save():
            q.update({k:v.get() for k,v in fields.items()});q.update(options=[v.get() for v in options],correct=answer.get(),explanation=ex.get('1.0','end').strip(),approved=approved.get(),type=kind.get(),answer=typed.get(),images=images);q['page']=int(edit_page.get()) if edit_page.get().strip() else None;q['quote']=edit_quote.get('1.0','end').strip();q['category']=fields['topic'].get();q['review_origin']='manual' if approved.get() else 'automatic';q.pop('showStem',None);q.pop('showAnswer',None);self.reviewer.check(q,preserve_manual=approved.get());self.store.put(q);self.refresh_bank();self.refresh_home();self.refresh_catalog();win.destroy()
        ttk.Button(right_host,text='저장',style='Primary.TButton',command=lambda:self.safe(save)).pack(side='bottom',fill='x',before=canvas)
    def start_quiz(self):
        if self.bank_level!='questions':return self.open_catalog(self.bank_doc_id if self.bank_doc_id not in (None,UNLINKED) else None)
        self.launch_quiz(self.selected_questions())
    def launch_quiz(self,qs):
        if not qs:raise ValueError('풀이할 문제가 없습니다. 교재와 카테고리를 선택하거나 JSON을 가져오세요.')
        qs=list(qs);count=self.quiz_count.get()
        if self.quiz_shuffle.get():random.shuffle(qs)
        self.quiz=qs if count=='전체' else qs[:int(count)];self.index=0;self.responses={};self.navigate('play');self.render_quiz()
    def stop_countdown(self):
        if self.timer_job is not None:
            self.after_cancel(self.timer_job);self.timer_job=None
        self.countdown.stop()
    def start_countdown(self):
        self.stop_countdown();self.countdown.start();self.tick_countdown()
    def tick_countdown(self):
        self.timer_job=None
        if self.countdown.deadline is None or not getattr(self,'timer_label',None) or not self.timer_label.winfo_exists():return
        remaining=self.countdown.remaining
        self.timer_label.configure(text=f'{remaining:02d}초' if remaining else '시간 종료',foreground='#b35b4c' if remaining<=3 else '#0c8476')
        if remaining:self.timer_job=self.after(100,self.tick_countdown)
    def quiz_key(self,event,delta):
        if self.current_view!='play' or not hasattr(self,'quiz'):return
        if isinstance(event.widget,(tk.Entry,tk.Text,ttk.Entry,ttk.Combobox,ttk.Spinbox)):return
        if delta:self.move_quiz(delta)
        else:self.toggle_answer()
        return 'break'
    def move_quiz(self,delta):
        self.responses[self.quiz[self.index]['id']]=self.quiz_choice.get()
        if 0<=self.index+delta<len(self.quiz):self.index+=delta;self.render_quiz()
        elif delta>0:self.stop_countdown();messagebox.showinfo('퀴즈 완료','마지막 문제입니다. 이전 문제로 돌아가 다시 확인할 수 있습니다.')
    def open_quiz_image(self,name):
        path=self.assets.resolve(name)
        if path and sys.platform=='win32':os.startfile(str(path))
    def show_answer(self):
        self.stop_countdown();q=self.quiz[self.index];value=self.quiz_choice.get();self.responses[q['id']]=value
        if q.get('type','객관식')=='단답형':matched=value.strip().casefold()==q['answer'].strip().casefold() if isinstance(value,str) else False
        else:matched=str(value)==str(q['correct'])
        self.quiz_revealed=True;self.paint_quiz_choices()
        self.quiz_result.configure(text=('정답입니다.' if matched else '정답을 확인하세요.')+'\n정답: '+answer_text(q)+'\n\n'+q['explanation']+f"\n\n출처: {q.get('source','미지정')} · PDF {q.get('page','미상')}쪽")
    def toggle_fullscreen(self):self.attributes('-fullscreen',not bool(self.attributes('-fullscreen')))
    def toggle_answer(self):
        if getattr(self,'quiz_revealed',False):
            self.quiz_revealed=False;self.quiz_result.configure(text='');self.paint_quiz_choices()
        else:self.show_answer()
    def paint_quiz_choices(self):
        if not hasattr(self,'quiz_choice'):return
        chosen=self.quiz_choice.get();q=self.quiz[self.index]
        for i,frame,number,label in getattr(self,'choice_tiles',[]):
            bg='#e9f4ef' if chosen==str(i) else '#ffffff';edge='#0c8476' if chosen==str(i) else '#e2eae7'
            if getattr(self,'quiz_revealed',False) and i==q.get('correct'):bg='#dcf3e5';edge='#0c8476'
            frame.configure(bg=bg,highlightbackground=edge)
            for child in (number,label):child.configure(bg=bg)
    def render_quiz(self):
        self.stop_countdown()
        for w in self.quizframe.winfo_children():w.destroy()
        self.quiz_revealed=False;self.choice_tiles=[]
        q=self.quiz[self.index];top=ttk.Frame(self.quizframe,style='Card.TFrame');top.pack(fill='x')
        self.timer_label=ttk.Label(top,text='10초',font=('맑은 고딕',26,'bold'),style='Card.TLabel');self.timer_label.pack(side='right')
        ttk.Label(top,text=f'문제 {self.index+1} / {len(self.quiz)} · {q.get("type","객관식")} · {category(q)}',style='Card.TLabel',wraplength=520,font=('맑은 고딕',12)).pack(side='left')
        progress=ttk.Progressbar(self.quizframe,style='Job.Horizontal.TProgressbar',maximum=len(self.quiz),value=self.index+1);progress.pack(fill='x',pady=(8,4))
        controls=ttk.Frame(self.quizframe,style='Card.TFrame');controls.pack(side='bottom',fill='x',pady=(8,0))
        self.action(controls,'← 이전',lambda:self.move_quiz(-1));self.action(controls,'정답·해설 (Space)',self.toggle_answer,True);self.action(controls,'10초 다시',self.start_countdown);self.action(controls,'다음 →',lambda:self.move_quiz(1),side='right')
        canvas=tk.Canvas(self.quizframe,bg='white',highlightthickness=0);self.quiz_canvas=canvas;scroll=ttk.Scrollbar(self.quizframe,orient='vertical',command=canvas.yview);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        content=ttk.Frame(canvas,style='Card.TFrame');item=canvas.create_window((0,0),window=content,anchor='nw')
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));content.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        width=max(480,self.quizframe.winfo_width()-65)
        ttk.Label(content,text=q['stem'],font=('맑은 고딕',19,'bold'),style='Card.TLabel',wraplength=width).pack(anchor='w',pady=12)
        self.quiz_images=[]
        from PIL import Image,ImageTk
        for name in q.get('images',[]):
            path=self.assets.resolve(name)
            if path:
                with Image.open(path) as im:
                    preview=im.convert('RGB');preview.thumbnail((min(width,850),min(280,max(150,int(self.quizframe.winfo_height()*.38)))));photo=ImageTk.PhotoImage(preview)
                self.quiz_images.append(photo);label=ttk.Label(content,image=photo,style='Card.TLabel',cursor='hand2');label.pack(anchor='w',pady=4);label.bind('<Button-1>',lambda e,n=name:self.open_quiz_image(n))
                ttk.Label(content,text=name+' · 클릭하면 원본 크기로 열기',style='CardMuted.TLabel').pack(anchor='w')
            else:ttk.Label(content,text='이미지 없음: '+name+' · 사용안내에서 교재 이미지 ZIP을 가져오세요.',foreground='#b35b4c',wraplength=width).pack(anchor='w')
        value=self.responses.get(q['id'],'' if q.get('type')=='단답형' else '-1');self.quiz_choice=tk.StringVar(value=str(value))
        if q.get('type')=='단답형':ttk.Entry(content,textvariable=self.quiz_choice,width=60).pack(anchor='w',pady=12)
        else:
            for i,o in enumerate(q['options']):
                row=tk.Frame(content,bg='white',highlightthickness=1,highlightbackground='#e2eae7',cursor='hand2');row.pack(fill='x',pady=5)
                number=tk.Label(row,text=('O' if i==0 else 'X') if q.get('type')=='OX' else str(i+1),font=('맑은 고딕',12,'bold'),bg='white',fg='#0c8476',width=3,pady=12);number.pack(side='left')
                label=tk.Label(row,text=o if q.get('type')!='OX' else ('옳다' if i==0 else '아니다'),bg='white',fg='#20343e',font=('맑은 고딕',12),wraplength=width-75,anchor='w',justify='left',pady=10);label.pack(side='left',fill='x',expand=True,padx=(0,10))
                self.choice_tiles.append((i,row,number,label))
                def choose(event,value=str(i)):self.quiz_choice.set(value);self.paint_quiz_choices()
                for widget in (row,number,label):widget.bind('<Button-1>',choose)
            self.paint_quiz_choices()
        self.quiz_result=ttk.Label(content,text='',style='Card.TLabel',wraplength=width);self.quiz_result.pack(fill='x',pady=15)
        self.start_countdown()
    def backup(self):
        if self.working:return self.show_busy()
        path=filedialog.asksaveasfilename(defaultextension='.zip',initialfile='EMSQuiz_전체백업.zip')
        if not path:return
        import tempfile,zipfile
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'bank.sqlite3';self.store.backup(db)
            with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                z.write(db,'bank.sqlite3')
                for folder in ('originals','assets'):
                    for p in (ROOT/folder).glob('*'):
                        if p.is_file():z.write(p,folder+'/'+p.name)
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
        doc,_=window.store.add_document('Example.pdf',b'example',[{'page':1,'text':'Example source for the UI test.'}],str(root/'scan.pdf'))
        window.store.add_chapter(doc,'Example',1,1)
        name=window.assets.attach(root/'ocr.png')
        q={'images':[name],'id':uid(),'type':'객관식','topic':'Example','concept':'Example objective','stem':'Example question?','options':['A','B','C','D'],'correct':0,'explanation':'Example explanation.','approved':True}
        q.update(doc_id=doc,chapter_id=window.store.chapters(doc)[0]['id'],source='Example.pdf',page=1,quote='Example source for the UI test.');window.reviewer.check(q);window.store.put(q);window.refresh();window.deiconify();window.geometry('+10+10');window.update()
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
        window.open_bank();window.update();capture('bank-textbooks');window.open_bank(doc);window.update();capture('bank-chapters');window.open_bank(doc,window.store.chapters(doc)[0]['id']);window.update();capture('question-bank');window.open_catalog(doc);window.update();capture('category-quiz')
        window.start_quiz();window.update();assert len(window.quiz_images)==1;assert window.countdown.remaining==10;capture('quiz-image-timer')
        window.quiz_choice.set('0');window.show_answer();window.update();capture('quiz-answer');assert window.countdown.remaining is None
        window.navigate('docs');window.edit_figure_regions();window.update();capture('figure-region-editor');assert window.figure_editor.photo.width()>500;window.figure_editor.close()
        window.navigate('settings');window.update();capture('offline-guide')
        from exchange import export_bundle,export_xlsx
        import hashlib
        digest=hashlib.sha256((root/'scan.pdf').read_bytes()).hexdigest()
        entries=window.assets.extract(root/'scan.pdf',digest,threading.Event(),lambda msg:None)
        assert not entries and window.assets.review_pages(digest)==[1]
        doc_pdf=pdfium.PdfDocument(str(root/'scan.pdf'));page_pdf=doc_pdf[0];w,h=page_pdf.get_size();page_pdf.close();doc_pdf.close()
        window.assets.set_regions(digest,1,[(w*.05,h*.2,w*.9,h*.9)])
        entries=window.assets.extract(root/'scan.pdf',digest,threading.Event(),lambda msg:None)
        assert entries and all(e['kind']=='figure' for e in entries)
        export_bundle(root/'material.zip',{'name':'scan.pdf','digest':digest,'pages':extracted},window.assets,entries)
        export_xlsx(root/'questions.xlsx',[q],window.assets);assert (root/'questions.xlsx').read_bytes().startswith(b'PK')
        window.editor(q);window.update();capture('editor');window.stop_countdown();window.store.db.close();window.destroy()
    Path(report).write_text(json.dumps({'ok':True,'python':sys.version,'frozen':bool(getattr(sys,'frozen',False)),'checks':['pdf_render','korean_english_ocr','scanned_pdf_to_text','database','gui','question_editor','quiz','sidebar_dashboard','visible_progress','busy_button_lock','completion_next_step','image_extraction','md_image_zip','json_image_quiz','xlsx_export','automatic_10_second_countdown']}),encoding='utf-8')

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--self-test':
        try:self_test(sys.argv[2])
        except Exception:
            import traceback
            Path(sys.argv[2]).write_text(json.dumps({'ok':False,'error':traceback.format_exc()}),encoding='utf-8')
            sys.exit(1)
    else:App().mainloop()


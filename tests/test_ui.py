import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

@unittest.skipUnless(sys.platform=='win32','Real Tk UI flow runs on the Windows build runner')
class WindowsUIFlowTests(unittest.TestCase):
    def test_task_visibility_controls_completion_and_navigation(self):
        import app
        with tempfile.TemporaryDirectory() as temp, patch.object(app,'ROOT',Path(temp)):
            window=app.App();window.update()
            try:
                self.assertEqual(window.current_view,'home');self.assertFalse(window.job_bar.winfo_ismapped())
                self.assertTrue(window.begin_task('교재 등록','테스트.pdf'));window.update()
                self.assertTrue(window.working);self.assertTrue(window.job_bar.winfo_ismapped())
                self.assertTrue(all(str(b.cget('state'))=='disabled' for b in window.task_controls))
                self.assertFalse(window.begin_task('겹치는 작업','다른파일.pdf'));self.assertEqual(window.task.name,'교재 등록')
                window.handle_event('status',{'phase':'한국어·영어 글자 인식 (OCR)','current':10,'total':40,'unit':'쪽','detail':'PDF 11쪽 인식 중'})
                self.assertIn('25%',window.job_numbers.cget('text'));self.assertIn('테스트.pdf',window.job_detail.cget('text'));self.assertIn('OCR',window.job_title.cget('text'))
                window.reocr();self.assertTrue(window.working)
                window.stop_task();self.assertEqual(window.task.state,'stopping')
                window.handle_event('cancelled','중단했습니다.');self.assertFalse(window.working);self.assertEqual(window.task.percent,25)
                window.begin_task('교재 등록','테스트.md');window.handle_event('status',{'phase':'저장','current':2,'total':2})
                pages=[{'page':1,'text':'첫 페이지 본문'},{'page':2,'text':'두 번째 페이지 본문'}]
                window.handle_event('doc',('테스트.md',b'markdown source',pages,'unused'));window.update()
                self.assertFalse(window.working);self.assertEqual(window.task.percent,100);self.assertEqual(window.current_view,'docs')
                self.assertEqual(window.doclist.get(),'테스트.md');self.assertIn('첫 페이지',window.body.get('1.0','end'));self.assertIn('GPT',window.job_detail.cget('text'))
                self.assertEqual(str(window.generate_button.cget('state')),'normal')
                window.ct.set('첫 챕터');window.cs.set('1');window.ce.set('2');window.add_chapter();window.update()
                self.assertEqual(str(window.generate_button.cget('state')),'normal')
                window.pagepick.current(1);window.show_page();self.assertIn('두 번째',window.body.get('1.0','end'))
                # Completing a new registration selects that document rather than retaining the old list index.
                window.begin_task('교재 등록','새 교재.md');window.handle_event('doc',('새 교재.md',b'new md',pages,'unused'));window.update()
                self.assertEqual(window.doclist.get(),'새 교재.md');self.assertEqual(window.chapters.get_children(),())
                self.assertEqual(str(window.generate_button.cget('state')),'normal')
                # Main next-action bar must remain mapped even in a smaller desktop window.
                self.assertTrue(window.nextstep.winfo_ismapped());self.assertLess(window.nextstep.winfo_rooty(),window.job_box.winfo_rooty())
                window.navigate('bank');window.update();self.assertTrue(window.bank_quiz_button.winfo_ismapped());self.assertLess(window.bank_quiz_button.winfo_rooty(),window.job_box.winfo_rooty())
                doc=next(d for d in window.docrows if d['name']=='테스트.md');window.open_document(doc['id'])
                # Imported JSON is immediately playable without approval or source-link dialogs.
                import json
                from PIL import Image
                image=Path(temp)/'figure.png';Image.new('RGB',(320,180),'teal').save(image);name=window.assets.attach(image)
                bank=Path(temp)/'questions.json';bank.write_text(json.dumps({'questions':[
                    {'type':'객관식','stem':'이미지 객관식','concept':'학습목표','options':['A','B','C','D'],'correct':0,'explanation':'설명','images':[name]},
                    {'type':'OX','stem':'OX 문제','concept':'목표','answer':'O','explanation':'OX 해설'},
                    {'type':'단답형','stem':'단답 문제','concept':'목표','answer':'정답','explanation':'단답 해설'}]},ensure_ascii=False),encoding='utf-8')
                with patch.object(app.filedialog,'askopenfilename',return_value=str(bank)),patch.object(window,'choose_destination',return_value=(doc['id'],None)):
                    window.import_bank()
                self.assertEqual(len(window.qlist.selection()),3);self.assertFalse(any(q['approved'] for q in window.qrows))
                window.start_quiz();window.update();self.assertEqual(len(window.quiz),3)
                window.navigate('bank');window.update();self.assertGreaterEqual(window.qlist.winfo_height(),120);window.navigate('play')
                # Find each type independent of database tie ordering.
                for kind in ('객관식','OX','단답형'):
                    window.index=next(i for i,q in enumerate(window.quiz) if q['type']==kind);window.render_quiz();window.update()
                    self.assertIn('10초',window.timer_label.cget('text'))
                    if kind=='객관식':self.assertEqual(len(window.quiz_images),1)
                    window.quiz_choice.set('정답' if kind=='단답형' else '0');window.show_answer();self.assertIn('정답입니다',window.quiz_result.cget('text'));self.assertIsNone(window.countdown.remaining)
                window.start_countdown();window.countdown.deadline=window.countdown.clock()-1
                if window.timer_job:window.after_cancel(window.timer_job)
                window.tick_countdown();self.assertEqual(window.timer_label.cget('text'),'시간 종료')
                window.render_quiz();self.assertEqual(window.quiz_result.cget('text'),'')
                window.navigate('bank');self.assertIsNone(window.countdown.remaining)
                xlsx=Path(temp)/'out.xlsx'
                with patch.object(app.filedialog,'asksaveasfilename',return_value=str(xlsx)):window.export_excel()
                self.assertTrue(xlsx.read_bytes().startswith(b'PK'))
                material=Path(temp)/'out.zip'
                with patch.object(app.filedialog,'asksaveasfilename',return_value=str(material)):window.export_material()
                import time
                until=time.monotonic()+5
                while window.working and time.monotonic()<until:window.update();time.sleep(.01)
                self.assertFalse(window.working);self.assertTrue(material.is_file())
                # Exercise the actual crop editor and worker on a scan page.
                from test_figures import fixture
                from types import SimpleNamespace
                pdf=Path(temp)/'figures.pdf';fixture(pdf)
                doc,_=window.store.add_document('figures.pdf',pdf.read_bytes(),[{'page':1,'text':'Figure source'},{'page':2,'text':'Scan'}],str(pdf));window.refresh(select_doc=doc)
                window.edit_figure_regions();window.update();editor=window.figure_editor
                editor.page_no.set(2);editor.show_page();self.assertEqual(editor.boxes,[])
                x0,y0,x1,y1=editor.to_canvas((40,100,240,300))
                editor.press(SimpleNamespace(x=x0,y=y0));editor.motion(SimpleNamespace(x=x1,y=y1));editor.release(SimpleNamespace(x=x1,y=y1));self.assertEqual(len(editor.boxes),1)
                editor.save();until=time.monotonic()+5
                while window.working and time.monotonic()<until:window.update();time.sleep(.01)
                self.assertFalse(window.working);self.assertEqual(len(window.assets.entries(window.store.document(doc)['digest'])),3)
                # Delete all registered documents through the UI, preserving questions and used images.
                ids=[d['id'] for d in window.docrows]
                with patch.object(window,'confirm_delete',return_value=True):
                    for id in ids:window.delete_doc(id)
                window.update();self.assertEqual(window.docrows,[]);self.assertEqual(window.doclist.get(),'');self.assertEqual(window.pagepick.get(),'')
                self.assertEqual(len(window.store.questions()),3);self.assertIsNotNone(window.assets.resolve(name));self.assertEqual(str(window.generate_button.cget('state')),'disabled')
                self.assertEqual(str(window.figures_button.cget('state')),'disabled')
            finally:window.stop_countdown();window.store.db.close();window.destroy()

    def test_textbook_chapter_checkboxes_catalog_and_auto_review(self):
        import app,json
        with tempfile.TemporaryDirectory() as temp,patch.object(app,'ROOT',Path(temp)):
            window=app.App();window.update()
            try:
                a,_=window.store.add_document('교재 A.pdf',b'A',[{'page':1,'text':'원문 A1'},{'page':2,'text':'원문 A2'}]);b,_=window.store.add_document('교재 B.pdf',b'B',[{'page':1,'text':'원문 B1'}])
                window.store.add_chapter(a,'A 챕터 1',1,1);window.store.add_chapter(a,'A 챕터 2',2,2);window.store.add_chapter(b,'B 챕터 1',1,1)
                ca=window.store.chapters(a);cb=window.store.chapters(b)
                qs=[{'type':'OX','stem':stem,'concept':'학습목표','answer':'O','explanation':quote,'page':page,'quote':quote,'source_digest':window.store.document(doc)['digest'],'category':'동일 카테고리'} for doc,page,quote,stem in [(a,1,'원문 A1','A1 문제'),(a,2,'원문 A2','A2 문제'),(b,1,'원문 B1','B1 문제')]]
                window.store.import_questions(qs,window.reviewer);window.refresh();window.open_bank();window.update()
                self.assertEqual(window.bank_level,'books');self.assertEqual(str(window.bank_quiz_button.cget('state')),'disabled')
                window.open_bank(a);window.update();self.assertEqual(window.bank_level,'chapters')
                window.open_bank(a,ca[0]['id']);window.update();self.assertEqual(len(window.qlist.get_children()),1)
                id=window.qlist.get_children()[0];row=window.qlist.rows[id];self.assertFalse(row['var'].get());row['checkbutton'].invoke();self.assertEqual(window.qlist.selection(),(id,))
                window.select_all_var.set(False);window.select_all_questions();self.assertEqual(window.qlist.selection(),())
                window.select_all_var.set(True);window.select_all_questions();self.assertEqual(window.qlist.selection(),(id,))
                with patch.object(window,'confirm_action',return_value=True):window.delete_selected()
                self.assertEqual(len(window.store.questions()),2);self.assertTrue(any(q['stem']=='A2 문제' for q in window.store.questions()));self.assertTrue(any(q['stem']=='B1 문제' for q in window.store.questions()))
                window.open_catalog(a);window.catalog_chapter.current(0);window.refresh_catalog_cards();pool=window.catalog_pool();self.assertEqual([q['stem'] for q in pool],['A2 문제'])
                self.assertTrue(all(q['approved'] for q in pool));window.launch_quiz(pool);self.assertTrue(all(q['doc_id']==a for q in window.quiz));self.assertEqual(window.current_view,'play')
                # Root import resolves fingerprint and page without opening a destination dialog.
                file=Path(temp)/'auto.json';new=dict(qs[0],stem='자동 등록 문제');file.write_text(json.dumps({'questions':[new]},ensure_ascii=False),encoding='utf-8');window.open_bank()
                with patch.object(app.filedialog,'askopenfilename',return_value=str(file)),patch.object(window,'choose_destination',side_effect=AssertionError('should identify textbook automatically')):window.import_bank()
                imported=next(q for q in window.store.questions() if q['stem']=='자동 등록 문제');self.assertTrue(imported['approved']);self.assertEqual(imported['chapter_id'],ca[0]['id']);self.assertEqual(window.bank_doc_id,a)
                # Editing source references reruns checks and manual verification remains available.
                window.editor(imported);window.update();editors=[w for w in window.winfo_children() if w.winfo_class()=='Toplevel']
                for editor in editors:editor.destroy()
            finally:window.stop_countdown();window.store.db.close();window.destroy()

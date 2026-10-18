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
                self.assertEqual(window.current_view,'home')
                self.assertTrue(window.begin_task('교재 등록','테스트.pdf'));window.update()
                self.assertTrue(window.working)
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
                self.assertEqual(window.doclist.get(),'테스트.md');self.assertIn('첫 페이지',window.body.get('1.0','end'));self.assertIn('다시 올릴 필요',window.job_detail.cget('text'))
                self.assertEqual(str(window.generate_button.cget('state')),'disabled')
                window.ct.set('첫 챕터');window.cs.set('1');window.ce.set('2');window.add_chapter();window.update()
                self.assertEqual(str(window.generate_button.cget('state')),'normal')
                window.pagepick.current(1);window.show_page();self.assertIn('두 번째',window.body.get('1.0','end'))
                # Completing a new registration selects that document rather than retaining the old list index.
                window.begin_task('교재 등록','새 교재.md');window.handle_event('doc',('새 교재.md',b'new md',pages,'unused'));window.update()
                self.assertEqual(window.doclist.get(),'새 교재.md');self.assertEqual(window.chapters.get_children(),())
                self.assertEqual(str(window.generate_button.cget('state')),'disabled')
                # Main next-action bar must remain mapped even in a smaller desktop window.
                self.assertTrue(window.nextstep.winfo_ismapped());self.assertLess(window.nextstep.winfo_rooty(),window.job_box.winfo_rooty())
                window.navigate('bank');window.update();self.assertTrue(window.bank_quiz_button.winfo_ismapped());self.assertLess(window.bank_quiz_button.winfo_rooty(),window.job_box.winfo_rooty())
            finally:window.store.db.close();window.destroy()

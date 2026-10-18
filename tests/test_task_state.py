import unittest
from task_state import TaskState

class TaskStateTests(unittest.TestCase):
    def test_indeterminate_until_page_count_known(self):
        s=TaskState();s.begin('교재 등록','교재.pdf');self.assertIsNone(s.percent);self.assertEqual(s.filename,'교재.pdf')
    def test_completed_page_percentage(self):
        s=TaskState();s.begin('OCR');s.update({'phase':'OCR 인식 중','current':0,'total':40});self.assertEqual(s.percent,0)
        s.update({'current':10,'detail':'11쪽 인식 중'});self.assertEqual(s.percent,25);self.assertEqual(s.phase,'OCR 인식 중')
    def test_cancel_does_not_pretend_completion(self):
        s=TaskState();s.begin('OCR');s.update({'current':3,'total':10});s.stop();self.assertEqual(s.state,'stopping');self.assertEqual(s.percent,30)
        s.end('cancelled','중단됨');self.assertEqual(s.percent,30)
    def test_finish_and_late_events(self):
        s=TaskState();s.begin('OCR');s.update({'current':3,'total':10});s.finish('본문 저장 완료');s.update({'current':2});self.assertEqual(s.percent,100);self.assertEqual(s.detail,'본문 저장 완료')
    def test_new_job_resets_progress(self):
        s=TaskState();s.begin('OCR');s.update({'current':9,'total':10});s.finish('완료');s.begin('AI','챕터1');self.assertEqual(s.current,0);self.assertEqual(s.total,0);self.assertIsNone(s.percent)
    def test_retry_message_preserves_count(self):
        s=TaskState();s.begin('AI');s.update({'current':2,'total':5,'unit':'구간'});s.update('4초 후 재시도');self.assertEqual(s.percent,40);self.assertEqual(s.detail,'4초 후 재시도')

class PdfProgressTests(unittest.TestCase):
    def test_page_completed_events_and_cache_reuse(self):
        import tempfile,threading
        from pathlib import Path
        from unittest.mock import patch,MagicMock
        from pipeline import extract_pdf
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sample.pdf';path.write_bytes(b'pdf')
            page=MagicMock();page.extract_text.return_value='장비는 사용하기 전에 작동 여부를 확인합니다. 충분히 긴 본문입니다.'
            reader=MagicMock();reader.pages=[page,page];events=[]
            with patch('pypdf.PdfReader',return_value=reader):
                result=extract_pdf(path,Path(tmp)/'cache',threading.Event(),events.append)
                self.assertEqual([e['current'] for e in events if e['phase']=='페이지 처리 완료'],[1,2])
                self.assertEqual(events[-1]['total'],2)
                page.extract_text.reset_mock();events.clear();self.assertEqual(extract_pdf(path,Path(tmp)/'cache',threading.Event(),events.append),result)
                page.extract_text.assert_not_called();self.assertTrue(any(e['phase']=='저장된 본문 재사용' for e in events))

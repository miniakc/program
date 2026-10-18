import json, tempfile, unittest
from pathlib import Path
from core import Store, parse_md, parse_questions

def question(**kw):
    return dict(stem='장비 사용 전 확인할 사항은?',concept='작동 점검',options=['작동 여부','제품 역사','개발자','출판일'],correct=0,explanation='사용 전 작동을 확인한다.',**kw)

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'bank.db')
        self.doc,_=self.s.add_document('test.pdf',b'pdf',[{'page':1,'text':'장비는 사용 전 작동 여부를 확인한다.'},{'page':2,'text':'두 번째 페이지'}])
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def test_md_roundtrip(self):self.assertEqual(parse_md('<!-- PDF_PAGE: 1 -->\n가\n<!-- PDF_PAGE: 2 -->\n나'),[{'page':1,'text':'가'},{'page':2,'text':'나'}])
    def test_unmapped(self):self.assertIsNone(parse_md('일반 본문')[0]['page'])
    def test_bad_pages(self):
        for text in ['<!-- PDF_PAGE: 0 -->\nx','<!-- PDF_PAGE: 1 -->\nx\n<!-- PDF_PAGE: 1 -->\ny','누락본문\n<!-- PDF_PAGE: 1 -->\nx']:
            with self.assertRaises(ValueError):parse_md(text)
    def test_chapter_validation(self):
        self.s.add_chapter(self.doc,'챕터1',1,1)
        with self.assertRaises(ValueError):self.s.add_chapter(self.doc,'겹침',1,2)
        with self.assertRaises(ValueError):self.s.add_chapter(self.doc,'범위밖',3,3)
    def test_atomic_import(self):
        with self.assertRaises(ValueError):self.s.import_questions([question(),{'stem':'잘못된 문제'}])
        self.assertEqual(self.s.questions(),[])
    def test_draft_and_duplicate(self):
        self.assertEqual(self.s.import_questions([question(approved=True),question()]),1)
        self.assertFalse(self.s.questions()[0]['approved'])
    def test_evidence(self):
        self.assertIn('일치',self.s.evidence(question(doc_id=self.doc,page=1,quote='사용 전 작동 여부')))
        self.assertIn('미일치',self.s.evidence(question(doc_id=self.doc,page=1,quote='없는 내용')))
    def test_outside_chapter(self):
        self.s.add_chapter(self.doc,'첫 장',1,1);c=self.s.chapters(self.doc)[0]
        self.assertEqual(self.s.evidence(question(doc_id=self.doc,chapter_id=c['id'],page=2,quote='두 번째')),'지정 챕터 밖의 근거')
    def test_prompt_scope(self):
        self.s.add_chapter(self.doc,'첫 장',1,1);text=self.s.prompt(self.doc,self.s.chapters(self.doc)[0]);self.assertIn('작동 여부',text);self.assertNotIn('두 번째 페이지',text)
    def test_json_and_markdown(self):
        text=json.dumps({'questions':[question()]},ensure_ascii=False)
        self.assertEqual(len(parse_questions('```json\n'+text+'\n```')),1)
    def test_backup(self):
        self.s.import_questions([question()]);target=Path(self.tmp.name)/'backup.db';self.s.backup(target);other=Store(target)
        try:self.assertEqual(len(other.questions()),1)
        finally:other.db.close()
    def test_deduplicate_document(self):self.assertFalse(self.s.add_document('same.pdf',b'pdf',[])[1])
    def test_delete(self):
        self.s.import_questions([question()]);self.s.delete([self.s.questions()[0]['id']]);self.assertEqual(self.s.questions(),[])

if __name__=='__main__':unittest.main()

import tempfile,unittest
from pathlib import Path
from core import Store
from exchange import AssetStore,markdown
from review import SourceReview,status_label

TEXT='심장의 전기자극은 방실결절에서 지연되어 심실이 채워질 시간을 확보한다.'
def question(**kw):
    q=dict(type='객관식',stem='전도 지연의 목적은?',concept='심실 충만',options=['충만 시간 확보','충만 방해','수축 차단','전도 제거'],correct=0,explanation=TEXT,page=1,quote=TEXT,topic='전기전도',images=[]);q.update(kw);return q

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.s=Store(root/'bank.db');self.a=AssetStore(root/'assets');self.r=SourceReview(self.s,self.a)
        self.doc,_=self.s.add_document('교재 A.pdf',b'A',[{'page':1,'text':TEXT},{'page':2,'text':'두 번째 챕터 본문이다.'}]);self.s.add_chapter(self.doc,'챕터 1',1,1);self.s.add_chapter(self.doc,'챕터 2',2,2)
        self.other,_=self.s.add_document('교재 B.pdf',b'B',[{'page':1,'text':TEXT}]);self.digest=self.s.document(self.doc)['digest']
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def test_automatic_link_and_review(self):
        q=self.r.prepare([question(source_digest=self.digest)])[0]
        self.assertEqual(q['doc_id'],self.doc);self.assertEqual(q['chapter_id'],self.s.chapters(self.doc)[0]['id']);self.assertTrue(q['approved']);self.assertEqual(status_label(q),'자동 대조 완료');self.assertFalse(q['review_report']['semantic_validation'])
        self.assertEqual(self.s.import_questions([question(source_digest=self.digest)],self.r),1);self.assertTrue(self.s.questions()[0]['approved'])
    def test_failure_reasons_and_untrusted_approval(self):
        for change,term in [({'quote':'없는 문장'},'인용'),({'page':99},'페이지'),({'images':['missing.png']},'이미지')]:
            q=self.r.prepare([question(source_digest=self.digest,approved=True,**change)])[0]
            self.assertFalse(q['approved']);self.assertTrue(any(term in x for x in q['review_report']['issues']))
        q=self.r.prepare([question(approved=True)])[0];self.assertFalse(q['approved']);self.assertNotIn('doc_id',q)
    def test_explicit_wrong_chapter_flagged(self):
        q=self.r.prepare([question(doc_id=self.doc,chapter_id=self.s.chapters(self.doc)[1]['id'])])[0]
        self.assertFalse(q['approved']);self.assertTrue(any('챕터' in v for v in q['review_report']['issues']))
    def test_identical_titles_and_same_stem_across_books(self):
        self.assertEqual(self.s.import_questions([question(source_digest=self.digest)],self.r),1)
        self.assertEqual(self.s.import_questions([question(doc_id=self.other)],self.r),1)
        self.assertEqual(self.s.import_questions([question(source_digest=self.digest)],self.r),0)
        self.assertEqual(len(self.s.questions()),2)
    def test_batch_image_source_links_text_only_siblings(self):
        name=self.digest[:16]+'_p0001_figure001.png'
        from PIL import Image
        Image.new('RGB',(30,30),'red').save(self.a.root/name)
        prepared=self.r.prepare([question(source='제목이 다른 교재',images=[name]),question(source='제목이 다른 교재',stem='다른 문제')])
        self.assertTrue(all(q['doc_id']==self.doc for q in prepared));self.assertTrue(all(q['approved'] for q in prepared))
    def test_manual_override_and_ocr_invalidation(self):
        q=self.r.prepare([question(source_digest=self.digest,quote='직접 확인한 다른 근거')])[0]
        q.update(approved=True,review_origin='manual');self.r.check(q,preserve_manual=True);self.s.put(q);self.assertEqual(status_label(q),'직접 검토 완료')
        self.s.update_pages(self.doc,[{'page':1,'text':'바뀐 본문'},{'page':2,'text':'두 번째 챕터 본문이다.'}]);self.r.reconcile();saved=self.s.questions()[0];self.assertFalse(saved['approved'])
    def test_metadata_roundtrip_and_md_image_provenance(self):
        md=markdown(self.s.document(self.doc),[]);self.assertIn('EMS_SOURCE_SHA256: '+self.digest,md)
        doc,_=self.s.add_document('변환된 교재.md',md.encode(),[{'page':1,'text':md}]);q=question(doc_id=doc,source_digest=self.digest)
        # Explicit digest prefers registered original PDF when it is present.
        self.assertEqual(self.r.prepare([q])[0]['doc_id'],self.doc)
        self.s.delete_document(self.doc)
        prepared=self.r.prepare([q])[0];self.assertEqual(prepared['doc_id'],doc);self.assertTrue(prepared['approved'])
    def test_recheck_after_missing_image_is_added(self):
        q=question(source_digest=self.digest,images=['new.png']);self.s.import_questions([q],self.r);self.assertFalse(self.s.questions()[0]['approved'])
        from PIL import Image
        Image.new('RGB',(30,30),'teal').save(self.a.root/'new.png');self.r.reconcile();self.assertTrue(self.s.questions()[0]['approved'])

import json, tempfile, threading, unittest
from pathlib import Path
from pipeline import generate, split_pages, response_payload, extract_pdf, Cancelled

class PipelineTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.cancel=threading.Event();self.pages=[{'page':1,'text':'장비는 사용 전에 작동 여부를 확인한다. 이후 상태를 기록한다.'}]
    def tearDown(self):self.tmp.cleanup()
    def fake(self,key,payload,cancel,progress):
        return [{'type':'객관식','topic':'점검','concept':'작동 점검','stem':'사용 전 확인할 사항은?','options':['작동 여부','개발 연도','개발자','출판일'],'correct':0,'explanation':'작동을 확인한다.','page':1,'quote':'장비는 사용 전에 작동 여부를 확인한다.','source':'테스트'}],{'input_tokens':50,'output_tokens':100}
    def test_source_validation_and_resume(self):
        args=(self.pages,1,'test-model','not-a-real-key','점검','테스트',self.tmp.name,self.cancel,lambda m:None)
        result,usage=generate(*args,request_fn=self.fake);self.assertEqual(len(result),1)
        def forbidden(*a):raise AssertionError('cached chunk must not call API')
        self.assertEqual(generate(*args,request_fn=forbidden)[0],result)
        self.assertNotIn('not-a-real-key',''.join(p.read_text(encoding='utf-8') for p in Path(self.tmp.name).rglob('*.json')))
    def test_reject_fake_quote(self):
        def fake(*args):
            qs,u=self.fake(*args);qs[0]['quote']='원문에 없는 텍스트를 인용했다';return qs,u
        with self.assertRaises(ValueError):generate(self.pages,1,'m','key','t','s',self.tmp.name,self.cancel,lambda m:None,request_fn=fake)
        self.assertEqual(list(Path(self.tmp.name).rglob('*.json')),[])
    def test_conservative_split(self):
        text='한글 본문\n'*20000;chunks=split_pages([{'page':3,'text':text}]);self.assertGreater(len(chunks),1)
        self.assertEqual(''.join(p['text'] for c in chunks for p in c),text.strip())
        self.assertTrue(all(len(p['text'].encode())<=14000 for c in chunks for p in c))
    def test_cancel(self):
        self.cancel.set()
        with self.assertRaises(Cancelled):generate(self.pages,1,'m','key','t','s',self.tmp.name,self.cancel,lambda m:None,request_fn=self.fake)
    def test_schema(self):
        payload=response_payload('m',self.pages,3,'t','s');self.assertFalse(payload['store']);self.assertTrue(payload['text']['format']['strict'])
        self.assertEqual(payload['text']['format']['schema']['properties']['questions']['maxItems'],3)
    def test_pdf_render(self):
        import pypdfium2 as pdfium
        from pypdf import PdfWriter
        path=Path(self.tmp.name)/'test.pdf';writer=PdfWriter();writer.add_blank_page(200,200)
        with path.open('wb') as f:writer.write(f)
        doc=pdfium.PdfDocument(path);page=doc[0];bitmap=page.render(scale=1)
        try:self.assertEqual(bitmap.width,200)
        finally:bitmap.close();page.close();doc.close()

if __name__=='__main__':unittest.main()

class ApiTransportTests(unittest.TestCase):
    def test_temporary_limit_retries(self):
        import io, urllib.error
        from unittest.mock import patch
        from pipeline import request_questions
        cancel=threading.Event()
        # Advance the retry wait without sleeping; preserve real cancellation semantics.
        cancel.wait=lambda seconds:False
        error=urllib.error.HTTPError('https://api.openai.com',429,'limit',{},io.BytesIO(b'{"error":{"code":"rate_limit_exceeded"}}'))
        response=io.StringIO(json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':'{"questions":[]}'}]}],'usage':{}}))
        with patch('urllib.request.urlopen',side_effect=[error,response]) as call:
            qs,_=request_questions('secret',{},cancel,lambda m:None)
            self.assertEqual(qs,[]);self.assertEqual(call.call_count,2)
    def test_quota_does_not_retry_and_redacts_key(self):
        import io, urllib.error
        from unittest.mock import patch
        from pipeline import request_questions
        error=urllib.error.HTTPError('https://api.openai.com',429,'quota',{},io.BytesIO(b'{"error":{"code":"insufficient_quota","message":"secret"}}'))
        with patch('urllib.request.urlopen',side_effect=error) as call:
            with self.assertRaises(RuntimeError) as exc:request_questions('secret',{},threading.Event(),lambda m:None)
            self.assertEqual(call.call_count,1);self.assertNotIn('secret',str(exc.exception))
    def test_incomplete_output_is_rejected(self):
        import io
        from unittest.mock import patch
        from pipeline import request_questions
        with patch('urllib.request.urlopen',return_value=io.StringIO('{"status":"incomplete"}')):
            with self.assertRaises(RuntimeError):request_questions('key',{},threading.Event(),lambda m:None)

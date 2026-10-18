import io,json,threading,unittest
from unittest.mock import patch
from pipeline import validate_api_key,request_questions,generate

class CredentialTests(unittest.TestCase):
    def test_reproduce_reported_header_error_without_network(self):
        import http.client
        c=http.client.HTTPConnection('example.invalid');c.putrequest('POST','/')
        with self.assertRaises(UnicodeEncodeError) as e:c.putheader('Authorization','Bearer abcde가')
        self.assertEqual(e.exception.encoding,'latin-1');self.assertEqual(e.exception.start,12)
    def test_non_ascii_rejected_before_request(self):
        for key in ['abcde가','sk-test\u200b','sk-테스트','sk-testé']:
            with self.subTest(key=key),patch('urllib.request.urlopen') as send:
                with self.assertRaises(ValueError) as e:request_questions(key,{},threading.Event(),lambda _:None)
                send.assert_not_called();self.assertNotIn(key,str(e.exception))
    def test_whitespace_and_control_rejected(self):
        for key in ['sk-ab cd','sk-ab\ncd','sk-ab\rcd','sk-ab\tcd','sk-ab\x00cd','sk-ab\x7fcd','Bearer sk-test']:
            with self.subTest(key=key),self.assertRaises(ValueError):validate_api_key(key)
    def test_outer_copy_whitespace_is_trimmed(self):self.assertEqual(validate_api_key(' \r\nsk-example\n '),'sk-example')
    def test_quoted_keys_and_empty_input(self):
        for key in ['', '   ', '"sk-example"', "'sk-example'"]:
            with self.subTest(key=key),self.assertRaises(ValueError):validate_api_key(key)
    def test_generate_checks_key_before_processing_or_cache(self):
        with patch('pipeline.split_pages') as split:
            with self.assertRaises(ValueError):generate([],1,'model','한글 입력','t','s','unused',threading.Event(),lambda _:None)
            split.assert_not_called()
    def test_korean_payload_remains_supported(self):
        response=io.StringIO('{"status":"completed","output":[{"content":[{"type":"output_text","text":"{\\"questions\\":[]}"}]}]}')
        with patch('urllib.request.urlopen',return_value=response) as send:
            request_questions('sk-example',{'input':'한글 교재 본문'},threading.Event(),lambda _:None)
            request=send.call_args.args[0];self.assertEqual(json.loads(request.data)['input'],'한글 교재 본문');request.get_header('Authorization').encode('latin-1')

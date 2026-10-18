import unittest
from types import SimpleNamespace
from pdf_layout import text_lines,paragraphs,sentence_lines,ocr_formats

def word(text,x,top,baseline,size=10,width=60,height=6):
    return {'text':text,'x0':x,'x1':x+width,'top':top,'bottom':top+height,'chars':[{'text':text,'size':size,'matrix':(1,0,0,1,x,baseline),'upright':True}]}

class SentenceLayoutTests(unittest.TestCase):
    def test_mixed_ink_bounds_and_reference_stay_on_one_baseline(self):
        words=[word('기도',10,10,300),word('평가',75,15,300),word('3',135,6,304,size=6,width=4,height=4)]
        page=SimpleNamespace(extract_words=lambda **kwargs:words)
        lines=text_lines(page)
        self.assertEqual(len(lines),1);self.assertEqual(lines[0]['text'],'기도 평가3')
    def test_tight_glyphs_do_not_make_mid_sentence_paragraphs(self):
        words=[word('가능한 경우',10,10,300,width=200),word('기도를 평가한다.',10,24,286,width=200),word('결과를 기록한다.',10,38,272,width=200)]
        lines=text_lines(SimpleNamespace(extract_words=lambda **kwargs:words))
        self.assertEqual(paragraphs(lines),'가능한 경우 기도를 평가한다.  \n결과를 기록한다.')
    def test_justified_gap_is_not_a_column(self):
        words=[word('Body',10,10,300,width=30),word('words',80,10,300,width=40)]
        self.assertEqual(len(text_lines(SimpleNamespace(extract_words=lambda **kwargs:words))),1)
    def test_recurring_column_gutter_is_retained(self):
        words=[word('Left',10,t,b,width=70) for t,b in [(10,300),(24,286),(38,272)]]+[word('Right',250,t,b,width=70) for t,b in [(10,300),(24,286),(38,272)]]
        self.assertEqual(len(text_lines(SimpleNamespace(extract_words=lambda **kwargs:words))),6)
    def test_sentences_preserve_decimals_and_english_abbreviations(self):
        text='수치는 2.5이다. C-L 분류를 확인한다. Dr. Kim uses e.g. a scale. 다음 문장이다.'
        self.assertEqual(sentence_lines(text),'수치는 2.5이다.  \nC-L 분류를 확인한다.  \nDr. Kim uses e.g. a scale.  \n다음 문장이다.')
    def test_quotes_parentheses_and_reference_numbers(self):
        self.assertEqual(sentence_lines('“확인했나요?” 다음을 평가한다(예: 2.5).3 결과이다.'),'“확인했나요?”  \n다음을 평가한다(예: 2.5).3  \n결과이다.')
    def test_real_paragraphs_and_lists_stay_separate(self):
        result=ocr_formats('첫 문장은 지면에서\n끊겼다. 다음 문장이다.\n\n다른 문단이다.\n\n• 첫 항목\n• 두 번째 항목')
        self.assertEqual(result,'첫 문장은 지면에서 끊겼다.  \n다음 문장이다.\n\n다른 문단이다.\n\n- 첫 항목\n- 두 번째 항목')
    def test_content_is_unchanged_by_sentence_breaks(self):
        import re
        source='U.S. 기관, Fig. 2.1 참고. 내용은 바꾸지 않는다! 수치 20%도 유지한다.'
        self.assertEqual(re.sub(r'\s+','',source),re.sub(r'\s+','',sentence_lines(source)))

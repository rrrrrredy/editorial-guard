import json
import pytest
from editorial_guard.core import Context,protected_ranges,lint_text,verify_edit
from editorial_guard.pipeline import rewrite_text
pytestmark=pytest.mark.unit

def test_multiline_json_is_protected_and_not_linted_as_prose():
 data={'note':'下面我先分析，再给出结论。','nested':[{'value':'右括号 } 与转义引号 " 都属于字符串'}]}
 block=json.dumps(data,ensure_ascii=False,indent=2)
 text='请按资料核对以下配置，不修改字段值。\n'+block+'\n项目仅支持本地读取。'
 begin=text.index('{');end=begin+len(block)
 assert (begin,end) in protected_ranges(text)
 assert lint_text(text)['issues']==[]
 candidate=text.replace('下面我先分析，再给出结论。','正式说明。')
 assert 'protected_span_changed' in verify_edit(text,candidate)['reasons']

def test_multiline_json_array_is_preserved_but_invalid_braces_do_not_hide_prose():
 block='[\n  "下面我先分析，再给出结论。",\n  {"enabled": true}\n]'
 text='以下数组只作为配置资料保留。\n'+block
 assert any(text[a:b]==block for a,b in protected_ranges(text))
 invalid='正文内容应当正常评审。\n{这不是有效JSON\n下面我先分析，再给出结论。\n}'
 assert any(i['suite']=='process' for i in lint_text(invalid)['issues'])

def test_english_source_does_not_change_chinese_target_and_unsupported_is_not_translated():
 context=Context(source_bundle={'source_language':'en','facts':['The project supports local reads only.']})
 text='本项目使用 API 和 JSON，目前仅支持本地读取。'
 assert lint_text(text,context)['language_scope_status']=='supported'
 class NoCalls:
  def call(self,*args,**kwargs):raise AssertionError('Unsupported input must not invoke translation or a judge')
 english='This project currently supports local reads only and does not provide remote writing.'
 result=rewrite_text(english,context,NoCalls(),'deepseek','glm')
 assert result['candidate_text']==english and result['attempts']==[]
 assert result['validation']['language_scope_status']=='unsupported'

def test_structured_table_command_and_path_are_protected():
 path='D:'+chr(92)+'data'+chr(92)+'config.json'
 text='以下资料必须原样保留，供项目参与者核对。\n| 字段 | 值 |\n| 说明 | 下面我先分析 |\nPS> python -m example\n'+path+'\nhttps://example.org/下面我先分析\n'
 assert lint_text(text)['issues']==[]
 for original,replacement in [('python -m example','python -m changed'),('config.json','changed.json'),('| 说明 |','| 备注 |')]:
  assert 'protected_span_changed' in verify_edit(text,text.replace(original,replacement))['reasons']

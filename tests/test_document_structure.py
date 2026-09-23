import pytest
from editorial_guard.core import Context, verify_edit
from editorial_guard.structure import structure_changes
from editorial_guard.pipeline import semantic_verify
from editorial_guard.finalize import acceptance_key

pytestmark = pytest.mark.unit
BASE = "# 使用说明\n\n正文必须保留完整含义和任务条件。\n\n## 保存文件\n\n[返回](#保存文件) [下载](./files/a(b).zip)\n\n<a id='stable'></a>\n\n1. 保存当前文件。\n2. 关闭窗口。\n"

@pytest.mark.parametrize('old,new,reason', [
    ('## 保存文件', '## 关闭窗口', 'headings'),
    ('#保存文件)', '#其他标题)', 'links'),
    ('./files/a(b).zip', './files/c.zip', 'links'),
    ("id='stable'", "id='changed'", 'ids'),
    ('1. 保存当前文件。\n2. 关闭窗口。', '1. 关闭窗口。\n2. 保存当前文件。', 'ordered_step_order'),
    ('2. 关闭窗口。', '  2. 关闭窗口。', 'list_shape'),
])
def test_detect_document_damage(old,new,reason):
    result = verify_edit(BASE, BASE.replace(old,new))
    assert 'document_structure_changed' in result['reasons']
    assert reason in result['structure_changes']


def test_legal_step_rewording_goes_to_semantic_review():
    result = verify_edit(BASE, BASE.replace('保存当前文件。', '将当前文件保存。'))
    assert 'document_structure_changed' not in result['reasons']
    assert result['status'] == 'unchecked'


def test_reference_targets_and_fenced_examples():
    original = '正文需要保存来源和链接。\n[资料][src]\n\n[src]: <../a(b).md> "资料"\n\n~~~md\n# 示例标题\n[这是代码](./example)\n~~~\n'
    assert 'reference_definitions' in structure_changes(original, original.replace('../a(b).md','../b.md'))
    # The structure scanner ignores fenced examples; byte protection separately checks code.
    assert structure_changes(original, original.replace('# 示例标题', '# 代码标题')) == []
    assert 'protected_span_changed' in verify_edit(original, original.replace('# 示例标题','# 代码标题'))['reasons']


def test_heading_permission_keeps_hierarchy_and_existing_anchors():
    ctx = Context(constraints={'allow_heading_edits': True})
    plain = '# 工作说明\n这是需要保持完整含义的中文正文。'
    assert 'document_structure_changed' not in verify_edit(plain, plain.replace('工作说明','任务说明'), ctx)['reasons']
    broken = verify_edit(BASE, BASE.replace('## 保存文件','## 文件保存'), ctx)
    assert 'broken_local_anchor' in broken['structure_changes']
    assert 'headings' in verify_edit(plain, plain.replace('# 工作','## 工作'),ctx)['structure_changes']


def test_structure_failure_short_circuits_model_call():
    class NoCalls:
        def call(self,*args,**kwargs): raise AssertionError('A deterministic structural failure must block before a model request')
    result = semantic_verify(NoCalls(), 'glm', BASE, BASE.replace("id='stable'", "id='lost'"), Context())
    assert result['status'] == 'fail'


def test_author_sample_is_carried_and_bound():
    a = Context.from_dict({'voice_sample':'我还没决定，想再看看。'})
    b = Context.from_dict({'voice_sample':'我的措辞更简练。'})
    assert a.public()['voice_sample'] == '我还没决定，想再看看。'
    assert acceptance_key({},a) != acceptance_key({},b)

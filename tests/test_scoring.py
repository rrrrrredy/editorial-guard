import pytest
pytestmark=pytest.mark.unit
from editorial_guard.scoring import detection_report

def test_detection_excludes_self_reference_and_keeps_disagreement_separate():
    issue={'suite':'style','action':'rewrite','start':1,'end':2}
    pred={'valid_task':True,'language_scope_status':'supported','style_problem':True,'process_problem':False,'issues':[issue]}
    opposite={**pred,'style_problem':False,'issues':[]}
    row={'id':'x','source_group_id':'family','suite':'StyleBench-ZH','annotation_records':[
        {'provider':'codex','annotation':pred},{'provider':'deepseek','annotation':opposite},{'provider':'glm','annotation':pred}]}
    result=detection_report([row],[{'provider':'codex','id':'x','status':'completed','annotation':pred}])
    assert all(x['reference_provider']!='codex' for x in result['comparisons'])
    style={x['reference_provider']:x for x in result['comparisons'] if x['task']=='style'}
    assert style['deepseek']['document']['fp']==1 and style['glm']['document']['tp']==1
    assert style['deepseek']['localization']['character_union']['fp']==1
    assert style['glm']['families']==1

def test_detection_missing_reference_failure_and_duplicate_are_explicit():
    row={'id':'x','source_group_id':'f','suite':'DeliveryBench-ZH','annotation_records':[]}
    done={'provider':'glm','id':'x','status':'completed','annotation':{}}
    error={'provider':'deepseek','id':'x','status':'error'}
    result=detection_report([row],[done,error])
    assert result['comparisons']==[]
    coverage={x['provider']:x for x in result['coverage']}
    assert coverage['glm']['no_independent_reference']==1 and coverage['deepseek']['execution_error']==1
    with pytest.raises(ValueError):detection_report([row],[done,done])

def test_literal_mask_merges_overlaps_and_preserves_unicode_and_quotes():
    from editorial_guard.scoring import mask_exact_process_spans
    assert mask_exact_process_spans('过程说明。正文😀。',['过程','过程说明。'])=='正文😀。'
    assert mask_exact_process_spans('正文😀。',[])=='正文😀。'
    with pytest.raises(ValueError,match='absent'):mask_exact_process_spans('正文。',['不存在'])
    with pytest.raises(ValueError,match='protected'):mask_exact_process_spans('引用“过程说明。”必须保留。',['过程说明。'])

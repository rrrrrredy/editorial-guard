import copy,runpy
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
check=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/check_site.py'))['check_result_counts']

def valid():
 return {'counts':{'registered':3,'recorded':2,'completed':1,'execution_errors':1,'without_terminal_record':1},'suite_results':[{'suite':'StyleBench-ZH','rows':[{'mode':'both','n':3,'recorded':2,'completed':1,'execution_errors':1,'without_terminal_record':1,'effective_success_count':1,'success':'1/2 (50.0%)','success_given_completion':'1/1 (100.0%)'}]}]}

def test_results_keep_registered_recorded_and_completed_denominators_distinct():
 report=valid();assert check(report)
 report['suite_results'][0]['rows'][0]['success']='1/3 (33.3%)'
 with pytest.raises(ValueError,match='denominator'):check(report)
 report=valid();report['counts']['registered']=4
 with pytest.raises(ValueError,match='totals'):check(report)

def test_missing_results_never_become_zero_percent_and_success_cannot_exceed_completion():
 report=valid();row=report['suite_results'][0]['rows'][0]
 row.update(recorded=0,completed=0,execution_errors=0,without_terminal_record=3,effective_success_count=0,success='未定义（分母为0）',success_given_completion='未定义（分母为0）')
 report['counts'].update(recorded=0,completed=0,execution_errors=0,without_terminal_record=3)
 assert check(report)
 row['success']='0/0 (0.0%)'
 with pytest.raises(ValueError,match='denominator'):check(report)
 report=valid();report['suite_results'][0]['rows'][0]['effective_success_count']=2
 with pytest.raises(ValueError,match='Inconsistent'):check(report)

"""Evidence-preserving checks for zh-Hans. Pattern matches are review signals."""
from __future__ import annotations
import collections
import hashlib
import json
import re
from dataclasses import dataclass, field
from .structure import structure_changes

RULE_VERSION = "0.2.0"
MODES = ('style', 'process', 'both')

@dataclass(frozen=True)
class Context:
    instruction: str = ''
    genre: str = 'project_documentation'
    audience: str = 'general'
    stage: str = 'final'
    delivery_channel: str = 'document'
    locale: str = 'zh-Hans'
    mode: str = 'both'
    profile: str = 'general-zh'
    source_bundle: dict = field(default_factory=dict)
    protected_spans: tuple = ()
    constraints: dict = field(default_factory=dict)
    voice_sample: str = ''

    def __post_init__(self):
        if self.mode not in MODES: raise ValueError('Unknown editing mode')
        if self.stage not in ('plan','progress','final','method','tutorial','explanation'): raise ValueError('Unknown delivery stage')
        if self.profile not in ('general-zh','editorial-zh'): raise ValueError('Unknown style profile')

    @classmethod
    def from_dict(cls, data):
        return cls(**{k:v for k,v in data.items() if k in cls.__dataclass_fields__})

    def public(self):
        return {k:getattr(self,k) for k in self.__dataclass_fields__}

def content_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def protected_ranges(text, explicit=()):
    ranges=[]
    # Offsets are Python Unicode code points; no normalization is applied.
    patterns=[r'\A---\r?\n.*?\r?\n---(?:\r?\n|$)',r'(?m)^(`{3,}|~{3,})[^\n]*\n[\s\S]*?^\1[^\n]*(?:\n|$)',r'`+[^`\n]+`+',r'(?m)^\s*>[^\n]*(?:\n|$)',r'https?://[^\s<>）]+',r'(?m)^\s*\|.*\|\s*$',r'(?m)^\s*[\[{][^\n]*[\]}]\s*$',r'[A-Za-z]:[\\/][^\s，。；]+',r'(?m)^\s*(?:\$ |PS> |>>> ).*$',r'[“「『][^”」』]*[”」』]']
    for pattern in patterns:
        ranges.extend((m.start(),m.end()) for m in re.finditer(pattern,text,re.S if pattern.startswith(r'\A') else 0))
    # Decode complete JSON containers rather than matching balanced braces with regex.
    # A line-start container with prose after its closing token is not a standalone block.
    decoder=json.JSONDecoder()
    for match in re.finditer(r'(?m)^[ \t]*([\[{])',text):
        start=match.start(1)
        try:value,end=decoder.raw_decode(text,start)
        except ValueError:continue
        line_end=text.find('\n',end)
        if line_end<0:line_end=len(text)
        if isinstance(value,(dict,list)) and not text[end:line_end].strip():
            ranges.append((start,end))
    for span in explicit:
        start,end=span['start'],span['end']
        if not 0<=start<end<=len(text):raise ValueError('Protected span outside input')
        if 'text' in span and text[start:end]!=span['text']:raise ValueError('Protected span text mismatch')
        ranges.append((start,end))
    return sorted(set(ranges))

def overlaps(start,end,ranges):
    return any(start<b and end>a for a,b in ranges)

def language_scope(text, locale='zh-Hans'):
    if locale!='zh-Hans': return 'unvalidated'
    ranges=protected_ranges(text)
    prose=''.join(c for i,c in enumerate(text) if not any(a<=i<b for a,b in ranges))
    han=len(re.findall(r'[\u3400-\u9fff]',prose))
    words=len(re.findall(r'[A-Za-z]{2,}',prose))
    if han==0:return 'unsupported' if words else 'unvalidated'
    # Technical nouns do not cancel Chinese syntax. Ambiguous mixtures abstain.
    if words>han*1.5:return 'unsupported'
    traditional=set('這個為與體學說開關實現資庫軟後發點應該無網絡將於讓從檢測')
    if sum(c in traditional for c in prose)>=max(2,han*0.025):return 'unvalidated'
    if han<8 and words>han:return 'unvalidated'
    return 'supported'

PROCESS_PATTERNS=[('structure_preview',r'(?:下面|接下来)(?:我|我们)?(?:先|将|会)?(?:分析|介绍|从[^。\n]{0,16}展开)[^。\n]*[。]?'),('self_evaluation',r'(?:以下是|这是一份)[^。\n]{0,20}(?:深入|可落地|高质量|完善)[^。\n]*[。]?'),('editing_residue',r'(?:我已(?:为你)?(?:去除|去掉|优化)[^。\n]*(?:AI味|AI 味|表达)|【(?:待补充|编辑备注|内部待办)[^】]*】|TODO[:：][^\n]*)')]
STYLE_PATTERNS=[('template_dependence',r'不是[^。\n]{1,60}[，,]?而是[^。\n]{1,60}'),('expression_efficiency',r'(?:赋能|闭环|抓手|底层逻辑|全方位|多维度|意义深远|至关重要)')]

def lint_text(text, context=None, profile=None):
    context=context or Context()
    status=language_scope(text,context.locale)
    if status!='supported':return {'language_scope_status':status,'status':'unchecked','issues':[],'rule_version':RULE_VERSION,'input_hash':content_hash(text)}
    ranges=protected_ranges(text,context.protected_spans);issues=[]
    active=[]
    if context.mode in ('process','both') and context.stage=='final':active.extend(('process',c,p) for c,p in PROCESS_PATTERNS)
    if context.mode in ('style','both'):active.extend(('style',c,p) for c,p in STYLE_PATTERNS)
    for suite,category,pattern in active:
        for m in re.finditer(pattern,text):
            if overlaps(m.start(),m.end(),ranges):continue
            issues.append({'start':m.start(),'end':m.end(),'text':m.group(),'category':category,'suite':suite,'severity':None,'rule':category,'action':'review','reason':'候选模式需结合任务语义判定；不是自动删词规则。','oracle_type':'programmatic_signal'})
    return {'language_scope_status':status,'status':'unchecked','issues':issues,'rule_version':RULE_VERSION,'input_hash':content_hash(text),'semantic_review_required':True}

def verify_edit(original,candidate,context=None,source_bundle=None):
    context=context or Context()
    reasons=[];scope=language_scope(original,context.locale)
    if scope!='supported':
        return {'status':'unchecked','language_scope_status':scope,'reasons':['language_out_of_scope'],'input_hash':content_hash(original),'candidate_hash':content_hash(candidate),'rule_version':RULE_VERSION}
    if not candidate.strip():reasons.append('empty_output')
    if language_scope(candidate,context.locale)!='supported':reasons.append('target_language_changed')
    protected=[original[a:b] for a,b in protected_ranges(original,context.protected_spans)]
    for value,count in collections.Counter(protected).items():
        if candidate.count(value)<count:reasons.append('protected_span_changed')
    structure = structure_changes(original, candidate, allow_heading_edits=context.constraints.get('allow_heading_edits') is True)
    if structure: reasons.append('document_structure_changed')
    # Conservative lexical signals can block pending semantic review, not prove all facts.
    numbers=lambda x:collections.Counter(re.findall(r'(?<![A-Za-z])\d+(?:\.\d+)?(?:%|％|万元|亿元|元|摄氏度|小时|天|年|月|日|个|台|次|人)?',x))
    if numbers(original)!=numbers(candidate):reasons.append('numeric_claim_changed')
    for term in ('不','未','仅','如果','除非','可能','预计','据','声称','尚未','并非'):
        if original.count(term)!=candidate.count(term):reasons.append('qualifier_change_requires_review');break
    if len(candidate.strip())<len(original.strip())*0.35:reasons.append('excessive_compression')
    if len(candidate)>max(40,len(original)*1.8):reasons.append('unsupported_expansion_risk')
    for required in context.constraints.get('literal_required',[]):
        if required not in candidate:reasons.append('required_literal_missing')
    max_chars=context.constraints.get('max_chars')
    if max_chars is not None and len(candidate)>max_chars:reasons.append('length_constraint')
    return {'status':'fail' if reasons else 'unchecked','language_scope_status':scope,'reasons':sorted(set(reasons)),'input_hash':content_hash(original),'candidate_hash':content_hash(candidate),'rule_version':RULE_VERSION,'semantic_review_required':True,'structure_changes':structure,'scope':'source_fidelity; not independent world-fact verification'}

PUBLIC_FIELDS=('id','source_group_id','suite','track','language','locale','source_language','is_translation','language_scope_status','genre','audience','stage','delivery_channel','instruction','style_profile','source_bundle','input_text','protected_spans','constraints')
def public_input(record):
    return {k:record[k] for k in PUBLIC_FIELDS if k in record}

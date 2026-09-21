"""Opaque transport identifiers prevent case names from hinting at labels."""
import hashlib

def opaque_id(value,namespace='annotation-v0.1.2'):
    return 'r'+hashlib.sha256((namespace+':'+value).encode()).hexdigest()[:24]

def blind_records(records,namespace='annotation-v0.1.2'):
    mapping={opaque_id(row['id'],namespace):row['id'] for row in records}
    if len(mapping)!=len(records):raise ValueError('Duplicate record identifiers')
    result=[]
    for row in records:
        item=dict(row);item['id']=opaque_id(row['id'],namespace)
        if 'source_group_id' in item:item['source_group_id']=opaque_id(item['source_group_id'],namespace+':family')
        result.append(item)
    return result,mapping

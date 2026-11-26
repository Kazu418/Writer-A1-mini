import json
import sqlite3
import zlib

import pytest

from plotnote.personal_metrics import geometry_digest
from plotnote.personal_ocr import audit, normalize_reading, page_readings, store_audit


def test_inline_ids_follow_reading_order_and_do_not_fold_confusables():
    page={'children':[{'html':'<p>PN-002: O</p><p>PN-001: <math>\\Sigma</math></p>'}]}
    assert page_readings(page)=={'PN-002':['O'],'PN-001':['Σ']}
    assert normalize_reading(' O ')!='0'
    assert normalize_reading('平 均')=='平均'


def test_multichar_missing_and_duplicate_are_not_agreements():
    manifest={'pages':[{'page_index':0,'glyphs':[
        {'trial_id':'PN-001','expected_label':'均'},
        {'trial_id':'PN-002','expected_label':'生'},
        {'trial_id':'PN-003','expected_label':'数'}]}]}
    result={'json':{'children':[{'id':'/page/0/Page/0','children':[
        {'html':'PN-001: 平均'},{'html':'PN-003: 数'},{'html':'PN-003: 数'}]}]}}
    rows=audit(manifest,result)['rows']
    assert [r['ocr_status'] for r in rows]==['multiple_or_unreadable','missing','ambiguous']
    # A duplicate ID must never be treated as a single unambiguous agreement.
    assert len(rows[2]['all_readings'])==2


def test_evidence_import_preserves_geometry_and_decisions_and_rejects_stale():
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE exemplars(id TEXT PRIMARY KEY,label TEXT,status TEXT,payload BLOB)')
    sample={'book':'b','page':'p','paths':[[[0,0],[1,2]]],'stroke_ids':['s']}
    packed=zlib.compress(json.dumps(sample).encode())
    db.execute('INSERT INTO exemplars VALUES (?,?,?,?)',('id','字','accepted',packed))
    row={'exemplar_id':'id','expected_label':'字','geometry_sha256':geometry_digest(sample),
         'reading':'宇','ocr_status':'different_single'}
    store_audit(db,[row],'job')
    assert db.execute('SELECT label,status,payload FROM exemplars').fetchone()==('字','accepted',packed)
    row['geometry_sha256']='changed'
    with pytest.raises(ValueError,match='geometry changed'):
        store_audit(db,[row],'other')
    assert db.execute('SELECT count(*) FROM independent_ocr').fetchone()[0]==1

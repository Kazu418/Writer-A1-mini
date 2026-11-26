from copy import deepcopy
import json
import sqlite3
import zlib

import pytest
from plotnote.personal_capture import extract_cells,store_samples
from plotnote.personal_font import export_library,text_page
from plotnote.personal_review import review
from plotnote.cli import export_pages


def sheet():
    return {'sheet_id':'test','page_pt':[100,200],'cells':[
        {'cell_id':'A','label':'授','ink_rect_normalized':[.1,.1,.4,.4]},
        {'cell_id':'B','label':'頻','ink_rect_normalized':[.6,.1,.9,.4]}]}


def extract(strokes):
    return extract_cells(strokes,(1000,2000),sheet(),book='mine.goodnotes',page='p',archive_sha='hash')


def test_known_cells_keep_original_points_and_source_ids_without_approving():
    ink=[{'id':'one','points':[[150,300],[250,500]]},
         {'id':'tap','points':[[170,450]]},
         {'id':'outside','points':[[50,1500],[80,1600]]}]
    original=deepcopy(ink);samples,report=extract(ink)
    assert ink==original
    assert samples[0]['paths']==[ink[0]['points'],ink[1]['points']]
    assert samples[0]['stroke_ids']==['one','tap']
    assert samples[0]['label']=='授' and samples[0]['label_status']=='unreviewed'
    assert report=={'missing_cells':['B'],'outside_strokes_ignored':1,'samples':1,'labels_approved':0}


@pytest.mark.parametrize('points',[[[50,500],[500,500]],[[150,300],[700,500]]])
def test_crossing_stroke_is_rejected_whole_even_when_endpoints_are_outside(points):
    with pytest.raises(ValueError,match='crosses'):
        extract([{'id':'cross','points':points}])


def test_capture_resume_preserves_review_and_taps_survive_existing_gcode(tmp_path,profile):
    samples,_=extract([{'id':'one','points':[[150,300],[250,500]]},
                       {'id':'tap','points':[[170,450]]}])
    db=sqlite3.connect(':memory:')
    assert store_samples(db,samples)==1
    with pytest.raises(ValueError,match='No confirmed'):
        export_library(db,tmp_path/'font.json')
    review(db,samples[0]['id'],'授','accepted')
    assert store_samples(db,samples)==0
    font=export_library(db,tmp_path/'font.json')
    glyph=font['glyphs']['授'][0]
    assert glyph['original_paths']==samples[0]['paths']
    assert len(glyph['paths'][1])==2 and glyph['paths'][1][0]==glyph['paths'][1][1]
    assert glyph['path_adaptations'][0]['path_index']==1
    page=text_page('授',font)
    export_pages([page],profile,tmp_path/'gcode',homed=True)
    result=json.loads((tmp_path/'gcode/validation.json').read_text())['pages'][0]
    assert result['valid'] and result['source_geometry_checked'] and result['strokes']==2


def test_wrong_page_scale_is_not_silently_guessed():
    with pytest.raises(ValueError,match='aspect ratio'):
        extract_cells([],(2000,1000),sheet(),book='b',page='p',archive_sha='h')

import importlib.util
import json
from pathlib import Path
import sys

import pytest

spec=importlib.util.spec_from_file_location('datalab_client',Path(__file__).parents[1]/'scripts/datalab_ocr.py')
client=importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


@pytest.mark.parametrize('count,mode',[(500,'fast'),(501,'lite')])
def test_count_policy_and_completed_job_resume_never_reposts(tmp_path,monkeypatch,count,mode):
    image=tmp_path/'blind.png';image.write_bytes(b'local trial bytes')
    state=tmp_path/'job.json';calls=[]
    def request(url,fields=None,source=None,authenticated=True):
        calls.append((url,fields))
        if fields is not None:
            return {'request_id':'one','request_check_url':'https://www.datalab.to/api/v1/check/one'}
        return {'status':'complete','success':True,'markdown':'PN-001: 字'}
    monkeypatch.setattr(client,'request',request)
    monkeypatch.setattr(sys,'argv',['client',str(image),'--state',str(state),'--planned-pages',str(count)])
    client.main();client.main()
    assert len(calls)==2
    assert calls[0][1]['mode']==mode
    assert calls[0][1].get('exact_transcription')==('true' if mode=='fast' else None)
    assert json.loads(state.read_text())['status']=='complete'


def test_uncertain_post_is_not_retried(tmp_path,monkeypatch):
    image=tmp_path/'blind.png';image.write_bytes(b'trial')
    state=tmp_path/'job.json';calls=[]
    def request(*args,**kwargs):
        calls.append(args)
        raise RuntimeError('upload timeout')
    monkeypatch.setattr(client,'request',request)
    monkeypatch.setattr(sys,'argv',['client',str(image),'--state',str(state),'--planned-pages','319'])
    with pytest.raises(RuntimeError,match='timeout'):client.main()
    with pytest.raises(RuntimeError,match='may have been accepted'):client.main()
    assert len(calls)==1


@pytest.mark.parametrize('url',['http://www.datalab.to/x','https://other.test/x',
    'https://www.datalab.to.evil.test/x','https://user@www.datalab.to/x'])
def test_credentials_only_go_to_expected_https_host(url):
    with pytest.raises(ValueError):client.authenticated_url(url)


def test_processing_failure_cannot_be_saved_as_completed(tmp_path,monkeypatch):
    image=tmp_path/'blind.png';image.write_bytes(b'trial')
    state=tmp_path/'job.json'
    responses=iter([{'request_check_url':'https://www.datalab.to/check/one'},
                    {'status':'complete','success':False,'error':'failed'}])
    monkeypatch.setattr(client,'request',lambda *a,**kw:next(responses))
    monkeypatch.setattr(sys,'argv',['client',str(image),'--state',str(state),'--planned-pages','319'])
    with pytest.raises(RuntimeError,match='failed'):client.main()
    assert json.loads(state.read_text())['status']=='failed'
    assert not state.with_suffix('.result.json').exists()

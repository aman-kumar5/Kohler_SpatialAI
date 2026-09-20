import os
from app.ai import with_gemini_failover

def test_uses_second_key_when_first_fails(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEYS','first-key, second-key')
    attempts=[]
    def operation(key):
        attempts.append(key)
        if key=='first-key': raise RuntimeError('quota exceeded')
        return 'success'
    assert with_gemini_failover(operation)=='success'
    assert attempts==['first-key','second-key']

def test_does_not_call_second_key_after_success(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEYS','first-key,second-key')
    attempts=[]
    assert with_gemini_failover(lambda key: attempts.append(key) or 'success')=='success'
    assert attempts==['first-key']

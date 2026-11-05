"""Recognize llama.cpp's explicit output-parser rejection; never repair model output."""
import json

PARSER_MESSAGE='does not match the expected peg-native format'

def read_output_parser_error(error):
    if error.code!=500:raise error
    try:value=json.loads(error.read().decode('utf-8'))
    except (ValueError,UnicodeDecodeError):raise error
    if not isinstance(value,dict) or not isinstance(value.get('error'),dict):raise error
    if value['error'].get('code')!=500 or PARSER_MESSAGE not in value['error'].get('message',''):raise error
    return value

def is_output_parser_error(raw):
    error=raw.get('response',{}).get('error',{})
    return raw.get('http_status')==500 and isinstance(error,dict) and error.get('code')==500 and PARSER_MESSAGE in error.get('message','')

def failure_fields(raw):
    assert is_output_parser_error(raw)
    return {'passed':False,'finish_reason':None,'reasoning_observed':None,'usage':None,
            'server_output_parser_error':True,'api_error':raw['response']['error'],
            'statistics_note':'Generation statistics and final/reasoning channels were not returned by the server.'}

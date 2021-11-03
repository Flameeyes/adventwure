from __future__ import print_function
# Copyright (c) 2016-2021 Twilio Inc.

import os

from twilio import twiml
from flask import Flask, request, jsonify, Request
from werkzeug.datastructures import ImmutableOrderedMultiDict

from state import run_for

class MyRequest(Request):
    """Request subclass to override request parameter storage"""
    parameter_storage_class = ImmutableOrderedMultiDict


class MyFlask(Flask):
    """Flask subclass using the custom request class"""
    request_class = MyRequest


app = MyFlask(__name__)

sid = os.getenv('TWILIO_SID')
token = os.getenv('TWILIO_TOKEN')
from_num = os.getenv('TWILIO_NUMBER')


@app.route("/incoming-voice", methods=['GET', 'POST'])
def voice_reply():
    print('Form', request.form)
    from_ = request.form['DialogueSid'][2:34]
    inp = ''
    if 'Field_word1_Value' in request.form:
      inp += ' ' + request.form.getlist('Field_word1_Value')[-1]
    if 'Field_word2_Value' in request.form and len((request.values.get('CurrentInput') or '').split(' ')) > 1:
            inp += ' ' + request.form.getlist('Field_word2_Value')[-1]
    inp = inp.strip()[:20]
    if inp == '':
        inp = request.values.get('CurrentInput') or ''
    inp = inp.strip().upper().replace('.', '').replace(',', '')
    inp = str(inp)
    print('Recognized input %s' % inp)

    text = run_for(from_, inp)
    print('Output %s' % text)
    actions = []
    if inp:
        text = 'I heard ' + inp + '. ' + text
    actions.append({'say': {'speech': text}})
    actions.append({'listen': True})
    resp = {'actions': actions}
    return jsonify(resp)

@app.route("/incoming-sms", methods=['GET', 'POST'])
def sms_reply():
    from_ = str(request.values.get('From'))
    inp = str(request.values.get('Body', ''))
    text = run_for(from_, inp)
    resp = twiml.Response()
    resp.message(text)
    return str(resp)

@app.route('/')
def hello_world():
    return 'Hello, World!'

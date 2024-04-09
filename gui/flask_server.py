import imp
import json
import time

import pyaudio
from flask import Flask, render_template, request
from flask_cors import CORS

import booter

from utils.tts_voice import EnumVoice
from gevent import pywsgi
from utils.thread_manager import MyThread
from utils import config_util, util
from utils import wsa_server
from core import control
from db import content_db
from input_process import yolov8


__app = Flask(__name__)
CORS(__app, supports_credentials=True)


def __get_template():
    return render_template('index.html')


def __get_device_list():
    audio = pyaudio.PyAudio()
    device_list = []
    for i in range(audio.get_device_count()):
        devInfo = audio.get_device_info_by_index(i)
        if devInfo['hostApi'] == 0:
            device_list.append(devInfo["name"])
    
    return list(set(device_list))


@__app.route('/api/submit', methods=['post'])
def api_submit():
    data = request.values.get('data')
    # print(data)
    config_data = json.loads(data)
    if(config_data['config']['source']['record']['enabled']):
        config_data['config']['source']['record']['channels'] = 0
        audio = pyaudio.PyAudio()
        for i in range(audio.get_device_count()):
            devInfo = audio.get_device_info_by_index(i)
            if devInfo['name'].find(config_data['config']['source']['record']['device']) >= 0 and devInfo['hostApi'] == 0:
                 config_data['config']['source']['record']['channels'] = devInfo['maxInputChannels']

    config_util.save_config(config_data['config'])


    return '{"result":"successful"}'

@__app.route('/api/control-eyes', methods=['post'])
def control_eyes():
    eyes = yolov8.new_instance()
    if(not eyes.get_status()):
       eyes.start()
       util.log(1, "YOLO v8正在启动...")
    else:
       eyes.stop()
       util.log(1, "YOLO v8正在关闭...")
    return '{"result":"successful"}'


@__app.route('/api/get-data', methods=['post'])
def api_get_data():
    config_data = config_util.config
    if  wsa_server.new_instance().isConnect:
        config_data['interact']['playSound'] = False
    else:
        config_data['interact']['playSound'] = True
    config_util.save_config(config_data)
    wsa_server.get_web_instance().add_cmd({
        "voiceList": [
            {"id": EnumVoice.XIAO_XIAO.name, "name": "晓晓"},
            {"id": EnumVoice.YUN_XI.name, "name": "云溪"},
            {"id": EnumVoice.YUN_JIAN.name, "name": "云健"},
            {"id": EnumVoice.XIAO_YI.name, "name": "晓伊"},
            {"id": EnumVoice.YUN_YANG.name, "name": "云阳"},
            {"id": EnumVoice.YUN_XIA.name, "name": "云夏"}
            
        ]
    })
    wsa_server.get_web_instance().add_cmd({"deviceList": __get_device_list()})
    return json.dumps({'config': config_util.config})


@__app.route('/api/start-live', methods=['post'])
def api_start_live():
    # time.sleep(5)
    booter.start()
    time.sleep(1)
    wsa_server.get_web_instance().add_cmd({"liveState": 1})
    return '{"result":"successful"}'


@__app.route('/api/stop-live', methods=['post'])
def api_stop_live():
    # time.sleep(1)
    booter.stop()
    time.sleep(1)
    wsa_server.get_web_instance().add_cmd({"liveState": 0})
    return '{"result":"successful"}'

@__app.route('/api/send', methods=['post'])
def api_send():
    data = request.values.get('data')
    info = json.loads(data)
    text = control.send_for_answer(info['msg'],info['sendto'])
    return '{"result":"successful","msg":"'+text+'"}'

@__app.route('/api/get-msg', methods=['post'])
def api_get_Msg():
    contentdb = content_db.new_instance()
    list = contentdb.get_list('all','desc',1000)
    relist = []
    i = len(list)-1
    while i >= 0:
        relist.append(dict(type=list[i][0],way=list[i][1],content=list[i][2],createtime=list[i][3],timetext=list[i][4]))
        i -= 1

    return json.dumps({'list': relist})


@__app.route('/api/send/v1/chat/completions', methods=['post'])
def api_send_v1_chat_completions():
    data = request.json  # 解析JSON数据
    # 检查'messages'键是否存在于数据中
    last_content = ""
    if 'messages' in data and data['messages']:
        last_message = data['messages'][-1]  # 获取最后一条消息
        last_content = last_message.get('content', 'No content provided')  # 获取'content'字段
    else:
        last_content = 'No messages found'
    text = control.send_for_answer("主人文字说了：" + last_content)
    return {
  "id": "chatcmpl-8jqorq6Fw1Vi5XoH7pddGGpQeuPe0",
  "object": "chat.completion",
  "created": 1705938489,
  "model": "ben-agent",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": text
      },
      "logprobs": "",
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": len(last_content),
    "completion_tokens": len(text),
    "total_tokens": len(last_content) + len(text)
  },
  "system_fingerprint": "fp_04de91a479"
}



@__app.route('/', methods=['get'])
def home_get():
    return __get_template()


@__app.route('/', methods=['post'])
def home_post():
    return __get_template()

def run():
    server = pywsgi.WSGIServer(('0.0.0.0',5000), __app)
    server.serve_forever()

def start():
    MyThread(target=run).start()

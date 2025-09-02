import zmq
import json

zmq_ctx = zmq.Context()
socket = zmq_ctx.socket(zmq.PUSH)
socket.connect("tcp://127.0.0.1:5555")

def send(dict):
    socket.send_string(json.dumps(dict))

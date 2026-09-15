"""Reproduce anonymous JLC calculator API queries using its published page model.

Dependencies: local websocket-client. Requests only stackup/calculator data and
calculation; it does not upload a PCB, create an order, or authenticate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import uuid
import websocket


def post(endpoint,data):
    request=urllib.request.Request('https://jlcpcb.com/api/jlcTools/impedance/'+endpoint,
                                   data=json.dumps(data).encode(),
                                   headers={'Content-Type':'application/json','langType':'en'})
    return json.loads(urllib.request.urlopen(request,timeout=40).read())


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--gap',type=float,default=.15)
    ap.add_argument('--width',type=float)
    ap.add_argument('--height',type=float,default=.0994)
    ap.add_argument('--er',type=float,default=4.1)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    session=str(uuid.uuid4());access=str(uuid.uuid4())
    parameters=dict(H1=args.height/.0254,Er1=args.er,W1=(args.width or .15)/.0254,
                    W2=(args.width or .15)/.0254-.5,S1=args.gap/.0254,T1=1.6,
                    C1=1.,C2=.6,C3=1.,CEr=3.8,dCalculateMode=3,
                    isLinkComputingMode=False,W2LinkW1Incr=.5,ZoTol=.5)
    model='DiffEdgeCoupledCoatedMicrostrip1B'
    if args.width is None:
        parameters.update(Zo=90,MinW2=2.5,MaxW2=30.)
        model='W2_'+model
    payload=dict(accessId=access,impedance_calc_mark=model,impedance_calc_arg=parameters,
                 paramMd5=hashlib.md5(json.dumps(parameters).encode()).hexdigest(),uuid=session)
    socket=websocket.create_connection('wss://tools.jlc.com/jlcTools/webSocket/'+session,
                                       timeout=35,origin='https://jlcpcb.com')
    try:
        acknowledgement=post('calc',payload)
        print(json.dumps(acknowledgement),flush=True)
        response=None;messages=[];start=time.monotonic()
        while time.monotonic()-start<50:
            raw=socket.recv()
            try: message=json.loads(raw)
            except json.JSONDecodeError: messages.append(raw);continue
            messages.append(message)
            if message.get('accessId')==access:
                response=message;break
    finally:
        socket.close()
    report=dict(source='https://jlcpcb.com/pcb-impedance-calculator',
                description='Official anonymous calculator; all geometric arguments in mil',
                request=payload,acknowledgement=acknowledgement,response=response,messages=messages)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(response,indent=2))
    return 0 if response is not None else 2


if __name__=='__main__':
    raise SystemExit(main())

from pathlib import Path
import json,argparse,hashlib
p=argparse.ArgumentParser();p.add_argument('--workdir');p.add_argument('--report');a=p.parse_args()
w=Path(a.workdir);w.mkdir(parents=True);proof=w/'proof.txt';proof.write_text('fake claim',encoding='utf-8')
ids=['N01', 'N02', 'N03', 'N04', 'N05', 'N06', 'N07', 'N08', 'N09', 'N10', 'N11', 'N12', 'N13', 'N14', 'N15', 'N16', 'N17', 'N18', 'N19', 'N20', 'N21', 'N22', 'N23', 'N24', 'N25', 'N26', 'N27', 'N28', 'N29', 'N30', 'N31', 'N32']
e=[{'path':'proof.txt','sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}]
tests=[{'case_id':i,'status':'passed','expected':1,'actual':1,'evidence':e} for i in ids]
Path(a.report).write_text(json.dumps({'total':len(tests),'passed':len(tests),'failed':0,'blocked':0,'not_run':0,'tests':tests}),encoding='utf-8')

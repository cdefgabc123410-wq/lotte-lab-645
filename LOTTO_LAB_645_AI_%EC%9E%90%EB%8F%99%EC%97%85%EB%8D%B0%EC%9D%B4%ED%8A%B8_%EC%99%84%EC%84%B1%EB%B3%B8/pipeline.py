"""1회~최신 데이터를 대상으로 전체 순차 검증과 최종 AI 모델 점수 캐시를 갱신한다."""
from __future__ import annotations
import argparse
import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile

from model_core import read_data, backtest, final_scores, summarize
from updater import DATA_PATH, update

ROOT=Path(__file__).resolve().parent
BT_PATH=ROOT/'data/backtest_walk_forward.csv'
SCORES_PATH=ROOT/'data/model_scores.json'
STATUS_PATH=ROOT/'data/update_status.json'


def atomic_bytes(path, data):
    path=Path(path)
    descriptor,name=tempfile.mkstemp(prefix='.lotto-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as f:f.write(data)
        Path(name).replace(path)
    finally:
        if Path(name).exists():Path(name).unlink()


def rebuild(force=False, online=False, session=None, data_path=DATA_PATH, output_dir=None):
    data_path=Path(data_path)
    out=Path(output_dir) if output_dir else data_path.parent
    out.mkdir(parents=True,exist_ok=True)
    bt_path=out/'backtest_walk_forward.csv'
    scores_path=out/'model_scores.json'
    status_path=out/'update_status.json'
    result={'added':0}
    if online:
        result=update(data_path,session=session)
    df=read_data(data_path)
    N=len(df)
    built=force or result['added']>0 or not (bt_path.exists() and scores_path.exists() and status_path.exists())
    if built:
        bt=backtest(df,start=300,retrain_interval=100)
        scores=final_scores(df)
        now=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
        status={'latest_round':int(df.drwNo.iloc[-1]),'latest_draw_date':df.drwNoDate.iloc[-1].date().isoformat(),
                'model_round':int(df.drwNo.iloc[-1]),'built_at_utc':now,
                'backtest_first_round':301,'backtest_round_count':int(N-300),
                'models':['logistic','forest','freq30','freq100','random'],
                'training':'첫 300회 확보, 회차 301부터 순차 검증; ML은 100회마다 이전 데이터로만 재학습',
                'source':'동행복권 공식 사이트 조회 결과 + 최초 사용자 제공 CSV',
                'added_this_build':result['added']}
        # Snapshot files are fully calculated before replacement; commit them as one git change-set.
        atomic_bytes(bt_path,bt.to_csv(index=False).encode('utf-8-sig'))
        atomic_bytes(scores_path,json.dumps({'as_of_round':N,'model_scores':scores,'generated_utc':now},ensure_ascii=False,indent=2).encode('utf-8'))
        atomic_bytes(status_path,json.dumps(status,ensure_ascii=False,indent=2).encode('utf-8'))
        print(summarize(bt).to_string(index=False))
    else:
        status=json.loads(status_path.read_text(encoding='utf-8'))
        if status['model_round']!=N:
            raise RuntimeError('모델 캐시가 최신 당첨번호와 다릅니다. --force 로 재빌드하세요.')
    print(json.dumps({'changed':built,'added':result['added'],'latest':N,'test_rounds':N-300},ensure_ascii=False))
    return {'changed':built,'added':result['added'],'latest':N}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--online',action='store_true',help='공식 사이트에서 새 회차 수집')
    p.add_argument('--force',action='store_true',help='데이터 변경이 없어도 모델·백테스트 재생성')
    args=p.parse_args()
    rebuild(force=args.force,online=args.online)

"""동행복권 2026년 개편 API로 새 로또 당첨 회차를 안전하게 수집한다.

실패 시 기존 CSV는 변경하지 않는다. API는 공식 페이지의 미문서화 JSON 엔드포인트로
변경/차단될 수 있으므로 HTTP/JSON/번호/날짜/회차 연속성을 모두 검사한다.
"""
from __future__ import annotations
import argparse
import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from model_core import COLS, NUM_COLS, read_data

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / 'data' / 'lotto_results.csv'
ENDPOINT = 'https://www.dhlottery.co.kr/lt645'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; LottoLab645/2.0; weekly-public-results-check)',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.dhlottery.co.kr/lt645/result',
}


def make_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1.0, status_forcelist=[429,500,502,503,504],
                    allowed_methods={'GET'})
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.headers.update(HEADERS)
    return session


def fetch_list(session, path, params=None):
    url = ENDPOINT + path
    response = session.get(url, params=params, timeout=(7, 20))
    response.raise_for_status()
    ct = response.headers.get('Content-Type','').lower()
    if 'json' not in ct:
        raise RuntimeError(f'공식 데이터 조회가 JSON 대신 {ct or "알 수 없는 형식"}을 반환했습니다. 기존 데이터를 유지합니다.')
    try:
        payload = response.json()
        items = payload['data']['list']
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError('공식 응답 형식이 변경되었거나 데이터가 없습니다.') from exc
    if not isinstance(items,list) or not items:
        raise RuntimeError('공식 응답에 발표된 당첨번호가 없습니다.')
    return items


def normalize_record(item):
    try:
        draw_no=int(item['ltEpsd'])
        ymd=str(item['ltRflYmd'])
        parsed=dt.datetime.strptime(ymd,'%Y%m%d').date()
        main=[int(item[f'tm{i}WnNo']) for i in range(1,7)]
        bonus=int(item['bnsWnNo'])
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError('당첨결과의 필수 항목이 누락되었거나 잘못되었습니다.') from exc
    if draw_no<1 or len(set(main))!=6 or not all(1<=x<=45 for x in main) or bonus in main or not (1<=bonus<=45):
        raise ValueError(f'{draw_no}회차 당첨번호가 6/45 규칙에 어긋납니다.')
    if parsed.weekday()!=5:
        raise ValueError(f'{draw_no}회차 추첨 날짜가 토요일이 아닙니다: {parsed}')
    if parsed > dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date():
        raise ValueError(f'{draw_no}회차 추첨일이 아직 미래입니다: {parsed}')
    out={'drwNo':draw_no,'drwNoDate':parsed.isoformat()}
    out.update({f'n{i}':n for i,n in enumerate(sorted(main),1)})
    out['bonus']=bonus
    for rank,name in ((1,'first'),(2,'second'),(3,'third'),(4,'fourth'),(5,'fifth')):
        for col,source in ((f'{name}Winamnt',f'rnk{rank}WnAmt'),(f'{name}PrzwnerCo',f'rnk{rank}WnNope')):
            val=item.get(source)
            out[col]=int(val) if val is not None and str(val).strip() else ''
    val=item.get('wholEpsdSumNtslAmt')
    out['totSellamnt']=int(val) if val is not None and str(val).strip() else ''
    return out


def fetch_updates(session, existing, sleep_seconds=1.0):
    old_count=len(existing)
    old_latest=int(existing.drwNo.max())
    old_date=existing.drwNoDate.max().date()
    recent_items=fetch_list(session,'/selectPstLt645Info.do')
    latest=max([normalize_record(v) for v in recent_items],key=lambda r:r['drwNo'])
    latest_no=latest['drwNo']
    if latest_no<=old_latest:
        if latest_no==old_latest:
            stored=existing.loc[existing.drwNo==old_latest].iloc[0]
            nums=[int(stored[c]) for c in NUM_COLS]
            if nums != [latest[c] for c in NUM_COLS] or int(stored.bonus)!=latest['bonus']:
                raise RuntimeError('공식 데이터와 저장된 마지막 회차가 다릅니다. 수동 확인이 필요합니다.')
        return []
    if latest_no-old_latest>16:
        raise RuntimeError('16회 이상 누락: 무단 대량 동기화를 막았습니다. 수동 확인 후 재실행하세요.')
    additions={latest_no:latest}
    for n in range(old_latest+1,latest_no):
        items=fetch_list(session,'/selectPstLt645InfoNew.do',{'srchDir':'center','srchLtEpsd':n})
        matching=[r for r in items if int(r.get('ltEpsd',-1))==n]
        if not matching:
            raise RuntimeError(f'{n}회차 공식 결과가 아직 없습니다. 기존 데이터를 유지합니다.')
        additions[n]=normalize_record(matching[0])
        if sleep_seconds: time.sleep(sleep_seconds)
    rows=[additions[n] for n in range(old_latest+1,latest_no+1)]
    check_date=old_date
    for row in rows:
        d=dt.date.fromisoformat(row['drwNoDate'])
        if not (5 <= (d-check_date).days <= 9):
            raise RuntimeError(f'회차별 추첨 날짜 간격에 문제가 있습니다: {row["drwNo"]}회')
        check_date=d
    return rows


def save_atomic(df, path):
    """CSV가 쓰다 실패해도 기존 파일이 보존되게 같은 폴더에서 원자적 교체."""
    path=Path(path)
    descriptor, name=tempfile.mkstemp(prefix='.lotto-',suffix='.csv',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8-sig',newline='') as handle:
            df.to_csv(handle,index=False)
        Path(name).replace(path)
    finally:
        if Path(name).exists(): Path(name).unlink()


def update(path=DATA_PATH,session=None,sleep_seconds=1.0):
    path=Path(path)
    existing=read_data(path)      # validates original CSV, including missing rounds
    raw=pd.read_csv(path,encoding='utf-8-sig')
    updates=fetch_updates(session or make_session(),existing,sleep_seconds=sleep_seconds)
    if not updates:
        return {'added':0,'latest':int(existing.drwNo.max()),'date':str(existing.drwNoDate.iloc[-1].date())}
    new=pd.concat([raw,pd.DataFrame(updates)],ignore_index=True)
    new=new.sort_values('drwNo',ascending=False).reset_index(drop=True)
    # 금액 필드는 결측값이 있어도 기존 정수값을 소수점 없이 보존한다.
    for column in [c for c in new.columns if c not in COLS]:
        new[column]=pd.to_numeric(new[column],errors='coerce').astype('Int64')
    # Check full final data in memory before mutating original CSV.
    check=read_data(new.to_csv(index=False).encode('utf-8-sig'))
    if len(check)!=len(existing)+len(updates):
        raise RuntimeError('추가된 회차의 연속성 검증에 실패했습니다.')
    save_atomic(new,path)
    return {'added':len(updates),'latest':int(check.drwNo.max()),'date':str(check.drwNoDate.iloc[-1].date())}


if __name__=='__main__':
    p=argparse.ArgumentParser(description='동행복권 최신 회차 안전 수집')
    p.add_argument('--data',type=Path,default=DATA_PATH)
    args=p.parse_args()
    result=update(args.data)
    print(json.dumps(result,ensure_ascii=False))

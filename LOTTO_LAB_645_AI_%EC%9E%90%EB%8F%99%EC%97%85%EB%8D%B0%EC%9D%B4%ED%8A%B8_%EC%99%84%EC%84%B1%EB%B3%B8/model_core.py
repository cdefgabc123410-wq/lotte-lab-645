"""Lotto 6/45 research app: no probability advantage implied.

All features for draw t use only draws <t. In walk-forward validation,
models are re-fitted on labels from strictly earlier rounds.
"""
from __future__ import annotations
import io
import hashlib
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

NUM_COLS = [f'n{i}' for i in range(1,7)]
COLS = ['drwNo','drwNoDate',*NUM_COLS,'bonus']
MODEL_LABELS = {"logistic":"AI · 로지스틱 회귀", "forest":"AI · 랜덤 포레스트", "freq30":"빈도형 · 직전 30회", "freq100":"빈도형 · 직전 100회", "random":"무작위 기준"}
FEATURE_NAMES = ["최근 5회 빈도", "최근 10회 빈도", "최근 30회 빈도", "최근 100회 빈도", "직전 등장 간격", "직전 회차 출현", "2회 전 출현", "최근-장기 빈도 차", "전체 출현 비율"]

def read_data(obj):
    """Read official-style CSV, retaining valid unique contiguous rounds."""
    if isinstance(obj, (str, Path)):
        df = pd.read_csv(obj, encoding='utf-8-sig')
    else:
        df = pd.read_csv(io.BytesIO(obj), encoding='utf-8-sig')
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise ValueError('데이터 파일에 필요한 열이 없어요: ' + ', '.join(missing))
    df = df[COLS].copy()
    for c in ['drwNo',*NUM_COLS,'bonus']:
        df[c] = pd.to_numeric(df[c], errors='raise').astype(int)
    df['drwNoDate'] = pd.to_datetime(df['drwNoDate'], errors='raise')
    df = df.sort_values('drwNo').reset_index(drop=True)
    rounds=df.drwNo.to_numpy()
    if len(df) < 350 or not np.array_equal(rounds, np.arange(1, int(rounds[-1])+1)):
        raise ValueError('1회부터 빠짐없이 이어지는 350회차 이상의 데이터가 필요해요.')
    a=df[NUM_COLS].to_numpy(dtype=int)
    if (a < 1).any() or (a > 45).any() or (df['bonus'].to_numpy() < 1).any() or (df['bonus'].to_numpy() >45).any():
        raise ValueError('번호가 1~45 범위를 벗어났어요.')
    if np.any(np.diff(np.sort(a,axis=1),axis=1)==0):
        raise ValueError('한 회차 내 본번호가 중복돼요.')
    if np.any((a == df['bonus'].to_numpy()[:,None]).any(axis=1)):
        raise ValueError('보너스 번호가 본번호와 중복돼요.')
    return df

def feature_matrix(draws):
    """Returns X[t, number, feature] for target draw t; draws shape N x 6."""
    N=len(draws)
    hits=np.zeros((N,45),dtype=np.float64)
    rr=np.arange(N)[:,None]
    hits[rr, draws-1]=1.0
    prefix=np.vstack([np.zeros((1,45)),np.cumsum(hits,axis=0)])
    X=np.zeros((N+1,45,len(FEATURE_NAMES)),dtype=np.float32)
    gap=np.full(45,100.,dtype=np.float64)
    for t in range(N+1):
        for i,k in enumerate([5,10,30,100]):
            X[t,:,i]=(prefix[t]-prefix[max(0,t-k)])/float(min(k,max(1,t)))
        X[t,:,4]=np.minimum(gap,100)/100.
        X[t,:,5]=hits[t-1] if t>=1 else 0
        X[t,:,6]=hits[t-2] if t>=2 else 0
        X[t,:,7]=X[t,:,1]-X[t,:,3]
        X[t,:,8]=prefix[t]/max(1,t)
        if t<N:
            gap=np.minimum(gap+1,100.)
            gap[draws[t]-1]=1
    return X, hits

def make_model(key, seed=1234):
    if key=='logistic':
        return LogisticRegression(solver='liblinear',C=0.12,max_iter=120, random_state=seed)
    if key=='forest':
        return RandomForestClassifier(n_estimators=55,max_depth=7,min_samples_leaf=65,
                                      max_features=0.7,n_jobs=-1,random_state=seed)
    raise ValueError(key)

def fit_model(X,hits,key,end_t, train_from=120):
    if end_t <=train_from:
        raise ValueError('학습 데이터가 부족해요.')
    # labels of rounds [train_from, end_t), predicting target end_t
    z=X[train_from:end_t].reshape(-1,X.shape[-1]); y=hits[train_from:end_t].reshape(-1).astype(int)
    model=make_model(key)
    model.fit(z,y)
    return model

def top6(scores,t,tag):
    # Stable seeded random tie-breaking, without preference for low numbers.
    seed=int(hashlib.sha256(f'{tag}:{t}'.encode()).hexdigest()[:8],16)
    jitter=np.random.default_rng(seed).random(45)*1e-8
    return tuple(sorted((np.argsort(scores+jitter)[-6:]+1).tolist()))

def backtest(df, start=300, retrain_interval=100):
    """Walk-forward train/test: no future draw in any training set.

    Refit model at start and every 100 draws using strictly earlier known results.
    """
    draws=df[NUM_COLS].to_numpy(dtype=int)
    X,hits=feature_matrix(draws)
    rng=np.random.default_rng(20261029)
    rows=[]
    models={}
    for t in range(start,len(df)):
        if t==start or (t-start)%retrain_interval==0:
            models={key:fit_model(X,hits,key,t) for key in ('logistic','forest')}
        actual=set(draws[t]); bonus=int(df.bonus.iloc[t])
        choices={
           'logistic':top6(models['logistic'].predict_proba(X[t])[:,1],t,'logistic'),
           'forest':top6(models['forest'].predict_proba(X[t])[:,1],t,'forest'),
           'freq30':top6(X[t,:,2],t,'freq30'),
           'freq100':top6(X[t,:,3],t,'freq100'),
           'random':tuple(sorted(rng.choice(np.arange(1,46),size=6,replace=False).tolist())),
        }
        for key,picks in choices.items():
            overlap=len(actual.intersection(picks))
            bonus_hit=(bonus in picks)
            grade = ('1등' if overlap==6 else '2등' if overlap==5 and bonus_hit else
                '3등' if overlap==5 else '4등' if overlap==4 else '5등' if overlap==3 else '낙첨')
            rows.append({'회차':int(df.drwNo.iloc[t]),'모델':key,'일치':overlap,'보너스일치':int(bonus_hit),
                         '등수':grade,'추천번호':','.join(map(str,picks)),'당첨번호':','.join(map(str,sorted(actual)))})
    return pd.DataFrame(rows)

def final_scores(df):
    draws=df[NUM_COLS].to_numpy(dtype=int)
    X,hits=feature_matrix(draws)
    t=len(df)
    model_scores={key:fit_model(X,hits,key,t).predict_proba(X[t])[:,1].tolist() for key in ['logistic','forest']}
    model_scores['freq30']=X[t,:,2].tolist()
    model_scores['freq100']=X[t,:,3].tolist()
    model_scores['random']=[1.0]*45
    return model_scores

def summarize(bt):
    out=[]
    for m,g in bt.groupby('모델',sort=False):
        out.append({'모델':m,'검증 회차':len(g),'평균 일치':round(g['일치'].mean(),4),
                  '3개 이상':int((g['일치']>=3).sum()),'4개 이상':int((g['일치']>=4).sum()),
                  '5개 이상':int((g['일치']>=5).sum()),'6개':int((g['일치']==6).sum())})
    return pd.DataFrame(out)

if __name__=='__main__':
    from time import monotonic
    s=monotonic()
    df=read_data('data/lotto_results.csv')
    bt=backtest(df)
    print(summarize(bt).to_string(index=False))
    bt.to_csv('data/backtest_300_1247.csv',index=False,encoding='utf-8-sig')
    import json
    scores=final_scores(df)
    Path('data/final_scores.json').write_text(json.dumps(scores,ensure_ascii=False))
    print('Done:',round(monotonic()-s,2),'secs')

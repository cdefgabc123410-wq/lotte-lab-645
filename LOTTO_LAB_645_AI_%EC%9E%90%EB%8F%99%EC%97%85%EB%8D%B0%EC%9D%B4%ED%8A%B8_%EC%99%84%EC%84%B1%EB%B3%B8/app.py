"""LOTTO LAB: Streamlit research dashboard. Run: streamlit run app.py"""
from __future__ import annotations
import io
import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from model_core import read_data, final_scores, backtest, summarize, MODEL_LABELS, NUM_COLS
ROOT=Path(__file__).parent
st.set_page_config(page_title="LOTTO LAB · 로또 6/45 데이터 실험실",page_icon="🎯",layout="wide",initial_sidebar_state="expanded")
st.markdown("""<style>
[data-testid='stAppViewContainer'] {background:#0c1424;color:#e7eef9}
[data-testid='stSidebar'] {background:#121f34}
.block-container {padding-top:1.8rem; max-width: 1280px;}
h1,h2,h3 {letter-spacing:-.04em}
[data-testid='stMetric'] {background:#17273d;padding:16px;border:1px solid #32435d;border-radius:15px}
[data-testid='stMetricLabel'] {color:#b6c8db}
</style>""",unsafe_allow_html=True)

@st.cache_data(show_spinner='최신 회차까지 모델을 학습하고 있어요…')
def compute_scores(csv_bytes):
    return final_scores(read_data(csv_bytes))
@st.cache_data(show_spinner=False)
def default_backtest(content):
    return pd.read_csv(io.BytesIO(content),encoding='utf-8-sig')
@st.cache_data(show_spinner=False)
def snapshot_scores(content):
    return json.loads(content.decode('utf-8'))
@st.cache_data(show_spinner='과거 회차 순차 검증 중입니다. 수십 초 걸릴 수 있어요…')
def compute_backtest(csv_bytes):
    return backtest(read_data(csv_bytes))

raw_default=(ROOT/'data/lotto_results.csv').read_bytes()
st.sidebar.markdown('### 🎯 LOTTO LAB')
st.sidebar.caption('데이터 기반 실험 · 6/45')
uploaded=st.sidebar.file_uploader('최신 당첨번호 CSV 업로드 (선택)',type=['csv'],help='drwNo, drwNoDate, n1~n6, bonus 열 포함. 1회부터 누락 없는 형식.')
source=uploaded.getvalue() if uploaded else raw_default
try:
    df=read_data(source)
except Exception as exc:
    st.error('CSV 파일을 확인해 주세요: '+str(exc)); st.stop()
original=(uploaded is None or source==raw_default)
N=len(df)
status_path=ROOT/'data/update_status.json'
score_path=ROOT/'data/model_scores.json'
bt_path=ROOT/'data/backtest_walk_forward.csv'
try:
    status=json.loads(status_path.read_text(encoding='utf-8'))
except (OSError,ValueError):
    status={}
snapshot_ready=(status.get('model_round')==N and score_path.exists() and bt_path.exists())
if original:
    st.sidebar.success(f'📅 자동 갱신 설정 · 최신 {N}회차')
    st.sidebar.caption('한국시간 일요일 09:17, 월요일 09:17 재확인 · GitHub 배포 후 자동 작동')
    if status.get('built_at_utc'):
        try:
            built=datetime.fromisoformat(status['built_at_utc']).astimezone(timezone(timedelta(hours=9)))
            st.sidebar.caption(f'AI 마지막 재학습: {built:%Y-%m-%d %H:%M} KST')
        except ValueError:
            pass
    age=(datetime.now(timezone(timedelta(hours=9))).date()-df.drwNoDate.iloc[-1].date()).days
    if age>9:
        st.sidebar.warning('⚠️ 마지막 추첨일이 9일 넘게 지났습니다. Actions 실행 기록을 확인하세요.')

start=300
models=list(MODEL_LABELS)
selected=st.sidebar.selectbox('추천 방식',models,format_func=lambda k: MODEL_LABELS[k])
window=st.sidebar.selectbox('통계 구간',[30,100,200,N],format_func=lambda v:'전체 회차' if v==N else f'최근 {v}회')
games=st.sidebar.slider('번호 조합 수',1,10,5)
balance=st.sidebar.checkbox('홀짝·합계 균형 필터 (선택)',value=False,help='당첨 확률을 높여주는 기능이 아니라 추천 조합 모양만 조절합니다.')
st.sidebar.divider()
st.sidebar.info('모든 번호 조합의 1등 확률은 동일합니다 (1 / 8,145,060). 분석 점수는 당첨 가능성의 증거가 아닙니다.')

st.title('🎯 LOTTO LAB 6/45')
st.caption(f'역대 당첨번호 분석 · 머신러닝 실험실 · 데이터 기준 {df.drwNo.iloc[-1]}회 / {df.drwNoDate.iloc[-1]:%Y-%m-%d} · 자동 업데이트 버전')

t1,t2,t3,t4,t5=st.tabs(['📊 대시보드','🔢 번호 통계','🎲 번호 추천','🧪 백테스트','📖 검증 방법'])

def graph_frame(fig,height=None):
    fig.update_layout(template='plotly_dark',paper_bgcolor='#0c1424',plot_bgcolor='#121f34',font_color='#dce8f5',margin=dict(l=20,r=20,t=40,b=20),height=height)
    return fig

def get_bt():
    if original and snapshot_ready:
        return default_backtest(bt_path.read_bytes())
    if st.session_state.get('bt_signature')==hash(source):
        return st.session_state['custom_bt']
    return None

bt=get_bt()
with t1:
    c1,c2,c3,c4=st.columns(4)
    c1.metric('수록 회차',f'{N:,}회')
    c2.metric('백테스트 대상',f'{max(0,N-start):,}회')
    c3.metric('분석 번호','45개')
    c4.metric('다음 예상 회차',f'{N+1}회')
    st.markdown('#### 최신 당첨번호')
    last=df.iloc[-1]
    st.markdown(' '.join([f'`{int(last[c]):02d}`' for c in NUM_COLS])+f'　보너스 `{int(last.bonus):02d}`')
    if bt is not None:
        s=summarize(bt).set_index('모델')
        display=s.loc[models].reset_index()
        display['모델']=display['모델'].map(MODEL_LABELS)
        st.markdown('#### 모델 성능 한눈에 보기')
        st.dataframe(display,hide_index=True,use_container_width=True)
        fig=px.bar(display,x='모델',y='평균 일치',text='평균 일치',color='모델')
        fig.update_traces(texttemplate='%{y:.3f}',textposition='outside')
        st.plotly_chart(graph_frame(fig,370),use_container_width=True)
    else:
        st.info('업로드한 새 데이터로 백테스트를 계산하려면 「백테스트」 탭에서 재계산 버튼을 누르세요.')
    st.warning('주의: 추첨이 독립적이라면 과거 번호와 AI 점수로 미래 당첨 확률을 높일 수 없습니다. 비교 결과는 연구용입니다.')

with t2:
    history=df.tail(window)
    nums=history[NUM_COLS].to_numpy().reshape(-1)
    counts=np.bincount(nums,minlength=46)[1:]
    plotdf=pd.DataFrame({'번호':range(1,46),'출현 횟수':counts})
    fig=px.bar(plotdf,x='번호',y='출현 횟수',color='출현 횟수',color_continuous_scale='Tealgrn')
    fig.update_xaxes(dtick=1)
    st.plotly_chart(graph_frame(fig,450),use_container_width=True)
    a,b=st.columns([1,1])
    with a:
        st.markdown('##### 많이 나온 번호 TOP 10')
        st.dataframe(plotdf.nlargest(10,'출현 횟수'),hide_index=True,use_container_width=True)
    with b:
        st.markdown('##### 구간 특성')
        odd=(history[NUM_COLS].to_numpy()%2).sum(axis=1)
        summ=history[NUM_COLS].sum(axis=1)
        st.metric('평균 번호 합계',f'{summ.mean():.1f}')
        st.metric('평균 홀수 개수',f'{odd.mean():.2f} / 6')
        st.metric('연속번호 포함',f'{100*np.mean((np.diff(np.sort(history[NUM_COLS].to_numpy(),axis=1),axis=1)==1).any(axis=1)):.1f}%')
    st.caption('여기서 높게 나온 빈도가 다음 회차에 다시 등장할 확률이 높다는 뜻은 아닙니다.')

with t3:
    st.markdown('#### 모델별 다음 회차 번호 추천')
    if selected != 'random':
        if original and snapshot_ready:
            pack=snapshot_scores(score_path.read_bytes())
            if int(pack.get('as_of_round',-1))==N:
                scores=pack['model_scores'][selected]
            else:
                st.error('AI 점수 캐시의 회차가 맞지 않습니다. 관리자에게 재학습을 요청하세요.');st.stop()
        else:
            scores=compute_scores(source)[selected]
    else:
        scores=[1.0]*45
    scores=np.array(scores,dtype=float)
    scaled=(scores-scores.min())/max(1e-9,float(np.ptp(scores)))
    if selected in ['freq30','freq100']:
        st.caption('번호 점수는 과거 출현 빈도를 나타냅니다.')
    elif selected=='random':
        st.caption('모든 번호를 동일한 확률로 추출합니다.')
    else:
        st.caption('AI 모델 점수는 상대적인 분류 점수이며 실제 로또 당첨 확률로 해석하면 안 됩니다.')
    def generate_once(seed):
        rng=np.random.default_rng(seed)
        out=[]
        seen=set()
        # Give more weight to higher-scoring numbers, but keep lower-scoring ones possible.
        positive=np.exp(1.7*scaled)
        p=positive/positive.sum()
        order=np.argsort(-scores,kind='stable')
        for k in range(games):
            found=False
            for _ in range(400):
                if k==0 and selected!='random':
                    chosen=np.sort(order[:6]+1)
                else:
                    chosen=np.sort(rng.choice(np.arange(1,46),6,replace=False,p=p))
                key=tuple(chosen)
                if key in seen:
                    continue
                if balance and not (2<=sum(x%2 for x in key)<=4 and 90<=sum(key)<=180):
                    continue
                out.append(key);seen.add(key);found=True;break
            if not found:
                out.append(tuple(np.sort(rng.choice(np.arange(1,46),6,replace=False)).tolist()))
        return out
    if 'generation' not in st.session_state: st.session_state['generation']=0
    if st.button('🔄 새 번호 조합 생성',type='primary',use_container_width=True):
        st.session_state['generation']+=1
    combo_key=(selected,games,balance,N,st.session_state['generation'])
    seed=int(hashlib.sha256(repr(combo_key).encode('utf-8')).hexdigest()[:8],16)
    combos=generate_once(seed)
    st.caption('첫 조합은 선택한 모델의 상위 6개 번호, 나머지는 점수에 따라 가중 추출합니다. 무작위 방식은 모든 조합이 무작위입니다.')
    for i,c in enumerate(combos,1):
        label='　'.join(f'**{v:02d}**' for v in c)
        st.markdown(f'**{i:02d}게임**　 {label}')
    st.download_button('📥 추천번호 CSV 저장',data=pd.DataFrame(combos,columns=NUM_COLS).to_csv(index=False).encode('utf-8-sig'),file_name='lotto_recommendations.csv',mime='text/csv',use_container_width=True)
    st.markdown('##### 모델 상위 15개 번호')
    ranking=pd.DataFrame({'번호':np.arange(1,46),'모델 점수':scores}).sort_values('모델 점수',ascending=False).head(15)
    st.dataframe(ranking.style.format({'모델 점수':'{:.4f}'}),hide_index=True,use_container_width=True)

with t4:
    st.markdown('#### 미래 정보 차단 순차 검증')
    st.caption('첫 300회를 학습에 활용하고, 301회부터 각 회차를 예측합니다. 모델은 100회마다 해당 시점 이전의 정답만 사용해 재학습합니다.')
    if not original:
        if st.button('업로드한 데이터로 전체 백테스트 다시 계산',type='primary'):
            newbt=compute_backtest(source)
            st.session_state['custom_bt']=newbt
            st.session_state['bt_signature']=hash(source)
            bt=newbt
    if bt is None:
        st.info('새 회차를 업로드했으므로 이전 백테스트 성적은 숨겼습니다. 버튼을 눌러 재계산해 주세요.')
    else:
        recent=st.radio('검증 범위',['전체', '최근 100회', '최근 200회'],horizontal=True)
        bt2=bt.copy()
        if recent!='전체':
            n=100 if '100' in recent else 200
            bt2=bt2[bt2['회차']>bt2['회차'].max()-n]
        stats=summarize(bt2)
        stats['모델']=stats['모델'].map(MODEL_LABELS)
        st.dataframe(stats,hide_index=True,use_container_width=True)
        fig=px.bar(stats,x='모델',y='3개 이상',color='모델',text='3개 이상')
        st.plotly_chart(graph_frame(fig,370),use_container_width=True)
        dist=bt2.groupby(['모델','일치']).size().unstack(fill_value=0).reindex(index=models,fill_value=0).reindex(columns=range(7),fill_value=0)
        fig2=go.Figure()
        for m in models:
            fig2.add_trace(go.Bar(x=list(range(7)),y=dist.loc[m],name=MODEL_LABELS[m]))
        fig2.update_layout(barmode='group',title='정확히 0~6개 일치 횟수',xaxis_title='맞힌 본번호 개수')
        st.plotly_chart(graph_frame(fig2,390),use_container_width=True)
        st.download_button('📥 전체 회차별 백테스트 내역 다운로드',data=bt.to_csv(index=False).encode('utf-8-sig'),file_name='lotto_model_backtest.csv',mime='text/csv')

with t5:
    st.markdown('''### 분석 방식
**통계 기준**은 과거 30회 및 100회 본번호 출현 비율로 45개 번호에 점수를 줍니다.

**AI 모델**은 로지스틱 회귀와 랜덤 포레스트로, 번호별 최근 5·10·30·100회 빈도, 등장 간격, 직전 회차 출현 여부 등 9개 특징을 사용합니다.

**백테스트**는 301회부터 1회차씩 전진하며 예측합니다. 각 대상 회차의 번호는 그 시점의 특징 계산이나 학습에 절대 포함되지 않습니다. AI 모델은 301회에서 처음 학습한 뒤 100회마다 갱신하며, 매번 대상 회차 이전 데이터만 사용합니다. 무작위 비교는 고정 난수 시드로 재현 가능합니다.

**주의할 점**: 본번호 6개를 45개 중 무작위로 추첨한다는 가정에서는 어떤 6개 조합도 1등 확률이 **1/8,145,060**입니다. AI 점수는 통계 실험용이며 독립 추첨의 미래 당첨을 예측한다는 근거가 아닙니다. 백테스트 결과 차이는 우연일 수 있으며, 여러 전략을 살펴본 뒤 성적 좋은 전략만 선택하면 성능이 과대평가될 수 있습니다.

**자동 갱신**: GitHub Actions가 매주 일요일 09:17 KST, 월요일 09:17 KST에 공식 사이트의 최신 회차를 확인합니다. 새로운 회차가 생기면 검증된 CSV, 전체 순차 백테스트, AI 점수를 다시 만들고 저장소에 커밋합니다. Streamlit Cloud에 배포해 두었다면 저장소 변경이 반영됩니다. 공식 사이트 응답 변경·접속 차단·GitHub 예약 작업 지연 시 갱신에 실패할 수 있습니다.

**수동 데이터 업로드**: 좌측에서 같은 구조의 CSV를 올리면 통계 및 추천용 AI 학습을 실행합니다. 백테스트는 「백테스트」 탭에서 다시 계산할 수 있습니다.
''')
    st.caption('데이터: 사용자가 제공한 로또 6/45 역대 당첨번호 CSV · 별도 서버 전송은 설치/배포 환경에 따라 달라질 수 있습니다.')

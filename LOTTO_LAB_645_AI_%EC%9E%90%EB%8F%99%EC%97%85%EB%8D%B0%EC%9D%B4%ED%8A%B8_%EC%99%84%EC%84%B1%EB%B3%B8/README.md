# 🎯 LOTTO LAB 6/45 · 자동 업데이트 + 머신러닝 웹앱

실제 1~1247회 당첨번호(2026-10-24까지)를 초기 데이터로 포함한 Streamlit 웹앱입니다.
GitHub에 배포하면 **일요일 오전 9:17(KST)** 새 당첨 회차를 확인하고, 실패 시 **월요일 9:17**에 한 번 더 확인합니다. 새 회차 발견 시 AI 점수·과거 백테스트를 자동 재산출하고, 결과를 GitHub 저장소에 기록합니다.

> **중요:** 이 ZIP 자체가 인터넷에 공개된 웹사이트는 아닙니다. 사용자의 GitHub 저장소 업로드 + Streamlit Community Cloud 배포를 완료해야 자동 갱신되는 웹주소를 얻을 수 있습니다. 또한 추첨이 무작위라면 어떤 6개 조합이든 1등 확률은 **1/8,145,060**으로 같습니다. AI 점수는 복권 당첨 예측력이나 수익 보장이 아닙니다.

## 시작하기: GitHub + Streamlit Cloud (권장)

1. [GitHub](https://github.com/) 계정을 만들고, 새 저장소(예: `lotto-lab-645`)를 생성하세요. 가급적 **Public** 저장소로 시작하면 Streamlit 배포가 간편합니다.
2. ZIP을 압축 해제하세요. **폴더 안의 전체 파일과 `.github/workflows/update-lotto.yml` 폴더를 포함하여** 저장소 루트로 올리세요. (숨김 폴더인 `.github`가 누락되면 예약 실행이 되지 않습니다.) 폴더 단위 전송이 쉬운 방법은 GitHub Desktop의 로컬 저장소 생성/복제 후 파일 복사 → Commit → Push입니다.
3. 저장소의 **Settings → Actions → General → Workflow permissions**에서 **Read and write permissions** 사용 가능 여부를 확인하세요. 조직의 정책에 따라 변경 불가할 수 있습니다. 워크플로에도 `contents: write`를 명시했습니다.
4. GitHub 저장소 **Actions** 탭에서 워크플로 **‘로또 최신 회차 · 통계 · AI 자동 업데이트’**를 선택하고 **Run workflow**를 눌러 최초 실행을 확인하세요. 저장소 설정에 따라 Actions를 먼저 활성화해야 할 수 있습니다.
5. [Streamlit Community Cloud](https://share.streamlit.io/) → **Create app** → GitHub 저장소 선택 → 브랜치 `main` → 앱 파일 `app.py` → **Deploy**. 배포 후 나오는 `*.streamlit.app` 주소로 PC·스마트폰에서 접속하세요.
6. 매주 GitHub Actions 실행 뒤 새 데이터가 있으면 저장소 `data` 파일이 커밋됩니다. Streamlit Cloud가 저장소의 변경을 반영하면 대시보드가 최신 회차로 갱신됩니다.

### 업데이트 일정과 예외

- **일요일 오전 09:17 KST**: 주간 업데이트 (토요일 추첨 공개 후).
- **월요일 오전 09:17 KST**: 지연·오류에 대비한 보조 확인. 이미 최신이면 파일을 변경하지 않습니다.
- GitHub Actions의 예약 실행은 지정된 분에 반드시 시작되는 보장이 없으며, 저장소가 오랜 기간 비활성 상태면 예약 워크플로가 비활성화될 수 있습니다. **Actions 탭을 가끔 확인**하세요.
- 동행복권의 2026년 개편된 **공식 사이트에서 사용되는 미문서화 JSON 엔드포인트**를 이용합니다. 사이트 구조가 바뀌거나 요청이 차단되면 업데이트는 실패하며 이전 데이터는 유지됩니다. 자동 갱신 성공을 100% 보장하지는 않습니다.
- 모니터링은 Streamlit 사이드바의 최신 추첨 회차·날짜, 재학습 시각과 GitHub Actions 실행 기록에서 확인합니다. 9일 이상 지난 데이터이면 앱에서 경고합니다.
- 16회차를 초과해 누락되면 자동으로 대량 요청하지 않습니다. 현재 코드상 최대 16회만 자동으로 따라잡고, 그 이상은 수동 확인을 권장합니다.

## 파일 안내

| 파일 | 역할 |
|---|---|
| `app.py` | 대시보드/번호 통계/AI 추천/백테스트 Streamlit 웹 화면 |
| `model_core.py` | 로지스틱 회귀, 랜덤 포레스트, 통계 모델, 시계열 검증 |
| `updater.py` | 최신 당첨번호 수집·형식 및 데이터 검증, 실패 시 이전 CSV 유지 |
| `pipeline.py` | 새 회차가 있으면 AI 모델·전체 순차 검증을 다시 계산 |
| `.github/workflows/update-lotto.yml` | 매주 자동 실행 + 테스트 + 변경 데이터 커밋 |
| `data/lotto_results.csv` | 역대 실데이터 |
| `data/backtest_walk_forward.csv` | 최신 백테스트 전체 검증 결과 |
| `data/model_scores.json` | 최신 회차까지 학습한 5개 모델의 번호 점수 |
| `data/update_status.json` | 데이터/재학습 시각/검증 회차 메타데이터 |
| `tests/test_pipeline.py` | 자동 수집 안전성 및 과거 데이터 누출 여부 테스트 |

## 로컬 실행 (Windows/Mac/Linux)

Python 3.12를 설치한 다음, 압축을 푼 폴더에서:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

처음부터 다시 백테스트와 AI 모델 점수를 재생성하려면:

```bash
python pipeline.py --force
```

공식 사이트에서 신규 회차를 직접 확인하고 전체 갱신까지 수행하려면:

```bash
python pipeline.py --online
```

네트워크 없이 테스트를 실행하려면:

```bash
python -m unittest discover -s tests -v
```

**주의:** Streamlit Community Cloud의 서버 로컬 파일에 신규 CSV를 직접 쓰면 서버 재시작 시 사라질 수 있습니다. 따라서 본 프로젝트는 **GitHub Actions에서 데이터/모델 산출물을 커밋하는 방식**으로 내구성을 확보합니다.

## 모델과 검증

- 1~300회: 초기 학습 구간
- 301회~최신: 백테스트 구간 (현재 947회)
- AI는 로지스틱 회귀와 랜덤 포레스트. 번호별 최근 5·10·30·100회 빈도, 직전 출현, 최근/장기 빈도 차이 등을 사용
- 100회마다 과거 데이터로 **재학습**, 검증 당첨번호를 미리 사용하지 않음
- 매주 새 회차가 포함되면 **전체 백테스트 재계산** + 다음 회차 AI 점수 재학습
- 비교용 무작위 모델은 난수 시드를 고정하여 재현 가능

이 모델은 독립·무작위 추첨에 대한 유의미한 예측 우위가 검증되지 않았습니다. 통계·학습 실험용으로 사용하세요.

## 데이터 소스

- [동행복권 로또 6/45 공식 결과](https://www.dhlottery.co.kr/lt645/result)
- 2026년 사이트 개편 후 `https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do`(최신), `selectPstLt645InfoNew.do`(특정 회차)의 JSON 구조를 사용. **이 엔드포인트는 공개 문서가 없는 내부 조회 주소이므로 변경될 수 있습니다.**

## 보안 / 유지보수

- API 토큰, 개인정보, GitHub PAT를 코드에 포함하지 않습니다. `GITHUB_TOKEN`은 GitHub Actions에서 자동 발급됩니다.
- 커밋 대상은 `data/`의 공개 당첨 결과 및 계산된 점수뿐입니다.
- 예약 작업이 계속 실패하면 Actions 탭 실행 로그의 마지막 오류와 동행복권 응답 변경 여부를 확인하세요.

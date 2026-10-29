"""네트워크 없이 실행 가능한 안전 수집·백테스트 회귀 테스트."""
from __future__ import annotations
import io
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from model_core import NUM_COLS,read_data,backtest,final_scores
from updater import normalize_record,update
from pipeline import rebuild

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'data/lotto_results.csv'

class Response:
    headers={'Content-Type':'application/json; charset=utf-8'}
    def __init__(self,rows):self.rows=rows
    def raise_for_status(self):pass
    def json(self):return {'data':{'list':self.rows}}

class Session:
    def __init__(self,rows):self.rows=rows
    def get(self,url,**kwargs):return Response(self.rows)

def item_from_row(row):
    d={'ltEpsd':int(row['drwNo']), 'ltRflYmd':pd.to_datetime(row['drwNoDate']).strftime('%Y%m%d'),
       'bnsWnNo':int(row['bonus'])}
    d.update({f'tm{i}WnNo':int(row[f'n{i}']) for i in range(1,7)})
    return d

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df=read_data(SRC)
        cls.latest=cls.df.loc[cls.df.drwNo==1247].iloc[0]
        cls.item=item_from_row(cls.latest)

    def test_dataset_integrity(self):
        self.assertGreaterEqual(len(self.df),1247)
        self.assertEqual(int(self.df.drwNo.iloc[0]),1)
        self.assertGreaterEqual(int(self.df.drwNo.iloc[-1]),1247)

    def test_official_json_fields(self):
        record=normalize_record(self.item)
        self.assertEqual(record['drwNo'],1247)
        self.assertEqual(record['drwNoDate'],'2026-10-24')
        self.assertEqual([record[f'n{i}'] for i in range(1,7)],[8,14,21,22,42,45])
        self.assertEqual(record['bonus'],24)

    def test_add_one_round_and_repeat_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'draws.csv'
            data=pd.read_csv(SRC,encoding='utf-8-sig')
            data[data.drwNo<=1246].to_csv(p,index=False,encoding='utf-8-sig')
            new=update(p,session=Session([self.item]),sleep_seconds=0)
            self.assertEqual(new['added'],1)
            self.assertEqual(len(read_data(p)),1247)
            content=p.read_bytes()
            again=update(p,session=Session([self.item]),sleep_seconds=0)
            self.assertEqual(again['added'],0)
            self.assertEqual(content,p.read_bytes())

    def test_bad_data_keeps_original_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'draws.csv'
            data=pd.read_csv(SRC,encoding='utf-8-sig')
            data[data.drwNo<=1246].to_csv(p,index=False,encoding='utf-8-sig')
            content=p.read_bytes()
            bad=dict(self.item);bad['tm2WnNo']=bad['tm1WnNo']
            with self.assertRaises(ValueError):
                update(p,session=Session([bad]),sleep_seconds=0)
            self.assertEqual(content,p.read_bytes())

    def test_pipeline_noop_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'lotto_results.csv'
            p.write_bytes(SRC.read_bytes())
            # Cache files pre-exist, so no expensive rebuild during no-change test.
            folder=Path(tmp)
            for n in ['backtest_walk_forward.csv','model_scores.json']:
                (folder/n).write_text('placeholder')
            (folder/'update_status.json').write_text(json.dumps({'model_round':int(self.df.drwNo.iloc[-1])}))
            v=rebuild(data_path=p,output_dir=folder)
            self.assertFalse(v['changed'])

    def test_no_future_data_in_features_or_backtest(self):
        sub=self.df.iloc[:311].copy()
        alt=self.df.iloc[:314].copy()
        one=backtest(sub,start=300)
        two=backtest(alt,start=300)
        two=two[two['회차']<=311]
        pd.testing.assert_frame_equal(one.reset_index(drop=True),two.reset_index(drop=True))

if __name__=='__main__':unittest.main()

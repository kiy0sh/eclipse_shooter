import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time
import warnings
warnings.simplefilter('ignore')

try:
    import gphoto2 as gp
    camera_initialized = True
except:
    camera_initialized = False
    pass

# loggerの生成
logger = logging.getLogger('mylog')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('eclipse_shooter.log')
sh = logging.StreamHandler()
logger.addHandler(fh)
logger.addHandler(sh)
fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
sh.setFormatter(logging.Formatter('%(message)s'))

# 現在時刻取得（撮影テスト時に時刻をずらして実験する）
def get_current_time(shift=14):

    # JST 15 → (hours = +20) → UTC 17
    # JST 22 → (hours = +13) → UTC 17

    d = datetime.utcnow() + timedelta(hours=shift)
    return d.astimezone(timezone.utc)

# EOSを制御するクラス
class EOS(object):

    def __init__(self):

        if not camera_initialized :
            return

        # カメラをオープン
        self.camera = gp.check_result(gp.gp_camera_new())
        self.context = gp.gp_context_new()

        # カメラの初期化
        gp.check_result(gp.gp_camera_init(self.camera, self.context))

        # カメラの設定ウィジェットを取得
        self.config = gp.check_result(gp.gp_camera_get_config(self.camera, self.context))
        self.config_list = self.get_config(self.config)[1]

        # カメラの設定保存
        self.setting = {'ss':'1/1000', 'iso':'200', 'format':'RAW + Large Fine JPEG', 'white_balance':'Color Temperature', 'color_temperature':'2500'}

        # 設定を変更
        self.setting_change(self.config_list['Camera Settings']['Capture Target'], 'Memory card')
        self.setting_change(self.config_list['Capture Settings']['Drive Mode'], 'Single')
        self.setting_change(self.config_list['Capture Settings']['Shutter Speed'], '1/1000')
        self.setting_change(self.config_list['Image Settings']['ISO Speed'], '200')
        self.setting_change(self.config_list['Image Settings']['Image Format'], 'RAW + Large Fine JPEG')
        self.setting_change(self.config_list['Image Settings']['WhiteBalance'], 'Color Temperature')
        self.setting_change(self.config_list['Image Settings']['Color Temperature'], '2500')
        self.apply_setting()

    def __del__(self):
        if not camera_initialized :
            return

        # カメラをクローズ
        gp.check_result(gp.gp_camera_exit(self.camera, self.context))

    def get_config(self, config):
        # カメラの設定ウィジェットを再帰的に取得
        label = gp.check_result(gp.gp_widget_get_label(config))
        count = gp.check_result(gp.gp_widget_count_children(config))
        if count == 0 :
            return [label,config]
        return [
            label,dict([
                self.get_config(gp.check_result(gp.gp_widget_get_child(config, i)))
                for i in range(count)
            ])
        ]

    def setting_change(self, child, data):
        return gp.check_result(gp.gp_widget_set_value(child, data))

    def apply_setting(self):
        retry = True
        while retry:
            try:
                gp.check_result(gp.gp_camera_set_config(self.camera, self.config, self.context))
                retry = False
            except:
                # カメライベントループの開始
                event_timeout = 5000  # イベントを待機するタイムアウト時間（ミリ秒）を設定
                event_type, event_data = gp.check_result(gp.gp_camera_wait_for_event(self.camera, event_timeout, self.context))                
                logger.info( f"retry[setting] :Type={event_data}, Data={event_data}" )

    def exposure(self, ss=None, iso=None, format=None, white_balance=None, color_temperature=None):

        if not camera_initialized :
            return

        setting_updated = False
        if ss and ss!=self.setting['ss'] :
            self.setting_change(self.config_list['Capture Settings']['Shutter Speed'], str(ss))
            self.setting['ss'] = ss
            setting_updated = True

        if iso and iso!=self.setting['iso'] :
            self.setting_change(self.config_list['Image Settings']['ISO Speed'], str(iso))
            self.setting['iso'] = iso
            setting_updated = True

        if format and format!=self.setting['format'] :
            self.setting_change(self.config_list['Image Settings']['Image Format'], str(format))
            self.setting['format'] = format
            setting_updated = True

        if white_balance and white_balance!=self.setting['white_balance'] :
            self.setting_change(self.config_list['Image Settings']['WhiteBalance'], str(white_balance))
            self.setting['white_balance'] = white_balance
            setting_updated = True

        if color_temperature and color_temperature!=self.setting['color_temperature'] and color_temperature!='nan':
            self.setting_change(self.config_list['Image Settings']['Color Temperature'], str(color_temperature))
            self.setting['color_temperature'] = color_temperature
            setting_updated = True

        if setting_updated :
            self.apply_setting()

        retry = True
        while retry:
            try:
                gp.check_result(gp.gp_camera_trigger_capture(self.camera, self.context))
                retry = False
            except:
                # カメライベントループの開始
                event_timeout = 5000  # イベントを待機するタイムアウト時間（ミリ秒）を設定
                event_type, event_data = gp.check_result(gp.gp_camera_wait_for_event(self.camera, event_timeout, self.context))      
                logger.info( f"retry[shoot] :Type={event_data}, Data={event_data}" )
        time.sleep(1.5)

def make_combination(row, keys):
    def flatten(x): return [z for y in x for z in (flatten(y) if hasattr(y, '__iter__') and not isinstance(y, str) else (y,))]
    key_ar = []
    value_hs = {}
    for key in keys:
        key_ar.append(key)
        value_hs[key] = str(row[key]).split(',')
    param_ar = value_hs[key_ar[0]]
    for i in range(len(key_ar)-1):
        param_ar = [[x, y] for x in param_ar for y in value_hs[key_ar[i+1]]]
        if i > 0:
            for i2 in range(len(param_ar)):
                param_ar[i2] = flatten(param_ar[i2])
    return param_ar


if __name__ == "__main__":

    now = get_current_time()

    # 撮影スクリプトデータを読込み
    df = pd.read_excel('usa_eclipse.xlsx')

    # スクリプトにあるイベント時刻（第一接触、第二接触、第三接触）をリストアップ（カウントダウン用）
    event_time = [(row['basetime'],datetime.combine(datetime.utcnow().date(), index, tzinfo=timezone.utc)) for index, row  in df.set_index('utc').sort_index().groupby(level=0).last().iterrows()]

    # 撮影スクリプトデータを実際の時間に展開
    exposure = {}
    for index, row in df.iterrows():
        data = []
        for i in range(int(row['count'])):
            data.append( {'utc':datetime.combine(datetime.utcnow().date(), row['utc'], tzinfo=timezone.utc)+timedelta(seconds=row['time(sec)']+i*row['interval(sec)']),
                          'ss':row['ss'], 'iso':row['iso'], 'format':row['format'], 'white_balance':row['white_balance'], 'color_temperature':row['color_temperature']})
        exposure[row['title']] = {'last': now, 'list': pd.DataFrame(data).set_index('utc').sort_index().groupby(level=0).last()}
        logger.info("{}\n{}\n".format(row['title'],exposure[row['title']]['list'])+'-'*50 )

    # カメラの初期化
    camera = EOS()

    # 撮影ループ
    while True:
        now = get_current_time()
        logger.info( "{}".format([title[:3]+':'+str(int((event-now).total_seconds())) for title,event in event_time]),extra={'date':'(utc:{})'.format(str(now)[11:19])} )

        # すべての撮影スクリプトリストのうち
        queue_list = []
        for title, i in exposure.items() :
            # 現在時刻よりも前の物（撮影時刻になったもの）で未撮影の物(lastより後）をピックアップ
            target = i['list'][i['last']:now]
            if len(target)>0 :
                # 最後の１個だけをピックアップ（撮影中に複数のトリガーが発生した場合は直近のトリガーのみを扱う）
                for index, row in target.tail(1).iterrows():
                    queue_list.append( {'title':title, 'utc':index, 'ss':row['ss'], 'iso':row['iso'], 'format':row['format'], 'white_balance':row['white_balance'], 'color_temperature':row['color_temperature']} )

        if queue_list :
            # 複数のスクリプトからトリガーが発動されていれば、トリガー発動済みの中で最も古いものを撮影処理
            for index, row in pd.DataFrame(queue_list).set_index('utc').sort_index().head(1).iterrows():
                # 組み合わせの生成
                keys = ['ss','iso','format','white_balance','color_temperature']
                for exp in make_combination(row, keys):
                    cond = dict([(keys[i],exp[i]) for i in range(len(keys))])
                    # 指定条件で撮像
                    logger.info( f"{row['title']} , {cond}" )
                    camera.exposure( ss=cond['ss'], iso=cond['iso'], format=cond['format'], white_balance=cond['white_balance'], color_temperature=cond['color_temperature'] )
                exposure[row['title']]['last'] = now

        time.sleep(1)



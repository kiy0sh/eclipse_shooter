# coding: utf-8
from datetime import datetime, timedelta, timezone
import logging
import numpy as np
import pandas as pd
import time
import traceback
import warnings
warnings.simplefilter('ignore')
import gphoto2 as gp

# 現在時刻取得（撮影テスト時に時刻をずらして実験するためにshiftを指定）
def get_current_time(shift=17):
    """
    現在時刻          shift   日食時刻
    JST 10 → (hours = +25) → UTC 17
    JST 11 → (hours = +24) → UTC 17
    JST 12 → (hours = +23) → UTC 17
    JST 13 → (hours = +22) → UTC 17
    JST 14 → (hours = +21) → UTC 17
    JST 15 → (hours = +20) → UTC 17
    JST 16 → (hours = +19) → UTC 17
    JST 17 → (hours = +18) → UTC 17
    JST 18 → (hours = +17) → UTC 17
    JST 19 → (hours = +16) → UTC 17
    JST 20 → (hours = +15) → UTC 17
    JST 21 → (hours = +14) → UTC 17
    JST 22 → (hours = +13) → UTC 17
    """
    d = datetime.utcnow() + timedelta(hours=shift)
    return d.astimezone(timezone.utc)

# カメラを制御するクラス
class camera_control(object):
    def __init__(self, logger, debug=False):
        self._logger = logger
        self._setting_updated = False

        # GPhoto2のデバッグログを取得
        if debug :
            callback_obj = gp.check_result(gp.gp_log_add_func(gp.GP_LOG_DATA, self._callback))

        # カメラをオープン
        self._camera = gp.Camera()

        # 接続されているカメラを認識
        while True:
            self._cameras = list(self._camera.autodetect())
            if self._cameras:
                break
            self._logger.error( "No camera detected. Please  connect camera." )
            time.sleep(2)
        self._cameras.sort(key=lambda x: x[0])

        # 接続されているカメラのリスト
        for n, (name, value) in enumerate(self._cameras):
            self._logger.info( f"camera number{n} ({value}): {name}")
        
        # 操作するカメラを選択
        if len(self._cameras)>1 :
            choice = input(f"Please input number of chosen camera(0~{len(self._cameras)-1}): ")
            try:
                choice = int(choice)
            except ValueError:
                self._logger.error("Integer values only!")
                raise ValueError
            if choice < 0 or choice >= len(self._cameras):
                self._logger.error("Number out of range")
                raise ValueError
        else:
            choice = 0
        name, addr = self._cameras[choice]

        # 接続情報の取得
        port_info_list = gp.PortInfoList()
        port_info_list.load()
        abilities_list = gp.CameraAbilitiesList()
        abilities_list.load()

        # カメラに接続
        idx = port_info_list.lookup_path(addr)
        self._camera.set_port_info(port_info_list[idx])
        idx = abilities_list.lookup_model(name)
        self._camera.set_abilities(abilities_list[idx])
        self._camera.init()

        # カメラの情報表示
        text = self._camera.get_summary()
        self._logger.info("Connected to camera.")
        self._logger.info("======= Summary info.")
        self._logger.info(str(text))

        # カメラの全設定ウィジェットを取得
        self._config = self._camera.get_config()
        self._logger.info("======= Current configurations")
        self._widgets = dict([self._get_config(self._config)])

    def __del__(self):
        # カメラをクローズ
        self._camera.exit()

    # カメラの設定ウィジェットを再帰的に取得
    def _get_config(self, config, depth=0):
        label = config.get_label()
        count = config.count_children()
        if count == 0 :

            # 現在値と選択肢を取得
            widget_type =config.get_type()
            if widget_type==gp.GP_WIDGET_RADIO or widget_type == gp.GP_WIDGET_MENU :
                choices = [c for c in config.get_choices()]
                value =config.get_value()
                self._logger.info( ' '*depth*4+f"{label} : {value}" )
                self._logger.debug( ' '*depth*4+f"{label} : choices = {choices}" )
                return ( label,{'widget':config,'current':value, 'choices':choices} )
            
            else:
                try :
                    value =config.get_value()
                    self._logger.info( ' '*depth*4+f"{label} : {value}" )
                    return ( label,{'widget':config,'current':value} )
                except:
                    self._logger.info( ' '*depth*4+f"{label} : (unknown type)" )
                    return ( label,{'widget':config,'current':None} )

        else:
            self._logger.info( ' '*depth*4+f"{label} :" )
            return ( label,dict([self._get_config(config.get_child(i), depth+1) for i in range(count)]) )

    # カメラの設定を変更
    def setting_change(self, param, value):
        idx = param.split('/')
        config = self._widgets
        for i in idx:
            config = config[i]
        
        # 選択できる選択肢が与えられている場合には事前にチェック
#        if 'choices' in config:
#            if value not in config['choices'] :
#                self._logger.error( f"You set {value} for [{param}]." )
#                self._logger.error( f"Value can be choosen from {config['choices']}" )
#                raise ValueError()

        # 必要があれば設定を変更            
        if config['current'] != value:
            config['widget'].set_value(value)
            self._logger.debug( f"[{param}] Setting changed from {config['current']} to {value}" )
            self._setting_updated = True
            config['current'] = value

    # 設定変更をカメラに適用
    def apply_setting(self):
        if not self._setting_updated :
            return

        retry = True
        while retry:
            try:
                self._camera.set_config(self._config)
                retry = False
            except Exception as e:
                self._logger.info( traceback.format_exc() )

                # カメライベントループの開始
                event_timeout = 5000  # イベントを待機するタイムアウト時間（ミリ秒）を設定
                event_type, event_data = self._camera.wait_for_event(event_timeout)
                self._logger.info( f"retry[setting] :Type={event_type}, Data={event_data}" )

        self._setting_updated = False

    # 撮影条件を指定して撮影
    def exposure(self, params={}):
        # 撮影設定
        for key,value in params.items() :
            self.setting_change(key, value)
        self.apply_setting()

        # 撮影を行って、撮影完了まで待機
        retry = True
        while retry:
            try:
                self._camera.trigger_capture()
                retry = False
            except:
                # カメライベントループの開始
                event_timeout = 5000  # イベントを待機するタイムアウト時間（ミリ秒）を設定
                event_type, event_data = self._camera.wait_for_event(event_timeout)
                self._logger.debug( f"retry[setting] :Type={event_type}, Data={event_data}" )

    # ログハンドラー
    def _callback(self, level, domain, string, data=None):
        self._logger.debug(f"[GPhoto2] level = {level}, domain = {domain}, string = {string}, data = {data}" )


# 複数の設定が列記されている場合の組みあわせを作成する関数
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

    #現在時刻の取得(utc基準)
    now = get_current_time()

    # loggerの生成
    logger = logging.getLogger('mylog')
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler('eclipse_shooter.log')
    sh = logging.StreamHandler()
    logger.addHandler(fh)
    logger.addHandler(sh)
    fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    sh.setFormatter(logging.Formatter('%(message)s'))
    sh.setLevel(logging.INFO)

    # カメラの初期化
    camera = camera_control(logger)

    # カメラに初期設定を適用
    camera.setting_change('Camera and Driver Configuration/Camera Settings/Capture Target', 'Memory card')
    camera.setting_change('Camera and Driver Configuration/Capture Settings/Drive Mode', 'Single')
    camera.apply_setting()

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

    # 撮影ループ
    while True:
        now = get_current_time()
        # イベント時刻（第一接触、第二接触、第三接触）までの時間（秒数）をカウントダウン
        logger.info( "now:{}UTC {}".format(now.strftime('%H:%M:%S'),[title[:3]+':'+str(int((event-now).total_seconds())) for title,event in event_time]),extra={'date':'(utc:{})'.format(str(now)[11:19])} )

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
                    params = {'Camera and Driver Configuration/Capture Settings/Shutter Speed': str(cond['ss']),
                              'Camera and Driver Configuration/Image Settings/ISO Speed': str(cond['iso']),
                              'Camera and Driver Configuration/Image Settings/Image Format': str(cond['format']),
                              'Camera and Driver Configuration/Image Settings/WhiteBalance': str(cond['white_balance'])}
                    if cond['color_temperature']!='nan':
                        params['Camera and Driver Configuration/Image Settings/Color Temperature'] = str(int(float(cond['color_temperature'])))
                    camera.exposure(params)

                    # 撮像後のスリープ時間などは実際にEOS6Dでトラブルなく撮影できるように追加したので、それぞれの機種や環境で評価必要
                    #   EOS RPの場合：1.3以上
                    #   EOS 6Dの場合：1.2以上
                    #   EOS 6D(ミラーアップ)の場合：1.0以上
                    time.sleep(1.5)
                    
                exposure[row['title']]['last'] = now

        time.sleep(1)

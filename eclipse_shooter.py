# coding: utf-8
from datetime import datetime, timedelta, timezone
import logging
import pandas as pd
import time
import warnings
warnings.simplefilter('ignore')
import gphoto2 as gp

# 現在時刻取得（撮影テスト時に時刻をずらして実験するためにshiftを指定することが出来ます）
def get_current_time(shift=0):
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
    d = datetime.now(timezone.utc) + timedelta(hours=shift)
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

        # カメラ名でログファイルを生成
        fh = logging.FileHandler(name.replace(' ','_')+'.log')
        logger.addHandler(fh)
        fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))

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
        #レリーズOFFしてからクローズ
        self.release_off()

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

    # 撮影条件を指定して適用
    def setting_params(self, params={}):
        while True:
            # 撮影設定
            for key,value in params.items() :
                self.setting_change(key, value)

            if not self._setting_updated :
                return

            if self.apply_setting():
                self.sleep(comment='after apply', event_timeout=100, target=[gp.GP_EVENT_TIMEOUT])
                return

            self.sleep(sec=1.0, event_timeout=1000, comment='wait retry')

    # カメラの現在設定を取得
    def get_current_value(self, param, get_value=False):
        idx = param.split('/')
        config = self._widgets
        for i in idx:
            config = config.get(i,{})

        if get_value :
            # 実際にカメラから読み込む
            return config['widget'].get_value()
        else:
            # 現在設定している値を返す
            return config['current']

    # カメラの設定を変更
    def setting_change(self, param, option):
        idx = param.split('/')
        config = self._widgets
        for i in idx:
            config = config.get(i,{})

        # 与えられたパラメータがリストの場合（優先順位をもったパラメータ）
        if type(option)==list :
            try:
                value = [v for v in option if v in config.get('choices',[])][0]
            except:
                value = option[0]
        else:
            value = option

        # 必要があれば設定を変更            
        if config['current'] != value:
            config['widget'].set_value(value)
            self._logger.debug( f"[{param}] Setting changed from {config['current']} to {value}" )
            self._setting_updated = True
            config['current'] = value

    # 設定変更をカメラに適用
    def apply_setting(self):
        if not self._setting_updated :
            return True

        try:
            self.sleep(comment='wait idle', event_timeout=50, target=[gp.GP_EVENT_TIMEOUT])
            self._camera.set_config(self._config)
        except Exception as e:
            self._logger.debug( f"gphoto2.GPhoto2Error: {e}" )
            return False

        self._setting_updated = False
        return True

    # 撮影条件を指定して撮影
    def exposure(self):
        # 撮影を行って、撮影完了まで待機
        while True:
            try:
                self._camera.trigger_capture()
                break
            except:
                self.sleep(comment='retry[exposure]', event_timeout=50, target=[gp.GP_EVENT_TIMEOUT])

    # 撮影条件を指定してレリーズON
    def release_on(self):
        while True:
            self.setting_change('Camera and Driver Configuration/Camera Actions/Canon EOS Remote Release', 'Press Full')
            if not self.apply_setting():
                continue
            break

    # レリーズOFF
    def release_off(self):
        while True:
            self.setting_change('Camera and Driver Configuration/Camera Actions/Canon EOS Remote Release', 'None')
            if not self.apply_setting():
                continue
            break

    def sleep(self, sec=60, event_timeout=100, comment='waiting..', target=[gp.GP_EVENT_CAPTURE_COMPLETE]):
        # イベントを待機するタイムアウト時間（ミリ秒）を設定
        start = time.time()
        while start+sec>time.time() :
            event_type, event_data = self._camera.wait_for_event(event_timeout)
            if event_type==gp.GP_EVENT_UNKNOWN :
                self._logger.debug( f"{comment} :Type=GP_EVENT_UNKNOWN, Data={event_data}" )
            elif event_type==gp.GP_EVENT_TIMEOUT :
                self._logger.debug( f"{comment} :Type=GP_EVENT_TIMEOUT" )
            elif event_type==gp.GP_EVENT_FILE_ADDED :
                self._logger.info( f"{comment} :Type=GP_EVENT_FILE_ADDED, Data={event_data.folder}/{event_data.name}" )
            elif event_type==gp.GP_EVENT_CAPTURE_COMPLETE :
                self._logger.info( f"{comment} :Type=GP_EVENT_CAPTURE_COMPLETE" )
            else :
                self._logger.info( f"{comment} :Type={event_type}, Data={event_data}" )
            
            # ターゲットが来たら終了
            if event_type in target :
                return

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
    sh = logging.StreamHandler()
    logger.addHandler(sh)
    sh.setFormatter(logging.Formatter('%(message)s'))
    sh.setLevel(logging.INFO)

    # カメラの初期化
    camera = camera_control(logger)

    # カメラに初期設定を適用
    params = {'Camera and Driver Configuration/Camera Settings/Capture Target' : 'Memory card',
              'Camera and Driver Configuration/Capture Settings/Metering Mode' : 'Center-weighted average' }
    camera.setting_params(params)

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
                          'interval':row['interval(sec)'],
                          'ss':row['ss'], 'bracket':row['bracket'], 'iso':row['iso'],
                          'format':row['format'],
                          'white_balance':row['white_balance'], 'color_temperature':row['color_temperature']})
        exposure[row['title']] = {'last': now, 'list': pd.DataFrame(data).set_index('utc').sort_index().groupby(level=0).last()}
        logger.info("{}\n{}\n".format(row['title'],exposure[row['title']]['list'])+'-'*50 )

    # 撮影ループ
    second = -1
    while True:
        now = get_current_time()

        if now.second != second :
            second = now.second
            # イベント時刻（第一接触、第二接触、第三接触）までの時間（秒数）をカウントダウン
            logger.info( "now:{}UTC {} Batt.{}".format(
                    now.strftime('%H:%M:%S'),
                    [title[:3]+':'+str(int((event-now).total_seconds())) for title,event in event_time],
                    camera.get_current_value('Camera and Driver Configuration/Other PTP Device Properties/Battery Level', get_value=True)
                ),extra={'date':'(utc:{})'.format(str(now)[11:19])} )

        # すべての撮影スクリプトリストのうち
        queue_list = []
        for title, i in exposure.items() :
            # 現在時刻よりも前の物（撮影時刻になったもの）で未撮影の物(lastより後）をピックアップ
            target = i['list'][i['last']:now]
            if len(target)>0 :
                logger.debug("\n{}".format(target))
                # 最後の１個だけをピックアップ（撮影中に複数のトリガーが発生した場合は直近のトリガーのみを扱う）
                for index, row in target.tail(1).iterrows():
                    queue_list.append( {'title':title, 'utc':index, 'interval':row['interval'],
                                        'ss':row['ss'], 'bracket':row['bracket'], 'iso':row['iso'],
                                        'format':row['format'],
                                        'white_balance':row['white_balance'], 'color_temperature':row['color_temperature']} )

        if queue_list :
            # 複数のスクリプトからトリガーが発動されていれば、トリガー発動済みの中で最も古いものを撮影処理
            for index, row in pd.DataFrame(queue_list).set_index('utc').sort_index().head(1).iterrows():
                # 組み合わせの生成
                keys = ['ss','bracket','iso','format','white_balance','color_temperature']
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

                    if cond['bracket']!='nan' and cond['bracket']!='Single':
                        # AEブラケット撮影
                        camera.setting_params({'Camera and Driver Configuration/Capture Settings/Drive Mode':['Super high speed continuous shooting','Continuous high speed']})
                        camera.setting_params({'Camera and Driver Configuration/Capture Settings/Bracket Mode':'AE bracket'})
                        camera.setting_params({'Camera and Driver Configuration/Capture Settings/Auto Exposure Bracketing':str(cond['bracket'])})
                        camera.setting_params(params)

                        camera.release_on()

                        # GP_EVENT_CAPTURE_COMPLETE または GP_EVENT_TIMEOUT(3sec) が来るまでシャッターON
                        camera.sleep(comment='release_on', event_timeout=3000, target=[gp.GP_EVENT_CAPTURE_COMPLETE,gp.GP_EVENT_TIMEOUT])
                        camera.release_off()

                    else:
                        if camera.get_current_value('Camera and Driver Configuration/Capture Settings/Auto Exposure Bracketing')!='off' :
                            camera.exposure()
                            # GP_EVENT_CAPTURE_COMPLETE または GP_EVENT_TIMEOUT(1sec) が来るまでシャッター待機
                            camera.sleep(sec=3.0, comment='dummy exposure', event_timeout=1000, target=[gp.GP_EVENT_CAPTURE_COMPLETE,gp.GP_EVENT_TIMEOUT])

                        # １枚ずつ設定・撮影
                        camera.setting_params({'Camera and Driver Configuration/Capture Settings/Auto Exposure Bracketing':'off'})
                        camera.setting_params({'Camera and Driver Configuration/Capture Settings/Drive Mode':'Single'})
                        camera.setting_params({'Camera and Driver Configuration/Capture Settings/Bracket Mode':'Unknown value 0000'})
                        camera.setting_params(params)
                        camera.exposure()

                        # GP_EVENT_CAPTURE_COMPLETE または GP_EVENT_TIMEOUT(1sec) が来るまでシャッター待機
                        camera.sleep(sec=3.0, comment='exposure', event_timeout=1000, target=[gp.GP_EVENT_CAPTURE_COMPLETE,gp.GP_EVENT_TIMEOUT])

                exposure[row['title']]['last'] = now

        camera.sleep(0.1, event_timeout=10, comment='idle' )

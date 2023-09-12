# eclipse_shooter

PythonでGPhoto2を利用してEOS 6Dなどのデジタルカメラを操作し、エクセルで指定したスクリプトに沿って自動的に日食の撮影を行います。
Raspberry piなどを利用して稼働させることでPCレスで撮影を行う事が出来ます。

* GPhoto2 対応機種リスト　http://www.gphoto.org/proj/libgphoto2/support.php


# 自動撮影スクリプト例
サンプルコードでは **usa_eclipse.xlsx** を読み込み、列記された撮影シーケンスを実行します。 

撮影シーケンスは基準時刻(utc列)に対して相対値(秒)で指定された開始時間(time列)から開始し、指定した間隔(interval列)で指定した回数(count列)の撮影を行います。 

撮影条件はiso, ss, format, ホワイトバランス(色温度)が指定出来、カンマで複数指定した場合には列記した条件すべてを順に撮影します。

![サンプルスクリプト](images/script.png "usa_eclipse.xlsx")

# 必要なパッケージ

### GPhoto2 
* Gphoto2 公式ページ http://www.gphoto.org/

こちらの記事を参考にして GPhoto2をインストールしました。
https://www.moyashi-koubou.com/blog/dslr_camera_raspberrypi/

```
$ wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh && wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/.env && chmod +x gphoto2-updater.sh && sudo ./gphoto2-updater.sh
```

### libcblas.so.3
```
$ sudo apt-get install libatlas-base-dev
```

### Pythonのライブラリパッケージ

動作に必要なライブラリを pip install などでインストールします。(括弧内は当方で動作確認済みのバージョン)
* numpy (1.25.2)
* pandas (2.0.3)
* openpyxl (3.1.2)
* gphoto2 (2.5.0)

# 実行結果例

![実行結果](images/result.png)

# 免責事項

* 必ずご自身で動作確認して、ご自身の責任においてご使用ください。
* 日食のタイミングに上手く動作しなかったとしても保証しかねます。

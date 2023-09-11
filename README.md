# eclipse_shooter
Shooting script for Eclipse with Gphoto2

PythonでGPhoto2を利用してEOS 6Dなどのデジタルカメラを操作し、エクセルで指定したスクリプトに沿って自動的に日食の撮影を行います。
Raspberry piなどを利用して稼働させることでPCレスで撮影を行う事が出来ます。

# 自動撮影スクリプト例
サンプルコードでは **usa_eclipse.xlsx** を読み込み、列記された撮影シーケンスを実行します。 

撮影シーケンスは基準時刻(utc列)に対して相対値(秒)で指定された開始時間(time列)から開始し、指定した間隔(interval列)で指定した回数(count列)の撮影を行います。 

撮影条件はiso, ss, format, ホワイトバランス(色温度)が指定出来、カンマで複数指定した場合には列記した条件すべてを順に撮影します。

![サンプルスクリプト](images/script.png)

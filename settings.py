from os import environ

SESSION_CONFIGS = [
    dict(
        name='trust_baseline',
        display_name='信任博弈 — 基线组（无沟通）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=False,
        doc='标准信任博弈，全程匿名，无任何沟通',
    ),
    dict(
        name='trust_communication',
        display_name='信任博弈 — 沟通组',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=True,
        doc='信任博弈，双方在决策前同时发送预设消息并互相可见',
    ),
    # 演示专用：-- 以下是两个「演示·单步」config。
    # use_browser_bots=True 让全体被试成为 browser bot（页面自动填写），
    # 单步控制台再据此把自动提交挡下来，改为按按钮驱动。
    # ！！绝不可把该键挪到上面两个真实 config 上！！——
    # 那样真实被试会被当成 bot、页面被自动提交，而数据照样入库、
    # otree test 照样全绿。trust_game/test_settings.py 会拦下这种改动。
    dict(
        name='trust_baseline_bots',
        display_name='信任博弈 — 基线组（演示·单步）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=False,
        use_browser_bots=True,
        doc='演示专用，非真实数据；配套 _static/global/step_console.html',
    ),
    dict(
        name='trust_communication_bots',
        display_name='信任博弈 — 沟通组（演示·单步）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=True,
        use_browser_bots=True,
        doc='演示专用，非真实数据；配套 _static/global/step_console.html',
    ),
]

# 规格第 11 节：出场费 20 元，1 点 = 1 元
SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00,
    participation_fee=20.00,
    doc='',
)

PARTICIPANT_FIELDS = []
SESSION_FIELDS = []

LANGUAGE_CODE = 'zh-hans'

REAL_WORLD_CURRENCY_CODE = 'CNY'
USE_POINTS = True

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """
<p><b>演示模式（单步）</b></p>
<p>1. 点下面任一「演示·单步」配置创建会话；<br>
2. 从地址栏复制会话码（<code>/SessionStartLinks/&lt;码&gt;</code>）；<br>
3. 打开
<a href="/static/global/step_console.html">/static/global/step_console.html</a>
并填入会话码；<br>
4. 按「全部前进一页」——按一次，8 人各填一页。</p>
<p>「连续跑完」按钮会撤掉单步开关，让机器人自动跑完全程。</p>
"""

# 与 ADMIN_PASSWORD 同一条纪律：该文件会进版本库，故密钥只从运行时环境读，
# 不在仓库里存真值。默认值仅供 otree test / devserver 本地跑通用，正式收集数据
# 前必须用环境变量替换（见 README「注意事项」第 2 条）。
# oTree 在 otree/common.py:125 直接做 settings.SECRET_KEY + ADMIN_PASSWORD 的
# 字符串拼接（用于 make_hash），故该值必须是字符串、不能为 None。
SECRET_KEY = environ.get('OTREE_SECRET_KEY', 'dev-only-not-for-production')

ROOMS = []

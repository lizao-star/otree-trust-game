from os import environ

# 四个处理组，2×2 析因：A（投资者）能否给 B 发消息 × B（受托人）能否给 A 发消息。
#
# 处理组由**两个布尔键**决定，而不是一个枚举字符串：四格就是两个因子的四种
# 组合，导出数据里两列直接进双因素分析；换成一个四值字符串的话，分析时得把
# 两个因子再拆回来，拆错（例如把 'both' 当成只有 B 发）不会有任何报错。
#
# 键名与「谁能给谁发」一一对应：
#   investor_sends_message = 投资者 A 能否给受托人 B 发一条意向消息
#   trustee_sends_message  = 受托人 B 能否给投资者 A 发一条承诺消息
#
# 名字与两个键的一致性由 trust_game/test_settings.py 的 CONDITIONS 表钉死。
SESSION_CONFIGS = [
    dict(
        name='trust_none',
        display_name='信任博弈 — 无沟通',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        investor_sends_message=False,
        trustee_sends_message=False,
        doc='标准信任博弈，全程匿名，双方向均无任何信息交流',
    ),
    dict(
        name='trust_b_to_a',
        display_name='信任博弈 — 仅 B→A（承诺）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        investor_sends_message=False,
        trustee_sends_message=True,
        doc='受托人 B 在决策前发一条承诺消息，投资者 A 只读、不能回发',
    ),
    dict(
        name='trust_a_to_b',
        display_name='信任博弈 — 仅 A→B（意向）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        investor_sends_message=True,
        trustee_sends_message=False,
        doc='投资者 A 在决策前发一条意向消息，受托人 B 只读、不能回发',
    ),
    dict(
        name='trust_both',
        display_name='信任博弈 — 双向沟通',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        investor_sends_message=True,
        trustee_sends_message=True,
        doc='双方在决策前同时发送预设消息并互相可见',
    ),
    # 演示专用：-- 以下是四个「演示·单步」config，与上面四个真实 config 一一对应，
    # 两个处理组键逐值相同（test_settings.py 会核对镜像关系）。
    # use_browser_bots=True 让全体被试成为 browser bot（页面自动填写），
    # 单步控制台再据此把自动提交挡下来，改为按按钮驱动。
    # ！！绝不可把该键挪到上面四个真实 config 上！！——
    # 那样真实被试会被当成 bot、页面被自动提交，而数据照样入库、
    # otree test 照样全绿。trust_game/test_settings.py 会拦下这种改动。
    dict(
        name='trust_none_bots',
        display_name='信任博弈 — 无沟通（演示·单步）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        investor_sends_message=False,
        trustee_sends_message=False,
        use_browser_bots=True,
        doc='演示专用，非真实数据；配套 _static/global/step_console.html',
    ),
    dict(
        name='trust_b_to_a_bots',
        display_name='信任博弈 — 仅 B→A（演示·单步）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        investor_sends_message=False,
        trustee_sends_message=True,
        use_browser_bots=True,
        doc='演示专用，非真实数据；配套 _static/global/step_console.html',
    ),
    dict(
        name='trust_a_to_b_bots',
        display_name='信任博弈 — 仅 A→B（演示·单步）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        investor_sends_message=True,
        trustee_sends_message=False,
        use_browser_bots=True,
        doc='演示专用，非真实数据；配套 _static/global/step_console.html',
    ),
    dict(
        name='trust_both_bots',
        display_name='信任博弈 — 双向沟通（演示·单步）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        investor_sends_message=True,
        trustee_sends_message=True,
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
<p>「连续跑完」按钮会反复点击直到全部跑完，中途再按一次可停下。</p>
"""

# 与 ADMIN_PASSWORD 同一条纪律：该文件会进版本库，故密钥只从运行时环境读，
# 不在仓库里存真值。默认值仅供 otree test / devserver 本地跑通用，正式收集数据
# 前必须用环境变量替换（见 README「注意事项」第 2 条）。
# oTree 在 otree/common.py:125 直接做 settings.SECRET_KEY + ADMIN_PASSWORD 的
# 字符串拼接（用于 make_hash），故该值必须是字符串、不能为 None。
SECRET_KEY = environ.get('OTREE_SECRET_KEY', 'dev-only-not-for-production')

ROOMS = []

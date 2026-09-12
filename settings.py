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
    # Task 3 加回沟通组（届时 MessageSend/MessageReveal 模板才存在）
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

DEMO_PAGE_INTRO_HTML = """信任博弈实验 — 演示"""

SECRET_KEY = 'trust-game-experiment-secret-key-2026'

ROOMS = []

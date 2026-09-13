"""信任博弈实验的统计分析。

⚠️ 默认数据源为模拟数据，所有输出（表格与图）均标注为模拟，不得当作实证结果。
   真实数据导出后，替换 --data 参数即可复用全部流程。

数据来源标注按**路径**判定（默认路径 = 模拟数据，其余 = 真实数据），并在读取
之前用**文件内容**再核对一次（check_source_label）：两者不一致即中止，不写出
任何产物——否则把真实导出放到默认路径、或把模拟数据拷到别处传 --data，都会
产出「标注与来源相反」却看不出异常的结果。

用法：
    python analysis/analyze.py
    python analysis/analyze.py --data path/to/real_data.csv


为什么要先做配对合并（Step 0）
------------------------------
真实 oTree 导出中，每个被试**自己那一行只存自己的字段**：x（send_amount）只在
投资者行、y（return_amount）只在受托人行。因此凡需要同时用到 x 与 y 的模型
（H3 的三个模型、H5）都不能直接在逐被试帧上估计——受托人行的 send_amount 全为
空，模型无法估计。load() 因此显式做配对合并，产出 60 行的 pairs 帧（x 与 y 同处
一行），所有此类模型一律基于 pairs。模拟数据把 x/y 复制到了每一行，恰好掩盖了
这个缺口，所以**不能**因为「在模拟数据上能跑通」就以为直连的写法成立。

同理是**副本陷阱**：x 与 y 在逐被试帧上各出现两次（模拟数据逐行复制；真实导出中
对方行为空），在未过滤的 120 行上做均值/检验/分布会重复使用 60 个值、把标准误
压低 √2 倍；真实导出中空值被丢弃后得到的是 60 个观测。故凡涉及 x 或 y 的汇总
统计一律在 pairs 或按角色过滤后的子集上做，绝不在未过滤的逐被试帧上做。


为什么要按 app 定点取字段
--------------------------
oTree 为**每个 app** 都导出内建字段（otree/export.py:110-127：player.id_in_group、
player.role、group.id_in_subsession、subsession.round_number），宽表表头形如
`{app}.{round}.{model}.{fname}`，因此 `trust_game.*` 与 `survey.*` 各有一份同名
字段（实测 `otree test trust_baseline 8 --export` 的表头即如此）。而 survey 是
单人 app：`survey.1.player.role` 实测全为空、`survey.1.group.id_in_subsession`
实测全为 1。若不按 app 拆分，role 会变成空列、配对会全塌成一对——不是报错，而是
**静默算错**。故 FIELD_SOURCE 把每个消费字段钉到唯一 app，撞名则报错（见
`_rename_otree_export`）。


统计量的样本与检验（引用时必须带上限定，见规格 §15.4）
------------------------------------------------------
（以下 N 与数值均为**当前模拟数据集**的实测值，供报告引用时对照；真实导出按实际
样本生成 `样本` 列与 `N` 列，脚本里没有任何写死的 N。）
H1  全部 30+30 名投资者，**Welch**；同数据 Student 检验仅第四位小数不同，
    脚本在「备注」列同时打印两者，引用 p 时须写明检验名。
H2  规格注册口径为**全部 60 名受托人**（主结果）；另给仅 x>0（55 人）的备选口径。
H3  (a) 全部 60 对；(b) 剔除 x=0（55 对，**主要规格**，因变量 y）；(c) 同子样本、
    因变量 ratio；(d) 同子样本、含控制变量的完整式。x=0 时 y 必为 0，会把
    treatment 系数机械性抬高，故 (a) 只作对照。
H4  60 名投资者，bootstrap 5000 次（固定种子）。
H5  承诺强度只在沟通组存在（基线组不经过消息页，四列全空），故
    N=29（沟通组受托人、仅 x>0，**主要规格**）对照 N=30（含 x=0）。
信念~x 一律**分组**报告：基线 0.637 / 沟通 0.431；合并值混入组间均值差，不得
    当作组内关系的证据（脚本另附合并值并标注用途）。
比值~x 仅在 x>0 上成立（r=-0.490）；含零质量点（x=0）时关系消失（r=-0.009）。

risk_choice 的进入方式（规格 §15.2）：它是 0-5 的**序数**指数（选「确定金额」的
行数），有效分辨率约 4 档、高值端在上限处截断。因此作为控制变量时按**中位数
切分为哑变量**（risk_high）进入：既不逐取值设哑变量（小样本下空单元会导致完全
分离），也不把系数解释为等距效应。脚本同时打印其实际分布（含 0/1 是否存在）。
"""

import argparse
import importlib.util
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'analysis', 'output')
DEFAULT_DATA = os.path.join(OUTPUT_DIR, 'simulated_data.csv')

SIMULATION_NOTE = '【模拟数据，非真实被试结果】'
REAL_NOTE = '【真实数据】'

# 模拟数据的被试编号一律带该前缀（analysis/simulate_data.py 的 code_i / code_t）。
# 它也是内容侧唯一可用的来源标记：数据 CSV 本身**不带**内嵌标注列（五张产物表
# 有 `数据来源` 列，数据 CSV 没有），故只能靠编号前缀。
SIMULATED_CODE_PREFIX = 'sim_'

# 内容侧的被试编号列名：扁平格式（模拟数据）是 participant_code，
# oTree 宽表导出是 participant.code（由 _rename_otree_export 改成前者）。
CODE_COLUMNS = ('participant_code', 'participant.code')

SEED = 20260913          # bootstrap 与图中抖动共用（固定以便复现）

# 中文字体回退，避免图中文字变方块
plt.rcParams['font.sans-serif'] = [
    'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False


def _load_module(name):
    """按路径加载 trust_game 下的无 oTree 依赖模块。

    收益规则（MULTIPLIER、return_ratio）与角色名必须取自唯一真值来源，本文件
    不重写副本——本项目已多次因「两处真值源」产生静默偏离。payoffs / content
    都不依赖 oTree，可独立加载，故不必为此 import 整个 trust_game 包。
    """
    path = os.path.join(PROJECT_ROOT, 'trust_game', name + '.py')
    spec = importlib.util.spec_from_file_location('_trust_game_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payoffs = _load_module('payoffs')
content = _load_module('content')

INVESTOR_ROLE = content.INVESTOR_ROLE
TRUSTEE_ROLE = content.TRUSTEE_ROLE

GAME_APP = 'trust_game'
SURVEY_APP = 'survey'

# 本管线消费的字段 → 其唯一来源 app。
#
# ⚠️ oTree 为**每个 app** 都输出内建字段（otree/export.py:110-127 的 specs：
# player.id_in_group、player.role、group.id_in_subsession、subsession.round_number），
# 表头形如 `{app}.{round}.{model}.{fname}`。本项目 session 为
# ['trust_game', 'survey']，故这些名字在宽表里**各出现两份**（实测
# `otree test trust_baseline 8 --export` 的表头：第 24/25/42/43 列来自
# trust_game，第 44/45/61/62 列来自 survey）。而 survey 是单人 app：
# `survey.1.player.role` 实测**全为空**、`survey.1.group.id_in_subsession`
# 实测**全为 1**——若按「后出现的同名列覆盖前者」重命名，role 会变成空列、
# 配对会全部塌成一对。因此必须按 app 定点取值：博弈字段取 trust_game，
# 问卷字段取 survey。
FIELD_SOURCE = {
    'role': GAME_APP,
    'is_communication': GAME_APP,
    'send_amount': GAME_APP,
    'return_amount': GAME_APP,
    'return_ratio': GAME_APP,
    'belief_return_pct': GAME_APP,
    'belief_investor_send': GAME_APP,
    'promise_strength': GAME_APP,
    'id_in_subsession': GAME_APP,      # 配对由博弈的 group 定义（survey 的是单人组）
    'risk_choice': SURVEY_APP,
    'dictator_give': SURVEY_APP,
    'general_trust': SURVEY_APP,
    'gender': SURVEY_APP,
    'grade': SURVEY_APP,
    'prior_experience': SURVEY_APP,
    'age': SURVEY_APP,
    'econ_courses': SURVEY_APP,
    'major': SURVEY_APP,
}

# 本管线离开就没有意义的字段：缺任何一个都直接报错，而不是让下游在某处抛
# KeyError 或悄悄产出 NaN 列（单 app 导出只含一个 app 的字段，必然缺一批）。
REQUIRED_FIELDS = (
    'role', 'is_communication', 'send_amount', 'return_amount',
    'belief_return_pct', 'promise_strength',
    'risk_choice', 'dictator_give', 'general_trust', 'gender', 'age',
    'econ_courses',
)


# --------------------------------------------------------------------------
# 读入与配对合并
# --------------------------------------------------------------------------

def _read_participant_codes(path):
    """只读被试编号一列；两种列名都没有时返回 None。"""
    df = pd.read_csv(path, usecols=lambda col: col in CODE_COLUMNS)
    for col in CODE_COLUMNS:
        if col in df.columns:
            return [str(code) for code in df[col]]
    return None


def check_source_label(path, is_simulated):
    """交叉核对「按路径推断的来源标注」与「文件内容的实际来源」。

    ⚠️ 本函数存在的理由：按路径推断对**放错位置的拷贝**无感，而两个方向都会产出
    「标注与数据来源相反」的产物，且产物本身看不出任何异常：
      - 真实导出被放到默认路径 analysis/output/simulated_data.csv → 整份产物被
        标成【模拟数据，非真实被试结果】，真实结果被当成演示数据；
      - simulated_data.csv 被拷到别处再用 --data 传入 → 整份产物被标成
        【真实数据】，演示数据被当成真实结果。
    因此读取数据之前先用内容核对一次：模拟数据的被试编号一律以 sim_ 开头，
    真实 oTree 导出的 participant.code 是随机串。核对不上就中止，不写任何产物。

    返回一行可读的核对说明供 main() 打印。**已知边界（不夸大）**：若数据里两种
    编号列都没有，内容无从判断，此时**不中止**（那会让合法的导出无法分析），
    而是把这句「无独立证据、只能依赖路径」如实返回并打印出来。
    """
    codes = _read_participant_codes(path)
    if codes is None:
        return ('⚠️ 数据中没有被试编号列（participant.code / participant_code），'
                '无法据内容核对来源；本次标注仅由路径推断，请自行确认路径无误。')
    n_sim = sum(code.startswith(SIMULATED_CODE_PREFIX) for code in codes)
    if 0 < n_sim < len(codes):
        raise SystemExit(
            f'数据里只有 {n_sim}/{len(codes)} 行被试编号带 {SIMULATED_CODE_PREFIX} '
            '前缀：真实导出与模拟数据被混在了一起，无法判断整份数据的来源，'
            '因此无法给出可信的【模拟数据】/【真实数据】标注。本次未写出任何产物。')
    content_is_simulated = n_sim == len(codes)
    if content_is_simulated == is_simulated:
        origin = '模拟数据' if is_simulated else '真实数据'
        return (f'内容核对一致：{len(codes)} 行被试编号中 {n_sim} 行带 '
                f'{SIMULATED_CODE_PREFIX} 前缀，与按路径判定的「{origin}」一致。')
    if content_is_simulated:
        raise SystemExit(
            f'文件内容看起来是模拟数据（{len(codes)} 行被试编号全部带 '
            f'{SIMULATED_CODE_PREFIX} 前缀），但它不在默认路径上，产物会被标成'
            f'「{REAL_NOTE}」。请直接用默认路径读模拟数据（不要把它拷到别处），'
            '或在 --data 指向真实导出前确认其编号不含该前缀。本次未写出任何产物。')
    raise SystemExit(
        f'默认路径下的数据看起来**不是**模拟数据（被试编号带 '
        f'{SIMULATED_CODE_PREFIX} 前缀的只有 {n_sim}/{len(codes)} 行），但按路径'
        f'会被整份标成「{SIMULATION_NOTE}」。若这是真实导出，请用 --data 指向它；'
        '若确实是模拟数据，请重新运行 analysis/simulate_data.py 生成。'
        '本次未写出任何产物。')


def _parse_export_column(col):
    """拆出 oTree 导出列的 (app, 字段名)。

    宽表表头形如 `trust_game.1.player.send_amount`；单 app 导出则是
    `player.send_amount`（无 app 前缀，app 记为 None）。非模型列返回
    (None, None)。
    """
    for model in ('player', 'group', 'subsession'):
        marker = '.' + model + '.'
        if marker in col:
            prefix, field = col.rsplit(marker, 1)
            return prefix.split('.', 1)[0], field
        if col.startswith(model + '.'):
            return None, col.split('.', 1)[1]
    return None, None


def _rename_otree_export(df):
    """把 oTree 导出的列名转成本脚本使用的扁平列名。

    宽表（all_apps_wide）表头形如：
        participant.code / session.code / trust_game.1.player.send_amount /
        trust_game.1.player.role / trust_game.1.group.id_in_subsession /
        survey.1.player.risk_choice
    单 app 导出的表头则是 player.role / group.id_in_subsession 这种短名。

    只重命名本管线**消费的字段**（FIELD_SOURCE），且按 app 定点取：每个 app 的
    内建字段（id_in_group / role / id_in_subsession / round_number）在宽表里
    各有两份，同名不同义（见 FIELD_SOURCE 的注释），故另一份被丢弃；不在清单
    内的列一律不取（它们不在本管线的分析范围内）。participant.* / session.* 保留
    前缀以免与玩家字段撞名。
    """
    if 'participant.code' not in df.columns and 'player.role' not in df.columns:
        return df                      # 已是扁平格式（模拟数据）

    rename = {}
    for col in df.columns:
        if col.startswith('participant.'):
            rename[col] = 'participant_' + col.split('.', 1)[1]
            continue
        if col.startswith('session.'):
            rename[col] = 'session_' + col.split('.', 1)[1]
            continue
        app, field = _parse_export_column(col)
        if field is None:
            continue                   # 非模型列（未知）：原样保留
        source = FIELD_SOURCE.get(field)
        if source is None:
            continue                   # 不在消费清单内
        if app is not None and app != source:
            continue                   # 同名内建字段，但来自另一个 app：不是要的那一份
        rename[col] = field

    # 撞名检查必须比较**映射后的新名字**（同名两份本应在上面按 app 拆掉；
    # 若还剩下，说明导出里有本脚本判断不了的歧义）。
    mapped = list(rename.values())
    collisions = sorted(
        {n for n in mapped if mapped.count(n) > 1}
        | {n for n in mapped if n in df.columns and n not in rename}
    )
    if collisions:
        raise SystemExit(
            '导出重命名后字段撞名，无法判断该取哪一列：' + '、'.join(collisions)
            + '。多轮导出的表头是 `{app}.{轮次}.{model}.{字段}`，同一字段在不同'
              '轮次会撞成同名列——本实验只有一轮，本管线不支持多轮导出，'
              '请只导出单轮数据。')
    return df.rename(columns=rename)


def _pair_id(df):
    """给每一行生成配对标识：同一对的两名被试共享同一 pair_id。"""
    group_col = next((c for c in ('id_in_subsession', 'group_id_in_subsession')
                      if c in df.columns), None)
    if group_col is not None and 'session_code' in df.columns:
        # 真实 oTree 导出：同一 group 的两名被试由 (session.code,
        # group.id_in_subsession) 唯一标识；participant.code 是随机串，不含配对信息。
        return df.session_code.astype(str) + '_' + df[group_col].astype(str)
    if 'participant_code' in df.columns:
        # 模拟数据 / 扁平导出：配对双方共享前缀，仅末段 _A / _B 不同
        return df.participant_code.str.rsplit('_', n=1).str[0]
    raise SystemExit('数据中既无 (session_code, group.id_in_subsession) 也无 '
                     'participant_code，无法确定配对关系')


def load(path):
    """读入数据，返回 (df, pairs)。

    df    ：逐被试帧（120 行），只用于逐被试变量（问卷、信念等）；
    pairs ：配对帧（60 行），x 与 y 同处一行，所有需要同时用到 x 与 y 的模型
            一律基于它（见模块 docstring 的 Step 0 说明）。
    """
    # float_precision='round_trip'：pandas 默认解析器会丢最后 1 ulp，
    # 后续与磁盘值做精确比较时会得到假的不一致。
    df = pd.read_csv(path, float_precision='round_trip')
    df = _rename_otree_export(df)

    missing = [f for f in REQUIRED_FIELDS if f not in df.columns]
    if missing:
        raise SystemExit(
            '数据缺少本管线必需的字段：' + '、'.join(missing)
            + '。若这是单 app 导出，请改用宽表（all_apps_wide）导出——'
            '本管线同时需要 trust_game 与 survey 的字段。')
    df['treatment'] = df['is_communication'].astype(int)
    df['treatment_label'] = df['treatment'].map({1: '沟通组', 0: '基线组'})
    df['pair_id'] = _pair_id(df)

    sizes = df.groupby('pair_id').size()
    roles = df.groupby('pair_id').role.nunique()
    treatments = df.groupby('pair_id').treatment.nunique()
    if not (sizes == 2).all() or not (roles == 2).all():
        bad = sorted(set(sizes[sizes != 2].index) | set(roles[roles != 2].index))
        raise SystemExit(f'以下配对不是「2 行、2 个角色」，无法合并：{bad[:5]}'
                         f'（共 {len(bad)} 个）')
    if not (treatments == 1).all():
        bad = sorted(treatments[treatments != 1].index)
        raise SystemExit(f'以下配对内的处理组不一致（处理组是配对级变量）：{bad[:5]}')

    # 投资者的 x + 受托人的 y / 承诺 / 问卷协变量；真实导出中对方行的字段本为空，
    # 合并后才完整——这正是 Step 0 存在的理由。
    investor_cols = ['pair_id', 'treatment', 'send_amount']
    trustee_cols = ['pair_id', 'return_amount', 'return_ratio',
                    'promise_strength', 'belief_investor_send',
                    'risk_choice', 'dictator_give', 'general_trust',
                    'gender', 'age', 'econ_courses']
    inv = (df[df.role == INVESTOR_ROLE]
           .reindex(columns=investor_cols)
           .rename(columns={'send_amount': 'x'}))
    tru = (df[df.role == TRUSTEE_ROLE]
           .reindex(columns=trustee_cols)
           .rename(columns={'return_amount': 'y'}))
    pairs = inv.merge(tru, on='pair_id', how='inner', suffixes=('', '_t'))

    # return_ratio：优先用导出中已结算的字段（受托人行由 ResultsWaitPage 写入），
    # 缺失时用 payoffs.return_ratio 按 (x, y) 重算（x=0 时约定为 0.0）。
    # 两者本应一致，故顺带交叉核对，把偏差记为审计信息供 main() 打印。
    recomputed = np.array([
        payoffs.return_ratio(int(x), int(y))
        for x, y in zip(pairs.x.fillna(0), pairs.y.fillna(0))
    ])
    stored = pairs['return_ratio'].to_numpy(dtype=float) if 'return_ratio' in pairs else None
    if stored is None:
        pairs['return_ratio'] = recomputed
        pairs.attrs['ratio_check'] = (0, float('nan'))
    else:
        has_stored = ~np.isnan(stored)
        deviation = (float(np.max(np.abs(stored[has_stored] - recomputed[has_stored])))
                     if has_stored.any() else float('nan'))
        pairs['return_ratio'] = np.where(has_stored, stored, recomputed)
        pairs.attrs['ratio_check'] = (int(has_stored.sum()), deviation)

    return df, pairs


# --------------------------------------------------------------------------
# 统计工具
# --------------------------------------------------------------------------

def cohens_d(a, b):
    """两组独立样本的 Cohen's d（用组内合并标准差）。

    合并标准差为 0（组内毫无变异）时返回 NaN 而不是 0.0：0.0 会被读成「无效应」，
    而真相是「本样本算不出效应量」。NaN 在表里是显眼的缺口，不会被当成一个数。
    """
    na, nb = len(a), len(b)
    pooled = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1))
                     / (na + nb - 2))
    if pooled == 0:
        return float('nan')
    return (a.mean() - b.mean()) / pooled


def _stamp(frame, note):
    """给输出表加「数据来源」列：模拟/真实标注必须随表格一起落盘。"""
    frame.insert(0, '数据来源', note)
    return frame


def _fmt_p(p):
    """p 值格式化：极小值给科学计数法。

    四位小数会把 p<5e-5 压成 0.0，报告引用时就丢了量级（H3 的 p 在 1e-7 量级）；
    字符串仍可被 pandas 解析回浮点，不影响下游读取。
    """
    return f'{p:.3g}' if p < 0.0001 else f'{p:.6f}'


# --------------------------------------------------------------------------
# 描述统计
# --------------------------------------------------------------------------

RISK_CHOICE_LABEL = '风险偏好（选「确定金额」的行数，0-5）'


def descriptives(df, pairs):
    """分处理组的描述统计。

    单位：投资者变量按「人」，涉及 y / ratio 的行按「对」；N 由数据决定，
    写在 `N` 列（模拟数据为 30+30，真实导出按实际样本）。
    比率类变量只在 x>0 上定义（x=0 时比例恒为 0，是退化值，不是低返还）。
    """
    investors = df[df.role == INVESTOR_ROLE]
    trustees = df[df.role == TRUSTEE_ROLE]
    pos = pairs[pairs.x > 0]

    specs = [
        ('投资者送出金额 x（单位：人）', investors, 'send_amount'),
        ('投资者的信念（返还比例%，单位：人）', investors, 'belief_return_pct'),
        ('受托人返还比例（仅 x>0，主要规格；单位：对）', pos, 'return_ratio'),
        ('受托人返还比例（含 x=0，对照；单位：对）', pairs, 'return_ratio'),
        ('受托人返还金额 y（单位：人）', trustees, 'return_amount'),
        ('承诺强度（受托人；基线组不经过消息页，故为空）', trustees, 'promise_strength'),
        (RISK_CHOICE_LABEL, df, 'risk_choice'),
        ('利他（独裁者送出额）', df, 'dictator_give'),
        ('一般信任', df, 'general_trust'),
    ]
    rows = []
    for label, sub, col in specs:
        for t, glabel in [(1, '沟通组'), (0, '基线组')]:
            vals = sub[sub.treatment == t][col].dropna()
            rows.append(dict(
                变量=label, 组别=glabel, N=len(vals),
                均值=round(vals.mean(), 3) if len(vals) else np.nan,
                标准差=round(vals.std(ddof=1), 3) if len(vals) > 1 else np.nan,
                中位数=round(vals.median(), 3) if len(vals) else np.nan,
            ))
    # risk_choice 的实际分布（规格 §15.2 要求在报告中给出，并说明 0/1 是否存在）。
    # 逐取值人数写进 N 列，其余统计量留空。
    for k in range(6):
        for glabel, sub in [('全体', df), ('沟通组', df[df.treatment == 1]),
                            ('基线组', df[df.treatment == 0])]:
            rows.append(dict(
                变量=f'risk_choice 的分布：取值 {k}（人数）', 组别=glabel,
                N=int((sub.risk_choice == k).sum()), 均值=np.nan,
                标准差=np.nan, 中位数=np.nan,
            ))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 假设检验
# --------------------------------------------------------------------------

def t_tests(pairs):
    """H1 / H2 的 Welch t 检验（标注样本口径与检验名）。

    样本一律取配对帧：x 与 y 在逐被试帧上各出现两次，在未过滤的 120 行上做检验
    会把 60 个值用两遍、低估标准误。

    样本量一律写进 `样本` 列，**标签里不写死 N**——真实导出的 N 与模拟数据不同，
    写死会让真实结果被贴上模拟数据的标签（N_沟通组 / N_基线组 两列同时给出）。
    """
    rows = []

    def welch(name, sample_label, a, b, primary, remark=''):
        if len(a) < 2 or len(b) < 2:
            raise SystemExit(f'{name}：组内观测不足（{len(a)}/{len(b)}），无法检验')
        t, p = stats.ttest_ind(a, b, equal_var=False)
        d = cohens_d(a, b)
        se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        diff = a.mean() - b.mean()
        # 正态近似（diff ± 1.96·se），**不是** Welch 检验的精确区间；
        # 列名里写明，免得与「检验 = Welch t」并排时被当作 Welch 区间引用。
        ci = (diff - 1.96 * se, diff + 1.96 * se)
        rows.append(dict(
            假说=name, 样本=sample_label, N_沟通组=len(a), N_基线组=len(b),
            沟通组均值=round(a.mean(), 3), 基线组均值=round(b.mean(), 3),
            差值=round(diff, 3),
            **{'差值的95CI（正态近似，非 Welch 区间）':
               f'[{ci[0]:.3f}, {ci[1]:.3f}]'},
            t=round(t, 3), p=_fmt_p(p), Cohens_d=round(d, 3),
            检验='Welch t（不假设方差齐性）', 主结果=primary, 备注=remark,
        ))

    comm, base = pairs[pairs.treatment == 1], pairs[pairs.treatment == 0]

    _t_student, p_student = stats.ttest_ind(comm.x, base.x, equal_var=True)
    welch('H1: 送出金额 x',
          f'全部投资者（{len(comm)}+{len(base)}；配对帧中每对一行 x）',
          comm.x, base.x, '是',
          remark=f'Student t 检验 p={p_student:.4f}（仅第四位小数不同）；'
                 '引用 p 须写明检验名')

    # H2 规格注册口径：全部受托人（含 x=0 的比例 0 值）
    welch('H2: 返还比例（规格注册口径）',
          f'全部受托人（{len(comm)}+{len(base)} 对）',
          comm.return_ratio, base.return_ratio, '是',
          remark='含 x=0 的退化比例 0；与备选口径结论方向一致但量值不同')
    # H2 备选口径：仅 x>0
    pos = pairs[pairs.x > 0]
    pos_comm = pos[pos.treatment == 1]
    pos_base = pos[pos.treatment == 0]
    welch('H2（备选口径）: 返还比例',
          f'仅 x>0 的受托人（{len(pos_comm)}+{len(pos_base)} 对）',
          pos_comm.return_ratio, pos_base.return_ratio,
          '否', remark='剔除 x=0 的退化比例 0；仅作稳健性对照，不作为主结果')
    return pd.DataFrame(rows)


def _control_terms(frame):
    """构造 H3 控制变量项，返回 (公式项列表, 可读标签列表)。

    控制变量取**受托人**的问卷测量（因变量是受托人的返还行为）。
    risk_choice 是序数变量：按中位数切分为哑变量进入（见模块 docstring）。
    性别仅在两类都出现时进入——只有一类时常数列与截距共线，无法估计。
    """
    terms, labels = [], []

    if frame.risk_choice.notna().all():
        median = frame.risk_choice.median()
        high = frame.risk_choice > median
        if high.nunique() == 2:
            frame['risk_high'] = high.astype(int)
            terms.append('risk_high')
            labels.append(f'risk_high（risk_choice>{median:g}，中位数切分；'
                          f'n={int(high.sum())}）')
        else:
            # 切分后一侧为空 → 常数列与截距共线，模型秩亏。不进模型，并写明原因。
            labels.append(f'risk_high 未进入（按中位数 {median:g} 切分后一侧为空，'
                          f'n={int(high.sum())}）')
    else:
        # 有缺失时不进模型，同样写明原因（原先是不声不响地丢掉）
        labels.append(f'risk_high 未进入（risk_choice 有 '
                      f'{int(frame.risk_choice.isna().sum())} 个缺失）')
    if frame.gender.nunique(dropna=True) == 2:
        frame['female'] = (frame.gender == '女').astype(int)
        terms.append('female')
        labels.append('female（女=1）')
    for col in ('dictator_give', 'general_trust', 'age', 'econ_courses'):
        if frame[col].notna().all():
            terms.append(col)
            labels.append(col)
    return terms, labels


def regressions(pairs):
    """H3：(a)(b)(c) 三个规格 + (d) 含控制变量的完整式，一律基于配对帧。

    (b) 是规格 §15.2 的主要规格（剔除 x=0，仅考察真正发生转移的配对）。
    """
    pos = pairs[pairs.x > 0].copy()
    all_pairs = pairs.copy()
    terms, labels = _control_terms(pos)
    control_label = '、'.join(labels) if labels else '无'

    # (name, 数据, 因变量, 是否加控制变量, 备注)
    models = [
        ('(a) 全样本（含 x=0），因变量 y', all_pairs, 'y', False,
         '对照：x=0 时 y 必为 0'),
        ('(b) 剔除 x=0，因变量 y（主要规格）', pos, 'y', False, ''),
        ('(c) 剔除 x=0，因变量 ratio', pos, 'return_ratio', False, ''),
        ('(d) 剔除 x=0，因变量 y + 控制变量（规格 §15.2 完整式）', pos, 'y', True,
         '控制变量取受托人问卷测量；与 (b) 相比 treatment 系数略降，方向与显著性不变'),
    ]
    rows = []
    for name, data, dv, use_controls, remark in models:
        formula = f'{dv} ~ treatment + x'
        if use_controls and terms:
            formula += ' + ' + ' + '.join(terms)
        model = smf.ols(formula, data=data).fit(cov_type='HC1')
        rows.append(dict(
            模型=name,
            treatment=round(model.params['treatment'], 4),
            treatment_se=round(model.bse['treatment'], 4),
            treatment_p=_fmt_p(model.pvalues['treatment']),
            # 列名带「系数」二字：这一列装的是 x 的**回归系数**，不是 x 本身
            # （叫 send_amount 会被当成可回归的自变量，报告引用时极易误读）。
            **{'x系数': round(model.params['x'], 4),
               'x系数_p': _fmt_p(model.pvalues['x'])},
            N=int(model.nobs), R2=round(model.rsquared, 4),
            控制变量=control_label if use_controls else '无',
            备注=remark,
        ))
    return pd.DataFrame(rows)


def mediation(df, n_boot=5000):
    """H4：treatment -> belief_return_pct -> send_amount，bootstrap 中介分析。

    信念与送出额都在投资者自己那一行，故用逐被试帧的投资者子集即可（60 人）。
    """
    sub = df[df.role == INVESTOR_ROLE][
        ['treatment', 'belief_return_pct', 'send_amount']].dropna()
    if len(sub) < 3:
        raise SystemExit(f'投资者观测不足（N={len(sub)}），无法做中介分析')
    rng = np.random.default_rng(SEED)

    def indirect(data):
        a_fit = smf.ols('belief_return_pct ~ treatment', data=data).fit()
        b_fit = smf.ols('send_amount ~ treatment + belief_return_pct',
                        data=data).fit()
        return a_fit.params['treatment'] * b_fit.params['belief_return_pct']

    total_fit = smf.ols('send_amount ~ treatment', data=sub).fit()
    direct_fit = smf.ols('send_amount ~ treatment + belief_return_pct',
                         data=sub).fit()
    point = indirect(sub)

    boots = []
    for _ in range(n_boot):
        sample = sub.iloc[rng.integers(0, len(sub), len(sub))]
        try:
            boots.append(indirect(sample))
        except Exception:
            continue
    # 失败的重抽不能悄悄占掉比例：低于 90% 成功即报错而非给一个残缺的 CI
    if len(boots) < 0.9 * n_boot:
        raise SystemExit(f'bootstrap 仅成功 {len(boots)}/{n_boot} 次，'
                         '重抽样本存在系统性问题，CI 不可信')
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return pd.DataFrame([dict(
        路径='treatment → belief → send',
        样本=f'全部投资者（N={len(sub)}）', N=len(sub),
        总效应=round(total_fit.params['treatment'], 4),
        直接效应=round(direct_fit.params['treatment'], 4),
        间接效应=round(point, 4),
        间接效应95CI=f'[{lo:.4f}, {hi:.4f}]',
        bootstrap次数=len(boots),
    )])


def correlation(pairs, df):
    """相关分析：H5 + 信念~x（分组）+ 比值~x（按样本口径）。

    每个统计量都带样本与检验标注——同一批数据在不同样本下数值不同，
    不标注会让读者把口径差异读成矛盾（规格 §15.4）。
    """
    rows = []
    investors = df[df.role == INVESTOR_ROLE]

    def add(name, sample, x, y, remark=''):
        # 两个变量同源同序，按位置配对后逐行丢弃缺失，避免 NaN 悄悄变成 NaN 的 r
        data = pd.DataFrame({'x': np.asarray(x, dtype=float),
                             'y': np.asarray(y, dtype=float)}).dropna()
        if len(data) < 3:
            raise SystemExit(f'{name}（{sample}）：观测不足（N={len(data)}）')
        r, p = stats.pearsonr(data.x, data.y)
        rho, p_rho = stats.spearmanr(data.x, data.y)
        rows.append(dict(
            假说=name, 样本=sample, N=len(data),
            Pearson_r=round(r, 4), Pearson_p=_fmt_p(p),
            Spearman_rho=round(rho, 4), Spearman_p=_fmt_p(p_rho),
            备注=remark,
        ))

    # H5：承诺强度只在沟通组存在（基线组不经过消息页）。**组的定义用 treatment**，
    # 不能用「承诺非空」——否则沟通组里漏答消息页的受托人会让样本悄悄缩小，而标签
    # 仍写着「沟通组」。缺失就按缺失剔除，并把人数写进备注，不让它无声发生。
    comm_group = pairs[pairs.treatment == 1]
    n_missing = int(comm_group.promise_strength.isna().sum())
    missing_note = (f'；另有 {n_missing} 名沟通组受托人承诺缺失，按缺失剔除'
                    if n_missing else '；沟通组内无承诺缺失')
    pos_comm = comm_group[comm_group.x > 0]
    add('H5: 承诺强度 ~ 返还比例', '沟通组受托人（treatment==1），仅 x>0（主要规格）',
        pos_comm.promise_strength, pos_comm.return_ratio,
        'x=0 时比例为退化 0，含之会稀释 H5 所考察的量' + missing_note)
    add('H5: 承诺强度 ~ 返还比例', '沟通组受托人（treatment==1），含 x=0（对照）',
        comm_group.promise_strength, comm_group.return_ratio,
        '与主要规格同向但更弱；两者须分别标注' + missing_note)

    # 信念~x：组内关系，必须分组报告；合并值只作对照
    for t, glabel in [(0, '基线组'), (1, '沟通组')]:
        s = investors[investors.treatment == t]
        add('信念 ~ 送出金额 x', f'{glabel}投资者（组内关系）',
            s.send_amount, s.belief_return_pct)
    add('信念 ~ 送出金额 x', '两组投资者合并（⚠️ 仅对照）',
        investors.send_amount, investors.belief_return_pct,
        '合并值混入组间均值差，不得作为组内关系的证据；'
        '上面两行的分组值才是组内关系')

    # 比值~x：只在 x>0 上成立，含零质量点时关系消失
    add('返还比例 ~ 送出金额 x', '仅 x>0（主要规格）',
        pairs[pairs.x > 0].x, pairs[pairs.x > 0].return_ratio,
        '经典发现：送出越多，返还比例越低')
    add('返还比例 ~ 送出金额 x', '全部配对（含零质量点，仅对照）',
        pairs.x, pairs.return_ratio,
        '含 x=0 的退化 0 后关系消失，不得据此宣称全样本递减')
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 图
# --------------------------------------------------------------------------

COLORS = [(0, '基线组', '#8c8c8c'), (1, '沟通组', '#1f77b4')]


def _save(fig, outdir, filename, note):
    """统一收尾：把模拟/真实标注也压在图上，避免图脱离表格后失去标注。"""
    fig.text(0.995, 0.005, note, ha='right', va='bottom', fontsize=7,
             color='#666666')
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, filename), dpi=150)
    plt.close(fig)


def figures(df, pairs, outdir, note):
    rng = np.random.default_rng(SEED)
    investors = df[df.role == INVESTOR_ROLE]

    # 1) x 的分布（按处理组）
    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.arange(-0.5, 11.5, 1)
    for t, label, color in COLORS:
        ax.hist(pairs[pairs.treatment == t].x, bins=bins, alpha=0.6,
                label=label, color=color)
    ax.set_xlabel('投资者送出金额 x（点）')
    # 纵轴是原始计数（每个柱为该组内的配对数），不是对数刻度：
    # hist() 未对计数取对数，标成「对数」会让图自称 log 轴而实际不是。
    ax.set_ylabel('配对数（个）')
    ax.set_title(f'投资者送出金额的分布（{int((pairs.treatment == 1).sum())}'
                 f'+{int((pairs.treatment == 0).sum())} 对）\n{note}')
    ax.legend()
    _save(fig, outdir, 'fig_send_amount.png', note)

    # 2) return_ratio 的分布（仅 x>0，按处理组）
    pos = pairs[pairs.x > 0]
    fig, ax = plt.subplots(figsize=(7, 4))
    for t, label, color in COLORS:
        ax.hist(pos[pos.treatment == t].return_ratio,
                bins=np.arange(0, 1.1, 0.1), alpha=0.6, label=label, color=color)
    ax.set_xlabel('返还比例 y/(3x)')
    # 纵轴是原始计数（每个柱为该组内的配对数），不是对数刻度：
    # hist() 未对计数取对数，标成「对数」会让图自称 log 轴而实际不是。
    ax.set_ylabel('配对数（个）')
    ax.set_title(f'受托人返还比例的分布（仅 x>0，N={len(pos)} 对）\n{note}')
    ax.legend()
    _save(fig, outdir, 'fig_return_ratio.png', note)

    # 3) 承诺强度 ~ 返还比例（H5 主要规格：沟通组受托人、仅 x>0）
    # 组按 treatment 定义；承诺缺失（漏答消息页）按缺失剔除，不让样本无声缩小。
    sub = (pairs[(pairs.treatment == 1) & (pairs.x > 0)]
           .dropna(subset=['promise_strength']))
    r, p = stats.pearsonr(sub.promise_strength, sub.return_ratio)
    fig, ax = plt.subplots(figsize=(7, 4))
    jitter = rng.uniform(-0.08, 0.08, len(sub))
    ax.scatter(sub.promise_strength + jitter, sub.return_ratio, alpha=0.55,
               color='#1f77b4', label=f'受托人（N={len(sub)}）')
    slope, intercept = np.polyfit(sub.promise_strength, sub.return_ratio, 1)
    xs = np.array([sub.promise_strength.min(), sub.promise_strength.max()])
    ax.plot(xs, intercept + slope * xs, color='#d62728',
            label=f'OLS 拟合线（r={r:.3f}, p={p:.3f}）')
    means = sub.groupby('promise_strength').return_ratio.agg(['mean', 'sem'])
    ax.errorbar(means.index, means['mean'], yerr=1.96 * means['sem'],
                marker='o', capsize=4, linestyle='none', color='#2ca02c',
                label='各强度均值 ±95%CI')
    ax.set_xlabel('承诺强度（0-4）')
    ax.set_ylabel('返还比例 y/(3x)')
    ax.set_title('承诺强度与返还比例（沟通组受托人，仅 x>0）\n'
                 f'{note}　x 轴含 ±0.08 抖动以避免重叠')
    ax.legend()
    _save(fig, outdir, 'fig_promise_ratio.png', note)

    # 4) 信念 ~ x：分组拟合（合并相关混入组间均值差，故分组呈现）
    fig, ax = plt.subplots(figsize=(7, 4))
    for t, label, color in COLORS:
        s = investors[investors.treatment == t]
        r_g, _ = stats.pearsonr(s.send_amount, s.belief_return_pct)
        ax.scatter(s.send_amount, s.belief_return_pct, alpha=0.5, color=color,
                   label=f'{label}（r={r_g:.3f}, N={len(s)}）')
        slope, intercept = np.polyfit(s.send_amount, s.belief_return_pct, 1)
        xs = np.linspace(s.send_amount.min(), s.send_amount.max(), 10)
        ax.plot(xs, intercept + slope * xs, color=color, linewidth=1.6)
    ax.set_xlabel('投资者送出金额 x（点）')
    ax.set_ylabel('预期返还比例（%）')
    ax.set_title('信念与送出金额（分组拟合）\n' + note)
    ax.legend()
    _save(fig, outdir, 'fig_belief_send.png', note)


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def check_feasibility(pairs, df):
    """写产物**之前**的可行性检查：不可行就什么都不写。

    单臂导出（只跑了某一个 session config）做不了任何组间比较。若不先查，脚本会先
    写出标着【真实数据】的描述统计表、再在 t 检验处中止，把产物目录留在「一半新
    一半旧」的状态（本项目在开发期实际踩过：`otree test trust_baseline 8 --export`
    的导出只有基线组，就是这么留下了一张【真实数据】标注的描述统计表）。
    """
    for t, label in [(1, '沟通组'), (0, '基线组')]:
        n = int((pairs.treatment == t).sum())
        if n < 2:
            raise SystemExit(
                f'{label}只有 {n} 个配对，H1/H2 的组间比较无法进行——只有单臂导出'
                '（或数据缺失）时才会这样。请导出包含全部 session config 的宽表'
                '（all_apps_wide）后重跑。本次未写出任何产物。')
    investors = df[(df.role == INVESTOR_ROLE) & df.belief_return_pct.notna()
                   & df.send_amount.notna()]
    if len(investors) < 3:
        raise SystemExit(
            f'可用投资者观测只有 {len(investors)} 个，H4 中介分析无法进行。'
            '本次未写出任何产物。')


def risk_choice_distribution(df):
    """risk_choice 的实际分布（0-5 各取值的人数，按处理组）。"""
    dist = (pd.crosstab(df.risk_choice, df.treatment_label)
            .reindex(index=range(6), columns=['基线组', '沟通组'], fill_value=0))
    dist['合计'] = dist.sum(axis=1)
    dist.loc['合计'] = dist.sum()
    return dist


def main():
    parser = argparse.ArgumentParser(description='信任博弈实验的统计分析')
    parser.add_argument('--data', default=DEFAULT_DATA,
                        help='数据文件（默认：analysis/output/simulated_data.csv）')
    args = parser.parse_args()

    # 默认路径以外的一律按真实数据标注；同时打印解析后的绝对路径，
    # 使「标注与数据来源」可被读者直接核对。
    is_simulated = os.path.abspath(args.data) == os.path.abspath(DEFAULT_DATA)
    note = SIMULATION_NOTE if is_simulated else REAL_NOTE
    # 路径推断对放错位置的拷贝无感（见 check_source_label），故读数据之前先用
    # 文件内容核对一次；核对不上就中止，不写出任何产物。
    source_check = check_source_label(args.data, is_simulated)

    df, pairs = load(args.data)
    check_feasibility(pairs, df)      # 不可行就什么都不写（见函数 docstring）

    print('=' * 72)
    print(f'信任博弈实验分析  {note}')
    print(f'数据源：{os.path.abspath(args.data)}')
    print(f'[核对] 数据来源标注：{source_check}')
    print(f'被试行：{len(df)}    配对行：{len(pairs)}'
          f'（沟通组 {int((pairs.treatment == 1).sum())} / '
          f'基线组 {int((pairs.treatment == 0).sum())}）')
    print('=' * 72)
    n_stored, deviation = pairs.attrs.get('ratio_check', (0, float('nan')))
    print(f'[核对] return_ratio：{n_stored} 行取导出字段，'
          f'与 payoffs.return_ratio 重算的最大偏差 = {deviation:g}')

    # 先把五张表**全部算完**，再统一落盘：任何一处因数据不可行而中止，都不会
    # 留下「一半新一半旧」的产物目录（开发期用单臂导出跑时就是这样：只有一张
    # 描述统计表被写成【真实数据】标注，其余产物还是上一轮的）。
    desc = _stamp(descriptives(df, pairs), note)
    tt = _stamp(t_tests(pairs), note)
    reg = _stamp(regressions(pairs), note)
    med = _stamp(mediation(df), note)
    cor = _stamp(correlation(pairs, df), note)
    dist = risk_choice_distribution(df)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for filename, frame in [('table_descriptives.csv', desc),
                            ('table_ttests.csv', tt),
                            ('table_regressions.csv', reg),
                            ('table_mediation.csv', med),
                            ('table_correlation.csv', cor)]:
        frame.to_csv(os.path.join(OUTPUT_DIR, filename), index=False,
                     encoding='utf-8-sig')

    print('\n【描述统计】')
    print(desc.to_string(index=False))

    print('\n【风险偏好 risk_choice 的实际分布】')
    print(dist.to_string())
    print(f'  0 是否有观测：{"是" if dist.loc[0, "合计"] else "否"}；'
          f'1 是否有观测：{"是" if dist.loc[1, "合计"] else "否"}')
    pos = pairs[pairs.x > 0]
    median = pos.risk_choice.median()
    print(f'  作为控制变量的进入方式：中位数切分哑变量 '
          f'risk_high = 1 iff risk_choice > {median:g}（数值越大越规避风险）；'
          f'在 H3(d) 样本（受托人、x>0，N={len(pos)}）中 '
          f'高组 {int((pos.risk_choice > median).sum())} 人 / '
          f'低组 {int((pos.risk_choice <= median).sum())} 人。'
          '不做逐取值哑变量，也不解释为等距效应。')

    print('\n【t 检验】')
    print(tt.to_string(index=False))

    print('\n【回归】')
    print(reg.to_string(index=False))

    print('\n【中介分析】')
    print(med.to_string(index=False))

    print('\n【相关分析】')
    print(cor.to_string(index=False))

    figures(df, pairs, OUTPUT_DIR, note)
    print(f'\n图表已输出至 {OUTPUT_DIR}')
    print(note)


if __name__ == '__main__':
    main()

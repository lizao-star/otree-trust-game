"""生成模拟实验数据。

⚠️ 本脚本产生的数据是模拟数据，不是真实被试数据。
   报告中引用这些结果时必须标注"模拟数据"。

生成原则（规格第 15.4 节）：按文献报告的效应量生成，而非随机噪声。
  - 基线组 x 均值约 5；零膨胀 + 上限堆积，**近似对称**（0 处与 10 处都有堆积）
  - 沟通组 x 均值上移，且零发送率更低；因右移撞上 x ≤ 禀赋 的天花板，**左偏**
  - 返还比例随 x 递减（经典发现）
  - 承诺强度与返还比例正相关
  - 信念与 x 正相关，沟通提升信念

数据生成过程（每对投资者-受托人）：
    x      零膨胀（基线 15% / 沟通 5%）+ Γ(4, 1.47) 截断到 [0, 10]；
           非零部分均值经零膨胀修正，使基线组整体均值 ≈ 5
    belief = 17 + 2.5x + 8*comm + N(0, 11)          投资者对返还比例的预期
    tau    ~ N(0, 1)                                受托人类型，在知道 x 之前确定
    ratio  = 0.45 - 0.035x + 0.19*comm + 0.11*tau   受托人的返还比例，截断到 [0, 1]
    y      = round(ratio * m * x)（x=0 时为 0，即真实规则）
    imsg   = 0.6 + 0.35x + N(0, 1.3)                投资者的消息强度（意图的代理）
    promise= 2.6 + 0.5*tau + N(0, 0.6)              承诺强度，只由 tau 驱动（见下）
    bonus  = payoffs.belief_bonus(...)              一律调用真值来源
    两条消息方程都没有单独的「沟通组」项：消息只在沟通组存在（消息页
    MessageSend.is_displayed = has_communication），没有基线组可比，
    该位移不可识别，已并入截距。文案与强度编码取自 trust_game.content
    的 0-4 量表。
    承诺不含 x 项：消息页排在投资者决策之前，真实被试无法让承诺依赖于 x；
    返还比例里的 -0.035x 是受托人对「收到多少」的反应，不属于类型。

空值结构与真实导出对齐（这是「同一套分析管线跑模拟与真实数据」的前提）：
  * 投资者行：promise_strength / belief_investor_send 为空；受托人行：
    belief_return_pct 为空（信念按角色分列）。
  * 消息四列（message_investor / message_trustee / investor_message_strength /
    promise_strength）在基线组全为空——真实实验中基线组根本不会经过消息页。
    因此 H5「承诺强度 ~ 返还比例」只在沟通组的 30 名受托人上成立，
    这是真实情形，不是缺陷，不得为凑样本量而填充基线组的消息。
  * 例外（有意为之，见交付说明）：send_amount / return_amount / return_ratio
    在两种角色行上都填充。真实导出里 x 只写在投资者行、y 只写在受托人行
    （投资者不会经过受托人的决策页），但分析计划要求在受托人行上直接做
    y ~ treatment + x 回归，故此处保留配对级列。真实数据导出后需先做
    配对合并再跑同一分析。

参数取值说明（为什么不是「照抄一个数」）：
  * x 的分布 = 零膨胀 + Γ 截断。规格第 15.4 节（实现阶段修正）写明：真实信任
    博弈的送出分布是「0 处有质量点、上限处有堆积（受禀赋约束），常近似对称
    甚至双峰」，并明确「不要为了让分布满足『右偏』而改动生成器」。本文件据此
    建模：零膨胀复现 0 处质量点（沟通显著减少它），Γ(4, 1.47) 的右尾在
    x ≤ 禀赋 处截断形成 10 处堆积。本种子实测：基线组偏度 -0.11、沟通组 -0.14
    （两组都近似对称、略偏左；沟通组偏左来自整体右移后撞上上限）——都是上式的
    后果，不是缺陷；10 处堆积比例基线 0.20、沟通 0.30。
  * 返还比例的斜率 -0.035 与噪声 0.11：这两者共同决定「比值随 x 递减」能否
    被检出。斜率太小时（如 -0.015）该相关在 N=120 下不可检出；噪声太大时
    （如 0.25）同理。
  * COMM_SHIFT = 2.0 点：规格第 15.4 节要求按文献效应量（d ≈ 0.5–0.9）生成，
    而设计的功效目标是在 N=120、80% 功效下检出 d ≈ 0.51（第 15.1 节）。
    n=30/组、α=.05 时 d=0.5 的功效仅约 50%，逐次抽样会落在阈值附近，故位移
    取到让**名义（设计）效应量**落在文献区间内的量级（进入区间的是名义值，
    不是某一次实现）。以本数据集的实测标准差表述：基线组 x 的 sd ≈ 3.56、
    组内合并 sd ≈ 3.134，2.0 点 ≈ 0.56 个基线 SD / 0.64 个合并 SD，
    名义 d = 2.0 / 3.134 ≈ 0.64。
    **单次实现会围绕名义值波动**：本种子实测 d = 0.415（低于该区间）、
    Welch t = 1.61、Welch p = 0.1140（同数据 Student t 检验 p = 0.1135；
    两者仅第四位不同，引用 p 时必须写明检验名）。方向为正但未达显著，
    正是规格第 15.4 节所述的「单次抽样落在功效阈值附近、不跨种子稳健」，
    故如实保留，未为改善 p 值调参或换种子。
"""

import os
import sys

import numpy as np
import pandas as pd

# 把项目根加入 sys.path，以便导入 trust_game.payoffs。
# 直接运行 `python analysis/simulate_data.py` 时 sys.path[0] 是 analysis/ 而非
# 项目根，故必须显式补上。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from trust_game import content, payoffs  # noqa: E402

# ⚠️ 收益与奖金规则一律取自 trust_game.payoffs，绝不在本文件重写副本。
# 本项目已多次因「两处真值源」产生静默偏离：奖金规则刚经历过一次变更
# （x=0 不再发放），若此处维护自己的副本，模拟数据会与真实机制悄悄脱节，
# 而所有测试仍会通过。
ENDOWMENT = payoffs.ENDOWMENT
MULTIPLIER = payoffs.MULTIPLIER

SEED = 20260913
N_PER_CONDITION = 60          # 规格第 15.1 节：N=120，每组 60
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'output',
                           'simulated_data.csv')

# 零发送率：真实数据中「一分不送」是常见类型，且沟通显著减少它。
# 两组取不同比例，既符合文献，也避免零膨胀把沟通效应稀释掉。
ZERO_RATE_BASELINE = 0.15
ZERO_RATE_COMMUNICATION = 0.05

# 非零送出额：Γ(shape, scale)，均值 = shape * scale。
# 零膨胀会把整体均值拉低，故非零部分的均值按比例放大，使基线组整体
# 均值仍约为 5：ZERO_RATE 与 SEND_MEAN_POSITIVE 满足
#   (1 - ZERO_RATE_BASELINE) * SEND_MEAN_POSITIVE = 5
SEND_SHAPE = 4.0
SEND_MEAN_POSITIVE = 5.0 / (1.0 - ZERO_RATE_BASELINE)
SEND_SCALE = SEND_MEAN_POSITIVE / SEND_SHAPE
COMM_SHIFT = 2.0              # 沟通组非零部分上移（见模块 docstring）

# 受托人类型对返还比例的贡献（标准差）与对承诺强度的贡献
RATIO_TYPE_SD = 0.11
PROMISE_A, PROMISE_B_TYPE, PROMISE_SD = 2.6, 0.5, 0.6

# 投资者消息强度：意图（=x）的代理。无沟通组项——消息只在沟通组存在
IMSG_A, IMSG_BX, IMSG_SD = 0.6, 0.35, 1.3

# 消息文案 ←→ 0-4 强度编码的唯一真值源就是 trust_game.content 的两张量表，
# 本文件不再自建映射表（此前按 dict 身份派发，属多余的间接层）。


def _truncated_normal(rng, mean, sd, low, high):
    return float(np.clip(rng.normal(mean, sd), low, high))


def _message(rng, mean, sd, messages):
    """抽一条消息，返回 (文案, 强度)。

    messages 直接传 content.INVESTOR_MESSAGES / content.TRUSTEE_MESSAGES；
    强度由 content.strength_of 反查，与真实量表同源。"""
    code = int(np.clip(round(rng.normal(mean, sd)), 0, 4))
    label = dict(messages)[code]
    return label, content.strength_of(messages, label)


def generate():
    rng = np.random.default_rng(SEED)
    rows = []

    for is_comm in (0, 1):
        zero_rate = ZERO_RATE_COMMUNICATION if is_comm else ZERO_RATE_BASELINE
        for pair_id in range(N_PER_CONDITION // 2):
            # --- 投资者 ---
            if rng.random() < zero_rate:
                # 显式零发送质量点（"不信任"类型），不是把连续分布截到 0
                send = 0
            else:
                send_latent = rng.gamma(SEND_SHAPE, SEND_SCALE)
                if is_comm:
                    send_latent += COMM_SHIFT
                send = int(round(float(np.clip(send_latent, 0, ENDOWMENT))))

            # 信念与送出额正相关，沟通组整体上移
            belief_shift = 8.0 if is_comm else 0.0
            belief = int(round(_truncated_normal(
                rng, 17 + 2.5 * send + belief_shift, 11, 0, 100)))

            # --- 受托人 ---
            # trustee_type 是受托人的类型（prosociality），在知道 x 之前就已确定。
            # 返还比例 = 对 x 的反应（随 x 递减）+ 沟通上移 + 类型；
            # 承诺强度只由类型驱动——消息页排在投资者决策之前，真实被试不可能
            # 让承诺依赖于 x，故承诺里不含 -0.035x 这一项。
            trustee_type = float(rng.standard_normal())
            max_return = MULTIPLIER * send
            ratio = float(np.clip(
                0.45 - 0.035 * send + (0.19 if is_comm else 0.0)
                + RATIO_TYPE_SD * trustee_type, 0.0, 1.0))
            return_amt = int(round(ratio * max_return))

            # 消息只在沟通组存在：基线组被试不经过消息页，四列全为空
            if is_comm:
                # 投资者的消息强度是其「打算送出多少」的代理，与 x 单调对应
                # （x 本身是同一意图的实现），故用 x 作简化式即可。此处没有
                # 单独的沟通组项：消息只在沟通组存在，该项不可识别。
                message_investor, imsg_strength = _message(
                    rng, IMSG_A + IMSG_BX * send, IMSG_SD,
                    content.INVESTOR_MESSAGES)
                # 承诺强度：只对沟通组生成。截距与噪声让分布铺满 0-4 而非在
                # 4 处堆顶——堆顶会压掉与返还比例的相关，而 H5 只在沟通组的
                # 30 名受托人上估计，样本已经很小。
                message_trustee, promise = _message(
                    rng, PROMISE_A + PROMISE_B_TYPE * trustee_type,
                    PROMISE_SD, content.TRUSTEE_MESSAGES)
            else:
                message_investor = message_trustee = None
                imsg_strength = promise = None

            # 信念奖金：直接调用真值来源，不在此重写规则。
            # x=0 时 payoffs 一律返回 0（奖金规则的变更点）。
            bonus = payoffs.belief_bonus(belief, send, return_amt)

            code_i = f'sim_{is_comm}_{pair_id}_A'
            code_t = f'sim_{is_comm}_{pair_id}_B'
            # 个体层协变量逐人独立抽（同一对的两名被试是不同的人，
            # 不应共享 general_trust / age / econ_courses；只有处理组是配对级）。
            common = dict(is_communication=is_comm)

            rows.append(dict(
                participant_code=code_i, role='Investor',
                send_amount=send, return_amount=return_amt,
                # 比例字段与真实结算同源：ResultsWaitPage 也是调这个函数
                return_ratio=payoffs.return_ratio(send, return_amt),
                belief_return_pct=belief, belief_investor_send=None,
                belief_bonus=bonus, promise_strength=None,
                message_investor=message_investor, message_trustee=None,
                investor_message_strength=imsg_strength,
                risk_choice=int(np.clip(round(rng.normal(2.5, 1.3)), 0, 5)),
                dictator_give=int(np.clip(round(rng.normal(3.5, 2)), 0, 10)),
                gender=str(rng.choice(['男', '女'], p=[0.45, 0.55])),
                grade=str(rng.choice(['大一', '大二', '大三', '大四'])),
                prior_experience=bool(rng.random() < 0.2),
                general_trust=int(np.clip(round(rng.normal(6, 2)), 0, 10)),
                age=int(np.clip(round(rng.normal(20, 1.8)), 16, 60)),
                econ_courses=int(np.clip(round(rng.normal(3, 2)), 0, 30)),
                **common,
            ))
            rows.append(dict(
                participant_code=code_t, role='Trustee',
                send_amount=send, return_amount=return_amt,
                return_ratio=payoffs.return_ratio(send, return_amt),
                belief_return_pct=None,
                belief_investor_send=int(np.clip(round(rng.normal(
                    2.0 + 0.6 * send + (0.8 if is_comm else 0.0), 1.5)), 0, 10)),
                belief_bonus=0, promise_strength=promise,
                message_investor=None, message_trustee=message_trustee,
                investor_message_strength=None,
                risk_choice=int(np.clip(round(rng.normal(2.5, 1.3)), 0, 5)),
                dictator_give=int(np.clip(round(rng.normal(3.5, 2)), 0, 10)),
                gender=str(rng.choice(['男', '女'], p=[0.45, 0.55])),
                grade=str(rng.choice(['大一', '大二', '大三', '大四'])),
                prior_experience=bool(rng.random() < 0.2),
                general_trust=int(np.clip(round(rng.normal(6, 2)), 0, 10)),
                age=int(np.clip(round(rng.normal(20, 1.8)), 16, 60)),
                econ_courses=int(np.clip(round(rng.normal(3, 2)), 0, 30)),
                **common,
            ))

    return pd.DataFrame(rows)


def main():
    df = generate()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
    print(f'已生成模拟数据：{OUTPUT_PATH}')
    print(f'  样本量：{len(df)}（投资者 {(df.role == "Investor").sum()}，'
          f'受托人 {(df.role == "Trustee").sum()}）')
    print(f'  沟通组：{(df.is_communication == 1).sum()}，基线组：{(df.is_communication == 0).sum()}')
    investors = df[df.role == 'Investor']
    print('  投资者送出金额均值（按处理组）：')
    print(investors.groupby('is_communication').send_amount.mean().to_string())
    print('  零发送人数（按处理组）：')
    print(investors.assign(zero=(investors.send_amount == 0).astype(int))
          .groupby('is_communication').zero.sum().to_string())
    print('  返还比例均值（按处理组，仅 x>0）：')
    pos = df[(df.role == 'Trustee') & (df.send_amount > 0)]
    print(pos.groupby('is_communication').return_ratio.mean().to_string())


if __name__ == '__main__':
    main()

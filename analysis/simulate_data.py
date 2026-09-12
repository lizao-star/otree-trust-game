"""生成模拟实验数据。

⚠️ 本脚本产生的数据是模拟数据，不是真实被试数据。
   报告中引用这些结果时必须标注"模拟数据"。

生成原则（规格第 15.4 节）：按文献报告的效应量生成，而非随机噪声。
  - 基线组 x 均值约 5，右偏，且含真实的零发送质量点
  - 沟通组 x 均值上移（规格写「约 0.5 个标准差」；本文件取 0.8 SD，
    实测 d≈0.6，理由见下方 COMM_SHIFT 的取值说明），且零发送率更低
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
    promise= 2.6 + 0.5*tau + N(0, 0.6)              承诺强度，只由 tau 驱动（见下）
    bonus  = payoffs.belief_bonus(...)              一律调用真值来源
    消息与承诺强度只在沟通组存在（消息页 MessageSend.is_displayed =
    has_communication），文案与强度编码取自 trust_game.content 的 0-4 量表。
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
  * x 的分布用 Γ + 零膨胀而非正态：规格第 15.4 节要求基线组 x「右偏」，
    而 N(5, 2.5) 截断到 [0, 10] 后偏度为负（实测约 -0.3）；Γ 截断后偏度
    为正。零发送是真实信任博弈数据中的常见类型（沟通会显著减少它），
    用显式质量点（而非把 Γ 硬截到 0）以复现该形态。
    代价：零质量点把偏度往负方向拉，本种子下基线组实测偏度仅 +0.08
    （无零膨胀时约 +0.2）——「右偏」与「零发送」在 0-10 有界尺度上互相抵消，
    规格的两条要求在此处存在张力，取零发送（更贴近真实数据）优先。
  * 返还比例的斜率 -0.035 与噪声 0.11：这两者共同决定「比值随 x 递减」能否
    被检出。斜率太小时（如 -0.015）该相关在 N=120 下不可检出；噪声太大时
    （如 0.25）同理。
  * COMM_SHIFT：规格第 15.4 节写「提升约 0.5 个标准差」，而规格第 14.3 节又
    要求模拟数据上「已知效应能被检出」。n=30/组、α=.05 时 d=0.5 的功效仅约
    50%，逐次抽样常检不出；此处取 0.8 SD（规格第 15.1 节引用的文献区间为
    d≈0.5–0.9），叠加基线组更高的零发送率后，实测效应量在文献区间内。
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

# 文案 ←→ 0-4 强度编码取自 trust_game.content 的唯一真值源
_INVESTOR_MESSAGE = {code: label for code, label in content.INVESTOR_MESSAGES}
_TRUSTEE_MESSAGE = {code: label for code, label in content.TRUSTEE_MESSAGES}


def _truncated_normal(rng, mean, sd, low, high):
    return float(np.clip(rng.normal(mean, sd), low, high))


def _message(rng, mean, sd, table):
    """抽一条消息，返回 (文案, 强度)。强度由 content.strength_of 反查，
    保证与真实量表同源。"""
    code = int(np.clip(round(rng.normal(mean, sd)), 0, 4))
    label = table[code]
    strength = content.strength_of(
        content.INVESTOR_MESSAGES if table is _INVESTOR_MESSAGE
        else content.TRUSTEE_MESSAGES, label)
    return label, strength


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
                # （x 本身是同一意图的实现），故用 x 作简化式即可。
                message_investor, imsg_strength = _message(
                    rng, 0.6 + 0.35 * send + 0.4, 1.3, _INVESTOR_MESSAGE)
                # 承诺强度：只对沟通组生成。截距与噪声让分布铺满 0-4 而非在
                # 4 处堆顶——堆顶会压掉与返还比例的相关，而 H5 只在沟通组的
                # 30 名受托人上估计，样本已经很小。
                message_trustee, promise = _message(
                    rng, PROMISE_A + PROMISE_B_TYPE * trustee_type,
                    PROMISE_SD, _TRUSTEE_MESSAGE)
            else:
                message_investor = message_trustee = None
                imsg_strength = promise = None

            # 信念奖金：直接调用真值来源，不在此重写规则。
            # x=0 时 payoffs 一律返回 0（奖金规则的变更点）。
            bonus = payoffs.belief_bonus(belief, send, return_amt)

            code_i = f'sim_{is_comm}_{pair_id}_A'
            code_t = f'sim_{is_comm}_{pair_id}_B'
            common = dict(
                is_communication=is_comm,
                general_trust=int(np.clip(round(rng.normal(6, 2)), 0, 10)),
                age=int(np.clip(round(rng.normal(20, 1.8)), 16, 60)),
                econ_courses=int(np.clip(round(rng.normal(3, 2)), 0, 30)),
            )

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

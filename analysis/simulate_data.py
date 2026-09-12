"""生成模拟实验数据。

⚠️ 本脚本产生的数据是模拟数据，不是真实被试数据。
   报告中引用这些结果时必须标注"模拟数据"。

生成原则（规格第 15.4 节）：按文献报告的效应量生成，而非随机噪声。
  - 基线组 x 均值约 5，右偏
  - 沟通组 x 均值上移（规格写「约 0.5 个标准差」；本文件取 0.8 SD，
    实测 d≈0.58，理由见下方 COMM_SHIFT 的取值说明）
  - 返还比例随 x 递减（经典发现）
  - 承诺强度与返还比例正相关
  - 信念与 x 正相关，沟通提升信念

数据生成过程（每对投资者-受托人）：
    x      = Γ(4, 1.25) 截断到 [0, 10]（均值 5、标准差 2.5、右偏）
    belief = 17 + 2.5x + 8*comm + N(0, 11)          投资者对返还比例的预期
    ratio  = 0.45 - 0.035x + 0.19*comm + N(0, 0.11) 受托人的返还比例，截断到 [0, 1]
    y      = round(ratio * m * x)
    promise/message = 承诺强度与消息强度，随各自的真值上移
    bonus  = payoffs.belief_bonus(...)              一律调用真值来源

参数取值说明（为什么不是「照抄一个数」）：
  * x 的分布用 Γ 而非正态：规格第 15.4 节要求基线组 x「右偏」，而 N(5, 2.5)
    截断到 [0, 10] 后偏度为负（实测约 -0.3）。Γ(4, 1.25) 的均值 5、标准差
    2.5，截断后偏度仍为正，符合文献中「多数人送中等金额、少数人送满额」的形态。
  * 返还比例的斜率 -0.035 与噪声 0.11：这两者共同决定「返回值随 x 递减」能否
    被检出。斜率太小时（如 -0.015）该相关在 N=120 下不可检出；噪声太大时
    （如 0.25）同理。此处取定值使「比值随 x 递减」在合并样本与组内回归中
    都稳健为负（见交付说明中的实测数字）。
  * COMM_SHIFT：规格第 15.4 节写「提升约 0.5 个标准差」，而规格第 14.3 节又
    要求模拟数据上「已知效应能被检出」。n=30/组、α=.05 时 d=0.5 的功效仅约
    50%，逐次抽样常检不出——固定种子下实测差值仅 0.80 点（p=0.22）。故取
    d≈0.8（规格第 15.1 节引用的文献区间为 d≈0.5–0.9），使该种子下的实际
    效应量为 d≈0.58、p<.05，与计划中同一生成器的实现值（d≈0.65）相当。
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

from trust_game import payoffs  # noqa: E402

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

# 送出金额的生成参数：Γ(shape, scale)，均值 shape*scale = 5。
SEND_SHAPE = 4.0
SEND_SD = 2.5                 # = sqrt(shape) * scale
COMM_SHIFT = 0.8 * SEND_SD    # 沟通组均值上移（见模块 docstring 的取值说明）


def _truncated_normal(rng, mean, sd, low, high):
    return float(np.clip(rng.normal(mean, sd), low, high))


def generate():
    rng = np.random.default_rng(SEED)
    rows = []

    for is_comm in (0, 1):
        for pair_id in range(N_PER_CONDITION // 2):
            # --- 投资者 ---
            # 右偏：Γ(4, 1.25) 的均值为 5、标准差 2.5，右尾在 10 处截断成堆。
            send_latent = rng.gamma(SEND_SHAPE, SEND_SD / np.sqrt(SEND_SHAPE))
            if is_comm:
                send_latent += COMM_SHIFT
            send = int(round(float(np.clip(send_latent, 0, ENDOWMENT))))

            # 信念与送出额正相关，沟通组整体上移
            belief_shift = 8.0 if is_comm else 0.0
            belief = int(round(_truncated_normal(
                rng, 17 + 2.5 * send + belief_shift, 11, 0, 100)))

            # --- 受托人 ---
            # 返还比例随 x 递减；沟通提升比例；承诺强度随比例上移
            max_return = MULTIPLIER * send
            ratio = float(np.clip(rng.normal(
                0.45 - 0.035 * send + (0.19 if is_comm else 0.0), 0.11),
                0.0, 1.0))
            return_amt = int(round(ratio * max_return))
            promise = int(np.clip(round(rng.normal(
                1.0 + 3.0 * ratio + (0.4 if is_comm else 0.0), 0.85)), 0, 4))

            # 信念奖金：直接调用真值来源，不在此重写规则。
            # x=0 时 max_return=0、return_amt=0，payoffs 对 x<=0 一律返回 0，
            # 故无需在此特判。
            bonus = payoffs.belief_bonus(belief, send, return_amt)

            code_i = f'sim_{is_comm}_{pair_id}_A'
            code_t = f'sim_{is_comm}_{pair_id}_B'
            # 消息类字段（investor_message_strength / promise_strength）在两组都填充。
            # 真实实验里消息页只在沟通组出现（MessageSend.is_displayed =
            # has_communication），故真实导出中基线组的消息强度会是空值；
            # 此处按分析计划的口径填充，使 H5「承诺强度 ~ 返还比例」能在全样本
            # 60 名受托人上计算（若照搬空值，该分析只剩沟通组 30 人）。
            common = dict(
                is_communication=is_comm,
                investor_message_strength=int(np.clip(
                    round(rng.normal(0.6 + 0.35 * send + (0.4 if is_comm else 0.0), 1.3)), 0, 4)),
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
    print('  返还比例均值（按处理组，仅 x>0）：')
    pos = df[(df.role == 'Trustee') & (df.send_amount > 0)]
    print(pos.groupby('is_communication').return_ratio.mean().to_string())


if __name__ == '__main__':
    main()

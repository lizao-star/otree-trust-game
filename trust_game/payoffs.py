"""信任博弈的收益与派生量计算。

本模块不依赖 oTree，可独立单元测试。

参数（规格第 5.1 节）：禀赋 ENDOWMENT = 10，乘子 MULTIPLIER = 3。

约定：send_amount 记为 x，return_amount 记为 y。
"""

ENDOWMENT = 10
MULTIPLIER = 3

# 信念奖金的判定容差（百分点）与奖金金额（点）
BELIEF_TOLERANCE_PCT = 10
BELIEF_BONUS_POINTS = 2


def investor_payoff(send_amount: int, return_amount: int) -> int:
    """投资者收益 A = E - x + y，范围 0-30。"""
    return ENDOWMENT - send_amount + return_amount


def trustee_payoff(send_amount: int, return_amount: int) -> int:
    """受托人收益 B = m*x - y，范围 0-30。"""
    return MULTIPLIER * send_amount - return_amount


def total_surplus(send_amount: int) -> int:
    """总额 A + B = E + (m-1)*x。"""
    return ENDOWMENT + (MULTIPLIER - 1) * send_amount


def return_ratio(send_amount: int, return_amount: int) -> float:
    """返还比例 y/(m*x)。

    x = 0 时 y 必然为 0（B 无可返还金额），约定比例记为 0.0。
    """
    if send_amount <= 0:
        return 0.0
    return return_amount / (MULTIPLIER * send_amount)


def belief_bonus(
    belief_return_pct: int,
    send_amount: int,
    return_amount: int,
    tolerance_pct: int = BELIEF_TOLERANCE_PCT,
    bonus: int = BELIEF_BONUS_POINTS,
) -> int:
    """信念奖金：预测返还比例与实际比例的偏差在 tolerance_pct 个百分点内则得奖。

    判定使用全整数运算：|belief*denom - 100*y| <= tolerance*denom，其中 denom = m*x。
    选择整数实现是为了让正确性由构造保证，而非由 IEEE 浮点舍入的行为保证——
    本函数决定真实金钱收益。

    该判定与**精确有理数解**的一致性由仓库内的穷举测试断言：
    test_payoffs.py::test_belief_bonus_matches_exact_rational_solution_exhaustively
    对 x > 0 的全部 (x, y, belief) 组合用 fractions.Fraction 计算精确偏差并逐一
    比对（x = 0 的期望值取规格第 7 节的规定，而非有理数解）。此前这里写的是
    「等价浮点实现已穷举验证」——那个实现不在仓库里，读者无法复现，故改为指向
    可运行的测试。

    x = 0 时不发奖金（规格第 7 节），与预测值无关：此时没有发生实际转移，
    信念无对象可评分。return_ratio 的 0.0 约定只是「比例」这一派生量在
    x=0 时的定义（B 无可返还金额，y 必为 0），并不蕴含「照发奖金」。
    若照发，送出 0 且预测 <= tolerance_pct 的投资者将确定得到
    10 + 2 = 12 点，高于 10 点禀赋——「什么都不送」于是成为唯一无风险
    且优于禀赋的选项，会在 x=0 处形成下限聚集、使信任度量向下偏，并把
    不信任、风险规避与惩罚三种动机混同（x=0 还把受托人收益打到 0，
    对照组的 y=6 情形为 9）。故 x=0 一律返回 0。
    """
    if send_amount <= 0:
        return 0
    denom = MULTIPLIER * send_amount
    if abs(belief_return_pct * denom - 100 * return_amount) <= tolerance_pct * denom:
        return bonus
    return 0

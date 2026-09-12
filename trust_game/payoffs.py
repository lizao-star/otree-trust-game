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
    这样正确性不依赖 IEEE 浮点舍入的推理。（等价浮点实现已在全部 17776 组
    (x,y,belief) 输入上穷举验证同样正确；此处选择整数实现是为了让正确性
    由构造保证，而非由浮点行为保证——本函数决定真实金钱收益。）

    x = 0 时实际比例约定为 0%，故预测 0..tolerance_pct 得奖。
    """
    if send_amount <= 0:
        return bonus if belief_return_pct <= tolerance_pct else 0
    denom = MULTIPLIER * send_amount
    if abs(belief_return_pct * denom - 100 * return_amount) <= tolerance_pct * denom:
        return bonus
    return 0

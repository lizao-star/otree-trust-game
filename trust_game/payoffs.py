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

# 受托人预测「投资者送出多少点」时使用的容差（点）与奖金金额（点）。
# 以点数而非百分比判定，是因为该问题的答案本身就是 0-10 的整数点。
TRUSTEE_BELIEF_TOLERANCE_POINTS = 2

# 信念计奖时点。沟通组在消息环节前后各报告一次，实验随机抽取其中一次计奖；
# 无沟通组只报告一次，计奖时点恒为 AFTER（不存在消息前的那次报告）。
BELIEF_TIMING_BEFORE = 'before'
BELIEF_TIMING_AFTER = 'after'


def scored_belief(
    belief_before,
    belief_after,
    timing: str,
):
    """按随机抽中的时点取用对应的返还比例判断。

    只负责取值，不负责判奖——容差判定仍由 belief_bonus 完成，两处规则
    因此不会各自演化。timing 恒为 BELIEF_TIMING_BEFORE / AFTER，由
    creating_session 写入，不来自被试输入。
    """
    if timing == BELIEF_TIMING_BEFORE:
        return belief_before
    return belief_after


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


def second_order_bonus(
    second_order_belief: int,
    investor_belief,
    tolerance_pct: int = BELIEF_TOLERANCE_PCT,
    bonus: int = BELIEF_BONUS_POINTS,
) -> int:
    """二阶信念奖金：受托人的二阶信念与**投资者报告的一阶信念**比较。

    二阶信念的真值是「对方相信什么」，只能以对方实际报告的信念为基准。
    若按实际返还比例评分，二阶信念在计量上退化为一阶信念的同义重述
    （两者都以实际结果判分，区别只在措辞），测不出内疚厌恶路径所需的内容。

    基准 belief 传入 None（时点对齐时对方同次报告缺失）返回 0；
    x = 0 的情形在调用处拦截：投资者自己的信念奖金为 0 时其报告缺乏
    激励支撑，作为基准不可靠。
    """
    if investor_belief is None:
        return 0
    if abs(second_order_belief - investor_belief) <= tolerance_pct:
        return bonus
    return 0


def trustee_belief_bonus(
    belief_send: int,
    send_amount: int,
    tolerance_points: int = TRUSTEE_BELIEF_TOLERANCE_POINTS,
    bonus: int = BELIEF_BONUS_POINTS,
) -> int:
    """受托人一阶信念奖金：预测送出点数与实际送出点数相差不超过容差点数。

    与投资者的比例判定不同，这里直接比较整数点，故不需要浮点或分母处理。
    受托人的预测不影响投资者决策，因此 x = 0 时也照常计奖：不存在「送出 0
    能额外拿钱」的激励问题——受托人无法改变 x，且 x=0 时其收益本就为 0，
    给 2 点奖金只是对准确预测的报酬，不会扭曲任何行为。
    """
    if abs(belief_send - send_amount) <= tolerance_points:
        return bonus
    return 0

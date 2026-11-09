"""payoffs 模块的单元测试。

运行（项目根目录）：
    & "C:\\Anaconda\\envs\\otree\\python.exe" -m unittest trust_game.test_payoffs -v
（不要用 unittest discover，它会误加载依赖 oTree 上下文的 tests.py）
"""

import unittest

from trust_game import payoffs


class TestPayoffs(unittest.TestCase):

    def test_investor_payoff_mid_values(self):
        # 规格第 14.1 节测试用例
        self.assertEqual(payoffs.investor_payoff(0, 0), 10)
        self.assertEqual(payoffs.investor_payoff(5, 6), 11)
        self.assertEqual(payoffs.investor_payoff(10, 15), 15)
        self.assertEqual(payoffs.investor_payoff(10, 30), 30)

    def test_trustee_payoff_mid_values(self):
        self.assertEqual(payoffs.trustee_payoff(0, 0), 0)
        self.assertEqual(payoffs.trustee_payoff(5, 6), 9)
        self.assertEqual(payoffs.trustee_payoff(10, 15), 15)
        self.assertEqual(payoffs.trustee_payoff(10, 30), 0)

    def test_investor_range_is_0_to_30_not_0_to_20(self):
        """规格自审修正的错误：A 的范围是 0-30。"""
        values = [
            payoffs.investor_payoff(x, y)
            for x in range(11)
            for y in range(3 * x + 1)
        ]
        self.assertEqual(min(values), 0)
        self.assertEqual(max(values), 30)

    def test_trustee_range_is_0_to_30(self):
        values = [
            payoffs.trustee_payoff(x, y)
            for x in range(11)
            for y in range(3 * x + 1)
        ]
        self.assertEqual(min(values), 0)
        self.assertEqual(max(values), 30)

    def test_total_surplus_identity_holds_exhaustively(self):
        """总额守恒：任意 (x, y) 下 A + B == 10 + 2x。"""
        for x in range(11):
            for y in range(3 * x + 1):
                with self.subTest(x=x, y=y):
                    total = payoffs.investor_payoff(x, y) + payoffs.trustee_payoff(x, y)
                    self.assertEqual(total, payoffs.total_surplus(x))

    def test_social_optimum_is_30_split_15_15(self):
        self.assertEqual(payoffs.total_surplus(10), 30)
        self.assertEqual(payoffs.investor_payoff(10, 15), 15)
        self.assertEqual(payoffs.trustee_payoff(10, 15), 15)

    def test_return_ratio_convention_when_x_is_zero(self):
        self.assertEqual(payoffs.return_ratio(0, 0), 0.0)

    def test_return_ratio_values(self):
        self.assertAlmostEqual(payoffs.return_ratio(5, 6), 0.4)
        self.assertAlmostEqual(payoffs.return_ratio(10, 30), 1.0)
        self.assertAlmostEqual(payoffs.return_ratio(10, 15), 0.5)
        self.assertAlmostEqual(payoffs.return_ratio(10, 0), 0.0)

    def test_belief_bonus_within_tolerance(self):
        # x=5, y=6 -> 实际 40%
        self.assertEqual(payoffs.belief_bonus(40, 5, 6), 2)
        self.assertEqual(payoffs.belief_bonus(35, 5, 6), 2)
        self.assertEqual(payoffs.belief_bonus(45, 5, 6), 2)

    def test_belief_bonus_boundary_is_inclusive(self):
        # 偏差恰好 10 个百分点 -> 得奖（边界含等号）
        self.assertEqual(payoffs.belief_bonus(30, 5, 6), 2)
        self.assertEqual(payoffs.belief_bonus(50, 5, 6), 2)

    def test_belief_bonus_outside_tolerance(self):
        # 偏差 11 个百分点 -> 不得奖
        self.assertEqual(payoffs.belief_bonus(29, 5, 6), 0)
        self.assertEqual(payoffs.belief_bonus(51, 5, 6), 0)

    def test_belief_bonus_is_zero_when_x_is_zero(self):
        """x=0 时没有实际转移，一律不发奖金（规格第 7 节）。

        覆盖容差内（0、5、10）与容差外（11、50、100）两侧：旧规则在
        预测 <= 10 时照发 2 点，会使「送出 0 且预测低」成为确定得到
        12 点（高于 10 点禀赋）的无风险选项。
        """
        for belief in (0, 5, 10, 11, 50, 100):
            with self.subTest(belief=belief):
                self.assertEqual(payoffs.belief_bonus(belief, 0, 0), 0)

    def test_scored_belief_follows_the_drawn_timing(self):
        """计奖时点决定取哪一次报告：两次取值不同，取错必然可见。"""
        before, after = 30, 50
        self.assertEqual(
            payoffs.scored_belief(before, after, payoffs.BELIEF_TIMING_BEFORE),
            before,
        )
        self.assertEqual(
            payoffs.scored_belief(before, after, payoffs.BELIEF_TIMING_AFTER),
            after,
        )

    def test_scored_belief_falls_back_to_after_without_message_round(self):
        """无沟通组只有消息后那一次测量，时点恒为 after。"""
        self.assertEqual(
            payoffs.scored_belief(None, 50, payoffs.BELIEF_TIMING_AFTER),
            50,
        )

    def test_second_order_bonus_compares_against_investor_belief(self):
        """二阶信念奖金按「与投资者报告的信念之差」判定，容差 10 个百分点。"""
        for second, investor in ((45, 50), (40, 50), (50, 50), (55, 50), (60, 50)):
            with self.subTest(second=second, investor=investor):
                self.assertEqual(
                    payoffs.second_order_bonus(second, investor), 2)
        for second, investor in ((30, 50), (39, 50), (61, 50), (70, 50)):
            with self.subTest(second=second, investor=investor):
                self.assertEqual(
                    payoffs.second_order_bonus(second, investor), 0)

    def test_second_order_bonus_boundary_is_inclusive(self):
        self.assertEqual(payoffs.second_order_bonus(40, 50), 2)
        self.assertEqual(payoffs.second_order_bonus(60, 50), 2)
        self.assertEqual(payoffs.second_order_bonus(39, 50), 0)
        self.assertEqual(payoffs.second_order_bonus(61, 50), 0)

    def test_second_order_bonus_returns_zero_without_investor_belief(self):
        """基准缺失（None）返回 0；x=0 的拦截在调用处完成，这里钉住
        「基准不可用时不得发奖」这条底线。"""
        self.assertEqual(payoffs.second_order_bonus(50, None), 0)

    def test_trustee_belief_bonus_within_tolerance(self):
        """预测送出点数误差 <= 2 点得 2 点。"""
        for belief, actual in ((3, 5), (4, 5), (5, 5), (6, 5), (7, 5)):
            with self.subTest(belief=belief, actual=actual):
                self.assertEqual(
                    payoffs.trustee_belief_bonus(belief, actual), 2)

    def test_trustee_belief_bonus_outside_tolerance(self):
        for belief, actual in ((1, 5), (2, 5), (8, 5), (9, 5), (10, 5)):
            with self.subTest(belief=belief, actual=actual):
                self.assertEqual(
                    payoffs.trustee_belief_bonus(belief, actual), 0)

    def test_trustee_belief_bonus_is_paid_when_x_is_zero(self):
        """x = 0 时受托人一阶奖金照发。

        受托人无法改变投资者送多少，因此「准确预测 0 点而额外拿钱」不会
        扭曲任何行为；这与投资者比例奖金的 x=0 规则是两回事。
        """
        for belief in (0, 1, 2):
            with self.subTest(belief=belief):
                self.assertEqual(payoffs.trustee_belief_bonus(belief, 0), 2)
        self.assertEqual(payoffs.trustee_belief_bonus(3, 0), 0)

    def test_trustee_belief_bonus_matches_rule_exhaustively(self):
        """穷举所有合法的 (预测, 实际) 组合。"""
        for actual in range(11):
            for belief in range(11):
                expected = 2 if abs(belief - actual) <= 2 else 0
                with self.subTest(actual=actual, belief=belief):
                    self.assertEqual(
                        payoffs.trustee_belief_bonus(belief, actual), expected)

    def test_belief_bonus_matches_exact_rational_solution_exhaustively(self):
        """穷举验证整数实现与规定期望值完全一致。

        x > 0 用精确有理数解；x = 0 的期望值是规格第 7 节的规定
        （一律 0），而非有理数解——此时比例无对象可评分。
        """
        from fractions import Fraction
        for x in range(11):
            for y in range(3 * x + 1):
                for belief in range(101):
                    if x == 0:
                        expected = 0
                    else:
                        exact = Fraction(100 * y, 3 * x)
                        expected = 2 if abs(Fraction(belief) - exact) <= 10 else 0
                    with self.subTest(x=x, y=y, belief=belief):
                        self.assertEqual(
                            payoffs.belief_bonus(belief, x, y), expected
                        )


if __name__ == '__main__':
    unittest.main()

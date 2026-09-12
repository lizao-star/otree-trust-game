"""payoffs 模块的单元测试。

运行：/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_payoffs -v
（在项目根目录执行；不要用 unittest discover，它会误加载依赖 oTree 上下文的 tests.py）
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

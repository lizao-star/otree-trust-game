"""content 模块与面向被试文案的单元测试。

运行：/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_content -v
"""

import unittest
from pathlib import Path
from types import SimpleNamespace

from otree.templating.loader import FileLoader

from trust_game import C, Introduction, content, payoffs

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestContent(unittest.TestCase):

    def test_both_scales_are_0_to_4(self):
        """规格自审修正的不一致：两侧量表必须对称，均为 0-4。"""
        for messages in (content.INVESTOR_MESSAGES, content.TRUSTEE_MESSAGES):
            codes = sorted(code for code, _ in messages)
            self.assertEqual(codes, [0, 1, 2, 3, 4])

    def test_labels_are_unique_within_each_scale(self):
        for messages in (content.INVESTOR_MESSAGES, content.TRUSTEE_MESSAGES):
            labels = [label for _, label in messages]
            self.assertEqual(len(labels), len(set(labels)))

    def test_message_labels_pairs_value_with_itself(self):
        pairs = content.message_labels(content.INVESTOR_MESSAGES)
        self.assertEqual(len(pairs), 5)
        for value, label in pairs:
            self.assertEqual(value, label)

    def test_strength_of_is_inverse_of_scale(self):
        for messages in (content.INVESTOR_MESSAGES, content.TRUSTEE_MESSAGES):
            for code, label in messages:
                self.assertEqual(content.strength_of(messages, label), code)

    def test_strength_of_is_total_over_choices(self):
        """表单给出的每个选项都必须能映射回编码，否则 before_next_page 会崩。"""
        for messages in (content.INVESTOR_MESSAGES, content.TRUSTEE_MESSAGES):
            for _, label in content.message_labels(messages):
                self.assertIsInstance(content.strength_of(messages, label), int)

    def test_strength_of_raises_on_unknown_label(self):
        with self.assertRaises(KeyError):
            content.strength_of(content.INVESTOR_MESSAGES, '不存在的消息')

    def test_highest_code_means_strongest_trust(self):
        codes = [code for code, _ in content.INVESTOR_MESSAGES]
        self.assertEqual(codes[0], 4)   # 全部送出
        self.assertEqual(codes[-1], 0)  # 还没有决定
        self.assertEqual(codes, sorted(codes, reverse=True))


def _stub_player(role):
    """构造 vars_for_template 所需的最小 player 替身。

    Introduction.vars_for_template 只读 player.role 与 session.config，
    不必启动 oTree 的 session 上下文（纯函数测试保持零会话依赖）。
    """
    return SimpleNamespace(role=role, session=SimpleNamespace(config={}))


class TestIntroductionDisclosure(unittest.TestCase):
    """指导语中的奖金披露必须与 payoffs 的规则**同源**，不会静默过期。

    本任务修复的缺陷之一就是「被试读到的规则」与「实际计奖的规则」可以各说
    各话（原先奖金规则根本没披露）。故把两半都钉住：

    1. Introduction.vars_for_template 提供的两个数字必须来自 payoffs 常量
       （拦住「在 __init__.py 里改回字面量」）；
    2. 渲染出的指导语文案必须含有这两个常量的**当前值**
       （拦住「在模板里改回字面量」——只要该字面量与常量不一致就会失败）。

    **覆盖边界（不夸大）**：第 2 条断言的是「渲染文本里出现了当前常量值」，
    因此模板里写死一个**恰好等于当前常量**的字面量不会被发现——它只在两
    者**背离**时才失败。换言之，它拦住的是「规则改了、文案没改」这种真实
    故障，而不是「文案的实现方式不优雅」。

    渲染直接用 oTree 自带的模板引擎（FileLoader + 绝对路径），不经
    otree.api.render_template：后者会 getattr(player, 'group'/'session'/...)
    并要求真实 player，且其 ibis_loader 以 cwd 为搜索根；用绝对路径可使本
    测试与调用时的 cwd 无关。
    """

    def _render(self, is_investor):
        ctx = Introduction.vars_for_template(
            _stub_player(C.INVESTOR_ROLE if is_investor else C.TRUSTEE_ROLE)
        )
        template = FileLoader(PROJECT_ROOT).load('trust_game/Introduction.html')
        return str(template.render(ctx, strict_mode=True))

    def test_vars_for_template_sources_bonus_constants_from_payoffs(self):
        ctx = Introduction.vars_for_template(_stub_player(C.INVESTOR_ROLE))
        self.assertEqual(
            ctx['belief_tolerance_pct'], payoffs.BELIEF_TOLERANCE_PCT
        )
        self.assertEqual(
            ctx['belief_bonus_points'], payoffs.BELIEF_BONUS_POINTS
        )

    def test_investor_copy_states_current_accuracy_rule(self):
        html = self._render(is_investor=True)
        self.assertIn(
            f'相差不超过 {payoffs.BELIEF_TOLERANCE_PCT} 个百分点', html
        )
        self.assertIn(
            f'额外获得 <strong>{payoffs.BELIEF_BONUS_POINTS} 点</strong>', html
        )

    def test_investor_copy_states_x_zero_exclusion(self):
        html = self._render(is_investor=True)
        self.assertIn('若你送出的点数为 0，则本项奖金为 0', html)

    def test_trustee_copy_has_no_bonus_disclosure(self):
        """受托人没有奖金，指导语不得出现该项披露。"""
        self.assertNotIn('信念判断奖金', self._render(is_investor=False))


if __name__ == '__main__':
    unittest.main()

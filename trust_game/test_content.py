"""content 模块的单元测试。

运行：/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_content -v
"""

import unittest

from trust_game import content


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


if __name__ == '__main__':
    unittest.main()

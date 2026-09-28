"""content 模块与面向被试文案的单元测试。

运行：/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_content -v
"""

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

from otree.templating.loader import FileLoader

from survey import C as SURVEY_C, DictatorGame

from trust_game import C, Introduction, MessageSend, content, payoffs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PY = PROJECT_ROOT / 'settings.py'


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


def shipped_session_config_defaults():
    """从 settings.py 取 SESSION_CONFIG_DEFAULTS（ast 解析，不 import 配置模块）。

    与 analysis/test_analyze.py 取 app_sequence 的做法一致：只解析字面量，避免在
    测试里走一遍 oTree 的配置加载路径。oTree 会把 SESSION_CONFIG_DEFAULTS 合并进
    每个 session config（otree/session.py:216-217），故它就是在跑实验时进入
    player.session.config 的那份值（参与费与兑换率还是 clean() 的必需键，
    见 otree/session.py:79-87）。
    """
    tree = ast.parse(SETTINGS_PY.read_text(encoding='utf-8'))
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and getattr(node.targets[0], 'id', None)
                == 'SESSION_CONFIG_DEFAULTS'):
            # settings.py 用的是 dict(...) 调用而非字面量，两种写法都接受
            if isinstance(node.value, ast.Call):
                return {kw.arg: ast.literal_eval(kw.value)
                        for kw in node.value.keywords}
            return ast.literal_eval(node.value)
    raise AssertionError('未能在 settings.py 中找到 SESSION_CONFIG_DEFAULTS')


def plain_amount(value):
    """把金额写成不带多余小数点的形式（20.0 -> '20'），供拼接期望文案。

    刻意不复用 trust_game.amount_for_copy：期望值若由被测函数生成，
    取整之类的问题就会被测试一并继承。
    """
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def _stub_player(role, config=None):
    """构造 vars_for_template 所需的最小 player 替身。

    Introduction.vars_for_template 只读 player.role 与 session.config，
    不必启动 oTree 的 session 上下文（纯函数测试保持零会话依赖）。
    不传 config 时用出厂设置（settings.py 的 SESSION_CONFIG_DEFAULTS）。
    """
    return SimpleNamespace(
        role=role,
        session=SimpleNamespace(
            config=shipped_session_config_defaults() if config is None else config
        ),
    )


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

    报酬口径（兑换率与出场费）走的是更严的第二条路：它们不只与当前值比对，还会
    用**另一份 config** 重新渲染（见
    test_payment_terms_come_from_config_not_from_template_literals）。因此模板里
    只要还留着字面量就必然失败，与那个字面量的取值无关——这一类断言没有上面那
    条覆盖缺口。

    渲染直接用 oTree 自带的模板引擎（FileLoader + 绝对路径），不经
    otree.api.render_template：后者会 getattr(player, 'group'/'session'/...)
    并要求真实 player，且其 ibis_loader 以 cwd 为搜索根；用绝对路径可使本
    测试与调用时的 cwd 无关。
    """

    def _render(self, is_investor, config=None):
        ctx = Introduction.vars_for_template(
            _stub_player(C.INVESTOR_ROLE if is_investor else C.TRUSTEE_ROLE,
                         config=config)
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

    # ---- 报酬口径（兑换率、出场费）同源：原先硬编码在模板里 ----

    def test_vars_for_template_sources_payment_terms_from_session_config(self):
        """两个金额必须取自 session.config，而不是写死在 vars_for_template 里。"""
        ctx = Introduction.vars_for_template(_stub_player(
            C.INVESTOR_ROLE,
            config=dict(real_world_currency_per_point=2.5,
                        participation_fee=40.0),
        ))
        self.assertEqual(ctx['currency_per_point'], '2.5')
        self.assertEqual(ctx['participation_fee'], '40')

    def test_payment_terms_come_from_config_not_from_template_literals(self):
        """换一份 config 重渲染，文案必须跟着变——否则模板里仍是字面量。

        这是「两处真值源」的直接探针：模板里若残留 '1 元' / '20 元'，本用例会
        失败；而用出厂配置渲染时同样的字面量不会被发现，故必须换值渲染。
        注意本函数**不做四舍五入**：2.5 必须原样出现在文案里（若实现改成
        `|to0` 之类，这里读到的会是 3），那会让被试读到的金额与实际不符。
        """
        html = self._render(is_investor=False, config=dict(
            real_world_currency_per_point=2.5, participation_fee=40.0))
        self.assertIn('每 1 点可兑换 2.5 元人民币', html)
        self.assertIn('另有 40 元出场费', html)
        self.assertNotIn('每 1 点可兑换 1 元人民币', html)
        self.assertNotIn('另有 20 元出场费', html)

    def test_rendered_copy_states_shipped_payment_terms(self):
        """出厂配置下，被试读到的兑换率与出场费必须等于 settings.py 里的值。"""
        terms = shipped_session_config_defaults()
        html = self._render(is_investor=True)
        self.assertIn(
            f'每 1 点可兑换 '
            f'{plain_amount(terms["real_world_currency_per_point"])} 元人民币',
            html,
        )
        self.assertIn(
            f'另有 {plain_amount(terms["participation_fee"])} 元出场费', html)


class TestMessageConditionCopy(unittest.TestCase):
    """四组指导语互斥，且各自说清「谁能给谁发」。

    四种情形共用同一个模板，靠 sends_message / receives_message 两个标志分支
    （trust_game/Introduction.html）。分支写错的后果是**被试读到的规则与实际
    经历的页面对不上**：例如两个单向组的措辞写反，A→B 组的被试会以为自己不能
    发送、于是干等对方的回信。而四个 config 都照样跑通、bot 测试也全绿——
    没有任何运行时报错。故四段话必须逐段钉住：本情形那段出现，另外三段不出现。

    渲染走 vars_for_template 的真实路径（配置键 → 读取函数 → 模板上下文），
    而不是手工往上下文里塞两个布尔值：后者会绕过 sends_message /
    receives_message 的角色映射，而那正是最容易写反的地方（投资者与受托人
    在两个单向组里的处境正好互换）。
    """

    BOTH = '双方都能看到对方的消息'
    SENDER_ONLY = '对方无法向你发送消息'
    RECEIVER_ONLY = '你无法向对方发送任何消息'
    NEITHER = '不会有任何信息交流'

    ALL_FOUR = (BOTH, SENDER_ONLY, RECEIVER_ONLY, NEITHER)

    def _render_intro(self, investor_sends, trustee_sends, role):
        config = dict(shipped_session_config_defaults(),
                      investor_sends_message=investor_sends,
                      trustee_sends_message=trustee_sends)
        ctx = Introduction.vars_for_template(
            _stub_player(role, config=config))
        template = FileLoader(PROJECT_ROOT).load('trust_game/Introduction.html')
        return str(template.render(ctx, strict_mode=True))

    def test_each_condition_shows_exactly_one_paragraph(self):
        """四种情形各自只出现对应那一段，另外三段都不出现。

        逐格列举而不是只测两端：中间两格（两个单向组）才是新写的分支，
        两端在改造前就已存在。
        """
        investor, trustee = C.INVESTOR_ROLE, C.TRUSTEE_ROLE
        # (投资者能否发, 受托人能否发, 被试角色, 该被试应读到的那段)
        cases = [
            (False, False, investor, self.NEITHER),
            (False, False, trustee, self.NEITHER),
            (True, True, investor, self.BOTH),
            (True, True, trustee, self.BOTH),
            # 仅 B→A：B 是发送方，A 是接收方
            (False, True, trustee, self.SENDER_ONLY),
            (False, True, investor, self.RECEIVER_ONLY),
            # 仅 A→B：A 是发送方，B 是接收方
            (True, False, investor, self.SENDER_ONLY),
            (True, False, trustee, self.RECEIVER_ONLY),
        ]
        for investor_sends, trustee_sends, role, expected in cases:
            with self.subTest(investor_sends=investor_sends,
                              trustee_sends=trustee_sends, role=role):
                html = self._render_intro(investor_sends, trustee_sends, role)
                self.assertIn(expected, html)
                for other in self.ALL_FOUR:
                    if other != expected:
                        self.assertNotIn(
                            other, html,
                            f'四段说明必须互斥：{role} 在 '
                            f'(investor={investor_sends}, '
                            f'trustee={trustee_sends}) 下除了「{expected}」'
                            f'还读到了「{other}」——被试因此无法确定'
                            '自己处在哪一种信息结构里')

    def test_message_send_page_states_the_same_direction_as_intro(self):
        """发消息页与指导语必须同一口径：单向组的发送方在页面上也读得到
        「对方无法向你发送消息」，否则他发完会一直等回信。"""
        def render(receives):
            ctx = MessageSend.vars_for_template(_stub_player(
                C.INVESTOR_ROLE,
                config=shipped_session_config_defaults()))
            ctx['other_also_sends'] = receives   # 显式覆盖，避免读真实配置
            ctx['form'] = []
            template = FileLoader(PROJECT_ROOT).load('trust_game/MessageSend.html')
            return str(template.render(ctx, strict_mode=True))

        both = render(receives=True)
        self.assertIn('双方都能看到对方的选择', both)
        self.assertNotIn(self.SENDER_ONLY, both)

        one_way = render(receives=False)
        self.assertIn(self.SENDER_ONLY, one_way)
        self.assertNotIn('双方都能看到对方的选择', one_way)

    def test_vars_for_template_reports_the_two_dimensions(self):
        """两个标志必须来自配置键，且角色映射方向正确。

        这是上一条的**下界**：即使模板分支全对，只要 sends/receives 的
        角色映射写反（把「A 发」映射到受托人），四组的行为就会整体错位。
        """
        investor, trustee = C.INVESTOR_ROLE, C.TRUSTEE_ROLE

        def flags(role, investor_sends, trustee_sends):
            config = dict(shipped_session_config_defaults(),
                          investor_sends_message=investor_sends,
                          trustee_sends_message=trustee_sends)
            ctx = Introduction.vars_for_template(
                _stub_player(role, config=config))
            return ctx['sends_message'], ctx['receives_message']

        # 仅 B 发：投资者只收、受托人只发
        self.assertEqual(flags(investor, False, True), (False, True))
        self.assertEqual(flags(trustee, False, True), (True, False))
        # 仅 A 发：正好相反
        self.assertEqual(flags(investor, True, False), (True, False))
        self.assertEqual(flags(trustee, True, False), (False, True))
        # 两端：两个维度同真 / 同假
        self.assertEqual(flags(investor, True, True), (True, True))
        self.assertEqual(flags(investor, False, False), (False, False))


class TestSurveyCopyDisclosure(unittest.TestCase):
    """问卷页上的报酬口径同样不得写死（本项目的第一号缺陷类）。

    `survey/DictatorGame.html` 原先也硬编码「每 1 点可兑换 1 元人民币」，与
    `settings.py` 的 `real_world_currency_per_point` 构成第二个真值源；本类把它
    也钉在 session.config 上，方式与 Introduction 的报酬口径相同。

    放在本文件（而不是新建一个 survey 的文案测试文件）：本项目只有这一张
    「面向被试文案与常量同源」的安全网，把它拆成两份之后，未来的改动只会记得
    更新其中一处——那正是这张网本要防的事。
    """

    def _render(self, config):
        ctx = DictatorGame.vars_for_template(
            _stub_player(C.INVESTOR_ROLE, config=config))
        # 模板还引用 C.DICTATOR_ENDOWMENT：真实渲染由 oTree 注入 C，
        # 这里手工补上（strict_mode 下缺变量会直接报错，不会静默渲染成空）
        ctx['C'] = SURVEY_C
        # {{ formfields }} 需要真实的 form 对象；本用例断言的是报酬文案那一段，
        # 故给一个空表单（渲染成空串）。空列表是有效的 form：字段名集合为空。
        ctx['form'] = []
        template = FileLoader(PROJECT_ROOT).load('survey/DictatorGame.html')
        return str(template.render(ctx, strict_mode=True))

    def test_rendered_copy_states_shipped_exchange_rate(self):
        """出厂配置下，被试读到的兑换率必须等于 settings.py 里的值。"""
        terms = shipped_session_config_defaults()
        html = self._render(terms)
        self.assertIn(
            f'每 1 点可兑换 '
            f'{plain_amount(terms["real_world_currency_per_point"])} 元人民币',
            html,
        )

    def test_exchange_rate_comes_from_config_not_template_literal(self):
        """换一份 config 重渲染：文案必须跟着变，否则模板里仍是字面量。"""
        html = self._render(dict(
            shipped_session_config_defaults(),
            real_world_currency_per_point=2.5,
        ))
        self.assertIn('每 1 点可兑换 2.5 元人民币', html)
        self.assertNotIn('每 1 点可兑换 1 元人民币', html)


if __name__ == '__main__':
    unittest.main()

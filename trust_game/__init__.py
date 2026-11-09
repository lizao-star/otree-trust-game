from otree.api import *

import random

from . import content
from . import payoffs

doc = """
信任博弈实验（Berg, Dickhaut & McCabe, 1995）。

处理组是 2×2 析因，由 session config 的**两个布尔键**控制：
  investor_sends_message = A（投资者）能否给 B 发一条意向消息
  trustee_sends_message  = B（受托人）能否给 A 发一条承诺消息

四格：
  都 False = 无沟通      仅 trustee = B→A 单向（承诺）
  仅 investor = A→B 单向  都 True  = 双向（决策前同时发送、互相可见）

默认按 session config 的两个键固定整场条件（用于演示与教学）。真实采集请用
`trust_random`：条件在**配对层**随机，四个格子同场并存，避免条件与场次混淆。
"""


class C(BaseConstants):
    NAME_IN_URL = 'trust_game'
    PLAYERS_PER_GROUP = 2
    NUM_ROUNDS = 1

    # 角色定义。定义顺序决定 id_in_group 的分配：
    # get_roles() 按 __dict__ 插入序取值，故 INVESTOR_ROLE 必须在前，
    # 以保证 id_in_group=1 是投资者。
    INVESTOR_ROLE = content.INVESTOR_ROLE
    TRUSTEE_ROLE = content.TRUSTEE_ROLE

    ENDOWMENT = payoffs.ENDOWMENT
    MULTIPLIER = payoffs.MULTIPLIER

    INVESTOR_MESSAGES = content.INVESTOR_MESSAGES
    TRUSTEE_MESSAGES = content.TRUSTEE_MESSAGES


# ---------------------------------------------------------------------------
# 处理组的读取入口。全部经此，不在别处直接读 config。
#
# `.get(key, False)` 里的默认值是**必需**的，不是防御性写法：
# trust_game/test_content.py 用只带报酬两个键的桩 config 渲染指导语，
# 缺键时必须退化为「无沟通」而不是抛 KeyError。
# ---------------------------------------------------------------------------

def _pair_flag(player, field):
    """读取本配对是否享有某个沟通条件。

    固定条件配置从 session config 读；`trust_random` 的条件由 creating_session
    写在每个 Player 上（同一配对两行相同），必须读字段——若这里仍读 config，
    随机配置没有那两个键，四格会全部退化为「无沟通」，而页面照样渲染、不报错。
    """
    if player.session.config.get('randomize_cells', False):
        value = player.field_maybe_none(field)
        if value is None:
            raise ValueError(
                f'{field} 未赋值：randomize_cells 下 creating_session 必须先'
                '把配对条件写入每个 Player'
            )
        return value
    return player.session.config.get(field, False)


def investor_sends(player):
    """A（投资者）能否给 B 发消息。"""
    return _pair_flag(player, 'investor_sends_message')


def trustee_sends(player):
    """B（受托人）能否给 A 发消息。"""
    return _pair_flag(player, 'trustee_sends_message')


def sends_message(player):
    """本方是不是**发送方**——决定 MessageSend 是否显示。"""
    if player.role == C.INVESTOR_ROLE:
        return investor_sends(player)
    return trustee_sends(player)


def receives_message(player):
    """本方是不是**接收方**——决定 MessageReveal 是否显示。

    ⚠️ 它与 sends_message 不是互补关系，而是 2×2 的两个独立维度：
    双向组里两者同为真，无沟通组里两者同为假，两个单向组里一真一假。
    不要把它当成 `not sends_message(player)` 的简写。
    """
    if player.role == C.INVESTOR_ROLE:
        return trustee_sends(player)
    return investor_sends(player)


def any_message(player):
    """本组是否存在消息环节——决定等待页是否显示。

    等待页对**组内所有人**显示（含不发送的那一方），这是时序安全的前提：
    接收方不进 MessageSend 而直接到等待页，发送方提交后才放行，故接收方
    不可能在发送方提交之前越过等待页看到消息。
    """
    return investor_sends(player) or trustee_sends(player)


def cell_name(investor_sends_flag, trustee_sends_flag):
    """把两个布尔因子折成四格标签，供导出数据与报告对照。"""
    if investor_sends_flag and trustee_sends_flag:
        return 'both'
    if investor_sends_flag:
        return 'a_to_b'
    if trustee_sends_flag:
        return 'b_to_a'
    return 'none'


def amount_for_copy(value):
    """把配置中的金额渲染成被试可读的字符串：20.0 -> '20'，2.5 -> '2.5'。

    **不做四舍五入**：取整会让指导语里的金额与被试实际拿到的金额不一致，
    那正是本项目反复出现的「两处真值源」缺陷，只不过这次印在被试读的文案上。
    模板侧只允许 `{{ ... }}` 引用本函数的返回值，不得写字面量。
    """
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    """把两个处理组因子降范式写入每个 Player，使导出数据自包含。

    ！！必须是模块级函数，不要改写成 Subsession 的类方法 ！！

    原因（oTree 6 的解析机制）：本模块含 import 语句，故
    common.is_noself(app) 为 True（otree/common.py:62）；
    Subsession.get_user_defined_target() 因此返回**模块**而非类
    （otree/database.py:706-707）。调用点
    run_creating_session_functions 执行
    getattr(target, 'creating_session', None)（otree/session.py:453），
    在模块上只能找到模块级函数：若写成类方法，getattr 返回 None，
    本函数被静默跳过，两个字段恒为 NULL —— 依赖它们的页面分派逻辑
    （谁发消息、谁看消息）会走错分支而假通过，而不会报错。
    这正是 oTree 自带模板的写法（otree/assets/app_template_trials/__init__.py）。
    trust_game/tests.py 中的断言会在任一字段为 None 时立刻失败，以防回归。
    """
    randomize_cells = bool(subsession.session.config.get('randomize_cells', False))
    if randomize_cells:
        # 真实采集：角色与条件都在**配对层**随机，四格同场并存。
        # 若按 session config 固定条件，条件会与场次、时段、到场人群完全混淆，
        # 且课程场景往往一次只能开一个 session，四格要开四场。
        players = list(subsession.get_players())
        if len(players) % 2 != 0:
            raise ValueError('随机分配条件需要偶数名被试。')
        random.shuffle(players)
        half = len(players) // 2
        investors = players[:half]
        trustees = players[half:]
        # 每组 [id_in_group=1, id_in_group=2]，按 C 中角色顺序即 [投资者, 受托人]
        subsession.set_group_matrix(
            [[investor, trustee] for investor, trustee in zip(investors, trustees)]
        )
        for group in subsession.get_groups():
            a_sends = random.choice([True, False])
            b_sends = random.choice([True, False])
            cell = cell_name(a_sends, b_sends)
            for player in group.get_players():
                player.investor_sends_message = a_sends
                player.trustee_sends_message = b_sends
                player.pair_cell = cell
                player.role_randomized = True
    else:
        investor = subsession.session.config.get('investor_sends_message', False)
        trustee = subsession.session.config.get('trustee_sends_message', False)
        cell = cell_name(investor, trustee)
        for player in subsession.get_players():
            player.investor_sends_message = investor
            player.trustee_sends_message = trustee
            player.pair_cell = cell
            player.role_randomized = False

    # 计奖时点：沟通组随机抽一次；无沟通组只有消息后那次真实报告计奖，
    # 时点固定为 after。无沟通组现在也会填写一次「假想的事前判断」，
    # 但该次报告只作基线、不参与计奖（见 BeliefBefore 页的说明）。
    for player in subsession.get_players():
        if player.investor_sends_message or player.trustee_sends_message:
            player.belief_paid_timing = random.choice([
                payoffs.BELIEF_TIMING_BEFORE,
                payoffs.BELIEF_TIMING_AFTER,
            ])
        else:
            player.belief_paid_timing = payoffs.BELIEF_TIMING_AFTER


class Group(BaseGroup):
    @property
    def investor(self):
        return self.get_player_by_role(C.INVESTOR_ROLE)

    @property
    def trustee(self):
        return self.get_player_by_role(C.TRUSTEE_ROLE)


class Player(BasePlayer):
    # 处理组标识：2×2 的两个因子，由上面的 creating_session 写入（固定 config
    # 时整场相同；trust_random 时按配对随机）。两个字段都是**组级**的。
    investor_sends_message = models.BooleanField()
    trustee_sends_message = models.BooleanField()
    # 四格标签（none / a_to_b / b_to_a / both）与「是否经配对层随机分配」。
    # 真实采集用 trust_random，导出后先按这两列核对四格平衡，再进入分析。
    pair_cell = models.StringField(blank=True)
    role_randomized = models.BooleanField(initial=False)

    # 诚信承诺（对应 Dufwenberg et al. (2026) 的 honesty pledge）。
    # 无消息组也要勾选：承诺对象是「随后填写的判断」，不是「将要发的消息」，
    # 这样四种条件接受完全相同的前置仪式，不会因条件不同产生仪式差异。
    pledge_honesty = models.BooleanField(
        initial=False,
        label='我承诺：我在本实验中发送的消息（如可发送）以及随后填写的判断，'
              '都反映我的真实想法。',
    )

    # 理解检验
    comprehension_attempts = models.IntegerField(initial=0)
    comp_q1 = models.IntegerField(
        min=0, max=999, label='问题 1：投资者初始获得多少点？'
    )
    comp_q2 = models.IntegerField(
        min=0, max=999,
        label='问题 2：若投资者送出 4 点，受托人实际收到多少点？（实验者会将送出额乘以 3）'
    )
    comp_q3 = models.IntegerField(
        min=0, max=999, label='问题 3：受托人最多可以返还多少点？（用刚才的例子回答）'
    )
    # 第 4 题防的是「以为发消息能提高乘子」——这是 cheap talk 设计最常见的
    # 失效点：若被试以为沟通改变收益规则，处理效应就不是信念更新了。
    comp_q4 = models.IntegerField(
        min=0, max=1,
        label='问题 4：发送消息会改变收益的乘子或返还规则吗？（会 = 1，不会 = 0）',
    )

    # 沟通消息：存文案而非编码，保留被试实际看到的内容
    message_investor = models.StringField(
        choices=content.message_labels(C.INVESTOR_MESSAGES),
        label='请选择你要发送给对方的消息：',
        widget=widgets.RadioSelect,
        blank=True,
    )
    message_trustee = models.StringField(
        choices=content.message_labels(C.TRUSTEE_MESSAGES),
        label='请选择你要发送给对方的消息：',
        widget=widgets.RadioSelect,
        blank=True,
    )
    investor_message_strength = models.IntegerField(blank=True, min=0, max=4)
    promise_strength = models.IntegerField(blank=True, min=0, max=4)
    # 派生承诺指标：1 = 受托人的消息属于「承诺返还一部分及以上」。
    # 由 MessageWaitPage 同时写入组内两行，便于导出后任一角色行都能直接使用；
    # 无消息条件与「未决定 / 不确定」两档为 0，无消息条件另需以 pair_cell 区分。
    promise = models.IntegerField(blank=True, min=0, max=1)

    # 信念
    # belief_return_pct / belief_investor_send 记录**消息环节之后**那次报告；
    # *_before 记录消息环节之前的那次报告。所有条件都会填写 *_before：沟通组
    # 读到的是真实的事前判断，无沟通组读到的是一个假设性问题（「假如可以交换
    # 消息」），并由 belief_before_hypothetical 区分。该假设性基线不参与计奖。
    # 注意：两次测量都在**决策之前**完成，分界是消息环节而不是决策——
    # 二阶信念尤其要在决策前测，否则会被自己的决策污染。
    belief_return_pct = models.IntegerField(
        min=0, max=100,
        label='你认为乙方会返还你送出金额被放大 3 倍后的百分之多少？（0-100）'
    )
    belief_investor_send = models.IntegerField(
        min=0, max=10, blank=True,
        label='你认为甲方会送出多少点？（0-10）'
    )
    belief_return_pct_before = models.IntegerField(
        min=0, max=100, blank=True,
        label='你认为乙方会返还你送出金额被放大 3 倍后的百分之多少？（0-100）'
    )
    belief_investor_send_before = models.IntegerField(
        min=0, max=10, blank=True,
        label='你认为甲方会送出多少点？（0-10）'
    )
    # 1 = 这次事前判断是无沟通组的假设性基线，不参与计奖；0 = 真实的事前判断。
    belief_before_hypothetical = models.BooleanField(blank=True)

    # 二阶信念：受托人认为「投资者相信受托人会返还多少比例」。
    # 这是 Charness & Dufwenberg (2006) 内疚厌恶路径所需的变量；只在受托人
    # 页面上出现，投资者行为 NULL。计奖基准是**投资者报告的一阶信念**
    # （见 ResultsWaitPage 与 payoffs.second_order_bonus 的说明）。
    second_order_belief_return_pct_before = models.IntegerField(
        min=0, max=100, blank=True,
        label='你认为，甲方相信你会返还你所收到点数的百分之多少？（0-100）'
    )
    second_order_belief_return_pct = models.IntegerField(
        min=0, max=100, blank=True,
        label='你认为，甲方相信你会返还你所收到点数的百分之多少？（0-100）'
    )

    # 本次计奖使用的时点（before / after）。每名玩家都有值，由
    # creating_session 随机写入；无沟通组恒为 after。被试作答时看不到该字段。
    belief_paid_timing = models.StringField(blank=True)

    # 决策。送出额只有 11 个整数值，改为完整可见的单选按钮组：消除键入误差，
    # 也是信任博弈文献的惯例做法（可见的完整选择集）。
    send_amount = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        choices=[(i, str(i)) for i in range(C.ENDOWMENT + 1)],
        widget=widgets.RadioSelectHorizontal,
        label='请决定你要送出多少点：'
    )
    # 返还额上限动态（0-3x），保持数字输入并在页面上显示上限。
    return_amount = models.IntegerField(blank=True, min=0, max=30)
    return_ratio = models.FloatField(blank=True)

    # 该玩家的信念奖金合计（点）：投资者为 0/2；受托人为两个信念任务的
    # 0/2 之和（一阶送出点数预测 + 二阶返还比例预测）。
    belief_bonus = models.IntegerField(initial=0)

    # 事后情绪与操纵检查（不参与报酬计算）。字段都是 blank=True，因为
    # 只有特定角色、特定条件才会看到对应题目；未展示的行保持 NULL。
    # 愤怒是双向的：投资者对「返还低于预期」不满，受托人对「送出额低」
    # 也会不满——后者是信任缺失的供给侧，与投资者的不满构成对偶比较。
    anger_intensity = models.IntegerField(
        blank=True, min=1, max=5,
        label='看到乙方实际返还的金额后，你在多大程度上感到不满？（1 = 一点也不，5 = 非常不满）',
    )
    trustee_anger_intensity = models.IntegerField(
        blank=True, min=1, max=5,
        label='看到甲方实际送出的金额后，你在多大程度上感到不满？（1 = 一点也不，5 = 非常不满）',
    )
    perceived_message = models.IntegerField(
        blank=True, min=1, max=5,
        label='你认为对方消息中表达的返还意向有多可信？（1 = 完全不可信，5 = 完全可信）',
    )
    perceived_intent = models.IntegerField(
        blank=True, min=1, max=5,
        label='你认为对方消息中表达的送出意向有多可信？（1 = 完全不可信，5 = 完全可信）',
    )


# PAGES

class Introduction(Page):
    @staticmethod
    def vars_for_template(player):
        return dict(
            is_investor=player.role == C.INVESTOR_ROLE,
            # 消息环节的两种角色。四个组合（都真/只发/只收/都假）对应指导语
            # 里四段互斥的说明，见 Introduction.html。
            sends_message=sends_message(player),
            receives_message=receives_message(player),
            any_message=any_message(player),
            endowment=C.ENDOWMENT,
            multiplier=C.MULTIPLIER,
            max_return=C.MULTIPLIER * C.ENDOWMENT,
            # 奖金规则的两个数字取自 payoffs 这唯一真值来源，供指导语文案渲染。
            # 面向被试的文案若与规则脱钩，被试读到的就是错的规则——而「规则
            # 未披露」正是本任务修复的缺陷，故此处不留硬编码字面量；
            # trust_game/test_content.py 会断言渲染结果与这两个常量一致。
            belief_tolerance_pct=payoffs.BELIEF_TOLERANCE_PCT,
            belief_bonus_points=payoffs.BELIEF_BONUS_POINTS,
            trustee_belief_tolerance_points=payoffs.TRUSTEE_BELIEF_TOLERANCE_POINTS,
            # 报酬口径（出场费、兑换率）同样取自唯一真值来源 session.config：
            # 这两个数字是被试最关心的两个数，此前硬编码在模板里，是两个真值源，
            # 且不在文案一致性测试的覆盖范围内（只覆盖奖金规则）。
            # 两个键的存在性由 oTree 保证：otree/session.py:79-87 的 clean() 把
            # participation_fee 与 real_world_currency_per_point 列为必需键，
            # :216-217 把 SESSION_CONFIG_DEFAULTS 合并进每个 config，故此处直接
            # 取值——缺键应当立刻报错，而不是在页面上渲染出 None。
            currency_per_point=amount_for_copy(
                player.session.config['real_world_currency_per_point']
            ),
            participation_fee=amount_for_copy(
                player.session.config['participation_fee']
            ),
        )


class Pledge(Page):
    """诚信承诺页（honesty pledge）。

    两种角色都必须勾选才能继续。无消息组也保留本页，但承诺对象是「随后填写的
    判断」——使四种条件接受完全相同的前置仪式，不因条件不同产生仪式差异。
    """
    form_model = 'player'
    form_fields = ['pledge_honesty']

    @staticmethod
    def error_message(player, values):
        if not values.get('pledge_honesty'):
            return {'pledge_honesty': '请勾选承诺后再继续。'}


class ComprehensionCheck(Page):
    form_model = 'player'
    form_fields = ['comp_q1', 'comp_q2', 'comp_q3', 'comp_q4']

    @staticmethod
    def error_message(player, values):
        solutions = dict(comp_q1=10, comp_q2=12, comp_q3=12, comp_q4=0)
        errors = {
            field: '答案不正确，请重新阅读说明后作答。'
            for field, correct in solutions.items()
            if values.get(field) != correct
        }
        if errors:
            # 已验证：oTree 6 中 error_message 内对模型的修改会持久化
            player.comprehension_attempts += 1
            return errors

    @staticmethod
    def before_next_page(player, timeout_happened):
        player.comprehension_attempts += 1


class MessageSend(Page):
    form_model = 'player'

    @staticmethod
    def is_displayed(player):
        # 本方是发送方才经过本页。单向组里接收方跳过它、直接到等待页。
        return sends_message(player)

    @staticmethod
    def vars_for_template(player):
        # 本页只有发送方会看到，故「对方是否也发」等价于「本方是否也收」。
        return dict(other_also_sends=receives_message(player))

    @staticmethod
    def get_form_fields(player):
        if player.role == C.INVESTOR_ROLE:
            return ['message_investor']
        return ['message_trustee']

    @staticmethod
    def error_message(player, values):
        # 消息字段是 blank=True（未经过本页的被试该字段合法为空），oTree 因此
        # 不会加 InputRequired；而未选中的单选组根本不会提交该键，values 里
        # 连 key 都没有。所以必须在这里按角色显式拒绝空选择，并给出中文提示，
        # 否则 before_next_page 读取空字段会抛 NullFieldError（HTTP 500）。
        field = (
            'message_investor'
            if player.role == C.INVESTOR_ROLE
            else 'message_trustee'
        )
        if not values.get(field):
            return {field: '请选择一条要发送的消息。'}

    @staticmethod
    def before_next_page(player, timeout_happened):
        if player.role == C.INVESTOR_ROLE:
            player.investor_message_strength = content.strength_of(
                C.INVESTOR_MESSAGES, player.message_investor
            )
        else:
            player.promise_strength = content.strength_of(
                C.TRUSTEE_MESSAGES, player.message_trustee
            )


class MessageWaitPage(WaitPage):
    # body_text 是 oTree WaitPage 的官方属性：默认等待页只有转圈动画，
    # 被试不知道自己在等什么、要等多久；一句说明能显著减少等待焦虑
    # 与「页面卡住了」的误判（等待页文案与 ProcessingWaitPage 的说明一致）。
    body_text = '正在等待对方完成消息环节，请稍候。'

    @staticmethod
    def is_displayed(player):
        return any_message(player)

    @staticmethod
    def after_all_players_arrive(group):
        # 承诺指标在消息提交后一次性算好，写入组内两行：
        # 投资者行也需要该变量（分组回归时直接可用，不必再连表取对方行）。
        #
        # 必须先用局部变量接住编码结果再写两行：oTree 6 读取一个仍为 NULL 的
        # 字段会抛 TypeError（与 blank=True 无关），故不能写
        # `group.investor.promise = group.trustee.promise`——在无 B→A 消息的
        # 条件下，上一行刚把 trustee 的该字段置为 None，这一读就是 HTTP 500。
        promise_value = (
            content.is_promise(group.trustee.message_trustee)
            if group.trustee.trustee_sends_message else None
        )
        group.trustee.promise = promise_value
        group.investor.promise = promise_value


class MessageReveal(Page):
    @staticmethod
    def is_displayed(player):
        # 本方是接收方才经过本页。单向组里发送方发完即走，看不到任何消息。
        return receives_message(player)

    @staticmethod
    def vars_for_template(player):
        other = player.get_others_in_group()[0]
        if player.role == C.INVESTOR_ROLE:
            message_from_other = other.message_trustee
        else:
            message_from_other = other.message_investor
        # 本方没有发送时 message_* 为 NULL，直接读会抛 TypeError——
        # 先判 sends 再取值，取不到时保持 None（模板按 both_sends 分支）。
        own_message = None
        if sends_message(player):
            own_message = (
                player.message_investor
                if player.role == C.INVESTOR_ROLE
                else player.message_trustee
            )
        return dict(
            message_from_other=message_from_other,
            # 双向组同时回显本方已发送的消息：被试无需回忆自己选了哪条，
            # 也确认「对方看到的确实是这条」。
            own_message=own_message,
            both_sends=sends_message(player),
        )


class BeliefBefore(Page):
    """决策之前的信念。

    沟通组读到的是一次真实的事前判断；无沟通组没有消息环节，读到的则是
    「假如可以交换消息」的假设性问题。两者共用同一页与同名字段，由
    belief_before_hypothetical 标记区分。假设性基线不参与计奖，只用于提供
    与沟通组可比的事前基准。
    """

    form_model = 'player'

    @staticmethod
    def is_displayed(player):
        return True

    @staticmethod
    def vars_for_template(player):
        return dict(
            hypothetical=not any_message(player),
            is_investor=player.role == C.INVESTOR_ROLE,
            has_message=any_message(player),
        )

    @staticmethod
    def get_form_fields(player):
        if player.role == C.INVESTOR_ROLE:
            return ['belief_return_pct_before']
        return [
            'belief_investor_send_before',
            'second_order_belief_return_pct_before',
        ]

    @staticmethod
    def before_next_page(player, timeout_happened):
        player.belief_before_hypothetical = not any_message(player)

    @staticmethod
    def error_message(player, values):
        # 受托人两个字段都是 blank=True，空提交会被 wtforms 的 Optional()
        # 静默放过；这里按字段显式拒绝，避免丢掉观测值。
        if player.role == C.TRUSTEE_ROLE:
            missing = {}
            if values.get('belief_investor_send_before') is None:
                missing['belief_investor_send_before'] = (
                    '请填写你认为对方会送出的点数（0-10）。'
                )
            if values.get('second_order_belief_return_pct_before') is None:
                missing['second_order_belief_return_pct_before'] = (
                    '请填写你认为对方相信你会返还的比例（0-100）。'
                )
            return missing or None


class BeliefElicit(Page):
    """消息环节之后的信念（无沟通组即唯一的那次真实测量）。"""

    form_model = 'player'

    @staticmethod
    def vars_for_template(player):
        return dict(is_investor=player.role == C.INVESTOR_ROLE)

    @staticmethod
    def get_form_fields(player):
        if player.role == C.INVESTOR_ROLE:
            return ['belief_return_pct']
        return [
            'belief_investor_send',
            'second_order_belief_return_pct',
        ]

    @staticmethod
    def error_message(player, values):
        # 受托人分支的两个字段是 blank=True，空提交会被 wtforms 的
        # Optional() 静默放过（同 TrusteeDecision.return_amount 的机制）。
        # 这里没有下游崩溃，但这两个字段是机制检验依赖的研究变量，
        # 静默缺失等于丢掉观测值，故按字段显式拒绝。
        if player.role == C.TRUSTEE_ROLE:
            missing = {}
            if values.get('belief_investor_send') is None:
                missing['belief_investor_send'] = (
                    '请填写你认为对方会送出的点数（0-10）。'
                )
            if values.get('second_order_belief_return_pct') is None:
                missing['second_order_belief_return_pct'] = (
                    '请填写你认为对方相信你会返还的比例（0-100）。'
                )
            return missing or None


class InvestorDecision(Page):
    form_model = 'player'
    form_fields = ['send_amount']

    @staticmethod
    def is_displayed(player):
        return player.role == C.INVESTOR_ROLE


class DecisionWaitPage(WaitPage):
    body_text = '正在等待甲方做出送出决策，请稍候。'


class TrusteeDecision(Page):
    form_model = 'player'

    @staticmethod
    def is_displayed(player):
        return player.role == C.TRUSTEE_ROLE

    @staticmethod
    def max_return(player):
        return C.MULTIPLIER * player.group.investor.send_amount

    @staticmethod
    def get_form_fields(player):
        # x = 0 时受托人无可返还金额，不渲染表单控件
        if TrusteeDecision.max_return(player) == 0:
            return []
        return ['return_amount']

    @staticmethod
    def vars_for_template(player):
        return dict(
            send_amount=player.group.investor.send_amount,
            max_return=TrusteeDecision.max_return(player),
        )

    @staticmethod
    def error_message(player, values):
        limit = TrusteeDecision.max_return(player)
        # x = 0 时本页不渲染表单，oTree 会以空 values 直接调用本函数
        # （otree/views/abstract.py:743-760）。此时必须返回假值，否则页面
        # 无法通过。下面针对空提交的拒绝逻辑只在有表单时才生效。
        if limit == 0:
            return
        amount = values.get('return_amount')
        # return_amount 是 blank=True：oTree 因此不加 InputRequired
        # （otree/forms/forms.py），wtforms_sqlalchemy 又为可空列补了
        # Optional()，而 Optional 会抹掉空输入的校验错误（wtforms
        # validators.py），所以空提交会以 None 静默通过校验。
        # 若不在此显式拒绝，该 NULL 会在结算阶段被读取
        # （ResultsWaitPage.after_all_players_arrive 中 y = trustee.return_amount）
        # 而抛 TypeError（HTTP 500），同组两人卡在等待页且都拿不到收益。
        if amount is None:
            return {'return_amount': '请填写返还金额（可以填 0）。'}
        if amount < 0 or amount > limit:
            return {'return_amount': f'返还金额必须在 0 到 {limit} 之间。'}

    @staticmethod
    def before_next_page(player, timeout_happened):
        # x = 0 时表单为空，此处补写 0，保证结算阶段字段可用
        if TrusteeDecision.max_return(player) == 0:
            player.return_amount = 0


class ResultsWaitPage(WaitPage):
    body_text = '正在结算本轮收益，请稍候。'

    @staticmethod
    def after_all_players_arrive(group):
        investor = group.investor
        trustee = group.trustee

        x = investor.send_amount
        y = trustee.return_amount

        investor.payoff = cu(payoffs.investor_payoff(x, y))
        trustee.payoff = cu(payoffs.trustee_payoff(x, y))

        ratio = payoffs.return_ratio(x, y)
        investor.return_ratio = ratio
        trustee.return_ratio = ratio

        # 沟通组随机抽中的时点决定用哪次报告判奖；无沟通组恒为 after。
        investor_timing = investor.field_maybe_none('belief_paid_timing')
        scored = payoffs.scored_belief(
            investor.field_maybe_none('belief_return_pct_before'),
            investor.belief_return_pct,
            investor_timing,
        )
        investor.belief_bonus = payoffs.belief_bonus(scored, x, y)
        if investor.belief_bonus:
            investor.payoff += cu(investor.belief_bonus)

        # 受托人有两个信念任务：预测送出点数（按点判定，与实际送出比较）与
        # 二阶信念（预测投资者认为的返还比例）。两者使用受托人的同一个
        # 抽中时点，奖金相加后计入收益。
        trustee_timing = trustee.field_maybe_none('belief_paid_timing')
        scored_send = payoffs.scored_belief(
            trustee.field_maybe_none('belief_investor_send_before'),
            trustee.belief_investor_send,
            trustee_timing,
        )
        scored_second = payoffs.scored_belief(
            trustee.field_maybe_none('second_order_belief_return_pct_before'),
            trustee.second_order_belief_return_pct,
            trustee_timing,
        )
        # 二阶信念的真值是「投资者相信什么」，只能以投资者实际报告的一阶信念
        # 为基准（两人使用受托人的抽中时点对齐：取投资者同一时点的那次报告）。
        # 若按实际返还比例评分，二阶信念会退化为一阶信念的同义重述，测不出
        # 内疚厌恶路径所需的内容。x = 0 时投资者的信念奖金本就为 0，其报告
        # 缺乏激励支撑，基准不可靠，故二阶奖金也为 0。
        if x > 0:
            if trustee_timing == payoffs.BELIEF_TIMING_BEFORE:
                investor_belief = investor.field_maybe_none(
                    'belief_return_pct_before'
                )
            else:
                investor_belief = investor.belief_return_pct
            second_bonus = payoffs.second_order_bonus(scored_second, investor_belief)
        else:
            second_bonus = 0
        trustee.belief_bonus = (
            payoffs.trustee_belief_bonus(scored_send, x)
            + second_bonus
        )
        if trustee.belief_bonus:
            trustee.payoff += cu(trustee.belief_bonus)


class Results(Page):
    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            is_investor=player.role == C.INVESTOR_ROLE,
            send_amount=group.investor.send_amount,
            return_amount=group.trustee.return_amount,
            return_ratio=group.investor.return_ratio,
            my_belief_bonus=player.belief_bonus,
            belief_paid_timing=player.field_maybe_none('belief_paid_timing'),
            my_payoff=player.payoff,
        )


class PostRound(Page):
    """事后情绪与操纵检查。不参与报酬计算，只用于检验操纵是否生效。

    投资者总显示（不满 + 收到承诺时的可信度评价）；受托人现在也总显示——
    对甲方送出额的不满是信任缺失的供给侧，与投资者的不满构成对偶比较，
    收到意向消息时另答可信度评价。单轮设计下只测「不满强度」，不测论文的
    「有消息/无消息哪个更生气」——后者需要同一被试经历两种条件，本设计
    做不到（见报告第 7 节）。

    注意本页在 Results 之后：Results 只显示本人信念奖金、不显示「预测 vs
    实际偏差」正是为了不在此前引入额外情绪，污染本页的测量。
    """
    form_model = 'player'

    @staticmethod
    def is_displayed(player):
        return True

    @staticmethod
    def get_form_fields(player):
        if player.role == C.INVESTOR_ROLE:
            fields = ['anger_intensity']
            if receives_message(player):
                fields.append('perceived_message')
            return fields
        fields = ['trustee_anger_intensity']
        if receives_message(player):
            fields.append('perceived_intent')
        return fields

    @staticmethod
    def error_message(player, values):
        # 三个字段都是 blank=True，空提交会被 Optional() 静默放过；
        # 这里按本页实际渲染的字段逐一显式拒绝，避免操纵检查出现缺失值。
        missing = {
            field: '请选择一个选项。'
            for field in PostRound.get_form_fields(player)
            if values.get(field) is None
        }
        if missing:
            return missing

    @staticmethod
    def vars_for_template(player):
        return dict(
            is_investor=player.role == C.INVESTOR_ROLE,
            saw_message=receives_message(player),
        )


page_sequence = [
    Introduction,
    ComprehensionCheck,
    Pledge,
    BeliefBefore,
    MessageSend,
    MessageWaitPage,
    MessageReveal,
    BeliefElicit,
    InvestorDecision,
    DecisionWaitPage,
    TrusteeDecision,
    ResultsWaitPage,
    Results,
    PostRound,
]

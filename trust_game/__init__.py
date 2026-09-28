from otree.api import *

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

def investor_sends(player):
    """A（投资者）能否给 B 发消息。"""
    return player.session.config.get('investor_sends_message', False)


def trustee_sends(player):
    """B（受托人）能否给 A 发消息。"""
    return player.session.config.get('trustee_sends_message', False)


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
    investor = subsession.session.config.get('investor_sends_message', False)
    trustee = subsession.session.config.get('trustee_sends_message', False)
    for player in subsession.get_players():
        player.investor_sends_message = investor
        player.trustee_sends_message = trustee


class Group(BaseGroup):
    @property
    def investor(self):
        return self.get_player_by_role(C.INVESTOR_ROLE)

    @property
    def trustee(self):
        return self.get_player_by_role(C.TRUSTEE_ROLE)


class Player(BasePlayer):
    # 处理组标识：2×2 的两个因子，取自 session.config 的同名键，由上面的
    # creating_session 降范式写入。两个字段都是**组级**的（同组两人相同），
    # 因为处理组在 session 层面分配。
    investor_sends_message = models.BooleanField()
    trustee_sends_message = models.BooleanField()

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

    # 信念
    belief_return_pct = models.IntegerField(
        min=0, max=100,
        label='你认为对方会返还你送出金额被放大后的百分之多少？（0-100）'
    )
    belief_investor_send = models.IntegerField(
        min=0, max=10, blank=True,
        label='你认为对方会送出多少点？（0-10）'
    )

    # 决策
    send_amount = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='请决定你要送出多少点：'
    )
    return_amount = models.IntegerField(blank=True, min=0, max=30)
    return_ratio = models.FloatField(blank=True)

    belief_bonus = models.IntegerField(initial=0)


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
            endowment=C.ENDOWMENT,
            multiplier=C.MULTIPLIER,
            max_return=C.MULTIPLIER * C.ENDOWMENT,
            # 奖金规则的两个数字取自 payoffs 这唯一真值来源，供指导语文案渲染。
            # 面向被试的文案若与规则脱钩，被试读到的就是错的规则——而「规则
            # 未披露」正是本任务修复的缺陷，故此处不留硬编码字面量；
            # trust_game/test_content.py 会断言渲染结果与这两个常量一致。
            belief_tolerance_pct=payoffs.BELIEF_TOLERANCE_PCT,
            belief_bonus_points=payoffs.BELIEF_BONUS_POINTS,
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


class ComprehensionCheck(Page):
    form_model = 'player'
    form_fields = ['comp_q1', 'comp_q2', 'comp_q3']

    @staticmethod
    def error_message(player, values):
        solutions = dict(comp_q1=10, comp_q2=12, comp_q3=12)
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
    @staticmethod
    def is_displayed(player):
        return any_message(player)


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
        return dict(message_from_other=message_from_other)


class BeliefElicit(Page):
    form_model = 'player'

    @staticmethod
    def get_form_fields(player):
        if player.role == C.INVESTOR_ROLE:
            return ['belief_return_pct']
        return ['belief_investor_send']

    @staticmethod
    def error_message(player, values):
        # 受托人分支的 belief_investor_send 是 blank=True，空提交会被
        # wtforms 的 Optional() 静默放过（同 TrusteeDecision.return_amount
        # 的机制）。这里没有下游崩溃，但该字段是分析计划依赖的研究变量，
        # 静默缺失等于丢掉观测值，故按角色显式拒绝并给出中文提示。
        if player.role == C.TRUSTEE_ROLE and values.get('belief_investor_send') is None:
            return {'belief_investor_send': '请填写你认为对方会送出的点数（0-10）。'}


class InvestorDecision(Page):
    form_model = 'player'
    form_fields = ['send_amount']

    @staticmethod
    def is_displayed(player):
        return player.role == C.INVESTOR_ROLE


class DecisionWaitPage(WaitPage):
    pass


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

        investor.belief_bonus = payoffs.belief_bonus(
            investor.belief_return_pct, x, y
        )
        trustee.belief_bonus = 0
        if investor.belief_bonus:
            investor.payoff += cu(investor.belief_bonus)


class Results(Page):
    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            is_investor=player.role == C.INVESTOR_ROLE,
            send_amount=group.investor.send_amount,
            return_amount=group.trustee.return_amount,
            return_ratio=group.investor.return_ratio,
            belief_bonus=group.investor.belief_bonus,
            my_payoff=player.payoff,
        )


page_sequence = [
    Introduction,
    ComprehensionCheck,
    MessageSend,
    MessageWaitPage,
    MessageReveal,
    BeliefElicit,
    InvestorDecision,
    DecisionWaitPage,
    TrusteeDecision,
    ResultsWaitPage,
    Results,
]

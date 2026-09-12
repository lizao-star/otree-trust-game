from otree.api import *
from otree.bots.bot import ExpectError
from . import *


def expect_populated(player, field):
    """前置条件断言：可空字段必须已有值，才谈得上对其值作断言。

    直接读取未赋值的字段在 oTree 6 中会抛 NullFieldError
    （otree/database.py:639），故读取可空字段一律经 field_maybe_none()。
    """
    value = player.field_maybe_none(field)
    if value is None:
        raise ExpectError(
            f'{field} 为 None：前置条件不成立（本用例下该字段本应有值），'
            '无法继续对其值作断言'
        )
    return value


class PlayerBot(Bot):
    """单一入口：按 session config 的 communication 分派到对应流程。

    本类只做分派，断言统一由 check_round 承担——oTree 6 的 PlayerBot 没有任何
    形如 validate_round 的框架钩子（全包搜索零结果），断言写在那里等于死代码，
    测试会通过但什么都没验证。
    """

    # oTree 的 runner（otree/bots/runner.py）按 case 逐个重跑整个 session，
    # 同一 session 内所有 bot 共用同一个 case，故同组两人的情形始终一致。
    # 两个 case 在**两个处理组**里都必须走不同路径：normal 送 10（基线为 5），
    # zero_send 送 0，使 x=0 的奖金规则在基线与沟通组各有一条真实覆盖。
    cases = ['normal', 'zero_send']

    def play_round(self):
        # 普通页面必须显式 yield，框架只自动处理 WaitPage；
        # 首页 Introduction 无表单字段也不例外。
        yield Introduction
        zero_send = self.case == 'zero_send'
        # 用 field_maybe_none 读取：若 creating_session 未被调用，该字段为 NULL，
        # 直接读取会抛 NullFieldError，那样就看不到 check_round 里那条指明根因的
        # 断言了；此处退化为 Falsy 走基线流程，由前置条件断言负责拦截。
        if self.player.field_maybe_none('is_communication'):
            yield from communication_round(self, zero_send=zero_send)
        else:
            yield from baseline_round(self, zero_send=zero_send)
        check_round(self, zero_send=zero_send)


def baseline_round(bot, zero_send=False):
    """基线组（communication=False）流程：无任何消息页。"""
    yield Submission(ComprehensionCheck,
                     dict(comp_q1=10, comp_q2=12, comp_q3=12),
                     check_html=False)
    send = 0 if zero_send else 5
    if bot.player.role == C.INVESTOR_ROLE:
        yield Submission(BeliefElicit,
                         dict(belief_return_pct=0 if zero_send else 50),
                         check_html=False)
        yield Submission(InvestorDecision, dict(send_amount=send),
                         check_html=False)
    else:
        # 空信念提交同样必须被拒（belief_investor_send 是 blank=True），
        # 否则受托人的信念观测被静默丢弃
        yield SubmissionMustFail(BeliefElicit, {}, check_html=False)
        yield Submission(BeliefElicit, dict(belief_investor_send=5),
                         check_html=False)
    if bot.player.role == C.TRUSTEE_ROLE:
        max_return = C.MULTIPLIER * bot.player.group.investor.send_amount
        if max_return > 0:
            # 空提交必须被拒（return_amount 是 blank=True，wtforms 会静默放过 None）
            yield SubmissionMustFail(TrusteeDecision, {}, check_html=False)
            # 超过动态上限（但仍在字段静态 max=30 之内）→ 必须由
            # TrusteeDecision.error_message 的动态校验拦下
            yield SubmissionMustFail(
                TrusteeDecision, dict(return_amount=max_return + 1),
                check_html=False
            )
            yield Submission(TrusteeDecision, dict(return_amount=6),
                             check_html=False)
        else:
            # x = 0：本页不渲染任何表单（get_form_fields 返回 []），
            # 而 must_fail 在无表单页面上必然抛极具误导性的
            # BotError: passed validation anyway，故必须跳过 must-fail。
            yield TrusteeDecision
    yield Results


def communication_round(bot, zero_send=False):
    """沟通组（communication=True）流程：决策前双方各发一条消息并互相可见。

    zero_send=True 时投资者送 0 点，使 x=0 路径**穿过** MessageSend /
    MessageReveal（此前两个 case 走的是同一条 x=10 路径，case 1 纯属重复，
    既浪费一倍运行时间，又让 x=0 在沟通组完全没有覆盖）。
    """
    yield Submission(ComprehensionCheck,
                     dict(comp_q1=10, comp_q2=12, comp_q3=12),
                     check_html=False)
    # 空提交必须被拒：未勾选的 RadioSelect 根本不提交该 key，而消息字段是
    # blank=True，若不拦会在 before_next_page 的 strength_of 处抛
    # NullFieldError（HTTP 500，见 trust_game/__init__.py 的 error_message）
    yield SubmissionMustFail(MessageSend, {}, check_html=False)
    if bot.player.role == C.INVESTOR_ROLE:
        # 最强意向（编码 4）
        yield Submission(MessageSend,
                         dict(message_investor=C.INVESTOR_MESSAGES[0][1]),
                         check_html=False)
    else:
        # 次强承诺（编码 3）
        yield Submission(MessageSend,
                         dict(message_trustee=C.TRUSTEE_MESSAGES[1][1]),
                         check_html=False)
    # MessageWaitPage 由框架自动处理，bot 不得 yield
    yield MessageReveal
    send = 0 if zero_send else 10
    if bot.player.role == C.INVESTOR_ROLE:
        yield Submission(BeliefElicit, dict(belief_return_pct=0),
                         check_html=False)
        yield Submission(InvestorDecision, dict(send_amount=send),
                         check_html=False)
    else:
        yield SubmissionMustFail(BeliefElicit, {}, check_html=False)
        yield Submission(BeliefElicit, dict(belief_investor_send=5),
                         check_html=False)
    if bot.player.role == C.TRUSTEE_ROLE:
        max_return = C.MULTIPLIER * bot.player.group.investor.send_amount
        if max_return > 0:
            # 走到这里即 x = 10 → 动态上限 30，恰好等于字段静态 max=30，
            # 故 max_return + 1 = 31 由字段级校验拦下；若将来放宽静态上限，
            # TrusteeDecision.error_message 的动态上限仍会拦截。两条防线
            # 任一生效都会让 must_fail 通过，这正是规格第 8 节要求的双重约束。
            yield SubmissionMustFail(
                TrusteeDecision, dict(return_amount=max_return + 1),
                check_html=False
            )
            yield Submission(TrusteeDecision, dict(return_amount=15),
                             check_html=False)
        else:
            # x = 0：本页不渲染任何表单（get_form_fields 返回 []），
            # must_fail 在无表单页面上必然抛极具误导性的
            # BotError: passed validation anyway，故必须跳过 must-fail。
            yield TrusteeDecision
    yield Results


def check_round(bot, zero_send=False):
    """验证处理组隔离、页面分派与结算正确性。

    在 play_round 末尾调用（oTree 6 无 validate_round 钩子）：生成器在最后一次
    yield 之后仍会被 runner 继续推进到 StopIteration，此时 ResultsWaitPage 的
    after_all_players_arrive 已执行完毕，可以安全读取最终字段值。
    """
    player = bot.player

    # ---------- 前置条件 1：处理组标识有效 ----------
    # 必须已由模块级 creating_session 降范式写入每个 Player（见
    # trust_game/__init__.py 的说明）。若该函数被误改回 Subsession 的类方法，
    # oTree 6 会静默跳过它，此字段恒为 NULL，依赖它的分派逻辑会走错分支而
    # 假通过——所以先显式断言非 None。
    is_comm = player.field_maybe_none('is_communication')
    if is_comm is None:
        raise ExpectError(
            'is_communication 为 None：creating_session 从未被调用，'
            '它必须是模块级函数（见 trust_game/__init__.py）'
        )
    # 与配置**逐值**比对，不能只做真值判断：None 与 False 在 if 下行为相同。
    expect(is_comm, player.session.config.get('communication', False))
    # session config 名是独立的真值来源：沟通组的该字段必须是 True 本身，
    # 而非碰巧为真的值。
    if player.session.config['name'] == 'trust_communication':
        expect(is_comm, True)
    else:
        expect(is_comm, False)

    # ---------- 前置条件 2：分派到的页面确实属于本处理组 ----------
    # 外部证据：otree test 的输出中，沟通组有 Submit .../MessageSend/ 与
    # .../MessageReveal/，基线组完全没有这两类提交。此处再断言页面自身的
    # is_displayed 判定与处理组一致，并把"消息字段是否有值"作为直接后果核对。
    expect(MessageSend.is_displayed(player), is_comm)
    expect(MessageReveal.is_displayed(player), is_comm)

    # ---------- C1：MessageReveal 必须展示「对方」的消息 ----------
    # vars_for_template 里的「我的角色 → 从对方行读哪个字段」映射若被写反，
    # 页面会渲染出错误的消息，而此前没有任何断言会失败。这里把页面**将要
    # 显示**的文本与对方**实际提交**的消息逐字比对，使映射方向可证伪：
    # 投资者必须看到受托人的 message_trustee，受托人必须看到投资者的
    # message_investor。两侧文案分属不同量表（互无交集），故读错字段、
    # 写反分支、乃至误读自己那一行，都会被这一条拦下。
    if is_comm:
        other = player.get_others_in_group()[0]
        other_message_field = (
            'message_trustee' if player.role == C.INVESTOR_ROLE
            else 'message_investor'
        )
        expect(MessageReveal.vars_for_template(player)['message_from_other'],
               expect_populated(other, other_message_field))

    if player.role == C.INVESTOR_ROLE:
        # 对方的消息字段只由受托人分支写入，投资者必须为空
        expect(player.field_maybe_none('message_trustee'), None)
        expect(player.field_maybe_none('promise_strength'), None)
        if is_comm:
            # MessageSend/MessageReveal 确实走过：消息文案已落库、强度已编码
            expect(expect_populated(player, 'message_investor'),
                   C.INVESTOR_MESSAGES[0][1])
            expect(expect_populated(player, 'investor_message_strength'), 4)
            expect(expect_populated(player, 'send_amount'),
                   0 if zero_send else 10)
            # 两种情形都报告预测 0%
            expect(player.belief_return_pct, 0)
            if zero_send:
                # x = 0 → 一律不发奖金（规格第 7 节）。这是最有区分力的一格：
                # 旧规则下预测 0% ≤ 10 个百分点会照发 2 点。
                expect(player.belief_bonus, 0)
                expect(expect_populated(player, 'return_ratio'), 0.0)
                # 收益 = (10 - 0 + 0) + 0 = 10
                expect(expect_populated(player, 'payoff'), 10)
            else:
                # 预测 0%，实际比例 15/(3*10) = 50%，偏差 50 个百分点 > 10
                # → 不得奖（x > 0 的规则未变，此处防回归）
                expect(player.belief_bonus, 0)
                expect(expect_populated(player, 'return_ratio'), 0.5)
                # 收益 = (10 - 10 + 15) + 0 = 15
                expect(expect_populated(player, 'payoff'), 15)
        else:
            # MessageSend 未展示：消息字段必须全程为 NULL
            expect(player.field_maybe_none('message_investor'), None)
            expect(player.field_maybe_none('investor_message_strength'), None)
            expect(expect_populated(player, 'send_amount'),
                   0 if zero_send else 5)
            if zero_send:
                # x = 0 → 一律不发奖金（规格第 7 节）：return_ratio 的 0.0
                # 约定只是比例的定义，不再推导出奖金。预测 0% 落在旧规则的
                # 容差内，故这一格能真实区分新旧规则。
                expect(player.belief_return_pct, 0)
                expect(player.belief_bonus, 0)
                expect(expect_populated(player, 'return_ratio'), 0.0)
                # 收益 = (10 - 0 + 0) + 0 = 10（恰好等于禀赋，不再高于禀赋）
                expect(expect_populated(player, 'payoff'), 10)
            else:
                # 预测 50%，实际比例 6/(3*5) = 40%，偏差恰好 10 个百分点
                # （边界内含等号）→ 得奖 2 点
                expect(player.belief_return_pct, 50)
                expect(player.belief_bonus, 2)
                expect(expect_populated(player, 'return_ratio'), 0.4)
                # 收益 = (10 - 5 + 6) + 2 = 13
                expect(expect_populated(player, 'payoff'), 13)
    else:
        # 对方的消息字段只由投资者分支写入，受托人必须为空
        expect(player.field_maybe_none('message_investor'), None)
        expect(player.field_maybe_none('investor_message_strength'), None)
        # 受托人永远拿不到信念奖金
        expect(player.belief_bonus, 0)
        expect(expect_populated(player, 'belief_investor_send'), 5)
        if is_comm:
            # MessageSend/MessageReveal 确实走过：消息文案已落库、强度已编码
            expect(expect_populated(player, 'message_trustee'),
                   C.TRUSTEE_MESSAGES[1][1])
            expect(expect_populated(player, 'promise_strength'), 3)
        else:
            # MessageSend 未展示：消息字段必须全程为 NULL
            expect(player.field_maybe_none('message_trustee'), None)
            expect(player.field_maybe_none('promise_strength'), None)
        # send_amount 是投资者那一行的字段：受托人自己的 Player 行从未写过它，
        # 只有 group.investor 上才有值（用 expect_populated 判空可暴露这一点）
        send_amount = expect_populated(player.group.investor, 'send_amount')
        return_amount = expect_populated(player, 'return_amount')
        if is_comm:
            expect(send_amount, 0 if zero_send else 10)
            if zero_send:
                # x = 0：TrusteeDecision 无表单，before_next_page 补写 0
                expect(return_amount, 0)
                expect(expect_populated(player, 'return_ratio'), 0.0)
                # 收益 = 3*0 - 0 = 0
                expect(expect_populated(player, 'payoff'), 0)
            else:
                expect(return_amount, 15)
                expect(expect_populated(player, 'return_ratio'), 0.5)
                # 收益 = 3*10 - 15 = 15
                expect(expect_populated(player, 'payoff'), 15)
        elif zero_send:
            # x = 0：本页无表单，before_next_page 补写 0
            expect(send_amount, 0)
            expect(return_amount, 0)
            expect(expect_populated(player, 'return_ratio'), 0.0)
            # 收益 = 3*0 - 0 = 0
            expect(expect_populated(player, 'payoff'), 0)
        else:
            expect(send_amount, 5)
            expect(return_amount, 6)
            expect(expect_populated(player, 'return_ratio'), 0.4)
            # 收益 = 3*5 - 6 = 9
            expect(expect_populated(player, 'payoff'), 9)

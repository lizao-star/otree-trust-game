from otree.api import *
from otree.bots.bot import ExpectError
from . import *

# 三个 bot case。**数值不再随处理组变化**——改造前基线组送 5、沟通组送 10，
# 于是「奖金该发 / 不该发」这两条分支是靠处理组区分的：四个组两两组合之后
# 那样写要维护四套期望值，且每个组只覆盖一半分支。
# 现在把分支挂到 **case** 上，四个处理组跑同一套数值、同一套断言，
# 每个组都完整覆盖两条分支。
CASES = {
    # 送出 5 → 受托人实际收到 15、返还 6 → 比例 0.4。
    # 投资者预测 50% → 偏差恰好 10 个百分点（容差边界，含等号）→ 得奖金 2 点。
    'normal':      dict(send=5, belief=50, returns=6),
    # 同上，但预测 0% → 偏差 40 个百分点 > 10 → **不得奖**。
    # 这一格防的是「容差判定被改宽或改没」：把 |偏差| ≤ 容差 写成恒真时，
    # 只有本条会失败。
    'miss_belief': dict(send=5, belief=0,  returns=6),
    # x = 0 的退化路径：受托人无可返还金额、本页不渲染表单。
    # 预测 0% 落在容差内，但 x = 0 一律不发奖金（规格第 7 节）。
    'zero_send':   dict(send=0, belief=0,  returns=0),
}

# 受托人对「对方会送出多少」的判断。不随 case 变化：它是次要测量，
# 没有奖金规则挂在上面，改它不会改变任何一条断言。
TRUSTEE_BELIEF = 5


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


def role_message_spec(player):
    """本角色「自己发的消息」涉及的三件事：字段名、强度字段名、会提交的文案与编码。

    集中在一处，使 check_round 不必按角色重复三段取值；写错方向（把投资者的
    字段配到受托人那一支）会让下面的逐字比对立刻失败。
    """
    if player.role == C.INVESTOR_ROLE:
        return dict(field='message_investor',
                    strength='investor_message_strength',
                    text=C.INVESTOR_MESSAGES[0][1], code=4,
                    others_field='message_trustee',
                    i_send_flag='investor_sends_message')
    return dict(field='message_trustee',
                strength='promise_strength',
                text=C.TRUSTEE_MESSAGES[1][1], code=3,
                others_field='message_investor',
                i_send_flag='trustee_sends_message')


class PlayerBot(Bot):
    """单一入口：按两个处理组因子（谁发消息、谁看消息）分派到对应流程。

    本类只做分派，断言统一由 check_round 承担——oTree 6 的 PlayerBot 没有任何
    形如 validate_round 的框架钩子（全包搜索零结果），断言写在那里等于死代码，
    测试会通过但什么都没验证。
    """

    # oTree 的 runner（otree/bots/runner.py）按 case 逐个重跑整个 session，
    # 同一 session 内所有 bot 共用同一个 case，故同组两人的情形始终一致。
    cases = list(CASES)

    def play_round(self):
        # 普通页面必须显式 yield，框架只自动处理 WaitPage；
        # 首页 Introduction 无表单字段也不例外。
        yield Introduction
        yield from comprehension_round(self)
        yield from message_round(self)
        yield from belief_round(self)
        yield from decision_round(self)
        check_round(self)


def comprehension_round(bot):
    """理解检验：先提交一题错的（必须被拒），再提交全对的（必须通过）。

    规格 §14.1 要求「答错时 SubmissionMustFail，答对后 comprehension_attempts
    正确累计」。缺了前半句，「全对才能继续」这道门就没被验过：bot 永远提交正确
    答案，即使拦截逻辑整个失效、计数器不再落库，测试也照样全绿——而报告 5.5 /
    7.3 的预注册决定（「无需按理解度剔除」）正建立在这道门有效的前提上。
    """
    yield SubmissionMustFail(
        ComprehensionCheck,
        dict(comp_q1=0, comp_q2=12, comp_q3=12),   # 只有问题 1 答错
        error_fields=['comp_q1'],                   # 且错误必须落在该字段上
        check_html=False,
    )
    yield Submission(ComprehensionCheck,
                     dict(comp_q1=10, comp_q2=12, comp_q3=12),
                     check_html=False)


def message_round(bot):
    """消息环节：**只 yield 本方实际会看到的页**。

    四个处理组的页面组合不同，靠 is_displayed 决定，故这里必须按同一对判定
    来条件 yield：
        发送方（sends_message）    → MessageSend
        接收方（receives_message） → MessageReveal
    单向组里两者一真一假（A→B 组只有投资者发、受托人看），无沟通组两者皆假。

    ⚠️ 不要图省事无条件 yield 三页再由框架跳过：oTree 的 bot 对「yield 了
    未显示的页」直接抛 BotError，而漏 yield 已显示的页会让该页的必填校验
    从未被触发——两种错都会让测试假过或假失败。MessageWaitPage 由框架自动
    处理，bot 不得 yield。

    消息字段是 blank=True（未经过本页的被试该字段合法为空），未勾选的
    RadioSelect 根本不提交该 key，若不拦会在 before_next_page 的 strength_of
    处抛 NullFieldError（HTTP 500）——故每个发送方都要先走一次空提交。
    """
    player = bot.player

    # ⚠️ 下面三个量必须在**第一次 yield 之前**全部读出来。
    #
    # 生成器是在每次请求里被恢复执行的，而 player 对象在上一次请求结束后已从
    # SQLAlchemy 会话脱落；此时再读它的属性会抛 DetachedInstanceError，表现为
    # 该页 HTTP 500、bot 卡死。实测复现：演示会话里 8 个 bot 同时推进时，注释
    # 掉的这两个后置读取（`player.role` 与 `receives_message(player)`）都触发过。
    # 角色与处理组在一次会话内不变，缓存成局部变量是安全的。
    #
    # 上一版把 `if player.role == ...` 写在 `yield` 之后，就是这么炸的。
    role = player.role
    sends = sends_message(player)
    receives = receives_message(player)

    if sends:
        yield SubmissionMustFail(MessageSend, {}, check_html=False)
        if role == C.INVESTOR_ROLE:
            # 最强意向（编码 4）
            yield Submission(MessageSend,
                             dict(message_investor=C.INVESTOR_MESSAGES[0][1]),
                             check_html=False)
        else:
            # 次强承诺（编码 3）
            yield Submission(MessageSend,
                             dict(message_trustee=C.TRUSTEE_MESSAGES[1][1]),
                             check_html=False)
    if receives:
        yield MessageReveal


def belief_round(bot):
    """信念页。两处空提交都必须被拒。"""
    case = CASES[bot.case]
    if bot.player.role == C.INVESTOR_ROLE:
        yield Submission(BeliefElicit,
                         dict(belief_return_pct=case['belief']),
                         check_html=False)
    else:
        # 空信念提交同样必须被拒（belief_investor_send 是 blank=True），
        # 否则受托人的信念观测被静默丢弃
        yield SubmissionMustFail(BeliefElicit, {}, check_html=False)
        yield Submission(BeliefElicit,
                         dict(belief_investor_send=TRUSTEE_BELIEF),
                         check_html=False)


def decision_round(bot):
    """决策与结算。角色不同，走的页不同（投资者决策页 / 受托人决策页互斥）。"""
    case = CASES[bot.case]
    player = bot.player

    if player.role == C.INVESTOR_ROLE:
        yield Submission(InvestorDecision, dict(send_amount=case['send']),
                         check_html=False)
        yield Results
        return

    # 受托人：等投资者决策完成后才轮到本页（DecisionWaitPage 由框架处理）
    max_return = C.MULTIPLIER * case['send']
    if max_return > 0:
        # 空提交必须被拒（return_amount 是 blank=True，wtforms 会静默放过 None）
        yield SubmissionMustFail(TrusteeDecision, {}, check_html=False)
        # 超过动态上限（但仍在字段静态 max=30 之内）→ 必须由
        # TrusteeDecision.error_message 的动态校验拦下
        yield SubmissionMustFail(
            TrusteeDecision, dict(return_amount=max_return + 1),
            check_html=False
        )
        yield Submission(TrusteeDecision,
                         dict(return_amount=case['returns']),
                         check_html=False)
    else:
        # x = 0：本页不渲染任何表单（get_form_fields 返回 []），
        # 而 must_fail 在无表单页面上必然抛极具误导性的
        # BotError: passed validation anyway，故必须跳过 must-fail。
        yield TrusteeDecision
    yield Results


def check_round(bot):
    """验证处理组分派、页面归属与结算正确性。

    在 play_round 末尾调用（oTree 6 无 validate_round 钩子）：生成器在最后一次
    yield 之后仍会被 runner 继续推进到 StopIteration，此时 ResultsWaitPage 的
    after_all_players_arrive 已执行完毕，可以安全读取最终字段值。
    """
    player = bot.player
    case = CASES[bot.case]
    spec = role_message_spec(player)

    # ---------- 前置条件 1：两个处理组因子有效且与配置逐值一致 ----------
    # 必须已由模块级 creating_session 降范式写入每个 Player（见
    # trust_game/__init__.py 的说明）。若该函数被误改回 Subsession 的类方法，
    # oTree 6 会静默跳过它，这两个字段恒为 NULL，依赖它们的页面分派逻辑
    # （谁发消息、谁看消息）会走错分支而假通过——所以先显式断言非 None。
    flags = {}
    for field in ('investor_sends_message', 'trustee_sends_message'):
        stored = player.field_maybe_none(field)
        if stored is None:
            raise ExpectError(
                f'{field} 为 None：creating_session 从未被调用，'
                '它必须是模块级函数（见 trust_game/__init__.py）'
            )
        # 与配置**逐值**比对，不能只做真值判断：None 与 False 在 if 下行为相同。
        expect(stored, player.session.config.get(field, False))
        flags[field] = stored

    # 分派依据必须由这两个因子算出，且**接收方与发送方是两个独立维度**
    # （不是互补）。这条断言拦的是把 receives_message 写成 `not sends_message`：
    # 那样双向组的两人都会看不到消息页、无沟通组反而会看到——四个 config
    # 仍然全部跑通，只有这条会失败。
    is_investor = player.role == C.INVESTOR_ROLE
    expect(sends_message(player), flags[spec['i_send_flag']])
    expect(receives_message(player),
           flags['trustee_sends_message'] if is_investor
           else flags['investor_sends_message'])
    expect(any_message(player),
           flags['investor_sends_message'] or flags['trustee_sends_message'])

    # ---------- 前置条件 2：分派到的页面确实属于本处理组 ----------
    # 外部证据：otree test 的输出里，各 config 出现的 Submit 页不同。此处再断言
    # 页面自身的 is_displayed 判定与两个因子一致——页面归属错了不会有别的报错。
    expect(MessageSend.is_displayed(player), sends_message(player))
    expect(MessageReveal.is_displayed(player), receives_message(player))
    expect(MessageWaitPage.is_displayed(player), any_message(player))

    # ---------- 前置条件 3：角色分配顺序 ----------
    # 规格第 12 节的实现约束：id_in_group = 1 必须是投资者。角色由 oTree 的
    # get_roles() 按 Constants.__dict__ 的插入序分配（otree/constants.py:54-63），
    # 故 C 中 INVESTOR_ROLE 必须先于 TRUSTEE_ROLE 定义。若两者被调换，
    # Group.investor / Group.trustee 两个属性会随角色名一起取反，结算与配对
    # 合并读到的是对方那一行——而按角色写的奖惩断言仍各自自洽，只有这条
    # 「角色 → id」映射断言会失败。断言的是映射本身，故顺序调换必然被拦下。
    expect(player.id_in_group, 1 if is_investor else 2)

    # ---------- 前置条件 4：理解检验的拦截与累计 ----------
    # 上面的 comprehension_round 先提交了一次错答案（必须被拒），再提交全对
    # （必须通过），故本题下该被试恰好作答 2 次：错的那次由 error_message 计入，
    # 对的那次由 before_next_page 计入。此断言同时钉住两件事：
    #   (a) error_message 内的一次自增**确实被 oTree 提交**（实测确认：把它改成
    #       不自增，本断言读到的就是 1，测试立刻失败），而非被静默回滚；
    #   (b) before_next_page 的终次自增没有丢失。
    # 任一机制失效，报告 5.5 / 7.3 的「无需按理解度剔除」就失去依据，故这里
    # 必须逐值断言，而不是断言 > 0。
    expect(player.comprehension_attempts, 2)

    # ---------- C1：本方消息字段的落库 / NULL 必须与「本方是否发送」一致 ----------
    if sends_message(player):
        # MessageSend 确实走过：消息文案已落库、强度已编码
        expect(expect_populated(player, spec['field']), spec['text'])
        expect(expect_populated(player, spec['strength']), spec['code'])
    else:
        # MessageSend 未展示：本方消息字段必须全程为 NULL
        expect(player.field_maybe_none(spec['field']), None)
        expect(player.field_maybe_none(spec['strength']), None)

    # 对方的消息字段只由对方那一行写入，本行必须为空
    expect(player.field_maybe_none(spec['others_field']), None)

    # ---------- C2：MessageReveal 必须展示「对方」的消息 ----------
    # vars_for_template 里的「我的角色 → 从对方行读哪个字段」映射若被写反，
    # 页面会渲染出错误的消息，而此前没有任何断言会失败。这里把页面**将要
    # 显示**的文本与对方**实际提交**的消息逐字比对，使映射方向可证伪：
    # 投资者必须看到受托人的 message_trustee，受托人必须看到投资者的
    # message_investor。两侧文案分属不同量表（互无交集），故读错字段、
    # 写反分支、乃至误读自己那一行，都会被这一条拦下。
    if receives_message(player):
        other = player.get_others_in_group()[0]
        expect(MessageReveal.vars_for_template(player)['message_from_other'],
               expect_populated(other, spec['others_field']))

    # ---------- 结算 ----------
    if is_investor:
        expect(expect_populated(player, 'send_amount'), case['send'])
        expect(player.belief_return_pct, case['belief'])
        if case['send'] == 0:
            # x = 0 → 一律不发奖金（规格第 7 节）。这是最有区分力的一格：
            # 旧规则下预测 0% ≤ 10 个百分点会照发 2 点。
            expect(player.belief_bonus, 0)
            expect(expect_populated(player, 'return_ratio'), 0.0)
            # 收益 = (10 - 0 + 0) + 0 = 10（恰好等于禀赋，不再高于禀赋）
            expect(expect_populated(player, 'payoff'), 10)
        elif bot.case == 'normal':
            # 预测 50%，实际比例 6/(3*5) = 40%，偏差恰好 10 个百分点
            # （边界内含等号）→ 得奖 2 点
            expect(player.belief_bonus, 2)
            expect(expect_populated(player, 'return_ratio'), 0.4)
            # 收益 = (10 - 5 + 6) + 2 = 13
            expect(expect_populated(player, 'payoff'), 13)
        else:
            # 预测 0%，实际比例 40%，偏差 40 个百分点 > 10 → 不得奖
            expect(player.belief_bonus, 0)
            expect(expect_populated(player, 'return_ratio'), 0.4)
            # 收益 = (10 - 5 + 6) + 0 = 11
            expect(expect_populated(player, 'payoff'), 11)
    else:
        # 受托人永远拿不到信念奖金
        expect(player.belief_bonus, 0)
        expect(expect_populated(player, 'belief_investor_send'), TRUSTEE_BELIEF)
        # send_amount 是投资者那一行的字段：受托人自己的 Player 行从未写过它，
        # 只有 group.investor 上才有值（用 expect_populated 判空可暴露这一点）
        expect(expect_populated(player.group.investor, 'send_amount'),
               case['send'])
        expect(expect_populated(player, 'return_amount'), case['returns'])
        if case['send'] == 0:
            expect(expect_populated(player, 'return_ratio'), 0.0)
            # 收益 = 3*0 - 0 = 0
            expect(expect_populated(player, 'payoff'), 0)
        else:
            expect(expect_populated(player, 'return_ratio'), 0.4)
            # 收益 = 3*5 - 6 = 9
            expect(expect_populated(player, 'payoff'), 9)

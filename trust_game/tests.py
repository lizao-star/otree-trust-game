from otree.api import *
from otree.bots.bot import ExpectError
from . import *

# 三个 bot case。**数值不随处理组变化**，四个处理组跑同一套数值与断言，
# 每个组都覆盖「得奖 / 不得奖」两条分支。
#
# 信念部分有三组数值：
#   investor_*     投资者预测返还比例（百分比，容差 10 个百分点）
#   trustee_send_* 受托人预测投资者送出点数（点数，容差 2 点）
#   second_*       受托人的二阶信念，即「投资者认为他会返还的比例」。
#                  ⚠️ 计奖基准是**投资者报告的一阶信念**（按受托人的抽中时点
#                  对齐），不是实际返还比例——二阶信念的真值是「对方相信
#                  什么」。若实现改回按实际比例评分，normal 的
#                  second_bonus_before 会从 0 变成 2，本表立刻失败。
# 每个 case 的 before/after 取值刻意相反，使「计奖时点」真正影响总奖金。
CASES = {
    # 送出 5 → 受托人实际收到 15、返还 6 → 比例 40%。
    # 投资者：0%（差 40）与 50%（差 10，边界）→ 抽中前不得奖、后得奖。
    # 受托人一阶：8（差 3）与 5（差 0）→ 前不得奖、后得奖。
    # 二阶：投资者两次报告为 0 / 50；受托人报 30 / 40。
    #   before：基准 0，|30-0|=30 → 0；after：基准 50，|40-50|=10（边界）→ 2。
    # 受托人总奖金：before = 0+0 = 0；after = 2+2 = 4。
    'normal': dict(
        send=5, returns=6,
        belief_before=0, belief=50,
        bonus_before=0, bonus_after=2,
        trustee_belief_before=8, trustee_belief=5,
        send_bonus_before=0, send_bonus_after=2,
        second_order_before=30, second_order=40,
        second_bonus_before=0, second_bonus_after=2,
        trustee_bonus_before=0, trustee_bonus_after=4,
    ),
    # 与上一条正好相反：抽中前一次得奖、后一次不得奖。
    # 二阶：投资者两次报告为 50 / 0；受托人报 40 / 55。
    #   before：基准 50，|40-50|=10（边界）→ 2；after：基准 0，|55-0|=55 → 0。
    # 若计奖时点被写死为 after，本条的断言会失败。
    'miss_belief': dict(
        send=5, returns=6,
        belief_before=50, belief=0,
        bonus_before=2, bonus_after=0,
        trustee_belief_before=5, trustee_belief=8,
        send_bonus_before=2, send_bonus_after=0,
        second_order_before=40, second_order=55,
        second_bonus_before=2, second_bonus_after=0,
        trustee_bonus_before=4, trustee_bonus_after=0,
    ),
    # x = 0 的退化路径：受托人无可返还金额、决策页不渲染表单。
    # 投资者奖金一律 0；受托人一阶预测 0 点，误差 0 → 两次都得 2 点
    # （x=0 不影响受托人一阶奖金）；二阶基准（投资者的报告）在 x=0 时
    # 缺乏激励支撑、不可靠 → 二阶奖金两次都为 0。
    'zero_send': dict(
        send=0, returns=0,
        belief_before=0, belief=0,
        bonus_before=0, bonus_after=0,
        trustee_belief_before=0, trustee_belief=0,
        send_bonus_before=2, send_bonus_after=2,
        second_order_before=0, second_order=0,
        second_bonus_before=0, second_bonus_after=0,
        trustee_bonus_before=2, trustee_bonus_after=2,
    ),
}


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
        yield from pledge_round(self)
        yield from belief_before_round(self)
        yield from message_round(self)
        yield from belief_round(self)
        yield from decision_round(self)
        yield from post_round(self)
        check_round(self)


def pledge_round(bot):
    """诚信承诺页：未勾选必须被拒，勾选后才能进入信念页。

    若只提交一次 True，那么 error_message 里的拦截整个删掉也不会失败——
    而「未勾选不得继续」正是这页存在的全部意义。
    """
    yield SubmissionMustFail(Pledge, {}, check_html=False)
    yield Submission(Pledge, dict(pledge_honesty=True), check_html=False)


def comprehension_round(bot):
    """理解检验：先提交一题错的（必须被拒），再提交全对的（必须通过）。

    规格 §14.1 要求「答错时 SubmissionMustFail，答对后 comprehension_attempts
    正确累计」。缺了前半句，「全对才能继续」这道门就没被验过：bot 永远提交正确
    答案，即使拦截逻辑整个失效、计数器不再落库，测试也照样全绿——而报告 5.5 /
    7.3 的预注册决定（「无需按理解度剔除」）正建立在这道门有效的前提上。
    """
    yield SubmissionMustFail(
        ComprehensionCheck,
        dict(comp_q1=0, comp_q2=12, comp_q3=12, comp_q4=0),  # 只有问题 1 答错
        error_fields=['comp_q1'],                   # 且错误必须落在该字段上
        check_html=False,
    )
    yield Submission(ComprehensionCheck,
                     dict(comp_q1=10, comp_q2=12, comp_q3=12, comp_q4=0),
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


def belief_before_round(bot):
    """决策之前的信念页。现在所有玩家都会看到这一页。

    沟通组的这次报告是真实的事前判断；无沟通组读到的是「假如可以交换消息」
    的假设性问题，同样提交数值，但由 belief_before_hypothetical 标记为基线。
    """
    case = CASES[bot.case]
    player = bot.player

    # 与 message_round 同理：判断要在第一次 yield 之前读完，避免
    # DetachedInstanceError（生成器跨请求恢复时 player 已脱离会话）。
    role = player.role

    if role == C.INVESTOR_ROLE:
        yield Submission(BeliefBefore,
                         dict(belief_return_pct_before=case['belief_before']),
                         check_html=False)
    else:
        # 两个字段都是 blank=True，空提交必须被拒；否则拦截被删掉也不会失败。
        yield SubmissionMustFail(BeliefBefore, {}, check_html=False)
        yield Submission(
            BeliefBefore,
            dict(
                belief_investor_send_before=case['trustee_belief_before'],
                second_order_belief_return_pct_before=case['second_order_before'],
            ),
            check_html=False,
        )


def belief_round(bot):
    """决策之后的信念页。受托人有两个问题，空提交都必须被拒。"""
    case = CASES[bot.case]
    if bot.player.role == C.INVESTOR_ROLE:
        yield Submission(BeliefElicit,
                         dict(belief_return_pct=case['belief']),
                         check_html=False)
    else:
        yield SubmissionMustFail(BeliefElicit, {}, check_html=False)
        yield Submission(
            BeliefElicit,
            dict(
                belief_investor_send=case['trustee_belief'],
                second_order_belief_return_pct=case['second_order'],
            ),
            check_html=False,
        )


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


def post_round(bot):
    """事后情绪与操纵检查：空提交必须先被拒，再按角色/条件提交。

    本页现在对**所有**玩家显示：投资者答不满强度（+收到承诺时的可信度），
    受托人答对甲方送出额的不满（+收到意向时的可信度）。
    三个作答字段都是 blank=True，若只有一次正常提交，error_message 里的
    逐字段拦截被删掉也不会失败——故必须先来一次空提交。
    """
    player = bot.player
    role = player.role
    receives = receives_message(player)

    yield SubmissionMustFail(PostRound, {}, check_html=False)

    if role == C.INVESTOR_ROLE:
        values = dict(anger_intensity=3)
        if receives:
            values['perceived_message'] = 4
    else:
        values = dict(trustee_anger_intensity=2)
        if receives:
            values['perceived_intent'] = 4
    yield Submission(PostRound, values, check_html=False)


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
        # trust_random 没有固定键（条件在配对层随机），此处不能拿配置做基准。
        if not player.session.config.get('randomize_cells', False):
            expect(stored, player.session.config.get(field, False))
        flags[field] = stored

    # 四格标签与随机化标记必须与两个因子自洽；同组两人条件必须一致
    # （条件在配对层分配，若按人分配，同一局的两名被试会看到不同的沟通结构）。
    expect(player.pair_cell,
           cell_name(flags['investor_sends_message'],
                     flags['trustee_sends_message']))
    expect(player.role_randomized,
           bool(player.session.config.get('randomize_cells', False)))
    for other in player.get_others_in_group():
        expect(other.field_maybe_none('investor_sends_message'),
               flags['investor_sends_message'])
        expect(other.field_maybe_none('trustee_sends_message'),
               flags['trustee_sends_message'])
        expect(other.pair_cell, player.pair_cell)

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
    # BeliefBefore 现在对所有玩家显示：无沟通组也要填一次假设性基线。
    expect(BeliefBefore.is_displayed(player), True)

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

    # ---------- 前置条件 5：诚信承诺确实勾选 ----------
    expect(player.pledge_honesty, True)

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

    # ---------- C1.5：承诺派生编码 ----------
    # 有承诺消息时，两行都必须拿到同一个 0/1 编码；无消息时两行都必须为 NULL。
    # 若把编码写成「只写受托人行」，投资者行的分组分析会读到空值却不报错。
    if flags['trustee_sends_message']:
        expected_promise = content.is_promise(C.TRUSTEE_MESSAGES[1][1])
        expect(expect_populated(player, 'promise'), expected_promise)
    else:
        expect(player.field_maybe_none('promise'), None)

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
    has_message = flags['investor_sends_message'] or flags['trustee_sends_message']

    # 决策前的那次报告现在所有人都要填；它是否为假设性基线只取决于本组
    # 有没有消息环节，与被试自己是否发送无关。
    expect(expect_populated(player, 'belief_before_hypothetical'),
           not has_message)

    if is_investor:
        expect(expect_populated(player, 'send_amount'), case['send'])
        expect(expect_populated(player, 'belief_return_pct'), case['belief'])
        expect(expect_populated(player, 'belief_return_pct_before'),
               case['belief_before'])
        # 二阶信念只出现在受托人页面
        expect(player.field_maybe_none('second_order_belief_return_pct_before'),
               None)
        expect(player.field_maybe_none('second_order_belief_return_pct'), None)

        # 计奖时点由 creating_session 写入，不来自被试输入。
        # 无沟通组只有决策后那次真实报告计奖，必须固定为 after。
        timing = expect_populated(player, 'belief_paid_timing')
        if has_message:
            expect(timing in (payoffs.BELIEF_TIMING_BEFORE,
                              payoffs.BELIEF_TIMING_AFTER), True)
        else:
            expect(timing, payoffs.BELIEF_TIMING_AFTER)

        # 奖金必须按抽中时点对应的那次判断计算。两个 case 的两次判断取值相反，
        # 因此「计奖时点被写死」或「取值取错字段」都会让其中一格失败。
        expected_bonus = (
            case['bonus_before'] if timing == payoffs.BELIEF_TIMING_BEFORE
            else case['bonus_after']
        )
        expect(player.belief_bonus, expected_bonus)

        if case['send'] == 0:
            # x = 0 → 投资者的比例奖金一律为 0
            expect(expect_populated(player, 'return_ratio'), 0.0)
            expect(expect_populated(player, 'payoff'),
                   payoffs.investor_payoff(0, 0))
        else:
            # 实际比例 6/(3*5) = 40%，与两格预测的偏差分别为 10 / 40 个百分点
            expect(expect_populated(player, 'return_ratio'), 0.4)
            expect(expect_populated(player, 'payoff'),
                   payoffs.investor_payoff(case['send'], case['returns'])
                   + expected_bonus)
    else:
        # 受托人一阶与二阶两次报告都必须有值（无沟通组那次为假设性基线）
        expect(expect_populated(player, 'belief_investor_send'),
               case['trustee_belief'])
        expect(expect_populated(player, 'belief_investor_send_before'),
               case['trustee_belief_before'])
        expect(expect_populated(player, 'second_order_belief_return_pct'),
               case['second_order'])
        expect(expect_populated(player, 'second_order_belief_return_pct_before'),
               case['second_order_before'])

        timing = expect_populated(player, 'belief_paid_timing')
        if has_message:
            expect(timing in (payoffs.BELIEF_TIMING_BEFORE,
                              payoffs.BELIEF_TIMING_AFTER), True)
        else:
            expect(timing, payoffs.BELIEF_TIMING_AFTER)

        expected_send_bonus = (
            case['send_bonus_before']
            if timing == payoffs.BELIEF_TIMING_BEFORE
            else case['send_bonus_after']
        )
        expected_second_bonus = (
            case['second_bonus_before']
            if timing == payoffs.BELIEF_TIMING_BEFORE
            else case['second_bonus_after']
        )
        expected_bonus = expected_send_bonus + expected_second_bonus
        expect(player.belief_bonus, expected_bonus)

        # send_amount 是投资者那一行的字段：受托人自己的 Player 行从未写过它，
        # 只有 group.investor 上才有值（用 expect_populated 判空可暴露这一点）
        expect(expect_populated(player.group.investor, 'send_amount'),
               case['send'])
        expect(expect_populated(player, 'return_amount'), case['returns'])
        if case['send'] == 0:
            expect(expect_populated(player, 'return_ratio'), 0.0)
            # 收益 = 3*0 - 0 + 一阶奖金 2 = 2（二阶比例奖金为 0）
            expect(expect_populated(player, 'payoff'),
                   payoffs.trustee_payoff(0, 0) + expected_bonus)
        else:
            expect(expect_populated(player, 'return_ratio'), 0.4)
            expect(expect_populated(player, 'payoff'),
                   payoffs.trustee_payoff(case['send'], case['returns'])
                   + expected_bonus)

    # ---------- 事后情绪与操纵检查 ----------
    # PostRound 现在对所有玩家显示；字段集合按「角色 + 是否收到消息」分派，
    # 故两侧都要钉：该出现的字段必须有值（空提交已被 post_round 验过必须
    # 被拒），不该出现的字段必须为 NULL。若把 perceived_message 与
    # perceived_intent 写反，两个单向组的页面仍会正常渲染、bot 也照样提交
    # ——只有这里的「谁看到哪个字段」断言会失败。
    expect(PostRound.is_displayed(player), True)
    if is_investor:
        expect(expect_populated(player, 'anger_intensity'), 3)
        expect(player.field_maybe_none('trustee_anger_intensity'), None)
        if receives_message(player):
            expect(expect_populated(player, 'perceived_message'), 4)
        else:
            expect(player.field_maybe_none('perceived_message'), None)
        expect(player.field_maybe_none('perceived_intent'), None)
    else:
        expect(expect_populated(player, 'trustee_anger_intensity'), 2)
        expect(player.field_maybe_none('anger_intensity'), None)
        if receives_message(player):
            expect(expect_populated(player, 'perceived_intent'), 4)
        else:
            expect(player.field_maybe_none('perceived_intent'), None)
        expect(player.field_maybe_none('perceived_message'), None)

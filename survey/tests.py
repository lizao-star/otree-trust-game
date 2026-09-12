from otree.api import *
from otree.bots.bot import ExpectError
from . import *


def expect_populated(player, field):
    """前置条件断言：可空字段必须已有值，才谈得上对其值作断言。

    直接读取未赋值的字段在 oTree 6 中会抛 NullFieldError
    （otree/database.py:639：访问 NULL 字段一律视为错误），故读取可空字段
    一律经 field_maybe_none()。注意判空用的是 `is None` 而非真值判断：
    本文件专门用 0 / False 作为输入，若写成 `if not value` 就会把
    「0 被静默丢弃」这一缺陷误判为「字段有值」。

    与 trust_game/tests.py 中的同名助手一致；此处独立定义，使 survey 的
    bot 测试不依赖其他 app 的测试模块（survey 是独立 app）。
    """
    value = player.field_maybe_none(field)
    if value is None:
        raise ExpectError(
            f'{field} 为 None：前置条件不成立（本用例下该字段本应有值），'
            '无法继续对其值作断言'
        )
    return value


# 两个 case 的输入在**每一处**都取互补值，使「只处理了一部分输入」的缺陷
# 无法靠某一路数据蒙混过关：
#   risk_rows 互为逐位补集（10101 / 01010）：任何「只对部分行求和」的实现
#   都会让两个 case 同时失败；
#   dictator_give 取 0 与 4：0 能暴露「0 被当作空值丢弃」这一经典缺陷，
#   4 则让「10 - s」与「10 + s」这类映射错误可证伪（s = 0 时二者同值，
#   只用 0 做输入无法区分）；
#   general_trust 与 prior_experience 覆盖 0/False 与 6/True 两端，
#   确保 False 与 0 被真正写入，而不是被静默当作缺失值。
CASES = {
    'send_zero': dict(
        risk_rows=dict(risk_row1=1, risk_row2=0, risk_row3=1,
                       risk_row4=0, risk_row5=1),
        dictator_give=0,
        general_trust=0,
        gender='女', age=19, grade='大一', major='心理学',
        econ_courses=0, prior_experience=False,
    ),
    'send_four': dict(
        risk_rows=dict(risk_row1=0, risk_row2=1, risk_row3=0,
                       risk_row4=1, risk_row5=0),
        dictator_give=4,
        general_trust=6,
        gender='男', age=22, grade='大三', major='经济学',
        econ_courses=3, prior_experience=True,
    ),
}


class PlayerBot(Bot):
    """survey 的 bot：逐页提交并核对落库值。

    断言统一由 check_round 承担，在 play_round 末尾显式调用——oTree 6 的
    PlayerBot 没有任何形如 validate_round 的框架钩子（全包搜索零结果），
    断言写在那里等于死代码，测试会通过但什么都没验证。生成器在最后一次
    yield 之后仍会被 runner 推进到 StopIteration，故此时读取最终字段值是安全的。
    """

    cases = list(CASES)

    def play_round(self):
        data = CASES[self.case]

        # survey 的独裁者博弈收益是**追加**到 participant.payoff 上的
        # （otree/models/player.py：payoff setter 把差值累加到 participant），
        # 故此处先记录基准值，check_round 里用**增量**断言 survey 自身的贡献。
        # 不对 participant 总额作任何假设：它已经含 trust_game 发出的收益。
        participant_payoff_before = self.player.participant.payoff

        # 空提交必须被拒，且**每一行**都必须报错：risk_choice 是对这 5 行求和
        # 得到的 blank=True 派生字段，只要有一行可空，sum 就会抛 TypeError
        # （HTTP 500）。error_fields 由框架逐字比对实际报错字段集合，
        # 缺一行或某一行未报错都会失败——这正是「五个字段真的必填」的证据。
        yield SubmissionMustFail(
            RiskPreference, {},
            check_html=False,
            error_fields=list(data['risk_rows']),
        )
        yield Submission(RiskPreference, data['risk_rows'], check_html=False)

        # dictator_give 必填：否则 before_next_page 的 10 - s 会以 TypeError 崩
        yield SubmissionMustFail(
            DictatorGame, {}, check_html=False, error_fields=['dictator_give'])
        yield Submission(DictatorGame,
                         dict(dictator_give=data['dictator_give']),
                         check_html=False)

        # 空提交必须被拒：本页只有 general_trust 一个字段，若它变成可空
        # （例如加上 blank=True —— 那会同时去掉 InputRequired 与 oTree 的
        # Boolean/必填拦截），空提交会静默存入 NULL，整套测试仍全绿，
        # 直到分析阶段读这个字段才炸。error_fields 精确比对保证报错的就是它。
        yield SubmissionMustFail(GeneralTrust, {},
                                 check_html=False,
                                 error_fields=['general_trust'])
        yield Submission(GeneralTrust,
                         dict(general_trust=data['general_trust']),
                         check_html=False)

        # 空提交必须被拒，含 prior_experience：BooleanField 未选择时 field.data
        # 为 None，由 oTree 在 ModelForm.validate 中统一拦截（otree/forms/forms.py:311）。
        # 若该拦截失效，NULL 会落库并在下游读取时炸成 HTTP 500。
        yield SubmissionMustFail(
            Demographics, {},
            check_html=False,
            error_fields=['gender', 'age', 'grade', 'major',
                          'econ_courses', 'prior_experience'],
        )
        # 本页刻意用 check_html=True：由框架核对渲染出的 HTML 中确实存在
        # name="prior_experience"（及本页其余）表单控件，即对
        # 「BooleanField + RadioSelect 能否正确渲染」的外部验证。
        # 其余提交沿用项目惯例 check_html=False。
        yield Submission(Demographics, dict(
            gender=data['gender'], age=data['age'], grade=data['grade'],
            major=data['major'], econ_courses=data['econ_courses'],
            prior_experience=data['prior_experience'],
        ), check_html=True)

        check_round(self, data, participant_payoff_before)


def check_round(bot, data, participant_payoff_before):
    """核对页面真的写入了正确的值，而不只是「页面提交成功」。"""
    player = bot.player

    # ---------- 前置条件 1：派生字段 risk_choice 已由 before_next_page 写入 ----------
    # risk_choice 是 blank=True（= nullable）。先断言非 None 再断言取值：
    # 直接读取 None 字段会抛 NullFieldError，看不出「sum 拿到 None」这一根因。
    risk_choice = expect_populated(player, 'risk_choice')
    expect(risk_choice, sum(data['risk_rows'].values()))

    # ---------- 前置条件 2：各页提交的原始值确实落库 ----------
    expect(expect_populated(player, 'dictator_give'), data['dictator_give'])
    expect(expect_populated(player, 'general_trust'), data['general_trust'])
    expect(expect_populated(player, 'gender'), data['gender'])
    expect(expect_populated(player, 'age'), data['age'])
    expect(expect_populated(player, 'grade'), data['grade'])
    expect(expect_populated(player, 'major'), data['major'])
    expect(expect_populated(player, 'econ_courses'), data['econ_courses'])
    # 0 == False 在 Python 中为真，故 expect(stored, False) 无法区分
    # 「落库为 False」与「落库为 0 / 空串」；再用类型断言把两者分开。
    stored_prior = expect_populated(player, 'prior_experience')
    expect(stored_prior, data['prior_experience'])
    expect(isinstance(stored_prior, bool), True)

    # ---------- 前置条件 3：收益确实被 before_next_page 赋值 ----------
    # 页面提交成功不等于收益被写入，故断言结算后的具体数值。
    expected_payoff = cu(C.DICTATOR_ENDOWMENT - data['dictator_give'])
    expect(expect_populated(player, 'payoff'), expected_payoff)
    # survey 自身的贡献 = participant.payoff 的增量，恰好是 10 - s；
    # 用它而不是总额，因为 participant.payoff 还含 trust_game 的收益。
    expect(player.participant.payoff,
           participant_payoff_before + expected_payoff)

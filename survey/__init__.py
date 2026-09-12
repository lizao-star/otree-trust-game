from otree.api import *

doc = """
个体测量与人口学问卷。独裁者博弈的收益计入总报酬（规格第 10 节）。
"""


def risk_row_label(row):
    """由 C.RISK_ROWS 的一行 (行号, 确定金额) 生成该行的问题文案。

    行号、确定金额、彩票奖金全部取自 C 里的常量（唯一真值来源）：文案若与
    参数各存一份，改参数而不改文案时被试读到的选项就是错的，且不会有任何
    测试或页面报错（同 fbde6eb「文案与常量同源」的教训）。
    两处 50% 与「0 点」不随行变化，是彩票本身固定的构成，故直接写在文案里。
    """
    index, certain = row
    return (
        f'第 {index} 行：确定获得 {certain} 点 或 '
        f'50% 概率获得 {C.RISK_LOTTERY} 点、50% 概率获得 0 点'
    )


class C(BaseConstants):
    NAME_IN_URL = 'survey'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    DICTATOR_ENDOWMENT = 10

    # 风险偏好：5 行菜单，每行在确定金额与固定彩票间二选一。
    # 每行是 (行号, 确定金额)；彩票在所有行都相同（见 RISK_LOTTERY）。
    # 这两处是风险菜单数字的**唯一**存放处：面向被试的行文案由
    # risk_row_label() 据此生成，不再另抄一份（改数字文案即随之改变）。
    RISK_ROWS = [(1, 3), (2, 4), (3, 5), (4, 6), (5, 7)]
    RISK_LOTTERY = 10

    # 选项编码 0 = 选择彩票（更耐受风险），1 = 选择确定金额（更规避风险）。
    # 5 行共用同一组选项，只此一份，避免逐行抄写时某一行被改歪。
    RISK_CHOICES = [(1, '选择确定金额'), (0, '选择彩票')]

    GENDERS = ['男', '女', '不愿透露']
    GRADES = ['大一', '大二', '大三', '大四', '研究生及以上']


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    # 风险偏好：每行 1 = 选确定金额，0 = 选彩票；risk_choice 为选确定金额的行数（0-5），
    # 数值越大表示越规避风险
    risk_row1 = models.IntegerField(
        choices=C.RISK_CHOICES, widget=widgets.RadioSelectHorizontal,
        label=risk_row_label(C.RISK_ROWS[0]))
    risk_row2 = models.IntegerField(
        choices=C.RISK_CHOICES, widget=widgets.RadioSelectHorizontal,
        label=risk_row_label(C.RISK_ROWS[1]))
    risk_row3 = models.IntegerField(
        choices=C.RISK_CHOICES, widget=widgets.RadioSelectHorizontal,
        label=risk_row_label(C.RISK_ROWS[2]))
    risk_row4 = models.IntegerField(
        choices=C.RISK_CHOICES, widget=widgets.RadioSelectHorizontal,
        label=risk_row_label(C.RISK_ROWS[3]))
    risk_row5 = models.IntegerField(
        choices=C.RISK_CHOICES, widget=widgets.RadioSelectHorizontal,
        label=risk_row_label(C.RISK_ROWS[4]))
    # risk_choice 是 blank=True（即 nullable），由 RiskPreference.before_next_page
    # 对上面 5 行求和写入。求和不会碰到 None 的前提是这 5 行**各自必填**
    # （无 blank=True，oTree 因此为每行加 InputRequired）：若某行可空，
    # 空提交时 sum 会抛 TypeError（HTTP 500）。
    # survey/tests.py 用 SubmissionMustFail(..., error_fields=...) 逐行核对该前提。
    risk_choice = models.IntegerField(blank=True, min=0, max=5)

    # 上限与上限的文案都取自 C.DICTATOR_ENDOWMENT（唯一真值来源）：
    # 若文案另写一个「10」，改禀赋时被试读到的区间会与实际约束不符。
    dictator_give = models.IntegerField(
        min=0, max=C.DICTATOR_ENDOWMENT,
        label=f'请决定你送给对方的点数（0-{C.DICTATOR_ENDOWMENT}）：')

    # !! choices 不可省略 !! oTree 6 的 get_choices_field（otree/forms/forms.py:255）
    # 对「带 RadioSelect/RadioSelectHorizontal 控件但无 choices」的字段直接抛
    # Exception('Field uses a radio/select widget but no choices are defined')：
    # 该页渲染即 HTTP 500（本任务实测）。取值 0-10 的约束由这个 choices 集合
    # 本身承担（选中集合外的值报「不是有效的选择」）；min/max 只在无 choices
    # 时才会变成 NumberRange 校验，此处仅作范围声明。
    general_trust = models.IntegerField(
        choices=list(range(0, 11)), min=0, max=10,
        widget=widgets.RadioSelectHorizontal,
        label='总体来说，你认为大多数人是可以信任的（0=完全不同意，10=完全同意）')

    gender = models.StringField(choices=C.GENDERS, widget=widgets.RadioSelect,
                                label='你的性别：')
    age = models.IntegerField(min=16, max=60, label='你的年龄：')
    grade = models.StringField(choices=C.GRADES, widget=widgets.RadioSelect,
                               label='你的年级：')
    major = models.StringField(label='你的专业：', max_length=100)
    econ_courses = models.IntegerField(
        min=0, max=30, label='你已修读过的经济学课程数量：')
    # 不加 blank=True：未作答时 oTree 会在 ModelForm.validate
    # （otree/forms/forms.py:311）按 Boolean 类型拦截 field.data is None 的情况，
    # 报框架自带的中文「该字段是必填字段。」（zh_Hans 目录有该 msgid），
    # 故无需自写 error_message；一旦加上 blank=True，该校验会被跳过，
    # NULL 落库后下游读取即抛 NullFieldError。survey/tests.py 断言空提交被拒。
    prior_experience = models.BooleanField(
        choices=[(True, '是'), (False, '否')],
        widget=widgets.RadioSelect, label='你此前是否参加过类似的经济学实验？')


# PAGES

class RiskPreference(Page):
    form_model = 'player'
    form_fields = ['risk_row1', 'risk_row2', 'risk_row3',
                   'risk_row4', 'risk_row5']

    @staticmethod
    def before_next_page(player, timeout_happened):
        player.risk_choice = sum([
            player.risk_row1, player.risk_row2, player.risk_row3,
            player.risk_row4, player.risk_row5,
        ])


class DictatorGame(Page):
    form_model = 'player'
    form_fields = ['dictator_give']

    @staticmethod
    def before_next_page(player, timeout_happened):
        # 收益 = 禀赋 − 送出额，计入 participant.payoff
        player.payoff = cu(C.DICTATOR_ENDOWMENT - player.dictator_give)


class GeneralTrust(Page):
    form_model = 'player'
    form_fields = ['general_trust']


class Demographics(Page):
    form_model = 'player'
    form_fields = ['gender', 'age', 'grade', 'major',
                   'econ_courses', 'prior_experience']


page_sequence = [RiskPreference, DictatorGame, GeneralTrust, Demographics]

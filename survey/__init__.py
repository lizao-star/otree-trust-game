from otree.api import *

doc = """
个体测量与人口学问卷。独裁者博弈的收益计入总报酬（规格第 10 节）。
"""


class C(BaseConstants):
    NAME_IN_URL = 'survey'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    DICTATOR_ENDOWMENT = 10

    # 风险偏好：5 行菜单，每行在确定金额与固定彩票间二选一。
    # 选项编码 0 = 选择彩票（更耐受风险），1 = 选择确定金额（更规避风险）。
    RISK_ROWS = [
        ('第 1 行：确定获得 3 点 或 50% 概率获得 10 点、50% 概率获得 0 点', 3, 10),
        ('第 2 行：确定获得 4 点 或 50% 概率获得 10 点、50% 概率获得 0 点', 4, 10),
        ('第 3 行：确定获得 5 点 或 50% 概率获得 10 点、50% 概率获得 0 点', 5, 10),
        ('第 4 行：确定获得 6 点 或 50% 概率获得 10 点、50% 概率获得 0 点', 6, 10),
        ('第 5 行：确定获得 7 点 或 50% 概率获得 10 点、50% 概率获得 0 点', 7, 10),
    ]

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
        choices=[(1, '选择确定金额'), (0, '选择彩票')],
        widget=widgets.RadioSelectHorizontal, label=C.RISK_ROWS[0][0])
    risk_row2 = models.IntegerField(
        choices=[(1, '选择确定金额'), (0, '选择彩票')],
        widget=widgets.RadioSelectHorizontal, label=C.RISK_ROWS[1][0])
    risk_row3 = models.IntegerField(
        choices=[(1, '选择确定金额'), (0, '选择彩票')],
        widget=widgets.RadioSelectHorizontal, label=C.RISK_ROWS[2][0])
    risk_row4 = models.IntegerField(
        choices=[(1, '选择确定金额'), (0, '选择彩票')],
        widget=widgets.RadioSelectHorizontal, label=C.RISK_ROWS[3][0])
    risk_row5 = models.IntegerField(
        choices=[(1, '选择确定金额'), (0, '选择彩票')],
        widget=widgets.RadioSelectHorizontal, label=C.RISK_ROWS[4][0])
    # risk_choice 是 blank=True（即 nullable），由 RiskPreference.before_next_page
    # 对上面 5 行求和写入。求和不会碰到 None 的前提是这 5 行**各自必填**
    # （无 blank=True，oTree 因此为每行加 InputRequired）：若某行可空，
    # 空提交时 sum 会抛 TypeError（HTTP 500）。
    # survey/tests.py 用 SubmissionMustFail(..., error_fields=...) 逐行核对该前提。
    risk_choice = models.IntegerField(blank=True, min=0, max=5)

    dictator_give = models.IntegerField(
        min=0, max=C.DICTATOR_ENDOWMENT,
        label='请决定你送给对方的点数（0-10）：')

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

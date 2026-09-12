from otree.api import *
from . import *


class PlayerBot(Bot):
    """基线组（communication=False）的完整流程测试。"""

    def play_round(self):
        # Introduction 无表单字段，但仍是需要提交的普通页面
        # （oTree 只自动处理 WaitPage），故必须先行 yield。
        yield Submission(Introduction, {}, check_html=False)
        yield Submission(ComprehensionCheck,
                         dict(comp_q1=10, comp_q2=12, comp_q3=12),
                         check_html=False)
        if self.player.role == C.INVESTOR_ROLE:
            yield Submission(BeliefElicit, dict(belief_return_pct=50),
                             check_html=False)
            yield Submission(InvestorDecision, dict(send_amount=5),
                             check_html=False)
        else:
            yield Submission(BeliefElicit, dict(belief_investor_send=5),
                             check_html=False)
        if self.player.role == C.TRUSTEE_ROLE:
            yield Submission(TrusteeDecision, dict(return_amount=6),
                             check_html=False)
        yield Results

        # oTree 6 的 PlayerBot 只有 play_round 一个钩子，没有 validate_round
        # （该名称在 oTree 6.0.15 中不存在）。因此断言必须在这里显式调用，
        # 写在生成器里才会真正执行；否则等于死代码，测试会假通过。
        # 生成器在最后一次 yield 之后仍会被 runner 继续推进直到 StopIteration，
        # 此时 ResultsWaitPage 已完成结算，可以安全读取最终字段值。
        self.validate_round()

    def validate_round(self):
        from trust_game import has_communication
        expect(has_communication(self.player), False)

        if self.player.role == C.INVESTOR_ROLE:
            expect(self.player.send_amount, 5)
            # 预测 50%，实际比例 6/(3*5) = 40%，偏差恰好 10 个百分点（边界内含等号）→ 得奖 2 点
            expect(self.player.belief_bonus, 2)
            # 收益 = (10 - 5 + 6) + 2 = 13
            expect(self.player.payoff, 13)
            # 基线组不应有任何消息内容。
            # oTree 6 中直接读取 null 字段会抛 TypeError（NullFieldError），
            # 读取可空字段必须用 field_maybe_none()。
            expect(self.player.field_maybe_none('message_investor'), None)
            expect(self.player.field_maybe_none('investor_message_strength'), None)
        else:
            expect(self.player.return_amount, 6)
            # 收益 = 3*5 - 6 = 9
            expect(self.player.payoff, 9)
            expect(self.player.field_maybe_none('message_trustee'), None)
            expect(self.player.field_maybe_none('promise_strength'), None)

# API 文档

本文件描述实验代码的对外接口：会话配置键、模型字段、页面行为与纯函数。
所有字段名、页面名与常量值与 `trust_game/`、`settings.py` 中的实现一一对应；
报告（`实验设计与实现报告.tex`）第 6 节与附录 B 使用同一套名称。

---

## 1. 会话配置（`settings.py`）

### 1.1 配置键

| 键 | 类型 | 默认 | 含义 |
| --- | --- | --- | --- |
| `name` | str | — | config 名，`otree test` 的参数 |
| `display_name` | str | — | 管理页显示名，不得重复 |
| `app_sequence` | list | — | `['trust_game', 'survey']` |
| `num_demo_participants` | int | 8 | 演示/默认人数，须为偶数 |
| `investor_sends_message` | bool | False | A 能否发意向消息（固定条件配置） |
| `trustee_sends_message` | bool | False | B 能否发承诺消息（固定条件配置） |
| `randomize_cells` | bool | False | 条件与角色在配对层随机（`trust_random`） |
| `use_browser_bots` | bool | False | **仅演示配置**可为 True；真实配置必须缺键或 False |

### 1.2 已注册配置

| config | 类型 | 条件来源 |
| --- | --- | --- |
| `trust_none` | 固定 | 两个键均为 False |
| `trust_b_to_a` | 固定 | trustee=True, investor=False |
| `trust_a_to_b` | 固定 | investor=True, trustee=False |
| `trust_both` | 固定 | 两个键均为 True |
| `trust_random` | 随机 | `randomize_cells=True`，不携带固定键 |
| `trust_none_bots` 等 4 个 | 演示 | 与对应真实 config 两个键逐值相同 |
| `trust_random_bots` | 演示 | `randomize_cells=True` |

### 1.3 报酬默认值（`SESSION_CONFIG_DEFAULTS`）

| 键 | 值 |
| --- | --- |
| `real_world_currency_per_point` | 1.00 |
| `participation_fee` | 20.00 |

---

## 2. 常量（`trust_game.C`）

| 常量 | 值 | 说明 |
| --- | --- | --- |
| `NAME_IN_URL` | `'trust_game'` | app 名 |
| `PLAYERS_PER_GROUP` | 2 | 每对两名被试 |
| `NUM_ROUNDS` | 1 | 单轮 |
| `INVESTOR_ROLE` | `'Investor'` | 必须先于受托人定义（决定 `id_in_group`） |
| `TRUSTEE_ROLE` | `'Trustee'` | 受托人 |
| `ENDOWMENT` | 10 | 投资者禀赋 |
| `MULTIPLIER` | 3 | 乘子 |
| `INVESTOR_MESSAGES` / `TRUSTEE_MESSAGES` | 5 档 | 消息量表 |

---

## 3. 条件函数（`trust_game/__init__.py`）

所有页面分派都必须经这几个函数，不得在别处直接读配置或字段。

| 函数 | 返回 | 说明 |
| --- | --- | --- |
| `investor_sends(player)` | bool | A 是否可发意向 |
| `trustee_sends(player)` | bool | B 是否可发承诺 |
| `sends_message(player)` | bool | 本方是否为发送方（决定 `MessageSend`） |
| `receives_message(player)` | bool | 本方是否为接收方（决定 `MessageReveal`） |
| `any_message(player)` | bool | 本组是否存在消息环节 |
| `cell_name(investor_sends_flag, trustee_sends_flag)` | str | 四格标签 |
| `amount_for_copy(value)` | str | 金额转文案（20.0→`'20'`，2.5→`'2.5'`，不四舍五入） |

`sends_message` 与 `receives_message` **不是互补关系**：双向组同为真，无沟通组同为假，
两个单向组一真一假。

读取规则：

- `randomize_cells=True`：读 `Player.investor_sends_message` / `Player.trustee_sends_message`；
  字段为 NULL 时抛 `ValueError`。
- 否则：读 `session.config` 的同名键，缺键退化为 `False`。

---

## 4. 模型字段（`trust_game.Player`）

### 4.1 条件与随机化

| 字段 | 类型 | 取值 | 说明 |
| --- | --- | --- | --- |
| `investor_sends_message` | bool | 0/1 | 组级条件，同一配对两行相同 |
| `trustee_sends_message` | bool | 0/1 | 组级条件 |
| `pair_cell` | str | `none` / `b_to_a` / `a_to_b` / `both` | 四格标签 |
| `role_randomized` | bool | 0/1 | 是否经配对层随机 |

### 4.2 承诺与理解检验

| 字段 | 类型 | 取值 | 说明 |
| --- | --- | --- | --- |
| `pledge_honesty` | bool | 0/1 | 诚信承诺是否勾选 |
| `comprehension_attempts` | int | ≥0 | 理解检验作答次数（答错与答对各计 1） |
| `comp_q1` | int | 正确答案 10 | 初始禀赋 |
| `comp_q2` | int | 正确答案 12 | 4 点 × 3 |
| `comp_q3` | int | 正确答案 12 | 最大返还 |
| `comp_q4` | int | 正确答案 0 | 消息不改变收益规则 |

### 4.3 消息

| 字段 | 类型 | 取值 | 说明 |
| --- | --- | --- | --- |
| `message_investor` | str | 5 档文案 | 未发送为 NULL |
| `message_trustee` | str | 5 档文案 | 未发送为 NULL |
| `investor_message_strength` | int | 0–4 | A 意向强度 |
| `promise_strength` | int | 0–4 | B 承诺强度 |
| `promise` | int | 0/1 或 NULL | 派生承诺编码，写入组内两行 |

### 4.4 信念

所有条件都会填写 `*_before` 字段：沟通组是真实的事前判断，无沟通组是「假如可以交换
消息」的假设性基线，由 `belief_before_hypothetical` 区分。假设性基线不参与计奖。

| 字段 | 类型 | 取值 | 说明 |
| --- | --- | --- | --- |
| `belief_return_pct` | int | 0–100 | A 消息环节后信念（返还比例） |
| `belief_return_pct_before` | int | 0–100 | A 消息环节前判断；无消息组为假设性基线 |
| `belief_investor_send` | int | 0–10 | B 消息环节后一阶信念（甲方送出点数） |
| `belief_investor_send_before` | int | 0–10 | B 消息环节前一阶判断 |
| `second_order_belief_return_pct` | int | 0–100 或 NULL | B 消息环节后二阶信念；A 行为 NULL |
| `second_order_belief_return_pct_before` | int | 0–100 或 NULL | B 消息环节前二阶判断；A 行为 NULL |
| `trustee_anger_intensity` | int | 1–5 或 NULL | 受托人对甲方送出额的不满；投资者行为 NULL |
| `belief_before_hypothetical` | bool | 0/1 | 1 = 决策前判断为假设性基线 |
| `belief_paid_timing` | str | `before` / `after` | 计奖时点；所有玩家均有值，无消息组恒为 `after` |

### 4.5 决策与结算

| 字段 | 类型 | 取值 | 说明 |
| --- | --- | --- | --- |
| `send_amount` | int | 0–10 | $x$；输入控件为 0–10 完整单选按钮组 |
| `return_amount` | int | 0–$3x$ 或 NULL | $y$；$x=0$ 时补写 0 |
| `return_ratio` | float | 0–1 | $y/(3x)$；$x=0$ 记 0 |
| `belief_bonus` | int | A: 0/2；B: 0/2/4 | 本人信念奖金合计（B 为一阶 + 二阶） |
| `payoff` | int | 点 | oTree 标准收益字段，已含信念奖金 |

### 4.6 事后测量（不参与报酬）

| 字段 | 类型 | 显示对象 |
| --- | --- | --- |
| `anger_intensity` | 1–5 | 投资者 |
| `perceived_message` | 1–5 | 收到承诺的投资者 |
| `perceived_intent` | 1–5 | 收到意向的受托人 |

---

## 5. 页面（`trust_game/__init__.py`）

`page_sequence`：

```
Introduction → ComprehensionCheck → Pledge → BeliefBefore → MessageSend →
MessageWaitPage → MessageReveal → BeliefElicit → InvestorDecision →
DecisionWaitPage → TrusteeDecision → ResultsWaitPage → Results → PostRound
```

| 页面 | `is_displayed` | 表单 / 行为 |
| --- | --- | --- |
| `Introduction` | 所有人 | 无表单；按角色与条件渲染四段互斥说明 |
| `ComprehensionCheck` | 所有人 | 四题；答错计数并拒绝，全对计数后放行 |
| `Pledge` | 所有人 | `pledge_honesty`；未勾选拒绝 |
| `BeliefBefore` | 所有人 | A: `belief_return_pct_before`；B: `belief_investor_send_before` + `second_order_belief_return_pct_before`；`before_next_page` 写 `belief_before_hypothetical` |
| `MessageSend` | `sends_message(player)` | A: `message_investor`；B: `message_trustee`；空提交拒绝 |
| `MessageWaitPage` | `any_message(player)` | 等待；写入 `promise` 到组内两行 |
| `MessageReveal` | `receives_message(player)` | 只读对方消息 |
| `BeliefElicit` | 所有人 | A: `belief_return_pct`；B: `belief_investor_send` + `second_order_belief_return_pct` |
| `InvestorDecision` | 投资者 | `send_amount` |
| `DecisionWaitPage` | 所有人 | 等待投资者决策 |
| `TrusteeDecision` | 受托人 | `return_amount`；$x=0$ 时无表单并补写 0 |
| `ResultsWaitPage` | 所有人 | 结算 `payoff`、`return_ratio` 与 A/B 的 `belief_bonus` |
| `Results` | 所有人 | 展示结果、计奖时点与本人奖金 |
| `PostRound` | 所有人 | A: `anger_intensity`（+`perceived_message`）；B: `trustee_anger_intensity`（+`perceived_intent`） |

`MessageWaitPage.after_all_players_arrive` 的承诺编码：

```python
promise_value = (
    content.is_promise(group.trustee.message_trustee)
    if group.trustee.trustee_sends_message else None
)
group.trustee.promise = promise_value
group.investor.promise = promise_value
```

---

## 6. `trust_game.payoffs`

| 名称 | 值 / 签名 | 说明 |
| --- | --- | --- |
| `ENDOWMENT` | 10 | 禀赋 |
| `MULTIPLIER` | 3 | 乘子 |
| `BELIEF_TOLERANCE_PCT` | 10 | 比例容差（百分点） |
| `BELIEF_BONUS_POINTS` | 2 | 单项奖金（点） |
| `TRUSTEE_BELIEF_TOLERANCE_POINTS` | 2 | 受托人一阶信念容差（点） |
| `BELIEF_TIMING_BEFORE` | `'before'` | 决策前计奖 |
| `BELIEF_TIMING_AFTER` | `'after'` | 决策后计奖 |
| `scored_belief(before, after, timing)` | int | 按抽中时点取对应信念 |
| `investor_payoff(x, y)` | int | $10-x+y$ |
| `trustee_payoff(x, y)` | int | $3x-y$ |
| `total_surplus(x)` | int | $10+2x$ |
| `return_ratio(x, y)` | float | $y/(3x)$；$x\le 0$ 返回 0.0 |
| `belief_bonus(belief, x, y, tolerance=10, bonus=2)` | int | 比例判定；$x\le 0$ 返回 0 |
| `trustee_belief_bonus(belief, x, tolerance=2, bonus=2)` | int | 点数判定；$x=0$ 时照常判奖 |
| `second_order_bonus(second, investor_belief, tolerance=10, bonus=2)` | int | 与甲方实际报告之差判定；基准缺失返回 0 |

---

## 7. `trust_game.content`

| 名称 | 值 / 签名 | 说明 |
| --- | --- | --- |
| `INVESTOR_MESSAGES` | `[(4, ...), ..., (0, ...)]` | A 侧意向量表 |
| `TRUSTEE_MESSAGES` | `[(4, ...), ..., (0, ...)]` | B 侧承诺量表 |
| `INVESTOR_ROLE` / `TRUSTEE_ROLE` | `'Investor'` / `'Trustee'` | 角色名 |
| `PROMISE_MIN_STRENGTH` | 2 | 承诺判定阈值 |
| `message_labels(messages)` | list | 生成 `(文案, 文案)` 的 choices |
| `strength_of(messages, label)` | int | 文案 → 0–4；未知文案抛 `KeyError` |
| `is_promise(label)` | 0/1 | 强度 ≥ 2 记 1；未知文案抛 `KeyError` |

`is_promise` 是**预设量表上的派生编码**，不是自由文本的人工双编码，不可与论文的
`Promise` 变量等同。

---

## 8. `survey` app

四页，均无报酬：`Demographics`（性别、年龄、年级、专业、经济学课程数、是否参加过
类似实验）、`GeneralTrust`（一般信任量表）、`RiskPreference`（5 行彩票菜单）、
`DictatorGame`（独裁者博弈送出额）。

---

## 9. 测试接口

| 文件 | 数量 | 覆盖 |
| --- | --- | --- |
| `test_payoffs.py` | 23 | 收益、比例、比例奖金、受托人点数奖金、二阶信念奖金（含穷举与边界） |
| `test_content.py` | 28 | 量表、编码、承诺判定、指导语文案同源、四组互斥、假设性基线文案 |
| `test_settings.py` | 10 | config 名集合、两个处理组键、随机配置、演示镜像 |
| `test_demo_templates.py` | 3 | 模板副本差异、`is_browser_bot` 门控、无 opt-in 开关 |
| `tests.py` | 3 case | 三个 bot case 的端到端流程与全部字段断言 |

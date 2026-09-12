# 信任博弈实验（oTree 6）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 oTree 6 实现一个完整的信任博弈实验（沟通 vs 基线双处理），并交付可复现的分析管线与实验报告。

**Architecture:** 单个 `trust_game` app 承载核心博弈，处理组由 session config 的 `communication` 键控制（不用两个 app，避免两份代码产生细微差异破坏内部效度）。`survey` app 承载个体测量。收益与消息映射逻辑抽到不依赖 oTree 的纯函数模块，以便独立单元测试。分析管线消费与 oTree 导出同构的 CSV，因此对模拟数据与真实数据完全通用。

**Tech Stack:** oTree 6.0.15（starlette + uvicorn + SQLAlchemy）、Python 3.11、unittest（标准库）、numpy/pandas/scipy/statsmodels/matplotlib

## Global Constraints

- **解释器路径固定**：所有 python 命令使用 `/share/zrs2022150501010/miniconda3/envs/otree/bin/python`，oTree 命令使用 `/share/zrs2022150501010/miniconda3/envs/otree/bin/otree`。不要用 `python3`。
- **⚠️ 文件系统限制（Task 1 实测确认，影响全部任务）**：项目位于 NFS 挂载（`170.254.70.14:/gpu` on `/share`，`vers=3, local_lock=none`），该挂载上**任何 sqlite 写入都失败**（`disk I/O error`；已在 `/tmp` 对照验证，`/tmp` 正常）。
  - `otree test` 与 `otree devserver` **不受影响**——oTree 在 `otree/main.py:107` 对 `bots` 与 `devserver_inner` 强制设置 `OTREE_IN_MEMORY=1`，数据库在内存中。
  - `otree resetdb` **必须**加前缀：`OTREE_IN_MEMORY=1 otree resetdb --noinput`。
  - **不要**试图用 symlink 把 `db.sqlite3` 指向 `/tmp` 来绕过——这会破坏 `otree test` 的版本校验（已实测被拒）。
  - 空文件 `db.sqlite3` 会在任何 app 导入时被重新创建（oTree 导入期无条件连接），属正常现象，已在 `.gitignore` 中忽略。
- **`otree test` 依赖 `requests`**：缺失时它打印提示后**静默退出且退出码为 0**，极易被误判为测试通过。Task 1 Step 2 必须先安装。

### ⚠️ oTree 6 Bot 测试的四个 API 事实（Task 2 实测确认，写测试代码前必读）

这四条是 Task 2 实现时踩实的，**本计划早期版本在四处都写错了**，会导致测试静默假通过。后续任务一律以此为准。

1. **`otree test` 的参数是 session config 名，不是 app 名**。CLI 定义见 `otree/cli/bots.py`：`parser.add_argument('session_config_name', ...)`，省略则运行全部 config。所以 `otree test <app名>`（例如 `otree test trust_game`）会报 `No session config with name '<app名>'`；正确写法是 `otree test trust_baseline` / `otree test trust_communication`。**注意本计划早期版本把此处写成 app 名，已全面改正。**
2. **oTree 6 的 `PlayerBot` 没有 `validate_round` 钩子**（全包搜索 `validate_round` 零结果；`api.pyi` 在 `Bot` 上只暴露 `play_round`）。把断言写在 `validate_round` 里等于**死代码**，测试会通过但什么都没验证。断言必须写在 `play_round` 内、最后一个 `yield` 之后。
3. **普通页面必须由 bot 显式 yield，只有 WaitPage 被框架自动处理**。因此 `play_round` 的第一句必须是 `yield Introduction`，否则 bot 停在首页就提交下一页的表单，直接失败。
4. **`expect(player.some_field, None)` 会抛 `NullFieldError`**（`otree/database.py:639`；oTree 6 对未赋值的字段访问即抛错）。判断"未设置"要用官方接口 `player.field_maybe_none('field_name')`。

**验证断言真的在跑（防止死代码假通过）**：改断言前先用变异探针确认它会被触发——故意把某个断言改错，运行测试必须看到 `ExpectError` 且退出码非 0；确认后再改回。

### ⚠️ 测试前置条件断言（本项目已出现三次"假通过"的硬性教训）

截至 Task 2，已连续出现**三次**"测试通过、但测的不是你以为的东西"的失效：

| 失效 | 机制 | 为什么测试没发现 |
|---|---|---|
| `validate_round` 里的断言是死代码 | oTree 6 无该钩子 | 断言从未执行，测试仍然全绿 |
| 沟通组空消息路径 500 | 未勾选的 RadioSelect 不提交该 key | bot 总会提交消息，天然走不到 |
| `creating_session` 未执行 | 类方法被 oTree 静默跳过 | 字段恒 NULL，分派静默走错分支 |

**共同特征：测试的隐含前提被静默违反，而测试只断言结果、从不断言前提。**

**因此，每个 bot 测试必须显式断言它赖以成立的前提**，而不只是断言结果：

1. **处理组标识有效**：`is_communication` 非 NULL 且等于 `session.config['communication']`。仅做真值判断不够——`None` 与 `False` 在 `if` 下行为相同，必须显式区分。
2. **应访问的页面确实被访问过**：沟通组必须能在输出中看到 `MessageSend` 与 `MessageReveal` 的提交记录；基线组必须**看不到**。这是"分派是否走对分支"的直接证据。
3. **用于断言的字段确实被赋值**：用 `field_maybe_none()` 判空，非 NULL 才继续断言其值。
4. **新断言须先用变异探针验证活性**：故意改错 → 必须看到 `ExpectError` 且退出码非 0 → 再改回。

**这四条是必须项，不是建议。** 本项目已经为"不这么做"付出了三次返工代价。

### ⚠️ `blank=True` 字段的判空规则（同类缺陷的根治）

`blank=True` 会让 oTree **不追加 `InputRequired`**（`forms/forms.py:86-87`），而 wtforms_sqlalchemy 对可空列追加的 `Optional()` 会**擦除空输入的处理错误**（`wtforms/validators.py:163-168`）。结果是：空输入以 `None` 正常落库、表单不报错，直到某个下游读取点才抛 `NullFieldError`（HTTP 500）。

本项目已两次因此产生 500：`MessageSend` 的消息字段（未勾选的 radio 不提交该 key）、`TrusteeDecision.return_amount`（**被测者清空数字输入框即可触发**，属普通操作而非边缘情况）。

**规则：每个 `blank=True` 字段必须满足下列之一，否则不得进入数据收集：**

| 字段 | 保障方式 |
|---|---|
| `message_investor` / `message_trustee` | 由 `MessageSend.error_message` 按角色拦截空值 |
| `return_amount` | 由 `TrusteeDecision.error_message` 拦截（仅 `max_return > 0` 时；x=0 走无表单路径） |
| `belief_investor_send` | 由 `BeliefElicit.error_message` 拦截（受托人分支） |
| `investor_message_strength` / `promise_strength` | 基线组本就应为 NULL，**读取前必须用 `field_maybe_none()` 判空** |
| `return_ratio` / `risk_choice` | 由各自 `before_next_page` 无条件写入 |

**新增 `blank=True` 字段时的必做检查：** 找出它的每一个下游读取点，确认要么已被 `error_message` 保证非空，要么在读取处判空。**只加字段不检查读取点，就是下一次 500。**

### ⚠️ 第五个 API 事实：`creating_session` 必须是模块级函数

Task 2 修复阶段实测发现。写成 `Subsession` 的实例方法时**永远不会被调用**：

```
common.is_noself(app) 判定 __init__.py 含 "import" → True      (common.py:62)
Subsession.get_user_defined_target() 返回「模块」而非「类」      (database.py:706-707)
run_creating_session_functions: getattr(模块, 'creating_session')  (session.py:453)
  → 定义在类上时返回 None → 静默跳过
```

正确写法（与 oTree 6 自带模板 `assets/app_template_trials/__init__.py:33` 一致）：

```python
def creating_session(subsession):
    """必须定义在模块级，不能写成 Subsession 的实例方法。"""
    is_comm = subsession.session.config.get('communication', False)
    for player in subsession.get_players():
        player.is_communication = is_comm
```

**失效后果（隐蔽且严重）**：`player.is_communication` 恒为 NULL → 导出数据缺处理组标识（违反规格 9.3）→ **任何依据该字段分派的测试都会静默走错分支**（例如沟通组的 bot 实际测的是基线路径），形成又一次假通过。

**因此**：bot 测试必须显式断言 `player.is_communication is not None` 且与 `session.config['communication']` 一致，否则该失效模式不可见。
- **oTree 版本**：6.0.15。角色必须定义为 `Constants` 中的字符串常量（`INVESTOR_ROLE = 'Investor'`），读取时用 `player.role` **属性**，不可写成 `player.role()`。
- **角色分配顺序**：`get_roles()` 按 `Constants.__dict__` 的插入序取值。`INVESTOR_ROLE` 必须在 `TRUSTEE_ROLE` 之前定义，以保证 `id_in_group=1` 是投资者。
- **开发服务器命令**：`otree devserver`（不是 `runserver`）。
- **测试文件位置**：必须是 `<app>/tests.py`，且类名必须是 `PlayerBot`（`otree.common.get_bots_module` 硬编码导入 `<app>.tests`，`session.py` 硬编码读取 `PlayerBot.cases`）。
- **tests.py 导入方式**：必须同时写 `from otree.api import *` 和 `from . import *`，否则页面类名不可见（已实地验证）。
- **无 git**：本目录不是 git 仓库，用户明确要求不使用 git。计划中的"提交"步骤一律替换为"验证并记录"检查点。
- **数值参数（规格第 5.1 节）**：禀赋 `ENDOWMENT = 10`，乘子 `MULTIPLIER = 3`，x ∈ [0,10]，y ∈ [0,3x]。
- **收益公式**：`A = 10 − x + y`，`B = 3x − y`，`A + B = 10 + 2x`。
- **收益范围**：A 为 0–30，B 为 0–30（**不是** 0–20）。
- **报酬**：`participation_fee = 20.00`，`real_world_currency_per_point = 1.00`。
- **点数小数位**：`POINTS_DECIMAL_PLACES` 保持默认 0，所有收益均为整数点。
- **报告中的模拟结果必须标注**：任何图表与表格的标题、图注中都必须出现"模拟数据"字样。
- **语言**：所有面向被试的文案为中文；`LANGUAGE_CODE = 'zh-hans'`。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `settings.py` | oTree 项目配置，两个 session config，中文与人民币设置 |
| `requirements.txt` | 依赖清单 |
| `trust_game/payoffs.py` | **纯函数**：收益、返还比例、信念奖金 |
| `trust_game/content.py` | **纯函数**：消息选项与强度映射 |
| `trust_game/__init__.py` | Constants / Subsession / Group / Player / 11 个页面 |
| `trust_game/tests.py` | oTree Bot 测试（两个处理组流程、边界、拦截） |
| `trust_game/test_payoffs.py` | 收益函数单元测试（unittest） |
| `trust_game/test_content.py` | 消息映射单元测试（unittest） |
| `trust_game/*.html` | 8 个页面模板 |
| `survey/__init__.py` | 个体测量 app：4 个页面 |
| `survey/tests.py` | survey 的 Bot 测试 |
| `survey/*.html` | 4 个页面模板 |
| `analysis/simulate_data.py` | 生成模拟数据（文献效应量） |
| `analysis/analyze.py` | 描述统计 / 检验 / 回归 / 中介 / 图表 |
| `analysis/output/` | 脚本输出目录 |
| `实验报告.md` | 交付物 1 |
| `README.md` | 安装、运行、测试、导出、分析说明 |

**边界划分理由：** `payoffs.py` 与 `content.py` 不含任何 oTree 依赖，因此可以用标准 unittest 秒级验证，且避免"测试与实现共享同一 bug"。`trust_game/__init__.py` 只做 oTree 的编排，所有计算委托给纯函数。

---

## Task 1: 项目脚手架 + 纯逻辑模块

**Files:**
- Create: `settings.py`
- Create: `requirements.txt`
- Create: `trust_game/__init__.py`（本任务仅放占位，Task 2 填充）
- Create: `trust_game/payoffs.py`
- Create: `trust_game/content.py`
- Create: `trust_game/test_payoffs.py`
- Create: `trust_game/test_content.py`
- Create: `_static/global/empty.css`（oTree 项目结构所需）

**Interfaces:**
- Consumes: 无
- Produces:
  - `payoffs.ENDOWMENT: int = 10`、`payoffs.MULTIPLIER: int = 3`
  - `payoffs.investor_payoff(send_amount: int, return_amount: int) -> int`
  - `payoffs.trustee_payoff(send_amount: int, return_amount: int) -> int`
  - `payoffs.total_surplus(send_amount: int) -> int`
  - `payoffs.return_ratio(send_amount: int, return_amount: int) -> float`
  - `payoffs.belief_bonus(belief_return_pct: int, send_amount: int, return_amount: int) -> int`
  - `content.INVESTOR_MESSAGES: list[tuple[int, str]]`、`content.TRUSTEE_MESSAGES: list[tuple[int, str]]`
  - `content.message_labels(messages) -> list[str]`
  - `content.strength_of(messages, label: str) -> int`

- [ ] **Step 1: 建立目录结构与依赖清单**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
mkdir -p trust_game survey analysis/output _static/global docs/superpowers/plans
touch trust_game/__init__.py survey/__init__.py
echo '/* placeholder */' > _static/global/empty.css
cat > requirements.txt <<'EOF'
otree==6.0.15
requests>=2.31
numpy>=1.26
pandas>=2.1
scipy>=1.11
statsmodels>=0.14
matplotlib>=3.8
EOF
echo "目录与依赖清单已建立"
```

- [ ] **Step 2: 安装依赖**

`requests` 是 `otree test` 的硬依赖，缺失时测试工具链完全无法运行（已实地验证）。分析依赖用于 Task 5–6。

```bash
/share/zrs2022150501010/miniconda3/envs/otree/bin/pip install requests numpy pandas scipy statsmodels matplotlib
```

Expected: 全部 `Successfully installed`，无 error。

- [ ] **Step 3: 写 `payoffs.py`**

```python
"""信任博弈的收益与派生量计算。

本模块不依赖 oTree，可独立单元测试。

参数（规格第 5.1 节）：禀赋 ENDOWMENT = 10，乘子 MULTIPLIER = 3。

约定：send_amount 记为 x，return_amount 记为 y。
"""

ENDOWMENT = 10
MULTIPLIER = 3

# 信念奖金的判定容差（百分点）与奖金金额（点）
BELIEF_TOLERANCE_PCT = 10
BELIEF_BONUS_POINTS = 2


def investor_payoff(send_amount: int, return_amount: int) -> int:
    """投资者收益 A = E - x + y，范围 0-30。"""
    return ENDOWMENT - send_amount + return_amount


def trustee_payoff(send_amount: int, return_amount: int) -> int:
    """受托人收益 B = m*x - y，范围 0-30。"""
    return MULTIPLIER * send_amount - return_amount


def total_surplus(send_amount: int) -> int:
    """总额 A + B = E + (m-1)*x。"""
    return ENDOWMENT + (MULTIPLIER - 1) * send_amount


def return_ratio(send_amount: int, return_amount: int) -> float:
    """返还比例 y/(m*x)。

    x = 0 时 y 必然为 0（B 无可返还金额），约定比例记为 0.0。
    """
    if send_amount <= 0:
        return 0.0
    return return_amount / (MULTIPLIER * send_amount)


def belief_bonus(
    belief_return_pct: int,
    send_amount: int,
    return_amount: int,
    tolerance_pct: int = BELIEF_TOLERANCE_PCT,
    bonus: int = BELIEF_BONUS_POINTS,
) -> int:
    """信念奖金：预测返还比例与实际比例的偏差在 tolerance_pct 个百分点内则得奖。

    判定使用全整数运算：|belief*denom - 100*y| <= tolerance*denom，其中 denom = m*x。
    这样正确性不依赖 IEEE 浮点舍入的推理。（等价浮点实现已在全部 17776 组
    (x,y,belief) 输入上穷举验证同样正确；此处选择整数实现是为了让正确性
    由构造保证，而非由浮点行为保证——本函数决定真实金钱收益。）

    x = 0 时不发放奖金：此时没有实际转移，信念无对象可评分。若照发，
    「送出 0 且预测 ≤10%」将确定获得 10 + 2 = 12 点，高于 10 点禀赋，
    使"什么都不送"成为唯一的无风险且优于禀赋的选项，在 x=0 处形成下限
    聚集、使信任度量向下偏，并混同不信任、风险规避与惩罚三种动机。
    详见规格第 7 节。
    """
    if send_amount <= 0:
        return 0
    denom = MULTIPLIER * send_amount
    if abs(belief_return_pct * denom - 100 * return_amount) <= tolerance_pct * denom:
        return bonus
    return 0
```

- [ ] **Step 4: 写 `test_payoffs.py`（先写测试，应全部失败）**

```python
"""payoffs 模块的单元测试。

运行：/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_payoffs -v
（在项目根目录执行；不要用 unittest discover，它会误加载依赖 oTree 上下文的 tests.py）
"""

import unittest

from trust_game import payoffs


class TestPayoffs(unittest.TestCase):

    def test_investor_payoff_mid_values(self):
        # 规格第 14.1 节测试用例
        self.assertEqual(payoffs.investor_payoff(0, 0), 10)
        self.assertEqual(payoffs.investor_payoff(5, 6), 11)
        self.assertEqual(payoffs.investor_payoff(10, 15), 15)
        self.assertEqual(payoffs.investor_payoff(10, 30), 30)

    def test_trustee_payoff_mid_values(self):
        self.assertEqual(payoffs.trustee_payoff(0, 0), 0)
        self.assertEqual(payoffs.trustee_payoff(5, 6), 9)
        self.assertEqual(payoffs.trustee_payoff(10, 15), 15)
        self.assertEqual(payoffs.trustee_payoff(10, 30), 0)

    def test_investor_range_is_0_to_30_not_0_to_20(self):
        """规格自审修正的错误：A 的范围是 0-30。"""
        values = [
            payoffs.investor_payoff(x, y)
            for x in range(11)
            for y in range(3 * x + 1)
        ]
        self.assertEqual(min(values), 0)
        self.assertEqual(max(values), 30)

    def test_trustee_range_is_0_to_30(self):
        values = [
            payoffs.trustee_payoff(x, y)
            for x in range(11)
            for y in range(3 * x + 1)
        ]
        self.assertEqual(min(values), 0)
        self.assertEqual(max(values), 30)

    def test_total_surplus_identity_holds_exhaustively(self):
        """总额守恒：任意 (x, y) 下 A + B == 10 + 2x。"""
        for x in range(11):
            for y in range(3 * x + 1):
                with self.subTest(x=x, y=y):
                    total = payoffs.investor_payoff(x, y) + payoffs.trustee_payoff(x, y)
                    self.assertEqual(total, payoffs.total_surplus(x))

    def test_social_optimum_is_30_split_15_15(self):
        self.assertEqual(payoffs.total_surplus(10), 30)
        self.assertEqual(payoffs.investor_payoff(10, 15), 15)
        self.assertEqual(payoffs.trustee_payoff(10, 15), 15)

    def test_return_ratio_convention_when_x_is_zero(self):
        self.assertEqual(payoffs.return_ratio(0, 0), 0.0)

    def test_return_ratio_values(self):
        self.assertAlmostEqual(payoffs.return_ratio(5, 6), 0.4)
        self.assertAlmostEqual(payoffs.return_ratio(10, 30), 1.0)
        self.assertAlmostEqual(payoffs.return_ratio(10, 15), 0.5)
        self.assertAlmostEqual(payoffs.return_ratio(10, 0), 0.0)

    def test_belief_bonus_within_tolerance(self):
        # x=5, y=6 -> 实际 40%
        self.assertEqual(payoffs.belief_bonus(40, 5, 6), 2)
        self.assertEqual(payoffs.belief_bonus(35, 5, 6), 2)
        self.assertEqual(payoffs.belief_bonus(45, 5, 6), 2)

    def test_belief_bonus_boundary_is_inclusive(self):
        # 偏差恰好 10 个百分点 -> 得奖（边界含等号）
        self.assertEqual(payoffs.belief_bonus(30, 5, 6), 2)
        self.assertEqual(payoffs.belief_bonus(50, 5, 6), 2)

    def test_belief_bonus_outside_tolerance(self):
        # 偏差 11 个百分点 -> 不得奖
        self.assertEqual(payoffs.belief_bonus(29, 5, 6), 0)
        self.assertEqual(payoffs.belief_bonus(51, 5, 6), 0)

    def test_belief_bonus_is_zero_when_x_is_zero(self):
        """x=0 时没有实际转移，不发奖金（规格第 7 节）。

            照发会使「送出 0 且预测低」成为高于禀赋的无风险收益。
        """
        for belief in (0, 5, 10, 11, 50, 100):
            with self.subTest(belief=belief):
                self.assertEqual(payoffs.belief_bonus(belief, 0, 0), 0)

    def test_belief_bonus_matches_exact_rational_solution_exhaustively(self):
        """穷举验证整数实现与精确有理数解完全一致。"""
        from fractions import Fraction
        for x in range(11):
            for y in range(3 * x + 1):
                for belief in range(101):
                    if x == 0:
                        expected = 0
                    else:
                        exact = Fraction(100 * y, 3 * x)
                        expected = 2 if abs(Fraction(belief) - exact) <= 10 else 0
                    with self.subTest(x=x, y=y, belief=belief):
                        self.assertEqual(
                            payoffs.belief_bonus(belief, x, y), expected
                        )


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 5: 运行测试，确认失败**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_payoffs -v
```

Expected: 若 `payoffs.py` 尚未写入则 `ModuleNotFoundError: No module named 'trust_game.payoffs'`；已写入则全部 PASS。

- [ ] **Step 6: 写 `content.py`**

```python
"""消息选项与强度映射。

本模块不依赖 oTree，可独立单元测试。

两侧量表均为 0-4 序数编码（规格第 6.2 节），编码越高表示信任意向 /
承诺强度越高。
"""

# (编码, 文案)。列表顺序即为界面显示顺序，从最强到最弱。
INVESTOR_MESSAGES = [
    (4, '我打算把全部 10 点都送给你'),
    (3, '我打算送出大部分点数'),
    (2, '我打算送出一部分点数'),
    (1, '我打算只送出很少的点数'),
    (0, '我还没有决定'),
]

TRUSTEE_MESSAGES = [
    (4, '我承诺会把收到的点数全部返还给你'),
    (3, '我承诺会返还一半以上'),
    (2, '我承诺会返还一部分'),
    (1, '我不确定会不会返还'),
    (0, '我还没有决定'),
]

INVESTOR_ROLE = 'Investor'
TRUSTEE_ROLE = 'Trustee'


def message_labels(messages):
    """返回用于 oTree 表单 choices 的 (存储值, 显示文案) 列表。

    存储值使用文案本身（而非编码），以便数据保留被试实际看到的内容。
    """
    return [(label, label) for _, label in messages]


def strength_of(messages, label):
    """把消息文案映射回 0-4 的强度编码。未知文案抛 KeyError。"""
    mapping = {text: code for code, text in messages}
    return mapping[label]
```

- [ ] **Step 7: 写 `test_content.py`**

```python
"""content 模块的单元测试。

运行：/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_content -v
"""

import unittest

from trust_game import content


class TestContent(unittest.TestCase):

    def test_both_scales_are_0_to_4(self):
        """规格自审修正的不一致：两侧量表必须对称，均为 0-4。"""
        for messages in (content.INVESTOR_MESSAGES, content.TRUSTEE_MESSAGES):
            codes = sorted(code for code, _ in messages)
            self.assertEqual(codes, [0, 1, 2, 3, 4])

    def test_labels_are_unique_within_each_scale(self):
        for messages in (content.INVESTOR_MESSAGES, content.TRUSTEE_MESSAGES):
            labels = [label for _, label in messages]
            self.assertEqual(len(labels), len(set(labels)))

    def test_message_labels_pairs_value_with_itself(self):
        pairs = content.message_labels(content.INVESTOR_MESSAGES)
        self.assertEqual(len(pairs), 5)
        for value, label in pairs:
            self.assertEqual(value, label)

    def test_strength_of_is_inverse_of_scale(self):
        for messages in (content.INVESTOR_MESSAGES, content.TRUSTEE_MESSAGES):
            for code, label in messages:
                self.assertEqual(content.strength_of(messages, label), code)

    def test_strength_of_is_total_over_choices(self):
        """表单给出的每个选项都必须能映射回编码，否则 before_next_page 会崩。"""
        for messages in (content.INVESTOR_MESSAGES, content.TRUSTEE_MESSAGES):
            for _, label in content.message_labels(messages):
                self.assertIsInstance(content.strength_of(messages, label), int)

    def test_strength_of_raises_on_unknown_label(self):
        with self.assertRaises(KeyError):
            content.strength_of(content.INVESTOR_MESSAGES, '不存在的消息')

    def test_highest_code_means_strongest_trust(self):
        codes = [code for code, _ in content.INVESTOR_MESSAGES]
        self.assertEqual(codes[0], 4)   # 全部送出
        self.assertEqual(codes[-1], 0)  # 还没有决定
        self.assertEqual(codes, sorted(codes, reverse=True))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 8: 运行全部纯函数测试，确认通过**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_payoffs trust_game.test_content -v
```

Expected: 全部 `ok`，最后打印 `OK`，共 **20** 个测试（`payoffs` 13 个 + `content` 7 个）。

- [ ] **Step 9: 写 `settings.py`**

```python
from os import environ

SESSION_CONFIGS = [
    dict(
        name='trust_baseline',
        display_name='信任博弈 — 基线组（无沟通）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=False,
        doc='标准信任博弈，全程匿名，无任何沟通',
    ),
    dict(
        name='trust_communication',
        display_name='信任博弈 — 沟通组',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=True,
        doc='信任博弈，双方在决策前同时发送预设消息并互相可见',
    ),
]

# 规格第 11 节：出场费 20 元，1 点 = 1 元
SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00,
    participation_fee=20.00,
    doc='',
)

PARTICIPANT_FIELDS = []
SESSION_FIELDS = []

LANGUAGE_CODE = 'zh-hans'

REAL_WORLD_CURRENCY_CODE = 'CNY'
USE_POINTS = True

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """信任博弈实验 — 演示"""

SECRET_KEY = 'trust-game-experiment-secret-key-2026'

ROOMS = []
```

- [ ] **Step 10: 验证项目可被 oTree 加载**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
OTREE_IN_MEMORY=1 /share/zrs2022150501010/miniconda3/envs/otree/bin/otree resetdb --noinput
```

Expected: 无报错。（必须加 `OTREE_IN_MEMORY=1` 前缀——见 Global Constraints 的 NFS 限制说明。）

- [ ] **Step 11: 检查点（无 git，改为记录验证结果）**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_payoffs trust_game.test_content 2>&1 | tail -3
ls -la settings.py requirements.txt trust_game/payoffs.py trust_game/content.py
```

Expected: 测试 OK；四个文件均存在。

---

## Task 2: trust_game 模型层 + 基线组完整流程

> **⚠️ 本节代码块是计划原始记录，其中测试部分已作废。**
> 实现时依据实测的 oTree 6 API 做了四处修正（详见 Global Constraints 的「oTree 6 Bot 测试的四个 API 事实」）：
> `otree test` 参数应为 session config 名、`validate_round` 钩子不存在（断言须移入 `play_round`）、
> 首页需显式 `yield Introduction`、字段判空须用 `field_maybe_none()`。
> **权威版本是仓库中的 `trust_game/tests.py`**，Task 3 应在它基础上扩展。

**Files:**
- Create: `trust_game/__init__.py`（覆盖占位）
- Create: `trust_game/Introduction.html`
- Create: `trust_game/ComprehensionCheck.html`
- Create: `trust_game/BeliefElicit.html`
- Create: `trust_game/InvestorDecision.html`
- Create: `trust_game/TrusteeDecision.html`
- Create: `trust_game/Results.html`
- Create: `trust_game/tests.py`
- Modify: `settings.py`（本任务暂时只保留 `trust_baseline`，Task 3 加回沟通组）

**Interfaces:**
- Consumes: Task 1 的 `payoffs.*` 与 `content.*`
- Produces:
  - `C.INVESTOR_ROLE == 'Investor'`、`C.TRUSTEE_ROLE == 'Trustee'`
  - `C.ENDOWMENT == 10`、`C.MULTIPLIER == 3`
  - `Player` 字段：`is_communication, send_amount, return_amount, return_ratio, belief_return_pct, belief_investor_send, belief_bonus, comprehension_attempts, message_investor, message_trustee, investor_message_strength, promise_strength, comp_q1, comp_q2, comp_q3`
  - 页面类：`Introduction, ComprehensionCheck, MessageSend, MessageWaitPage, MessageReveal, BeliefElicit, InvestorDecision, DecisionWaitPage, TrusteeDecision, ResultsWaitPage, Results`
  - 模块函数 `has_communication(player) -> bool`

- [ ] **Step 1: 写 `trust_game/__init__.py`**

```python
from otree.api import *

from . import content
from . import payoffs

doc = """
信任博弈实验（Berg, Dickhaut & McCabe, 1995）。

处理组由 session config 的 communication 键控制：
  False = 基线组（无沟通）
  True  = 沟通组（双方决策前同时发送预设消息并互相可见）
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


def has_communication(player):
    """处理组判定：唯一的读取入口。"""
    return player.session.config.get('communication', False)


class Subsession(BaseSubsession):
    pass


def creating_session(subsession):
    """把处理组标识降范式写入每个 Player，使导出数据自包含。

    ⚠️ 必须定义在模块级，不能写成 Subsession 的实例方法——oTree 6 会把
    调用目标解析为模块（is_noself 为真时，见 common.py:62 / database.py:706），
    getattr(模块, 'creating_session') 会返回 None 从而静默跳过，
    导致 player.is_communication 恒为 NULL。详见 Global Constraints 第五条 API 事实。
    """
    is_comm = subsession.session.config.get('communication', False)
    for player in subsession.get_players():
        player.is_communication = is_comm


class Group(BaseGroup):
    @property
    def investor(self):
        return self.get_player_by_role(C.INVESTOR_ROLE)

    @property
    def trustee(self):
        return self.get_player_by_role(C.TRUSTEE_ROLE)


class Player(BasePlayer):
    is_communication = models.BooleanField()

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
            is_communication=has_communication(player),
            endowment=C.ENDOWMENT,
            multiplier=C.MULTIPLIER,
            max_return=C.MULTIPLIER * C.ENDOWMENT,
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
        return has_communication(player)

    @staticmethod
    def get_form_fields(player):
        if player.role == C.INVESTOR_ROLE:
            return ['message_investor']
        return ['message_trustee']

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
        return has_communication(player)


class MessageReveal(Page):
    @staticmethod
    def is_displayed(player):
        return has_communication(player)

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
        amount = values.get('return_amount')
        if amount is None:
            return
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
```

- [ ] **Step 2: 写 6 个页面模板**

`trust_game/Common` 无公共模板，每个模板独立。全部使用 oTree 标准块语法。

`trust_game/Introduction.html`：

```html
{{ block title }}
    实验说明
{{ endblock }}

{{ block content }}
<div class="card">
  <div class="card-body">
    <p>欢迎参加本实验。你将与另一位参与者随机配对，双方互不认识。</p>

    {{ if is_investor }}
      <h5>你的角色：投资者（甲方）</h5>
      <p>你初始获得 <strong>{{ endowment }} 点</strong>。你需要决定从中送出多少点给乙方。</p>
      <p>你送出的点数会被实验者<strong>乘以 {{ multiplier }}</strong> 后交给乙方。</p>
      <p>随后乙方决定返还多少点给你。你的最终收益为：</p>
      <p class="text-center"><strong>{{ endowment }} − 你送出的点数 + 乙方返还的点数</strong></p>
    {{ else }}
      <h5>你的角色：受托人（乙方）</h5>
      <p>甲方初始获得 <strong>{{ endowment }} 点</strong>，并决定送出其中一部分给你。</p>
      <p>甲方送出的点数会被实验者<strong>乘以 {{ multiplier }}</strong> 后交给你，因此你最多可获得 {{ max_return }} 点。</p>
      <p>随后你决定返还多少点给甲方。你的最终收益为：</p>
      <p class="text-center"><strong>你收到的点数 − 你返还给甲方的点数</strong></p>
    {{ endif }}

    {{ if is_communication }}
      <p>在做出决策之前，你与对方可以各自选择一条消息发送给对方，双方都能看到对方的消息。</p>
    {{ else }}
      <p>整个过程中你与对方完全匿名，不会有任何信息交流。</p>
    {{ endif }}

    {{ if is_investor }}
      <p><strong>信念判断奖金：</strong>在你做出送出决策之前，你会被问及「你认为对方会返还你所送出金额放大后的百分之多少」。
      若你的判断与实际结果相差不超过 10 个百分点，你将额外获得 <strong>2 点</strong>奖金；否则为 0 点。</p>
      <p><strong>请注意：若你送出的点数为 0，则本项奖金为 0</strong>——此时没有发生实际转移，无法对你的判断进行评分。</p>
    {{ endif }}

    <p class="text-muted">每 1 点可兑换 1 元人民币，另有 20 元出场费。</p>
  </div>
</div>

{{ next_button }}
{{ endblock }}
```

`trust_game/ComprehensionCheck.html`：

```html
{{ block title }}
    理解检验
{{ endblock }}

{{ block content }}
<p>请回答以下三个问题以确认你已理解实验规则。全部答对才能继续。</p>
{{ formfields }}
{{ next_button }}
{{ endblock }}
```

`trust_game/BeliefElicit.html`：

```html
{{ block title }}
    你的判断
{{ endblock }}

{{ block content }}
<p>在做出决策之前，请先回答一个关于对方行为的问题。</p>
{{ formfields }}
{{ next_button }}
{{ endblock }}
```

`trust_game/InvestorDecision.html`：

```html
{{ block title }}
    你的决策
{{ endblock }}

{{ block content }}
<p>你初始获得 {{ C.ENDOWMENT }} 点。请决定送出多少点给乙方。</p>
<p>送出多少点，就会被乘以 {{ C.MULTIPLIER }} 后交给乙方。</p>
{{ formfields }}
{{ next_button }}
{{ endblock }}
```

`trust_game/TrusteeDecision.html`：

```html
{{ block title }}
    你的决策
{{ endblock }}

{{ block content }}
<p>甲方送出了 <strong>{{ send_amount }} 点</strong>。</p>

{{ if max_return == 0 }}
  <p>经过乘以 {{ C.MULTIPLIER }} 后，你收到 <strong>0 点</strong>，因此没有可返还的金额。</p>
  <p class="text-danger">你的本轮收益为 0 点。</p>
{{ else }}
  <p>经过乘以 {{ C.MULTIPLIER }} 后，你收到 <strong>{{ max_return }} 点</strong>。</p>
  <p>请决定返还多少点给甲方（0 到 {{ max_return }} 之间）：</p>
  {{ formfields }}
{{ endif }}

{{ next_button }}
{{ endblock }}
```

`trust_game/Results.html`：

```html
{{ block title }}
    本轮结果
{{ endblock }}

{{ block content }}
<ul class="list-group">
  <li class="list-group-item">甲方送出的点数：{{ send_amount }}</li>
  <li class="list-group-item">乙方返还的点数：{{ return_amount }}</li>
  {{ if is_investor }}
    <li class="list-group-item">你获得的信念判断奖金：{{ belief_bonus }} 点</li>
  {{ endif }}
  <li class="list-group-item active">你的本轮收益：{{ my_payoff }}</li>
</ul>

{{ next_button }}
{{ endblock }}
```

- [ ] **Step 3: 写 `trust_game/tests.py`**

```python
from otree.api import *
from . import *


class PlayerBot(Bot):
    """基线组（communication=False）的完整流程测试。"""

    def play_round(self):
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

    def validate_round(self):
        pass
```

- [ ] **Step 4: 收窄 `settings.py` 到单一 config（临时）**

把 `SESSION_CONFIGS` 暂时替换为只有基线组，因为沟通组页面在 Task 3 才验证：

```python
SESSION_CONFIGS = [
    dict(
        name='trust_baseline',
        display_name='信任博弈 — 基线组（无沟通）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=False,
        doc='标准信任博弈，全程匿名，无任何沟通',
    ),
]
```

- [ ] **Step 5: 建一个最小的 survey 占位 app**

因为 `app_sequence` 引用了 `survey`，需先有最小实现（Task 4 会替换）：

```python
# survey/__init__.py
from otree.api import *


class C(BaseConstants):
    NAME_IN_URL = 'survey'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pass


page_sequence = []
```

同时创建 `survey/tests.py`：

```python
from otree.api import *
from . import *


class PlayerBot(Bot):
    def play_round(self):
        pass
```

- [ ] **Step 6: 运行基线组 Bot 测试**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
rm -f db.sqlite3
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline
```

Expected: `Bots completed session`，无 Traceback。

- [ ] **Step 7: 验证收益计算与消息页跳过**

在 `trust_game/tests.py` 的 `PlayerBot` 中追加断言，验证结算结果正确、且基线组确实跳过了消息页。

**⚠️ 本步骤的代码已在 Task 2 实现时修正——权威版本是仓库中实际的 `trust_game/tests.py`。** 下面给出的是修正后的写法（断言位于 `play_round` 末尾，字段判空用 `field_maybe_none`）：

```python
    def check_round(self):
        # 断言直接写在 play_round 末尾调用；oTree 6 无 validate_round 钩子
        from trust_game import has_communication
        expect(has_communication(self.player), False)

        if self.player.role == C.INVESTOR_ROLE:
            expect(self.player.send_amount, 5)
            # 预测 50%，实际比例 6/(3*5) = 40%，偏差恰好 10 个百分点（边界内含等号）→ 得奖 2 点
            expect(self.player.belief_bonus, 2)
            # 收益 = (10 - 5 + 6) + 2 = 13
            expect(self.player.payoff, 13)
            # 基线组不应有任何消息内容
            expect(self.player.message_investor, None)
            expect(self.player.investor_message_strength, None)
        else:
            expect(self.player.return_amount, 6)
            # 收益 = 3*5 - 6 = 9
            expect(self.player.payoff, 9)
            expect(self.player.message_trustee, None)
            expect(self.player.promise_strength, None)
```

**数值推导（务必核对）：**
- 投资者：`A = 10 − 5 + 6 = 11`，信念奖金 `2`（偏差恰好 10 个百分点，边界判定为得奖）→ 总计 `13`
- 受托人：`B = 3×5 − 6 = 9`

该用例**同时覆盖了信念奖金的边界含等号行为**，是刻意设计的。若实测输出与上述不符，说明 `payoffs.belief_bonus` 的边界语义有误，应回到 Task 1 修实现而非改断言。

- [ ] **Step 8: 重跑测试确认通过**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
rm -f db.sqlite3
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline
```

Expected: `Bots completed session`，断言全部通过。

- [ ] **Step 9: 检查点**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
ls trust_game/*.html
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_payoffs trust_game.test_content 2>&1 | tail -2
```

Expected: 6 个模板文件存在；纯函数测试仍 OK。

---

## Task 3: 沟通组页面与第二个 session config

**Files:**
- Create: `trust_game/MessageSend.html`
- Create: `trust_game/MessageReveal.html`
- Modify: `trust_game/tests.py`（增加沟通组 bot 与跳过验证）
- Modify: `settings.py`（恢复两个 config）

**Interfaces:**
- Consumes: Task 2 的 `has_communication`、`MessageSend`、`MessageWaitPage`、`MessageReveal`、`content.strength_of`
- Produces: 无新接口；`trust_communication` session config

- [ ] **Step 1: 写消息页模板**

`trust_game/MessageSend.html`：

```html
{{ block title }}
    发送消息
{{ endblock }}

{{ block content }}
<p>你可以选择一条消息发送给对方。对方也会选择一条消息发送给你，双方都能看到对方的选择。</p>
{{ formfields }}
{{ next_button }}
{{ endblock }}
```

`trust_game/MessageReveal.html`：

```html
{{ block title }}
    对方的消息
{{ endblock }}

{{ block content }}
<div class="alert alert-info">
  <p>对方选择的消息是：</p>
  <p class="lead">「{{ message_from_other }}」</p>
</div>
<p class="text-muted">请注意：消息不具约束力，对方没有义务遵守。</p>
{{ next_button }}
{{ endblock }}
```

- [ ] **Step 2: 写沟通组的 bot 测试**

在 `trust_game/tests.py` 中追加：

```python
class CommunicationBot(Bot):
    """沟通组（communication=True）的完整流程测试。

    需要把本类设为该 session config 使用的 bot；具体做法见 Step 3。
    """

    def play_round(self):
        yield Submission(ComprehensionCheck,
                         dict(comp_q1=10, comp_q2=12, comp_q3=12),
                         check_html=False)
        if self.player.role == C.INVESTOR_ROLE:
            yield Submission(MessageSend,
                             dict(message_investor=C.INVESTOR_MESSAGES[0][1]),
                             check_html=False)
        else:
            yield Submission(MessageSend,
                             dict(message_trustee=C.TRUSTEE_MESSAGES[1][1]),
                             check_html=False)
        # MessageWaitPage 由框架自动处理
        yield MessageReveal
        if self.player.role == C.INVESTOR_ROLE:
            yield Submission(BeliefElicit, dict(belief_return_pct=50),
                             check_html=False)
            yield Submission(InvestorDecision, dict(send_amount=10),
                             check_html=False)
        else:
            yield Submission(BeliefElicit, dict(belief_investor_send=5),
                             check_html=False)
        if self.player.role == C.TRUSTEE_ROLE:
            yield Submission(TrusteeDecision, dict(return_amount=15),
                             check_html=False)
        yield Results

    # 注意：不要在这里写 validate_round —— oTree 6 没有这个钩子，
    # 写在那里的断言永远不会执行。断言统一由 Step 3 的 check_round() 承担。
```

- [ ] **Step 3: 让 `PlayerBot` 按处理组分派**

oTree 只识别 `tests.py` 中名为 `PlayerBot` 的类。改为单一入口按 `is_communication` 分派：

```python
from otree.api import *
from . import *


class PlayerBot(Bot):
    """单一入口：按 session config 的 communication 分派到对应流程。"""

    def play_round(self):
        if self.player.is_communication:
            yield from communication_round(self)
        else:
            yield from baseline_round(self)


def baseline_round(bot, zero_send=False):
    yield Submission(ComprehensionCheck,
                     dict(comp_q1=10, comp_q2=12, comp_q3=12),
                     check_html=False)
    if bot.player.role == C.INVESTOR_ROLE:
        yield Submission(BeliefElicit, dict(belief_return_pct=50),
                         check_html=False)
        yield Submission(InvestorDecision, dict(send_amount=5),
                         check_html=False)
    else:
        yield Submission(BeliefElicit, dict(belief_investor_send=5),
                         check_html=False)
    if bot.player.role == C.TRUSTEE_ROLE:
        yield Submission(TrusteeDecision, dict(return_amount=6),
                         check_html=False)
    yield Results


def communication_round(bot):
    yield Submission(ComprehensionCheck,
                     dict(comp_q1=10, comp_q2=12, comp_q3=12),
                     check_html=False)
    if bot.player.role == C.INVESTOR_ROLE:
        yield Submission(MessageSend,
                         dict(message_investor=C.INVESTOR_MESSAGES[0][1]),
                         check_html=False)
    else:
        yield Submission(MessageSend,
                         dict(message_trustee=C.TRUSTEE_MESSAGES[1][1]),
                         check_html=False)
    yield MessageReveal
    if bot.player.role == C.INVESTOR_ROLE:
        yield Submission(BeliefElicit, dict(belief_return_pct=0),
                         check_html=False)
        yield Submission(InvestorDecision, dict(send_amount=10),
                         check_html=False)
    else:
        yield Submission(BeliefElicit, dict(belief_investor_send=5),
                         check_html=False)
    if bot.player.role == C.TRUSTEE_ROLE:
        yield Submission(TrusteeDecision, dict(return_amount=15),
                         check_html=False)
    yield Results


def check_round(bot):
    """验证结算正确性与处理组隔离。

    在 play_round 末尾调用（oTree 6 无 validate_round 钩子）。

    注意：判断"字段未设置"必须用 field_maybe_none()，直接访问未赋值的字段
    会抛 NullFieldError（otree/database.py:639）。
    """
    if bot.player.role == C.INVESTOR_ROLE:
        if bot.player.is_communication:
            # 投资者选了最强的消息（编码 4），送出 10 点
            expect(bot.player.investor_message_strength, 4)
            expect(bot.player.send_amount, 10)
            # 预测 0%，实际比例 15/(3*10) = 50%，偏差 50 个百分点 > 10 → 不得奖
            expect(bot.player.belief_bonus, 0)
            # 收益 = (10 - 10 + 15) + 0 = 15
            expect(bot.player.payoff, 15)
        else:
            expect(bot.player.field_maybe_none('message_investor'), None)
            expect(bot.player.send_amount, 5)
    else:
        if bot.player.is_communication:
            # 受托人选了次强的承诺（编码 3）
            expect(bot.player.promise_strength, 3)
            # 收益 = 3*10 - 15 = 15
            expect(bot.player.payoff, 15)
        else:
            expect(bot.player.field_maybe_none('message_trustee'), None)
```

**数值推导（务必核对）：**
- 沟通组投资者：送出 10，收到返还 15 → `A = 10 − 10 + 15 = 15`；信念预测 0% 而实际 50%，偏差 50 > 10 → 奖金 0 → 总计 `15`
- 沟通组受托人：`B = 3×10 − 15 = 15`

- [ ] **Step 4: 在 `PlayerBot` 中挂上断言**

oTree 6 **没有** `PlayerBot.validate_round` 钩子，把断言写在那里等于死代码——测试会通过但什么都没验证。断言必须写在 `play_round` 内、最后一个 `yield` 之后（生成器被驱动到结束后继续执行到函数末尾，断言因此在流程中真实运行）。

```python
class PlayerBot(Bot):
    cases = ['normal', 'zero_send']

    def play_round(self):
        # 普通页面必须显式 yield，框架只自动处理 WaitPage
        yield Introduction
        zero_send = (self.case == 'zero_send')
        if self.player.is_communication:
            yield from communication_round(self)
        else:
            yield from baseline_round(self, zero_send=zero_send)
        check_round(self)
```

**必做：用变异探针证明断言真的在跑。** 把 `check_round` 中任意一条断言故意改错（例如把 `expect(bot.player.send_amount, 5)` 改成 `999`），运行 `otree test trust_baseline`，**必须**看到 `ExpectError` 且退出码非 0。确认后再改回。Task 2 已用此法验证过断言是活的。

- [ ] **Step 5: 恢复两个 session config**

把 `settings.py` 的 `SESSION_CONFIGS` 恢复为 Task 1 中的两个 config（`trust_baseline` 与 `trust_communication`）。

- [ ] **Step 6: 运行两个处理组的 Bot 测试**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
echo "--- 基线组 ---"
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline 2>&1 | grep -E "Bots completed session|MessageSend|MessageReveal|Traceback|Error"
echo "--- 沟通组 ---"
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_communication 2>&1 | grep -E "Bots completed session|MessageSend|MessageReveal|Traceback|Error"
```

Expected: 两条各打印一次 `Bots completed session`；**沟通组**流程中出现 `Submit .../MessageSend/` 与 `.../MessageReveal/`；**基线组**流程中这两类提交**完全不出现**。任何 `Traceback` 都表示失败。

- [ ] **Step 7: 验证边界情形 x=0**

> **⚠️ 与已加入的空提交 must-fail 用例冲突（Task 2 修复阶段实测发现）**
> `TrusteeDecision` 现在已有一条 `SubmissionMustFail(TrusteeDecision, {}, ...)` 空提交用例。**当 x=0 时该页不渲染任何表单**，而 `must_fail` 在无表单页面上必然抛错（期望失败却"成功"翻页）。因此 `zero_send` 情形下**必须跳过**这条 must-fail 用例。实现时请把 must-fail 放在 `max_return > 0` 的分支内，或按 case 条件跳过。
> 同样地，空提交用例本身也应在 `max_return > 0` 时才执行。

在 `tests.py` 增加一个独立 bot 情形（用 `cases` 机制）：

```python
class PlayerBot(Bot):
    cases = ['normal', 'zero_send']

    def play_round(self):
        if self.player.is_communication:
            yield from communication_round(self)
        else:
            yield from baseline_round(self, zero_send=(self.case == 'zero_send'))
```

并把 `baseline_round` 改为接受 `zero_send` 参数，投资者送 0 点、受托人不提交 `TrusteeDecision`（表单为空）：

```python
def baseline_round(bot, zero_send=False):
    yield Submission(ComprehensionCheck,
                     dict(comp_q1=10, comp_q2=12, comp_q3=12),
                     check_html=False)
    send = 0 if zero_send else 5
    if bot.player.role == C.INVESTOR_ROLE:
        yield Submission(BeliefElicit, dict(belief_return_pct=0),
                         check_html=False)
        yield Submission(InvestorDecision, dict(send_amount=send),
                         check_html=False)
    else:
        yield Submission(BeliefElicit, dict(belief_investor_send=5),
                         check_html=False)
    if bot.player.role == C.TRUSTEE_ROLE and not zero_send:
        yield Submission(TrusteeDecision, dict(return_amount=6),
                         check_html=False)
    elif bot.player.role == C.TRUSTEE_ROLE:
        yield TrusteeDecision   # x=0 时表单为空，直接翻页
    yield Results
```

- [ ] **Step 8: 重跑测试，覆盖两种情形**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
rm -f db.sqlite3
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline
```

Expected: 全部通过。x=0 情形下受托人 `return_amount` 为 0，其 `payoff` 为 0。

- [ ] **Step 9: 验证表单越界拦截**

在 `communication_round` 的受托人分支中，先尝试一次越界提交（`y = 3x + 1`），再提交合法值。`SubmissionMustFail` 断言该提交**必须被拒绝**——若 `TrusteeDecision.error_message` 的越界校验失效，oTree 会因"预期失败却成功"而报错：

```python
    if bot.player.role == C.TRUSTEE_ROLE:
        max_r = 3 * bot.player.group.investor.send_amount
        if max_r > 0:
            yield SubmissionMustFail(
                TrusteeDecision, dict(return_amount=max_r + 1), check_html=False
            )
        yield Submission(TrusteeDecision, dict(return_amount=15),
                         check_html=False)
```

注意 `max_r + 1` 可能超过 `IntegerField` 的静态 `max=30`，此时会被字段级校验拦下；同时 `error_message` 也做动态校验。两条防线任一生效都会使 `SubmissionMustFail` 通过——这属于预期行为（规格第 8 节要求"双重约束"）。

- [ ] **Step 10: 重跑并确认拦截生效**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
rm -f db.sqlite3
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline
```

Expected: 输出中出现 `SubmissionMustFail` 且测试通过（若越界提交未被拒，oTree 会抛错）。

- [ ] **Step 11: 检查点**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
ls trust_game/*.html | wc -l
```

Expected: `8`。

---

## Task 4: survey app（个体测量）

**Files:**
- Modify: `survey/__init__.py`（替换占位）
- Create: `survey/RiskPreference.html`
- Create: `survey/DictatorGame.html`
- Create: `survey/GeneralTrust.html`
- Create: `survey/Demographics.html`
- Modify: `survey/tests.py`

**Interfaces:**
- Consumes: 无（独立 app）
- Produces: `Player` 字段 `risk_choice, dictator_give, general_trust, gender, age, grade, major, econ_courses, prior_experience`

- [ ] **Step 1: 写 `survey/__init__.py`**

```python
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
    risk_choice = models.IntegerField(blank=True, min=0, max=5)

    dictator_give = models.IntegerField(
        min=0, max=C.DICTATOR_ENDOWMENT,
        label='请决定你送给对方的点数（0-10）：')

    general_trust = models.IntegerField(
        min=0, max=10, widget=widgets.RadioSelectHorizontal,
        label='总体来说，你认为大多数人是可以信任的（0=完全不同意，10=完全同意）')

    gender = models.StringField(choices=C.GENDERS, widget=widgets.RadioSelect,
                                label='你的性别：')
    age = models.IntegerField(min=16, max=60, label='你的年龄：')
    grade = models.StringField(choices=C.GRADES, widget=widgets.RadioSelect,
                               label='你的年级：')
    major = models.StringField(label='你的专业：', max_length=100)
    econ_courses = models.IntegerField(
        min=0, max=30, label='你已修读过的经济学课程数量：')
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
```

- [ ] **Step 2: 写 4 个模板**

`survey/RiskPreference.html`：

```html
{{ block title }}
    风险偏好
{{ endblock }}

{{ block content }}
<p>以下 5 行，请为每一行选择你更偏好的选项。</p>
{{ formfields }}
{{ next_button }}
{{ endblock }}
```

`survey/DictatorGame.html`：

```html
{{ block title }}
    分配决策
{{ endblock }}

{{ block content }}
<p>你获得 10 点。你可以决定将其中的一部分送给另一位匿名参与者，剩余部分归你所有。</p>
<p>对方无法拒绝或回应，你的决定即为最终结果。</p>
{{ formfields }}
{{ next_button }}
{{ endblock }}
```

`survey/GeneralTrust.html`：

```html
{{ block title }}
    一般信任
{{ endblock }}

{{ block content }}
{{ formfields }}
{{ next_button }}
{{ endblock }}
```

`survey/Demographics.html`：

```html
{{ block title }}
    背景信息
{{ endblock }}

{{ block content }}
{{ formfields }}
{{ next_button }}
{{ endblock }}
```

- [ ] **Step 3: 替换 `survey/tests.py`**

```python
from otree.api import *
from . import *


class PlayerBot(Bot):
    def play_round(self):
        # survey 的第 1 页 RiskPreference 本身有表单，故首个 yield 直接提交它，
        # 不需要额外的裸页面 yield（对比 trust_game：其首页 Introduction 无表单，
        # 必须先 yield Introduction 才能推进）。
        yield Submission(RiskPreference, dict(
            risk_row1=1, risk_row2=1, risk_row3=0, risk_row4=0, risk_row5=0,
        ), check_html=False)
        yield Submission(DictatorGame, dict(dictator_give=4), check_html=False)
        yield Submission(GeneralTrust, dict(general_trust=6), check_html=False)
        yield Submission(Demographics, dict(
            gender='男', age=20, grade='大三', major='经济学',
            econ_courses=3, prior_experience=False,
        ), check_html=False)

        # 断言写在 play_round 末尾（oTree 6 无 validate_round 钩子）
        expect(self.player.risk_choice, 2)
        expect(self.player.payoff, 6)   # 10 - 4
```

- [ ] **Step 4: 运行 survey 的测试**

`survey` 不是 session config 名，不能直接 `otree test survey`。两个 config 的 `app_sequence` 都是 `['trust_game', 'survey']`，所以跑 `trust_baseline` 会连 survey 一起跑完：

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline 2>&1 | tail -20
```

Expected: `Bots completed session`，survey 的 `risk_choice == 2`、`payoff == 6` 断言通过。

- [ ] **Step 5: 运行全项目测试（两个处理组）**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
echo "--- 基线组 ---"
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline 2>&1 | grep -cE "Bots completed session"
echo "--- 沟通组 ---"
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_communication 2>&1 | grep -cE "Bots completed session"
```

Expected: 两条各输出 `1`。此时完整 session（trust_game → survey）在两个处理组下都能端到端跑通。

- [ ] **Step 6: 检查点**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
ls survey/*.html | wc -l
```

Expected: `4`。

---

## Task 5: 模拟数据生成

**Files:**
- Create: `analysis/simulate_data.py`
- Create: `analysis/output/`（目录已在 Task 1 建立）

**Interfaces:**
- Consumes: `trust_game/payoffs.py` 的常量
- Produces: `analysis/output/simulated_data.csv`，列名与 oTree 导出同构，至少含：
  `participant_code, is_communication, role, send_amount, return_amount, return_ratio, belief_return_pct, belief_investor_send, promise_strength, investor_message_strength, belief_bonus, risk_choice, dictator_give, general_trust, gender, age, grade, econ_courses`

- [ ] **Step 1: 写 `analysis/simulate_data.py`**

```python
"""生成模拟实验数据。

⚠️ 本脚本产生的数据是模拟数据，不是真实被试数据。
   报告中引用这些结果时必须标注"模拟数据"。

生成原则（规格第 15.4 节）：按文献报告的效应量生成，而非随机噪声。
  - 基线组 x 均值约 5，右偏
  - 沟通组 x 均值提升约 0.5 个标准差
  - 返还比例随 x 递减（经典发现）
  - 承诺强度与返还比例正相关
  - 信念与 x 正相关，沟通提升信念
"""

import os

import numpy as np
import pandas as pd

SEED = 20260913
N_PER_CONDITION = 60          # 规格第 15.1 节：N=120，每组 60
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'output',
                           'simulated_data.csv')

ENDOWMENT = 10
MULTIPLIER = 3


def _truncated_normal(rng, mean, sd, low, high):
    return float(np.clip(rng.normal(mean, sd), low, high))


def generate():
    rng = np.random.default_rng(SEED)
    rows = []

    for is_comm in (0, 1):
        for pair_id in range(N_PER_CONDITION // 2):
            # --- 投资者 ---
            base_mean = 5.0
            if is_comm:
                base_mean += 0.5 * 2.5      # +0.5 SD，SD 取 2.5
            send = int(round(_truncated_normal(rng, base_mean, 2.5, 0, ENDOWMENT)))

            # 信念与送出额正相关，沟通组整体上移
            belief_shift = 8.0 if is_comm else 0.0
            belief = int(round(_truncated_normal(
                rng, 30 + 5 * send + belief_shift, 15, 0, 100)))

            # --- 受托人 ---
            # 返还比例随 x 递减；沟通提升比例；承诺强度正相关
            max_return = MULTIPLIER * send
            if max_return == 0:
                ratio = 0.0
                promise = int(rng.choice([0, 1]))
            else:
                ratio_mean = 0.45 - 0.015 * send + (0.10 if is_comm else 0.0)
                ratio = float(np.clip(rng.normal(ratio_mean, 0.25), 0.0, 1.0))
                promise = int(np.clip(
                    round(rng.normal(2 + 1.5 * ratio + (0.5 if is_comm else 0), 1.0)),
                    0, 4))
            return_amt = int(round(ratio * max_return))

            # --- 信念奖金（必须与 trust_game.payoffs.belief_bonus 的规则一致）---
            # x=0 时不发放奖金（规格第 7 节）
            if send <= 0:
                bonus = 0
            else:
                denom = MULTIPLIER * send
                bonus = 2 if abs(belief * denom - 100 * return_amt) <= 10 * denom else 0

            code_i = f'sim_{is_comm}_{pair_id}_A'
            code_t = f'sim_{is_comm}_{pair_id}_B'
            common = dict(
                is_communication=is_comm,
                investor_message_strength=int(np.clip(
                    round(rng.normal(2 + 0.3 * send + (1.0 if is_comm else 0), 1.0)), 0, 4)),
                general_trust=int(np.clip(round(rng.normal(6, 2)), 0, 10)),
                age=int(np.clip(round(rng.normal(20, 1.8)), 16, 60)),
                econ_courses=int(np.clip(round(rng.normal(3, 2)), 0, 30)),
            )

            rows.append(dict(
                participant_code=code_i, role='Investor',
                send_amount=send, return_amount=return_amt,
                return_ratio=return_amt / max_return if max_return else 0.0,
                belief_return_pct=belief, belief_investor_send=None,
                belief_bonus=bonus, promise_strength=None,
                risk_choice=int(np.clip(round(rng.normal(2.5, 1.3)), 0, 5)),
                dictator_give=int(np.clip(round(rng.normal(3.5, 2)), 0, 10)),
                gender=str(rng.choice(['男', '女'], p=[0.45, 0.55])),
                grade=str(rng.choice(['大一', '大二', '大三', '大四'])),
                prior_experience=bool(rng.random() < 0.2),
                **common,
            ))
            rows.append(dict(
                participant_code=code_t, role='Trustee',
                send_amount=send, return_amount=return_amt,
                return_ratio=return_amt / max_return if max_return else 0.0,
                belief_return_pct=None,
                belief_investor_send=int(np.clip(round(rng.normal(5, 2.5)), 0, 10)),
                belief_bonus=0, promise_strength=promise,
                risk_choice=int(np.clip(round(rng.normal(2.5, 1.3)), 0, 5)),
                dictator_give=int(np.clip(round(rng.normal(3.5, 2)), 0, 10)),
                gender=str(rng.choice(['男', '女'], p=[0.45, 0.55])),
                grade=str(rng.choice(['大一', '大二', '大三', '大四'])),
                prior_experience=bool(rng.random() < 0.2),
                **common,
            ))

    return pd.DataFrame(rows)


def main():
    df = generate()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
    print(f'已生成模拟数据：{OUTPUT_PATH}')
    print(f'  样本量：{len(df)}（投资者 {(df.role == "Investor").sum()}，'
          f'受托人 {(df.role == "Trustee").sum()}）')
    print(f'  沟通组：{(df.is_communication == 1).sum()}，基线组：{(df.is_communication == 0).sum()}')
    investors = df[df.role == 'Investor']
    print('  投资者送出金额均值（按处理组）：')
    print(investors.groupby('is_communication').send_amount.mean().to_string())
    print('  返还比例均值（按处理组，仅 x>0）：')
    pos = df[(df.role == 'Trustee') & (df.send_amount > 0)]
    print(pos.groupby('is_communication').return_ratio.mean().to_string())


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 运行生成脚本**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/python analysis/simulate_data.py
```

Expected: 打印样本量 120，沟通组 60、基线组 60；沟通组投资者的送出金额均值高于基线组；沟通组返还比例均值高于基线组。

- [ ] **Step 3: 验证数据形状与效应方向**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/python - <<'EOF'
import pandas as pd
df = pd.read_csv('analysis/output/simulated_data.csv')
assert len(df) == 120, len(df)
assert df.is_communication.value_counts().to_dict() == {1: 60, 0: 60}
inv = df[df.role == 'Investor']
t = inv[inv.is_communication == 1].send_amount.mean()
c = inv[inv.is_communication == 0].send_amount.mean()
print(f'沟通组 x 均值 = {t:.2f}，基线组 = {c:.2f}')
assert t > c, '沟通组送出金额应高于基线组'
tr = df[(df.role == 'Trustee') & (df.send_amount > 0)]
t2 = tr[tr.is_communication == 1].return_ratio.mean()
c2 = tr[tr.is_communication == 0].return_ratio.mean()
print(f'沟通组返还比例 = {t2:.3f}，基线组 = {c2:.3f}')
assert t2 > c2, '沟通组返还比例应高于基线组'
print('数据形状与效应方向验证通过')
EOF
```

Expected: `数据形状与效应方向验证通过`。

- [ ] **Step 4: 检查点**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
wc -l analysis/output/simulated_data.csv
```

Expected: `121`（表头 + 120 行）。

---

## Task 6: 统计分析管线

**Files:**
- Create: `analysis/analyze.py`

**Interfaces:**
- Consumes: Task 5 的 `analysis/output/simulated_data.csv`
- Produces: `analysis/output/` 下的
  `table_descriptives.csv`、`table_ttests.csv`、`table_regressions.csv`、
  `table_mediation.csv`、`table_correlation.csv`、
  `fig_send_amount.png`、`fig_return_ratio.png`、`fig_promise_ratio.png`、`fig_belief_send.png`

- [ ] **Step 1: 写 `analysis/analyze.py`**

```python
"""信任博弈实验的统计分析。

⚠️ 默认数据源为模拟数据，所有输出均标注为模拟。
   真实数据导出后，替换 --data 参数即可复用全部流程。

用法：
    python analysis/analyze.py
    python analysis/analyze.py --data path/to/real_data.csv
"""

import argparse
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
DEFAULT_DATA = os.path.join(OUTPUT_DIR, 'simulated_data.csv')

SIMULATION_NOTE = '【模拟数据，非真实被试结果】'

# 中文字体回退，避免图中文字变方块
plt.rcParams['font.sans-serif'] = [
    'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False


def load(path):
    df = pd.read_csv(path)
    df['treatment'] = df['is_communication'].astype(int)
    df['treatment_label'] = df['treatment'].map({1: '沟通组', 0: '基线组'})
    return df


def cohens_d(a, b):
    na, nb = len(a), len(b)
    pooled = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    if pooled == 0:
        return 0.0
    return (a.mean() - b.mean()) / pooled


def descriptives(df):
    investors = df[df.role == 'Investor']
    trustees = df[df.role == 'Trustee']
    rows = []
    for label, sub, col in [
        ('投资者送出金额 x', investors, 'send_amount'),
        ('投资者的信念（返还比例%）', investors, 'belief_return_pct'),
        ('受托人返还比例', trustees[trustees.send_amount > 0], 'return_ratio'),
        ('受托人返还金额 y', trustees, 'return_amount'),
        ('承诺强度（受托人）', trustees, 'promise_strength'),
        ('风险偏好（选确定金额的行数）', df, 'risk_choice'),
        ('利他（独裁者送出额）', df, 'dictator_give'),
        ('一般信任', df, 'general_trust'),
    ]:
        for t, glabel in [(1, '沟通组'), (0, '基线组')]:
            vals = sub[sub.treatment == t][col].dropna()
            rows.append(dict(
                变量=label, 组别=glabel, N=len(vals),
                均值=round(vals.mean(), 3) if len(vals) else np.nan,
                标准差=round(vals.std(ddof=1), 3) if len(vals) > 1 else np.nan,
                中位数=round(vals.median(), 3) if len(vals) else np.nan,
            ))
    return pd.DataFrame(rows)


def t_tests(df):
    investors = df[df.role == 'Investor']
    trustees = df[df.role == 'Trustee']
    tests = [
        ('H1: 送出金额 x', investors, 'send_amount', True),
        ('H2: 返还比例', trustees[trustees.send_amount > 0], 'return_ratio', False),
    ]
    rows = []
    for name, sub, col, primary in tests:
        a = sub[sub.treatment == 1][col].dropna()
        b = sub[sub.treatment == 0][col].dropna()
        t, p = stats.ttest_ind(a, b, equal_var=False)
        d = cohens_d(a, b)
        se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        diff = a.mean() - b.mean()
        ci = (diff - 1.96 * se, diff + 1.96 * se)
        rows.append(dict(
            假说=name, 沟通组均值=round(a.mean(), 3), 基线组均值=round(b.mean(), 3),
            差值=round(diff, 3),
            差值的95CI=f'[{ci[0]:.3f}, {ci[1]:.3f}]',
            t=round(t, 3), p=round(p, 4), Cohens_d=round(d, 3),
            主结果='是' if primary else '否',
        ))
    return pd.DataFrame(rows)


def regressions(df):
    trustees = df[(df.role == 'Trustee') & (df.send_amount > 0)].copy()
    full = df[df.role == 'Trustee'].copy()

    m1 = smf.ols('return_amount ~ treatment + send_amount', data=full).fit(cov_type='HC1')
    m2 = smf.ols('return_amount ~ treatment + send_amount', data=trustees).fit(cov_type='HC1')
    m3 = smf.ols('return_ratio ~ treatment + send_amount', data=trustees).fit(cov_type='HC1')

    rows = []
    for name, m in [('(a) 全样本，因变量 y', m1),
                    ('(b) 剔除 x=0，因变量 y', m2),
                    ('(c) 剔除 x=0，因变量 ratio', m3)]:
        rows.append(dict(
            模型=name,
            treatment=round(m.params['treatment'], 4),
            treatment_se=round(m.bse['treatment'], 4),
            treatment_p=round(m.pvalues['treatment'], 4),
            send_amount=round(m.params['send_amount'], 4),
            send_amount_p=round(m.pvalues['send_amount'], 4),
            N=int(m.nobs), R2=round(m.rsquared, 4),
        ))
    return pd.DataFrame(rows)


def mediation(df, n_boot=5000):
    """H4：treatment -> belief_return_pct -> send_amount，bootstrap 中介分析。"""
    sub = df[df.role == 'Investor'][['treatment', 'belief_return_pct', 'send_amount']].dropna()
    rng = np.random.default_rng(20260913)

    def indirect(data):
        a_fit = smf.ols('belief_return_pct ~ treatment', data=data).fit()
        b_fit = smf.ols('send_amount ~ treatment + belief_return_pct', data=data).fit()
        return a_fit.params['treatment'] * b_fit.params['belief_return_pct']

    total_fit = smf.ols('send_amount ~ treatment', data=sub).fit()
    direct_fit = smf.ols('send_amount ~ treatment + belief_return_pct', data=sub).fit()
    point = indirect(sub)

    boots = []
    for _ in range(n_boot):
        sample = sub.iloc[rng.integers(0, len(sub), len(sub))]
        try:
            boots.append(indirect(sample))
        except Exception:
            continue
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return pd.DataFrame([dict(
        路径='treatment → belief → send',
        总效应=round(total_fit.params['treatment'], 4),
        直接效应=round(direct_fit.params['treatment'], 4),
        间接效应=round(point, 4),
        间接效应95CI=f'[{lo:.4f}, {hi:.4f}]',
        bootstrap次数=len(boots),
    )])


def correlation(df):
    sub = df[df.role == 'Trustee'][['promise_strength', 'return_ratio', 'send_amount']].dropna()
    r, p = stats.pearsonr(sub.promise_strength, sub.return_ratio)
    rho, p_rho = stats.spearmanr(sub.promise_strength, sub.return_ratio)
    return pd.DataFrame([dict(
        假说='H5: 承诺强度 ~ 返还比例',
        Pearson_r=round(r, 4), Pearson_p=round(p, 6),
        Spearman_rho=round(rho, 4), Spearman_p=round(p_rho, 6),
        N=len(sub),
    )])


def figures(df, outdir):
    investors = df[df.role == 'Investor']
    trustees = df[df.role == 'Trustee']

    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.arange(-0.5, 11.5, 1)
    for t, label, color in [(0, '基线组', '#8c8c8c'), (1, '沟通组', '#1f77b4')]:
        ax.hist(investors[investors.treatment == t].send_amount, bins=bins,
                alpha=0.6, label=label, color=color)
    ax.set_xlabel('投资者送出金额 x（点）')
    ax.set_ylabel('人数')
    ax.set_title(f'投资者送出金额的分布\n{SIMULATION_NOTE}')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, 'fig_send_amount.png'), dpi=150)
    plt.close(fig)

    pos = trustees[trustees.send_amount > 0]
    fig, ax = plt.subplots(figsize=(7, 4))
    for t, label, color in [(0, '基线组', '#8c8c8c'), (1, '沟通组', '#1f77b4')]:
        ax.hist(pos[pos.treatment == t].return_ratio, bins=np.arange(0, 1.1, 0.1),
                alpha=0.6, label=label, color=color)
    ax.set_xlabel('返还比例 y/(3x)')
    ax.set_ylabel('人数')
    ax.set_title(f'受托人返还比例的分布（仅 x>0）\n{SIMULATION_NOTE}')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, 'fig_return_ratio.png'), dpi=150)
    plt.close(fig)

    sub = trustees.dropna(subset=['promise_strength', 'return_ratio'])
    sub = sub[sub.send_amount > 0]
    fig, ax = plt.subplots(figsize=(7, 4))
    means = sub.groupby('promise_strength').return_ratio.agg(['mean', 'sem'])
    ax.errorbar(means.index, means['mean'], yerr=1.96 * means['sem'],
                marker='o', capsize=4, color='#1f77b4')
    ax.set_xlabel('承诺强度（0-4）')
    ax.set_ylabel('平均返还比例')
    ax.set_title(f'承诺强度与返还比例\n{SIMULATION_NOTE}')
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, 'fig_promise_ratio.png'), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for t, label, color in [(0, '基线组', '#8c8c8c'), (1, '沟通组', '#1f77b4')]:
        s = investors[investors.treatment == t]
        ax.scatter(s.send_amount, s.belief_return_pct, alpha=0.5,
                   label=label, color=color)
    ax.set_xlabel('投资者送出金额 x（点）')
    ax.set_ylabel('预期返还比例（%）')
    ax.set_title(f'信念与送出金额\n{SIMULATION_NOTE}')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, 'fig_belief_send.png'), dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default=DEFAULT_DATA)
    args = parser.parse_args()

    is_simulated = os.path.abspath(args.data) == os.path.abspath(DEFAULT_DATA)
    note = SIMULATION_NOTE if is_simulated else '【真实数据】'

    df = load(args.data)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print('=' * 60)
    print(f'信任博弈实验分析  {note}')
    print(f'数据源：{args.data}    样本量：{len(df)}')
    print('=' * 60)

    desc = descriptives(df)
    desc.to_csv(os.path.join(OUTPUT_DIR, 'table_descriptives.csv'),
                index=False, encoding='utf-8-sig')
    print('\n【描述统计】'); print(desc.to_string(index=False))

    tt = t_tests(df)
    tt.to_csv(os.path.join(OUTPUT_DIR, 'table_ttests.csv'),
              index=False, encoding='utf-8-sig')
    print('\n【t 检验】'); print(tt.to_string(index=False))

    reg = regressions(df)
    reg.to_csv(os.path.join(OUTPUT_DIR, 'table_regressions.csv'),
               index=False, encoding='utf-8-sig')
    print('\n【回归】'); print(reg.to_string(index=False))

    med = mediation(df)
    med.to_csv(os.path.join(OUTPUT_DIR, 'table_mediation.csv'),
               index=False, encoding='utf-8-sig')
    print('\n【中介分析】'); print(med.to_string(index=False))

    cor = correlation(df)
    cor.to_csv(os.path.join(OUTPUT_DIR, 'table_correlation.csv'),
               index=False, encoding='utf-8-sig')
    print('\n【相关分析】'); print(cor.to_string(index=False))

    figures(df, OUTPUT_DIR)
    print(f'\n图表已输出至 {OUTPUT_DIR}')
    print(note)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 运行分析脚本**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/python analysis/analyze.py
```

Expected: 打印五张表，末尾出现 `图表已输出至`；无异常。

- [ ] **Step 3: 验证已知效应被检出**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/python - <<'EOF'
import pandas as pd
tt = pd.read_csv('analysis/output/table_ttests.csv')
h1 = tt[tt.假说.str.startswith('H1')].iloc[0]
h2 = tt[tt.假说.str.startswith('H2')].iloc[0]
print(f"H1 差值={h1.差值}, p={h1.p}, d={h1.Cohens_d}")
print(f"H2 差值={h2.差值}, p={h2.p}, d={h2.Cohens_d}")
assert h1.差值 > 0, 'H1 方向应为正'
assert h1.p < 0.05, 'H1 应显著'
assert h2.差值 > 0, 'H2 方向应为正'

reg = pd.read_csv('analysis/output/table_regressions.csv')
print(reg[['模型','treatment','treatment_p','N']].to_string(index=False))
assert reg.iloc[1].treatment > 0, 'H3 剔除 x=0 后处理组系数应为正'

med = pd.read_csv('analysis/output/table_mediation.csv')
print(med.to_string(index=False))
assert med.iloc[0].间接效应 > 0, 'H4 间接效应应为正'

cor = pd.read_csv('analysis/output/table_correlation.csv')
print(cor.to_string(index=False))
assert cor.iloc[0].Pearson_r > 0, 'H5 相关应为正'
print('全部假说方向与显著性验证通过')
EOF
```

Expected: `全部假说方向与显著性验证通过`。

- [ ] **Step 4: 验证图表文件已生成**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
ls -la analysis/output/*.png
```

Expected: 4 个 PNG 文件，大小均 > 10KB。

- [ ] **Step 5: 验证分析脚本对真实数据格式通用**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
cp analysis/output/simulated_data.csv analysis/output/_format_check.csv
/share/zrs2022150501010/miniconda3/envs/otree/bin/python analysis/analyze.py --data analysis/output/_format_check.csv 2>&1 | tail -3
rm -f analysis/output/_format_check.csv
```

Expected: 输出末尾为 `【真实数据】`（证明脚本能区分数据来源并相应标注）。

- [ ] **Step 6: 检查点**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
ls analysis/output/
```

Expected: 5 个 CSV + 4 个 PNG。

---

## Task 7: 实验报告

**Files:**
- Create: `实验报告.md`

**Interfaces:**
- Consumes: Task 6 的全部表格与图、Task 2–4 的实现细节、`docs/superpowers/specs/2026-09-13-trust-game-design.md`
- Produces: 交付物 1

- [ ] **Step 1: 从分析脚本导出真实数值供报告引用**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
for f in table_ttests table_regressions table_mediation table_correlation; do
  echo "########## $f ##########"
  cat analysis/output/$f.csv
done
```

**把输出中的数值抄进报告，不要凭记忆填写。**

- [ ] **Step 2: 撰写 `实验报告.md` 的前 6 节**

按规格第 16 节的结构撰写。第 1–6 节不含结果：

1. **摘要** — 研究问题、设计、样本、主要发现（基于模拟数据，须标注）、关键词
2. **引言与研究问题** — 信任的经济学意义、信任博弈范式的结构性背离、沟通的作用
3. **文献综述与理论框架** — Berg et al. (1995)、Charness & Dufwenberg (2006) 的二阶信念与内疚厌恶机制
4. **研究假说** — H1–H5 表格（复制规格第 3 节），含多重比较控制说明
5. **实验设计** — 处理组、博弈参数与收益推导、随机化、样本量功效分析（含 d≈0.51 的推导）
6. **实验实施** — oTree 6 实现、11 页流程表、操纵有效性保障、角色分配机制

- [ ] **Step 3: 撰写第 7 节（分析计划）**

复制规格第 15 节的预注册内容：主结果变量为 x、五个假说的检验方法、H3 的三模型稳健性规格、剔除规则、控制变量。

- [ ] **Step 4: 撰写第 8 节（模拟数据演示结果）**

**本节开头必须有以下醒目声明：**

```markdown
> ⚠️ **重要声明：本节全部结果基于模拟数据，不是真实被试的行为数据。**
> 模拟数据按文献报告的效应量生成，仅用于演示分析管线可以跑通、
> 表格与图表的格式符合报告要求。这些数值不得被解读为实证发现。
```

随后按 Step 1 导出的真实数值填写：描述统计表、t 检验表（H1/H2）、回归表（H3 三模型）、中介分析表（H4）、相关分析表（H5），并插入 4 张图：

```markdown
![投资者送出金额的分布](analysis/output/fig_send_amount.png)
```

每张图的图注都须以 `（模拟数据）` 结尾。

- [ ] **Step 5: 撰写第 9–11 节**

9. **讨论与局限** — 结论解读（限定在模拟框架内）、规格第 17 节的局限表逐条展开，另需额外声明：风险偏好为**假设性测量**（未激励），而其余测量均真实支付
10. **参考文献** — 规格第 19 节的四篇，另加 Holt & Laury (2002)
11. **附录** — 实验指导语全文（抄自 `Introduction.html`）、两侧消息选项表、问卷题项清单、oTree 项目运行说明

- [ ] **Step 6: 检查报告完整性与标注**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
echo "=== 章节数 ==="; grep -c "^## " 实验报告.md
echo "=== 模拟数据标注出现次数 ==="; grep -c "模拟数据" 实验报告.md
echo "=== 是否残留占位符 ==="; grep -n "TODO\|TBD\|待补\|XXX" 实验报告.md || echo "无占位符"
echo "=== 图片引用 ==="; grep -c "analysis/output/fig_" 实验报告.md
```

Expected: 章节数 ≥ 11；"模拟数据" 出现 ≥ 6 次；无占位符；图片引用 4 处。

---

## Task 8: README 与端到端验收

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: 全部前序任务
- Produces: 交付物说明文档

- [ ] **Step 1: 写 `README.md`**

须包含以下小节，命令中的路径全部使用绝对路径：

1. **项目简介** — 实验内容一句话、处理组设计一句话
2. **环境要求** — conda 环境 `otree`（Python 3.11.16，oTree 6.0.15）、依赖安装命令
3. **目录结构** — 文件树与各目录职责
4. **运行实验** — `otree devserver` 启动、浏览器访问 `http://localhost:8000`、用 admin 账号创建 session、两个 config 的说明
5. **运行测试** — `otree test trust_baseline`、`otree test trust_communication`（参数是 **session config 名**，不是 app 名）、以及纯函数单元测试命令
6. **导出数据** — admin 界面 Data → Export，或 `otree zip`；说明 CSV 中 `is_communication` 字段即处理组标识
7. **运行分析** — 模拟数据生成、分析脚本、真实数据替换方法（`--data` 参数）
8. **交付物清单** — 实验报告路径、代码路径、规格与计划路径
9. **注意事项** — 模拟数据不得当作实证结果；真实实验前需设置 `OTREE_ADMIN_PASSWORD` 环境变量；正式收集数据时应设置 `OTREE_PRODUCTION=1`

- [ ] **Step 2: 端到端验收——启动服务器**

后台启动开发服务器，用 HTTP 请求实际探测，而不是只读日志（原写法用 `|| true` 掩盖退出码，无法真正失败）：

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree devserver 8000 > /tmp/devserver_task8.log 2>&1 &
DEV_PID=$!
sleep 8
echo "--- /demo 探测 ---"
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/demo
echo "--- 日志中的 Traceback ---"
grep -c "Traceback" /tmp/devserver_task8.log || true
kill $DEV_PID 2>/dev/null || true
wait $DEV_PID 2>/dev/null || true
```

Expected: `/demo` 返回 `HTTP 200`；`grep -c Traceback` 输出 `0`。若 HTTP 码不是 200 或出现 Traceback，本步骤**失败**。

注意：`otree devserver` 会通过 PATH 重新 exec 裸 `otree` 命令，故需确保 `PATH` 含 `/share/zrs2022150501010/miniconda3/envs/otree/bin`。

- [ ] **Step 3: 端到端验收——完整测试套件**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
rm -f db.sqlite3
echo "=== 纯函数单元测试 ==="
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_payoffs trust_game.test_content 2>&1 | tail -3
echo "=== 基线组 session（含 trust_game + survey）==="
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline 2>&1 | grep -cE "Bots completed session"
echo "=== 沟通组 session（含 trust_game + survey）==="
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_communication 2>&1 | grep -cE "Bots completed session"
```

Expected: 单元测试 `OK`；两条各输出 **1**（每个 config 各完成一次完整 session，覆盖 trust_game 与 survey 两个 app）。

- [ ] **Step 4: 端到端验收——分析管线**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
/share/zrs2022150501010/miniconda3/envs/otree/bin/python analysis/simulate_data.py > /dev/null
/share/zrs2022150501010/miniconda3/envs/otree/bin/python analysis/analyze.py > /dev/null
echo "分析产物："
ls analysis/output/
```

Expected: 5 个 CSV + 4 个 PNG，共 9 个文件。

- [ ] **Step 5: 交付物清单核对**

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
for f in 实验报告.md README.md settings.py requirements.txt \
         trust_game/__init__.py trust_game/payoffs.py trust_game/content.py \
         trust_game/tests.py survey/__init__.py \
         analysis/simulate_data.py analysis/analyze.py \
         docs/superpowers/specs/2026-09-13-trust-game-design.md \
         docs/superpowers/plans/2026-09-13-trust-game-implementation.md; do
  [ -f "$f" ] && echo "✓ $f" || echo "✗ 缺失 $f"
done
echo "模板文件数：$(ls trust_game/*.html survey/*.html | wc -l)（应为 12）"
```

Expected: 全部 `✓`，模板 12 个。

- [ ] **Step 6: 最终检查点**

对照规格第 18 节交付物清单逐项确认，并在回复中报告：
- 测试通过情况（实际数字）
- 分析产物清单
- 任何已知未完成项或偏差

---

## 自审记录

**规格覆盖检查：** 规格第 3 节（假说 H1–H5）→ Task 6 全部分析；第 4 节（设计）→ Task 1 的两个 config；第 5 节（博弈与收益）→ Task 1 的 `payoffs.py` + Task 2 结算；第 6 节（沟通操纵）→ Task 3；第 7 节（信念引出）→ Task 2 的 `BeliefElicit` 与 `ResultsWaitPage`；第 8 节（页面流程）→ Task 2/3 的 `page_sequence`；第 9 节（数据模型）→ Task 2/3/4 字段；第 10 节（survey）→ Task 4；第 11 节（报酬）→ Task 1 `settings.py` + Task 4 独裁者博弈；第 12 节（oTree 6 约束）→ Global Constraints；第 13 节（结构）→ 文件结构表；第 14 节（测试）→ Task 2/3/4 的 bot 测试 + Task 1 单元测试；第 15 节（分析计划）→ Task 6；第 16 节（报告结构）→ Task 7；第 17 节（局限）→ Task 7 Step 5；第 18 节（交付物）→ Task 8 Step 5。无遗漏。

**类型一致性检查：** `content.strength_of(messages, label)` 在 Task 1 定义、Task 2 的 `MessageSend.before_next_page` 调用，签名一致；`payoffs.belief_bonus(belief_return_pct, send_amount, return_amount)` 在 Task 1 定义、Task 2 的 `ResultsWaitPage` 调用，参数顺序一致；`has_communication(player)` 在 Task 2 定义、Task 3 的 `MessageSend/MessageWaitPage/MessageReveal.is_displayed` 调用，签名一致；`Group.investor` / `Group.trustee` 属性在 Task 2 定义并在同任务内使用。

**断言数值的推导已全部锁定：** 所有 `expect()` 的字面值均由收益公式推导得出并写在计划中，无"实测后再填"的悬空值。两处关键推导：

- 基线组投资者（x=5, y=6, 信念 50%）：`A = 10−5+6 = 11`，实际比例 `6/15 = 40%`，偏差恰好 10 个百分点 → 奖金 2 → 总计 **13**。该用例**刻意覆盖信念奖金的边界含等号行为**。
- 沟通组投资者（x=10, y=15, 信念 0%）：`A = 10−10+15 = 15`，实际比例 50%，偏差 50 > 10 → 奖金 0 → 总计 **15**。

**计划中已在实地验证后才写入的 oTree 6 行为（非假设）：**
1. `tests.py` 必须同时写 `from otree.api import *` 与 `from . import *`，否则页面类名不可见。
2. `otree test` 依赖 `requests` 包，未安装时报 "You need to install requests to run bots" 并静默退出（退出码 0）。故 Task 1 Step 2 必须先装 `requests`。
3. `error_message` 内对模型的修改**会持久化**——实测：答错一次后 `attempts == 1`，答对后累计为 `2`。故 `ComprehensionCheck` 的计数方案成立。
4. `SubmissionMustFail` 需要对应页面模板存在，否则抛 `TemplateLoadError`。
5. 修改 app 代码后若沿用旧 `db.sqlite3`，oTree 会提示"Please delete your database"，所有测试命令前均须 `rm -f db.sqlite3`。

**一处经穷举后推翻的假设（如实记录）：** 计划初稿曾假设信念奖金的浮点实现存在边界舍入错误。经穷举全部 17776 组 `(x, y, belief)` 输入，浮点实现与精确有理数解的判定**完全一致，零处不符**。故计划中不将其描述为 bug 修复；改用整数比较实现的理由是**正确性由构造保证、不依赖浮点行为**，因为该函数决定真实金钱收益。此理由已如实写在 `payoffs.belief_bonus` 的 docstring 中。

**技能流程偏差声明：** writing-plans 技能要求每任务以 git commit 收尾，但用户明确约定本目录不使用 git，故所有提交步骤替换为"验证并记录"检查点。

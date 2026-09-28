"""`analysis/analyze.py` 的回归测试（复审 I1：把值级守卫搬进仓库）。

运行（项目根目录）：

    python -m unittest analysis.test_analyze -v

⚠️ 本文件是**规格 §18 交付物清单之外的有意新增**。理由：I1 要求的值级守卫原先只
存在于 `.superpowers/sdd/task-6-verify.py`，而 `.superpowers/` 被 `.gitignore`
排除——一个无法入库、未来修改者拿不到的守卫提供不了任何保护。本文件把该守卫变成
可提交、可运行的测试。

为什么带一个空的 `analysis/__init__.py`（本机 Python 3.11.16 实测）：
  - `python -m unittest analysis.test_analyze -v`：有没有它都能跑（命名空间包）；
  - `python -m unittest discover -s analysis -t .`：**没有它直接 ImportError**
    （Start directory is not importable）；
  - `python -m unittest discover`（全仓）：没有它时**静默跳过** `analysis/`（只跑
    24 个其他测试），有它时才跑到本文件（30 个）。
  最后一条正是本项目最忌讳的「静默不发生」，故保留这个空文件。

守卫思路（为什么不是「跑通就行」）：
  `load()` 对 oTree 宽表导出走的是「按 app 定点取字段」的分支（FIELD_SOURCE），
  对扁平格式（模拟数据）走早退分支。只断言「扁平格式下算得对」不会覆盖前者。
  故这里**程序化构造**一份忠实宽表夹具——表头从 `otree/export.py` 的 specs 推导、
  app 清单取自 `settings.py`、自定义字段扫各 app 自己的源码——**刻意不复用
  `analyze.py` 的 FIELD_SOURCE**（借用被测映射的夹具抓不到映射错误），再断言
  `load(夹具)` 与 `load(simulated_data.csv)` 给出**逐位相同**的配对帧与 H3 系数。
  另外把「把 FIELD_SOURCE 指错 app 必须报错」也做成测试：只断言happy path
  无法证明守卫真的在守。
"""

import ast
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
DATA_PATH = os.path.join(HERE, 'output', 'simulated_data.csv')

# 内建字段的真实定义处：otree/export.py 的 specs（见该文件 _get_table_fields）
OTREE_EXPORT_PY = os.path.join(
    os.path.dirname(importlib.util.find_spec('otree').origin),
    'export.py',
)
SETTINGS_PY = os.path.join(PROJECT_ROOT, 'settings.py')

GAME_APP = 'trust_game'          # 博弈字段的唯一来源
SURVEY_APP = 'survey'            # 问卷字段的唯一来源


def _load_analyze_module():
    """按路径加载被测模块（不依赖 cwd，也不依赖 analysis 是否为包）。"""
    path = os.path.join(HERE, 'analyze.py')
    spec = importlib.util.spec_from_file_location('analyze_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def otree_builtin_specs():
    """从 otree/export.py 的 specs 解析出每个模型的内建字段（ast，不手抄）。

    真实定义（export.py `_get_table_fields`）：
        specs = [('player', BasePlayer, ['id_in_group', 'role'] + (['payoff'] if ... )),
                 ('group', BaseGroup, ['id_in_subsession']),
                 ('subsession', BaseSubsession, ['round_number'])]
    """
    with open(OTREE_EXPORT_PY, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, 'id', None) == 'specs' for t in node.targets):
            specs = []
            for elt in node.value.elts:
                model = elt.elts[0].value

                def collect(n, names):
                    if isinstance(n, ast.List):
                        names.extend(e.value for e in n.elts)
                    elif isinstance(n, ast.BinOp):
                        collect(n.left, names)
                        collect(n.right, names)
                    elif isinstance(n, ast.IfExp):   # payoff 受 AUTO_TABULATE 开关控制
                        collect(n.body, names)
                        collect(n.orelse, names)
                names = []
                collect(elt.elts[2], names)
                specs.append((model, names))
            return specs
    raise AssertionError('未能在 otree/export.py 中找到 specs')


def app_sequence():
    """从 settings.py 的 SESSION_CONFIGS 取 app 顺序（ast，不 import 配置）。"""
    with open(SETTINGS_PY, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == 'app_sequence':
            return [e.value for e in node.value.elts]
    raise AssertionError('未能在 settings.py 中找到 app_sequence')


def app_custom_fields(app):
    """扫 app 自己的源码取字段名（不引用 analyze.py 的任何映射，避免循环论证）。"""
    with open(os.path.join(PROJECT_ROOT, app, '__init__.py'),
              encoding='utf-8') as fh:
        # re.M：字段定义在类体里逐行缩进，没有 MULTILINE 时 `^` 只匹配串首
        return re.findall(r'^\s+(\w+)\s*=\s*models\.\w+Field', fh.read(), re.M)


def build_wide_fixture(sim, apps, builtins):
    """把扁平格式的模拟数据塑造成 oTree 宽表结构。

    逐行=逐被试；每个 app 各一份 `{app}.1.{model}.{field}` 列表头。

    取值形状按**真实导出实测**（`otree test --export`）：
      - `survey` 是单人 app → 其 player.role 全为空、group.id_in_subsession 恒为 1；
      - `trust_game` 的 role 为 Investor/Trustee、group.id_in_subsession 为真实组号。
    正是这个「同名不同义」让 FIELD_SOURCE 的 app 定向成为必需：取错 app 会静默塌成
    一对/空角色，所以夹具必须如实复现它，否则守卫是假的。
    """
    pair_index = sim.pair_id.astype('category').cat.codes + 1
    wide = pd.DataFrame(index=sim.index)
    wide['participant.code'] = sim.participant_code.values
    wide['session.code'] = 'simtest'
    for app in apps:
        for model, names in builtins:
            for field in names:
                col = f'{app}.1.{model}.{field}'
                if model == 'player' and field == 'role':
                    wide[col] = sim.role.values if app == GAME_APP else np.nan
                elif model == 'player' and field == 'id_in_group':
                    # 未被本管线消费的列：填一个形状合理的占位值即可
                    wide[col] = sim.role.map({'Investor': 1, 'Trustee': 2}).values
                elif model == 'group' and field == 'id_in_subsession':
                    wide[col] = pair_index.values if app == GAME_APP else 1
                elif model == 'subsession' and field == 'round_number':
                    wide[col] = 1
                else:
                    wide[col] = 0
        for field in app_custom_fields(app):
            wide[f'{app}.1.player.{field}'] = (
                sim[field].values if field in sim.columns else np.nan)
    return wide


@unittest.skipUnless(os.path.exists(DATA_PATH),
                     '需要 analysis/output/simulated_data.csv；'
                     '请先在项目根运行 python analysis/simulate_data.py')
class TestWideExportValueGuard(unittest.TestCase):
    """I1：忠实宽表夹具上，load() 必须与扁平模拟数据逐位一致。"""

    @classmethod
    def setUpClass(cls):
        cls.analyze = _load_analyze_module()
        cls.raw = pd.read_csv(DATA_PATH, float_precision='round_trip')
        cls.raw['pair_id'] = cls.raw.participant_code.str.rsplit('_', n=1).str[0]
        cls.builtins = otree_builtin_specs()
        cls.apps = app_sequence()

        cls.tmpdir = tempfile.mkdtemp(prefix='task6_wide_fixture_')
        cls.addClassCleanup(shutil.rmtree, cls.tmpdir, ignore_errors=True)
        cls.fixture_path = os.path.join(cls.tmpdir, 'wide_fixture.csv')
        cls.fixture = build_wide_fixture(cls.raw, cls.apps, cls.builtins)
        cls.fixture.to_csv(cls.fixture_path, index=False, encoding='utf-8-sig')

        cls.pairs_flat = cls.analyze.load(DATA_PATH)[1]
        cls.pairs_wide = cls.analyze.load(cls.fixture_path)[1]

    # ---- 夹具本身的忠实性：不忠实的话下面的守卫就是假的 ----

    def test_fixture_header_covers_otree_specs(self):
        """表头必须覆盖 export.py specs 里每个 app 的全部内建字段。"""
        expected = [f'{app}.1.{model}.{field}'
                    for app in self.apps
                    for model, names in self.builtins
                    for field in names]
        missing = [c for c in expected if c not in self.fixture.columns]
        self.assertEqual(missing, [])
        self.assertGreaterEqual(len(self.fixture.columns), 2 * len(expected))

    def test_fixture_mirrors_real_export_value_shapes(self):
        """两个 app 的同名字段必须「同名不同义」，否则这个夹具抓不到错映射。"""
        self.assertTrue(self.fixture['survey.1.player.role'].isna().all(),
                        'survey 是单人 app：其 role 在真实导出里全为空')
        self.assertEqual(
            self.fixture['survey.1.group.id_in_subsession'].nunique(), 1,
            'survey 是单人 app：其 group.id_in_subsession 在真实导出里恒为 1')
        self.assertEqual(
            set(self.fixture['trust_game.1.player.role'].dropna()),
            {'Investor', 'Trustee'})
        self.assertEqual(
            self.fixture['trust_game.1.group.id_in_subsession'].nunique(),
            len(self.raw) // 2, 'trust_game 的 group.id_in_subsession 应是真实组号')

    # ---- 值级守卫（I1 的核心断言）----

    def test_pairs_bit_identical_to_flat_format(self):
        self.assertEqual(len(self.pairs_wide), len(self.pairs_flat))
        self.assertEqual(len(self.pairs_flat), len(self.raw) // 2)
        for col in ('x', 'y', 'return_ratio', 'treatment'):
            got = np.sort(self.pairs_wide[col].to_numpy(dtype=float))
            exp = np.sort(self.pairs_flat[col].to_numpy(dtype=float))
            self.assertTrue(np.array_equal(got, exp),
                            f'{col} 在宽表夹具与模拟数据上不是逐位相等')

    def test_h3_treatment_coefficients_bit_identical(self):
        reg_wide = self.analyze.regressions(self.pairs_wide)
        reg_flat = self.analyze.regressions(self.pairs_flat)
        self.assertTrue(reg_wide.equals(reg_flat),
                        'H3 四模型整表不等：\n'
                        f'{reg_wide.to_string()}\n{reg_flat.to_string()}')
        for i in range(len(reg_flat)):
            self.assertEqual(reg_wide.iloc[i].treatment,
                             reg_flat.iloc[i].treatment,
                             f'{reg_wide.iloc[i].模型} 的 treatment 系数不逐位相等')
        # 四个模型都必须在合并帧上真实估计出来（有限系数、N 正确）
        self.assertEqual(reg_flat.N.tolist(), [60, 55, 55, 55])
        self.assertTrue(np.isfinite(reg_flat.treatment.astype(float)).all())

    # ---- 突变守卫：映射指错 app 必须报错，而不是静默算错 ----

    def test_misdirected_field_source_is_rejected(self):
        """把 FIELD_SOURCE 指向错误的 app，load() 必须中止。

        分工：内建字段（role / id_in_subsession）由「每对 2 行 2 角色」的配对校验
        拦下；自定义字段由 REQUIRED_FIELDS 拦下。若哪一个不再报错，说明对应的守卫
        被弱化或夹具不再忠实。
        """
        cases = [('role', SURVEY_APP), ('id_in_subsession', SURVEY_APP),
                 ('send_amount', SURVEY_APP), ('risk_choice', GAME_APP)]
        for field, wrong_app in cases:
            with self.subTest(field=field, wrong_app=wrong_app):
                saved = self.analyze.FIELD_SOURCE[field]
                self.analyze.FIELD_SOURCE[field] = wrong_app
                try:
                    with self.assertRaises(SystemExit) as ctx:
                        self.analyze.load(self.fixture_path)
                    self.assertTrue(str(ctx.exception).strip(),
                                    '中止时必须给出可读原因')
                finally:
                    self.analyze.FIELD_SOURCE[field] = saved

    def test_field_source_restored_after_mutation(self):
        """突变测试不得留下被改过的模块状态（否则后续测试会假通过）。"""
        for field, app in [('role', GAME_APP), ('id_in_subsession', GAME_APP),
                           ('send_amount', GAME_APP), ('risk_choice', SURVEY_APP)]:
            self.assertEqual(self.analyze.FIELD_SOURCE[field], app)
        pairs_again = self.analyze.load(self.fixture_path)[1]
        self.assertTrue(np.array_equal(
            np.sort(pairs_again.x.to_numpy(dtype=float)),
            np.sort(self.pairs_flat.x.to_numpy(dtype=float))))


@unittest.skipUnless(os.path.exists(DATA_PATH),
                     '需要 analysis/output/simulated_data.csv；'
                     '请先在项目根运行 python analysis/simulate_data.py')
class TestSourceLabelBackstop(unittest.TestCase):
    """I1 的另一半：按路径推断的「数据来源」标注必须与文件内容交叉核对。

    路径推断对**放错位置的拷贝**无感，两个方向都会产出「标注与来源相反」的产物，
    且产物本身看不出异常：
      - 真实导出放到默认路径 → 整份产物被标成【模拟数据】；
      - 模拟数据拷到别处传给 --data → 整份产物被标成【真实数据】。
    两个方向都做成用例。另外把「无编号列时只能依赖路径」这一**已知边界**也钉住，
    免得读者以为这个守卫能覆盖那个情形（不夸大覆盖范围）。

    注意：需要「默认路径 + 内容不像模拟」这一情形的用例，一律通过显式传入
    is_simulated=True 来构造，**不往默认路径写任何文件**——那是模拟数据集本身，
    不能被测试改写。
    """

    @classmethod
    def setUpClass(cls):
        cls.analyze = _load_analyze_module()
        cls.raw = pd.read_csv(DATA_PATH, float_precision='round_trip')

    def _rewritten_codes_file(self, tmpdir, name, rewrite):
        """把模拟数据的被试编号按 rewrite 改写后另存，模拟「内容不同的数据」。"""
        path = os.path.join(tmpdir, name)
        frame = self.raw.copy()
        frame['participant_code'] = frame.participant_code.map(rewrite)
        frame.to_csv(path, index=False, encoding='utf-8-sig')
        return path

    def test_simulated_data_at_default_path_is_accepted(self):
        """本仓库的常态：默认路径 + 模拟内容，不得中止。"""
        msg = self.analyze.check_source_label(DATA_PATH, is_simulated=True)
        self.assertIn(self.analyze.SIMULATED_CODE_PREFIX, msg)

    def test_simulated_copy_outside_default_path_is_rejected(self):
        """模拟数据被拷到别处再传给 --data：会被标成【真实数据】，必须中止。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            copy_path = os.path.join(tmpdir, 'all_apps_wide.csv')
            shutil.copyfile(DATA_PATH, copy_path)
            with self.assertRaises(SystemExit) as ctx:
                self.analyze.check_source_label(copy_path, is_simulated=False)
            self.assertIn(self.analyze.SIMULATED_CODE_PREFIX, str(ctx.exception))

    def test_real_looking_data_at_default_path_is_rejected(self):
        """真实导出落到默认路径：会被标成【模拟数据】，必须中止。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake = self._rewritten_codes_file(
                tmpdir, 'real_like.csv', lambda code: code.replace('sim_', 'p_'))
            with self.assertRaises(SystemExit) as ctx:
                self.analyze.check_source_label(fake, is_simulated=True)
            self.assertIn('sim_', str(ctx.exception))

    def test_mixed_codes_are_rejected_under_either_label(self):
        """真实数据与模拟数据混在一起：两个方向的标注都不可信，必须中止。"""
        # 编号形如 sim_{处理组}_{配对号}_{A|B}（处理组 0/1 各 30 对）：
        # 处理组 0 的编号保持带前缀，处理组 1 的改写成「真实」编号，
        # 于是得到一份两半来源不同的数据
        prefix = self.analyze.SIMULATED_CODE_PREFIX
        for is_simulated in (True, False):
            with self.subTest(is_simulated=is_simulated):
                with tempfile.TemporaryDirectory() as tmpdir:
                    mixed = self._rewritten_codes_file(
                        tmpdir, 'mixed.csv',
                        lambda code: code
                        if code.rsplit('_', 2)[0].endswith('_0')
                        else code.replace(prefix, 'p_', 1))
                    with self.assertRaises(SystemExit) as ctx:
                        self.analyze.check_source_label(mixed, is_simulated=is_simulated)
                    self.assertIn('混在了一起', str(ctx.exception))

    def test_main_wires_the_guard_before_reading_data(self):
        """端到端接线：main() 必须真的调用这道核对，且发生在读数据**之前**。

        没有这一条，把 check_source_label 的调用从 main() 里删掉不会有任何测试
        失败——守卫就成了死代码（本项目最忌讳的「静默不发生」）。用 load 被打桩
        成哨兵异常来证明：核对通过时确实走到了 load，核对不通过时根本走不到。
        两个方向各跑一次，且把 DEFAULT_DATA 指向临时文件，绝不碰真实产物目录。
        """
        class _ReachedLoad(Exception):
            """哨兵：main() 走到了 load()（即核对已通过）。"""

        with tempfile.TemporaryDirectory() as tmpdir:
            simulated_default = os.path.join(tmpdir, 'simulated_data.csv')
            shutil.copyfile(DATA_PATH, simulated_default)
            fake_default = self._rewritten_codes_file(
                tmpdir, 'not_simulated.csv',
                lambda code: code.replace('sim_', 'p_', 1))
            saved = self.analyze.DEFAULT_DATA
            try:
                with mock.patch.object(sys, 'argv', ['analyze.py']):
                    for default, expected in [
                        # 默认路径 + 模拟内容 → 放行（走到 load）
                        (simulated_default, _ReachedLoad),
                        # 默认路径 + 内容不像模拟 → 在读数据前中止
                        (fake_default, SystemExit),
                    ]:
                        with self.subTest(default=os.path.basename(default)):
                            self.analyze.DEFAULT_DATA = default
                            with mock.patch.object(self.analyze, 'load',
                                                   side_effect=_ReachedLoad):
                                with self.assertRaises(expected):
                                    self.analyze.main()
            finally:
                self.analyze.DEFAULT_DATA = saved

    def test_missing_code_column_is_reported_not_aborted(self):
        """**已知边界**：没有编号列时内容无从判断——不中止，但必须打印出来。

        这一条钉住的是「守卫覆盖到哪里为止」：此时标注仍只由路径决定，
        守卫提供不了任何独立证据。
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'no_codes.csv')
            (self.raw.drop(columns=['participant_code'])
             .to_csv(path, index=False, encoding='utf-8-sig'))
            msg = self.analyze.check_source_label(path, is_simulated=False)
            self.assertIn('无法据内容核对来源', msg)


if __name__ == '__main__':
    unittest.main(verbosity=2)

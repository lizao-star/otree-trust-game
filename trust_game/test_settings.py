"""settings.py 的 session config 守卫。

运行（项目根目录）：
    python -m unittest trust_game.test_settings -v

⚠️ 本文件守两件事：

1. **演示开关不得落到真实 config 上。** `use_browser_bots=True` 的语义是「本会话
   的全体被试由 bot 驱动」。它一旦出现在真实 config 上，被试拿到的每一页都会在
   渲染后被 JS 自动提交（otree/views/abstract.py:483-513），被试还没读完题目就
   翻页；而数据照样写库、otree test 照样全绿。这是不会自己报出来的错误：它只在
   收完数据后表现为一片无意义的常量。

2. **config 名与两个处理组键必须自洽。** 名字里的 `b_to_a` / `a_to_b` / `none` /
   `both` 是给人读的，真正决定流程的是 `investor_sends_message` 与
   `trustee_sends_message` 两个键。两者若各说各话（例如把 `trust_a_to_b` 的两个
   键写反），跑出来的会话会与名字暗示的完全相反，而**没有任何运行时报错**——四个
   config 都照样跑通，只是数据和结论整个反过来。CONDITIONS 是这两者的唯一登记
   处，下面逐条钉死。

为什么按文件路径 importlib 加载 settings.py，而不是 `import settings`：
    被测对象是仓库里这个文件的**实际取值**；用 spec_from_file_location 读它，
    既不依赖当前工作目录（discover 的顶层目录由 -t 决定），也不向 sys.modules
    注册一个顶层的 settings 模块。
"""

import importlib.util
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PY = PROJECT_ROOT / 'settings.py'

INVESTOR_KEY = 'investor_sends_message'
TRUSTEE_KEY = 'trustee_sends_message'

# 唯一的处理组事实表：真实 config 名 → (A 能否发消息, B 能否发消息)。
#
# 四个格子即 2×2 析因：① 无沟通 ② 仅 B→A（承诺） ③ 仅 A→B（意向） ④ 双向。
# 改这里的映射即改守卫的适用范围；settings.py 里多一个或少一个 config，
# test_config_names_match_conditions_exactly 会立刻失败。
CONDITIONS = {
    'trust_none':   (False, False),
    'trust_b_to_a': (False, True),
    'trust_a_to_b': (True, False),
    'trust_both':   (True, True),
}


def load_settings():
    """按文件路径加载项目根的 settings.py。"""
    spec = importlib.util.spec_from_file_location('project_settings', SETTINGS_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configs_by_name():
    return {c['name']: c for c in load_settings().SESSION_CONFIGS}


class TestDemoConfigs(unittest.TestCase):

    def setUp(self):
        self.configs = configs_by_name()

    def config(self, name):
        self.assertIn(name, self.configs,
                      f'settings.py 中缺少 session config：{name}')
        return self.configs[name]

    def demo_name(self, real_name):
        return real_name + '_bots'

    # ---- 名字集合 ----

    def test_config_names_match_conditions_exactly(self):
        """config 名集合必须恰好是 CONDITIONS 的四个真名 + 四个演示名。

        断言写成**集合相等**而不是「逐个检查以 _bots 结尾的名字」：后者有个已
        实测到的空洞——把 config 改名成 trust_both_v2 之后，它不再以 _bots 结尾，
        于是**根本不会进入被检查的集合**，测试照样全绿。集合相等把「改名」和
        「少登记」都变成失败。
        """
        expected = set(CONDITIONS) | {self.demo_name(n) for n in CONDITIONS}
        self.assertEqual(
            set(self.configs), expected,
            'settings.py 里的 config 名必须恰好是 CONDITIONS 登记的四个真实 config'
            ' 与它们的 _bots 演示版。少了/多了/改了名，本文件与 tests.py 的核对'
            '都会失去覆盖对象',
        )

    def test_real_configs_must_not_use_browser_bots(self):
        """真实 config 绝不可带 use_browser_bots：否则真实被试会被 bot 顶替。"""
        for name in CONDITIONS:
            value = self.config(name).get('use_browser_bots', False)
            # 缺键与显式 False 都必须通过。用 assertIs 而非真值判断，
            # 使 None / 0 / '' 这些「碰巧为假」的值同样被拦下——
            # 本仓库已有把 0 误当缺失值的先例。
            self.assertIs(
                value, False,
                f'{name} 的 use_browser_bots 必须是 False 或缺键，实际是 {value!r}；'
                '真实 config 带该开关会让真实被试的页面被自动提交',
            )

    def test_demo_configs_use_browser_bots(self):
        """演示 config 必须带 use_browser_bots：单步控制台全靠它。"""
        for real_name in CONDITIONS:
            demo_name = self.demo_name(real_name)
            value = self.config(demo_name).get('use_browser_bots', False)
            self.assertIs(
                value, True,
                f'{demo_name} 的 use_browser_bots 必须是 True，实际是 {value!r}；'
                '否则该会话不会由 bot 驱动，控制台无对象可驱动',
            )

    # ---- 两个处理组键 ----

    def test_real_configs_carry_the_expected_two_flags(self):
        """每个真实 config 的两个键必须**逐值**等于 CONDITIONS 的登记。

        这是本文件存在的首要理由（见模块 docstring 第 2 条）：名字与键不一致
        时四个 config 都会正常跑通，只是行为与名字相反，没有任何运行时报错。
        """
        for name, (investor_sends, trustee_sends) in CONDITIONS.items():
            cfg = self.config(name)
            for key, expected in ((INVESTOR_KEY, investor_sends),
                                  (TRUSTEE_KEY, trustee_sends)):
                self.assertIn(
                    key, cfg,
                    f'{name} 缺少 {key} 键。**不许**靠 get(key, False) 的默认值'
                    '蒙混——缺键会让「没登记」与「登记为 False」同形，'
                    '本守卫就失去了区分能力',
                )
                actual = cfg[key]
                self.assertIs(
                    actual, expected,
                    f'{name} 的 {key} 应为 {expected!r}，实际是 {actual!r}。'
                    '用 assertIs 而非相等比较：None 与 False 在真值判断下同形，'
                    '而对页面显示判定的后果不同',
                )

    def test_demo_configs_mirror_the_two_flags(self):
        """演示 config 的两个键必须与对应真实 config 逐值相同。

        否则单步控制台上看到的流程不是真实实验的流程——而演示的唯一用途
        就是观察真实流程。
        """
        for name in CONDITIONS:
            real = self.config(name)
            demo = self.config(self.demo_name(name))
            for key in (INVESTOR_KEY, TRUSTEE_KEY):
                self.assertIn(key, real,
                              f'{name} 缺少 {key} 键，无法作对齐基准')
                self.assertIs(
                    demo[key], real[key],
                    f'{self.demo_name(name)} 的 {key} 与 {name} 不一致',
                )

    def test_demo_configs_mirror_app_sequence(self):
        for name in CONDITIONS:
            demo_name = self.demo_name(name)
            self.assertEqual(
                self.config(demo_name)['app_sequence'],
                self.config(name)['app_sequence'],
                f'{demo_name} 的 app_sequence 必须与 {name} 相同，'
                '否则演示覆盖不到调查问卷',
            )

    # ---- 其余 ----

    def test_display_names_are_distinct(self):
        """显示名不得重复：演示页上四个 config 靠它区分，重名等于分不清。"""
        labels = [c['display_name'] for c in self.configs.values()]
        self.assertEqual(len(labels), len(set(labels)),
                         'display_name 有重复：' + '、'.join(
                             sorted({x for x in labels if labels.count(x) > 1})))

    def test_demo_num_participants_within_grid_view_limits(self):
        """人数必须落在网格视图限额内，否则演示页上 Grid view 不可用。

        限额从 otree.views.admin 导入而非写死字面量：写死会随 oTree 升级
        变成一句关于旧版本的陈述，而本断言要保证的是「现在仍然可用」。
        """
        from otree.views.admin import GRID_LOWER_LIMIT, GRID_UPPER_LIMIT

        for name in CONDITIONS:
            demo_name = self.demo_name(name)
            num = self.config(demo_name)['num_demo_participants']
            self.assertGreaterEqual(
                num, GRID_LOWER_LIMIT,
                f'{demo_name} 人数 {num} 低于网格视图下限 {GRID_LOWER_LIMIT}')
            self.assertLessEqual(
                num, GRID_UPPER_LIMIT,
                f'{demo_name} 人数 {num} 高于网格视图上限 {GRID_UPPER_LIMIT}')


if __name__ == '__main__':
    unittest.main()

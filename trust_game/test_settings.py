"""settings.py 的 session config 守卫。

运行（项目根目录）：
    python -m unittest trust_game.test_settings -v

⚠️ 本文件守的是**演示开关不得落到真实 config 上**。

`use_browser_bots=True` 的语义是「本会话的全体被试由 bot 驱动」。它一旦出现在
trust_baseline / trust_communication 上，真实被试拿到的每一页都会在渲染后被 JS
自动提交（otree/views/abstract.py:483-513），被试还没读完题目就翻页；而数据照样
写库、otree test 照样全绿。这是不会自己报出来的错误：它只在收完数据后表现为
一片无意义的常量。故此处逐条钉死，让误改在测试阶段就失败。

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

# 真实 config → 其对应的演示 config。改这里的映射即改守卫的适用范围。
REAL_TO_DEMO = {
    'trust_baseline': 'trust_baseline_bots',
    'trust_communication': 'trust_communication_bots',
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

    def test_real_configs_must_not_use_browser_bots(self):
        """真实 config 绝不可带 use_browser_bots：否则真实被试会被 bot 顶替。"""
        for name in REAL_TO_DEMO:
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
        for demo_name in REAL_TO_DEMO.values():
            value = self.config(demo_name).get('use_browser_bots', False)
            self.assertIs(
                value, True,
                f'{demo_name} 的 use_browser_bots 必须是 True，实际是 {value!r}；'
                '否则该会话不会由 bot 驱动，控制台无对象可驱动',
            )

    def test_demo_configs_mirror_communication_flag(self):
        """演示 config 的 communication 必须与对应真实 config 逐值相同。

        用 assertIs 比较：None 与 False 在真值判断下同形，而它们对
        has_communication() 的后果不同。
        """
        for real_name, demo_name in REAL_TO_DEMO.items():
            real = self.config(real_name)
            self.assertIn('communication', real,
                          f'{real_name} 缺少 communication 键，无法作对齐基准')
            self.assertIs(
                self.config(demo_name).get('communication'),
                real['communication'],
                f'{demo_name} 的 communication 与 {real_name} 不一致',
            )

    def test_demo_config_names_follow_the_bots_suffix_convention(self):
        """演示 config 名必须是「对应真实 config 名 + `_bots`」，一个不多一个不少。

        这不是取名偏好，而是 trust_game/tests.py 的**依赖**：那里的 check_round
        用 `name.removesuffix('_bots')` 归一后再与 'trust_communication' 比较，
        以核对「config 名 ↔ communication 键」是否自洽。名字不符合该约定
        （例如叫 trust_communication_bots_v2），那条核对会静默走错分支——
        沟通组被当成基线组要求 is_communication 为假，演示会话直接 500。

        断言写成「集合相等」而不是「逐个检查以 _bots 结尾的名字」：后者有个
        已实测到的空洞——把 config 改名成 trust_communication_bots_v2 之后，
        它不再以 _bots 结尾，于是**根本不会进入被检查的集合**，测试照样全绿。
        集合相等把「改名」和「少登记」都变成失败。
        """
        names = set(self.configs)
        bots_names = {n for n in names if n.endswith('_bots')}
        self.assertEqual(
            bots_names, set(REAL_TO_DEMO.values()),
            'settings.py 里以 _bots 结尾的 config 必须恰好是 REAL_TO_DEMO 列出的'
            '那些。少了/多了/改了名，trust_game/tests.py 的名字归一核对就会'
            '走错分支，沟通组的演示会话会直接 500',
        )
        for real_name, demo_name in REAL_TO_DEMO.items():
            self.assertEqual(
                demo_name, real_name + '_bots',
                f'演示 config 名必须等于 {real_name!r} + "_bots"，实际 {demo_name!r}',
            )

    def test_demo_configs_mirror_app_sequence(self):
        for real_name, demo_name in REAL_TO_DEMO.items():
            self.assertEqual(
                self.config(demo_name)['app_sequence'],
                self.config(real_name)['app_sequence'],
                f'{demo_name} 的 app_sequence 必须与 {real_name} 相同，'
                '否则演示覆盖不到调查问卷',
            )

    def test_demo_num_participants_within_grid_view_limits(self):
        """人数必须落在网格视图限额内，否则演示页上 Grid view 不可用。

        限额从 otree.views.admin 导入而非写死字面量：写死会随 oTree 升级
        变成一句关于旧版本的陈述，而本断言要保证的是「现在仍然可用」。
        """
        from otree.views.admin import GRID_LOWER_LIMIT, GRID_UPPER_LIMIT

        for demo_name in REAL_TO_DEMO.values():
            num = self.config(demo_name)['num_demo_participants']
            self.assertGreaterEqual(
                num, GRID_LOWER_LIMIT,
                f'{demo_name} 人数 {num} 低于网格视图下限 {GRID_LOWER_LIMIT}')
            self.assertLessEqual(
                num, GRID_UPPER_LIMIT,
                f'{demo_name} 人数 {num} 高于网格视图上限 {GRID_UPPER_LIMIT}')


if __name__ == '__main__':
    unittest.main()

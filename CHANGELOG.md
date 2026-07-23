# 更新日志

所有 DBSKiter 版本的显著变更都会记录在此文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [3.0.30-3.0.40] - 2026-07-21 to 2026-07-22

### 🐛 Bug 修复 (v3.0.40)
- 修复 config.py 中 @dataclass 与手动 __init__ 冲突，移除 50 行死代码
- 移除 Config 类中的 DEFAULTS/ENV_MAPPING 死代码

### ✨ 新增 (v3.0.36-v3.0.39)
- 配置系统新增 --url 连接字符串（mysql://root@localhost/test）
- 配置系统新增 --password-stdin（安全密码输入）
- 配置系统新增 --profile 和 --env 参数
- 7 种数据库全部支持专用备份（MySQL/PG/SQLite/Oracle/MSSQL/CH/Generic）

### ♻️ 重构 (v3.0.34-v3.0.35)
- report_generator.py 从 2427 行降到 909 行（HTML 模板抽取到 templates.py）
- 5 个 V2 文件重命名为清晰名称，旧文件保留向后兼容
- 添加 DeprecationWarning 到 V2 文件

### 🧪 测试 (v3.0.32)
- 新增 207 个测试用例
- 6 个 0% 覆盖模块提升到 60-100%（sql_validator 99%, host_mapping 92%, schema_detector 93%）
- 总测试数从 762 增长到 1000

### 📝 文档 (v3.0.30-v3.0.34)
- MkDocs 文档站点部署到 GitHub Pages
- 新增配置指南（docs/configuration.md）
- CHANGELOG 更新到 v3.0.40

## [3.0.29] - 2026-07-21

### 🐛 Bug 修复
- 修复 13 处裸 `except:` 为 `except Exception:`，防止捕获 `KeyboardInterrupt` / `SystemExit`
- 修复 5 个测试失败（CLI 命令导入、模块响应函数 re-export、V2/V3 引用清理）
- 修复 `sql` 命令别名 Bug（导致 `dbskiter sql execute` 命令双倍展开）

### ✨ 新增
- Docker 支持（Dockerfile + docker-compose，包含 MySQL/PG/ClickHouse/MSSQL）
- GitHub Actions CI/CD 4 阶段工作流（test/benchmark/integration/publish）
- Pre-commit 钩子（black + flake8 + bare except 检测）
- MkDocs 文档站点（15 个页面，Material 主题）
- 4 个性能基准测试用例
- 3 个 Docker 数据库集成测试
- 覆盖率检查（当前 25%，阈值 20%）

### ♻️ 重构
- `report_generator.py` (2668行) 拆分为 `report_generator/` 包
- `backup.py` (2328行) 拆分为 `backup/` 包

### 📝 文档
- README 更新（生产就绪状态表）
- docs/README.md 更新（案例状态）
- AI 集成指南更新（版本号）

### 🔧 其他
- 6 个 CLI 命令文件添加类型注解
- 修复 SQL 指纹测试 14 个 + SQL 验证测试 1 个

## [3.0.24] - 2026-06-17

### 🐛 Bug 修复
- 修复 6 个 Bug
- 新增 LICENSE
- CLI 风格化
- Mock 测试支持

## [3.0.20] - 2026-06-15

### ✨ 新增
- config/history/shell-setup 命令
- 计时器模块

## [3.0.19] - 2026-06-13

### ✨ 新增
- Tab 补全支持
- 新增命令

## [3.0.0] - 2026-04-29

### 🎉 主要重构
- 新增 ClickHouse/MSSQL/SQLite 支持
- 新增 Generic 驱动（自动能力探测）
- 完成项目模块化重构
- 引入"6 + N"双层驱动架构

## [2.0.0] - 2026-04-16

### 🎉 首个生产版本
- 数据库 AIOps 运维工具集
- 8 大核心 Skill：诊断、监控、安全、调度、SQL 执行、巡检、锁分析、SQL 审核
- 支持 MySQL、Oracle、PostgreSQL
- CLI 命令行工具
- 环境变量配置

---

## 版本命名规则

本项目使用 [语义化版本](https://semver.org/lang/zh-CN/)：
- **主版本号**：不兼容的 API 修改
- **次版本号**：向下兼容的功能性新增
- **修订号**：向下兼容的问题修正

## 维护者

- [MagiCzc](https://github.com/magicCzc) - 项目创始人

## 贡献者

感谢所有为 DBSKiter 做出贡献的开发者！
<!--
文件功能：DBSKiter v3 → v4 迁移指南
主要变更：V2 模块移除、API 变更
作者：MagiCzc
创建时间：2026-07-24
最后修改：2026-07-24
-->

# v3 → v4 迁移指南

DBSKiter v4.0 计划于 **2026-12-31** 发布，届时将移除 v3.0 标记为 deprecated 的 V2 模块。本指南帮助你提前完成迁移。

---

## 移除时间表

| 模块 | 状态 | 移除版本 | 预计日期 |
|------|------|----------|----------|
| `dbskiter.db_security.sensitive_data_scanner_v2` | ⚠️ 已弃用 | v4.0 | 2026-12-31 |
| `dbskiter.db_security.sql_injection_detector_v2` | ⚠️ 已弃用 | v4.0 | 2026-12-31 |
| `dbskiter.shared.mysql_aas_calculator_v2` | ⚠️ 已弃用 | v4.0 | 2026-12-31 |
| `dbskiter.sql_master.security_executor_v2` | ⚠️ 已弃用 | v4.0 | 2026-12-31 |

---

## 迁移清单

### 1. 敏感数据扫描器

#### 旧代码（v3.0）

```python
from dbskiter.db_security.sensitive_data_scanner_v2 import (
    SensitiveDataScannerV2,
    ScanResult,
)

scanner = SensitiveDataScannerV2(connector)
result = scanner.scan_table("users")
```

#### 新代码（v3.1+ / v4.0）

```python
from dbskiter.db_security.sensitive_data_scanner import (
    SensitiveDataScanner,
    ScanResult,
)

scanner = SensitiveDataScanner(connector)
result = scanner.scan_table("users")
```

#### 变更说明

- 类名从 `SensitiveDataScannerV2` 改为 `SensitiveDataScanner`
- 模块路径去掉 `_v2` 后缀
- **API 100% 向后兼容**（方法签名、返回值、异常类型完全一致）

#### 自动化迁移

```bash
# 使用 sed 批量替换
find . -name "*.py" -type f -exec sed -i \
  's/sensitive_data_scanner_v2/sensitive_data_scanner/g' {} \;

# 使用 sed 替换类名
find . -name "*.py" -type f -exec sed -i \
  's/SensitiveDataScannerV2/SensitiveDataScanner/g' {} \;
```

---

### 2. SQL 注入检测器

#### 旧代码

```python
from dbskiter.db_security.sql_injection_detector_v2 import (
    SQLInjectionDetectorV2,
    DetectionResult,
)

detector = SQLInjectionDetectorV2()
result = detector.detect("SELECT * FROM users WHERE id = 1 OR 1=1")
```

#### 新代码

```python
from dbskiter.db_security.sql_injection_detector import (
    SQLInjectionDetector,
    DetectionResult,
)

detector = SQLInjectionDetector()
result = detector.detect("SELECT * FROM users WHERE id = 1 OR 1=1")
```

#### 自动化迁移

```bash
find . -name "*.py" -type f -exec sed -i \
  's/sql_injection_detector_v2/sql_injection_detector/g' {} \;

find . -name "*.py" -type f -exec sed -i \
  's/SQLInjectionDetectorV2/SQLInjectionDetector/g' {} \;
```

---

### 3. MySQL AAS 计算器

#### 旧代码

```python
from dbskiter.shared.mysql_aas_calculator_v2 import (
    MySQLAASCalculatorV2,
    AASConfig,
    AASMetrics,
)

config = AASConfig.from_env()
calculator = MySQLAASCalculatorV2(connector, config=config)
aas = calculator.calculate_current_aas()
```

#### 新代码

```python
from dbskiter.shared.mysql_aas_calculator import (
    MySQLAASCalculator,
    AASConfig,
    AASMetrics,
)

config = AASConfig.from_env()
calculator = MySQLAASCalculator(connector, config=config)
aas = calculator.calculate_current_aas()
```

#### 自动化迁移

```bash
find . -name "*.py" -type f -exec sed -i \
  's/mysql_aas_calculator_v2/mysql_aas_calculator/g' {} \;

find . -name "*.py" -type f -exec sed -i \
  's/MySQLAASCalculatorV2/MySQLAASCalculator/g' {} \;
```

---

### 4. 安全执行器

#### 旧代码

```python
from dbskiter.sql_master.security_executor_v2 import (
    SecurityExecutorV2,
    ExecutionContext,
)

executor = SecurityExecutorV2()
result = executor.execute_with_check(sql, context)
```

#### 新代码

```python
from dbskiter.sql_master.security_executor import (
    SecurityExecutor,
    ExecutionContext,
)

executor = SecurityExecutor()
result = executor.execute_with_check(sql, context)
```

#### 自动化迁移

```bash
find . -name "*.py" -type f -exec sed -i \
  's/security_executor_v2/security_executor/g' {} \;

find . -name "*.py" -type f -exec sed -i \
  's/SecurityExecutorV2/SecurityExecutor/g' {} \;
```

---

## 完整自动化迁移脚本

如果你的项目大量使用了 V2 模块，可以使用以下脚本一键迁移：

```bash
#!/usr/bin/env bash
# scripts/migrate_v3_to_v4.sh

set -e

echo "=== DBSKiter v3 → v4 迁移脚本 ==="
echo "警告：操作前请确保已 git commit 当前所有更改"
read -p "按 Enter 继续，Ctrl+C 取消..."

# 1. 敏感数据扫描器
echo "[1/4] 迁移 sensitive_data_scanner..."
find . -name "*.py" -type f -exec sed -i \
  's/sensitive_data_scanner_v2/sensitive_data_scanner/g' {} \;
find . -name "*.py" -type f -exec sed -i \
  's/SensitiveDataScannerV2/SensitiveDataScanner/g' {} \;

# 2. SQL 注入检测器
echo "[2/4] 迁移 sql_injection_detector..."
find . -name "*.py" -type f -exec sed -i \
  's/sql_injection_detector_v2/sql_injection_detector/g' {} \;
find . -name "*.py" -type f -exec sed -i \
  's/SQLInjectionDetectorV2/SQLInjectionDetector/g' {} \;

# 3. MySQL AAS 计算器
echo "[3/4] 迁移 mysql_aas_calculator..."
find . -name "*.py" -type f -exec sed -i \
  's/mysql_aas_calculator_v2/mysql_aas_calculator/g' {} \;
find . -name "*.py" -type f -exec sed -i \
  's/MySQLAASCalculatorV2/MySQLAASCalculator/g' {} \;

# 4. 安全执行器
echo "[4/4] 迁移 security_executor..."
find . -name "*.py" -type f -exec sed -i \
  's/security_executor_v2/security_executor/g' {} \;
find . -name "*.py" -type f -exec sed -i \
  's/SecurityExecutorV2/SecurityExecutor/g' {} \;

echo ""
echo "=== 迁移完成 ==="
echo "下一步："
echo "  1. 运行测试: pytest tests/"
echo "  2. 检查 import 警告: python -W error::DeprecationWarning -c 'import dbskiter'"
echo "  3. git diff 检查变更"
```

---

## 验证迁移成功

```bash
# 1. 不应再触发 DeprecationWarning
python -W error::DeprecationWarning -c "from dbskiter.db_security import *"

# 2. 单元测试应全部通过
pytest tests/test_db_security.py -v

# 3. 完整测试
pytest tests/ -v
```

---

## 常见问题

### Q1: 我必须现在迁移吗？

**A**：不必。V2 模块在 v3.x 仍可正常使用，仅会有 `DeprecationWarning`。v4.0 发布（2026-12-31）后才会移除。

### Q2: 迁移会影响行为吗？

**A**：不会。V2 名称去掉后，类与原 V2 实现等价（已合并到非 V2 模块）。API 100% 兼容。

### Q3: 如果我使用了非公开 API 怎么办？

**A**：V2 内部的私有方法（如 `_scan_with_entropy_v2`）在合并时已统一命名。建议先升级到 v3.1+，等 v3.x 全部完成后再升级 v4.0。

### Q4: 升级到 v4.0 后 v3 还能用吗？

**A**：v3.x 和 v4.x 会并行维护一段时间（通常是 6 个月）。具体看发布公告。

---

## 获取帮助

迁移过程中遇到问题？

- 📝 [提交 Issue](https://github.com/magicCzc/dbskiter/issues)
- 📧 邮件：magiczc@139.com
- 💬 微信群：见 README.md

---

**最后更新**：2026-07-24

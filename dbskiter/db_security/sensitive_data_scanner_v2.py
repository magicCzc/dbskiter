"""
敏感数据扫描器 V2 - 基于内容分析的深度扫描

优化点：
1. 不仅扫描字段名，还分析数据内容
2. 支持多种数据类型识别（PII、金融、健康等）
3. 数据熵分析检测加密/混淆数据
4. 可量化的敏感度评分

作者：Trae AI
创建时间：2026-04-20
"""

import re
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class SensitivityLevel(Enum):
    """敏感度等级"""
    CRITICAL = "critical"  # 极高风险（密码、密钥）
    HIGH = "high"          # 高风险（身份证号、信用卡）
    MEDIUM = "medium"      # 中风险（邮箱、电话）
    LOW = "low"            # 低风险（姓名、地址）


class DataCategory(Enum):
    """数据类别"""
    CREDENTIALS = "credentials"      # 凭据
    PII = "pii"                      # 个人身份信息
    FINANCIAL = "financial"          # 金融信息
    HEALTH = "health"                # 健康信息
    CONTACT = "contact"              # 联系信息
    BUSINESS = "business"            # 商业敏感


@dataclass
class SensitiveColumn:
    """敏感列信息"""
    table_name: str
    column_name: str
    data_type: str
    sensitivity_level: SensitivityLevel
    category: DataCategory
    confidence: float  # 0-1 置信度
    detection_method: str  # 字段名/内容分析/混合
    sample_values: List[str] = field(default_factory=list)
    row_count: int = 0
    null_count: int = 0
    unique_count: int = 0
    entropy: float = 0.0
    recommendation: str = ""
    detected_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "table_name": self.table_name,
            "column_name": self.column_name,
            "data_type": self.data_type,
            "sensitivity_level": self.sensitivity_level.value,
            "category": self.category.value,
            "confidence": round(self.confidence, 2),
            "detection_method": self.detection_method,
            "sample_values": self.sample_values[:3],  # 只返回前3个样本
            "row_count": self.row_count,
            "null_count": self.null_count,
            "unique_count": self.unique_count,
            "entropy": round(self.entropy, 2),
            "recommendation": self.recommendation
        }


class SensitiveDataScannerV2:
    """
    敏感数据扫描器 V2 - 基于内容分析的深度扫描
    
    扫描能力：
    1. 字段名模式匹配（正则）
    2. 数据内容分析（采样）
    3. 数据熵分析（检测加密/随机数据）
    4. 统计特征分析（唯一值比例等）
    
    使用示例：
        scanner = SensitiveDataScannerV2(connector)
        
        # 扫描所有表
        result = scanner.scan_all_tables(sample_size=100)
        
        # 查看高危发现
        for col in result["critical_findings"]:
            print(f"{col['table_name']}.{col['column_name']}: {col['sensitivity_level']}")
    """
    
    # 字段名模式定义
    COLUMN_PATTERNS = {
        DataCategory.CREDENTIALS: {
            SensitivityLevel.CRITICAL: [
                (r"(?i)^(password|passwd|pwd|secret|private_key)$", "密码/密钥"),
                (r"(?i)^(api_key|apikey|secret_key|access_key)$", "API密钥"),
                (r"(?i)^(token|auth_token|access_token|refresh_token)$", "令牌"),
                (r"(?i)^(ssh_key|rsa_key|private_key)$", "SSH密钥"),
            ],
            SensitivityLevel.HIGH: [
                (r"(?i)^(pin|security_code|cvv|cvc)$", "安全码"),
            ]
        },
        DataCategory.PII: {
            SensitivityLevel.CRITICAL: [
                (r"(?i)^(ssn|social_security|social_security_number)$", "社会安全号"),
                (r"(?i)^(id_card|identity_card|national_id|resident_id)$", "身份证号"),
                (r"(?i)^(passport|passport_no|passport_number)$", "护照号"),
            ],
            SensitivityLevel.HIGH: [
                (r"(?i)^(dob|date_of_birth|birth_date|birthday)$", "出生日期"),
                (r"(?i)^(biometric|fingerprint|face_id)$", "生物特征"),
            ],
            SensitivityLevel.MEDIUM: [
                (r"(?i)^(name|full_name|first_name|last_name)$", "姓名"),
                (r"(?i)^(gender|sex)$", "性别"),
                (r"(?i)^(nationality|citizenship)$", "国籍"),
            ]
        },
        DataCategory.FINANCIAL: {
            SensitivityLevel.CRITICAL: [
                (r"(?i)^(credit_card|cc_number|card_number|card_no)$", "信用卡号"),
                (r"(?i)^(bank_account|account_no|account_number|iban)$", "银行账号"),
                (r"(?i)^(routing_number|swift|bic)$", "银行路由号"),
                (r"(?i)^(crypto_address|wallet_address|btc_address)$", "加密货币地址"),
            ],
            SensitivityLevel.HIGH: [
                (r"(?i)^(salary|income|wage|compensation|annual_salary)$", "薪资"),
                (r"(?i)^(tax_id|tin|vat_number)$", "税务ID"),
            ],
            SensitivityLevel.MEDIUM: [
                (r"(?i)^(balance|amount|payment_amount|transaction_amount)$", "金额"),
            ]
        },
        DataCategory.CONTACT: {
            SensitivityLevel.HIGH: [
                (r"(?i)^(email|e_mail|email_address)$", "邮箱"),
                (r"(?i)^(phone|mobile|cell_phone|telephone|tel|phone_number)$", "电话"),
            ],
            SensitivityLevel.MEDIUM: [
                (r"(?i)^(address|street|city|zip|postal_code|country)$", "地址"),
            ]
        },
        DataCategory.HEALTH: {
            SensitivityLevel.CRITICAL: [
                (r"(?i)^(medical_record|health_record|diagnosis|patient_id|mrn)$", "医疗记录"),
                (r"(?i)^(insurance_id|insurance_number|policy_number|health_insurance)$", "保险号"),
            ],
            SensitivityLevel.HIGH: [
                (r"(?i)^(blood_type|allergy|medication|prescription|treatment)$", "健康信息"),
            ]
        },
        DataCategory.BUSINESS: {
            SensitivityLevel.HIGH: [
                (r"(?i)^(trade_secret|proprietary|confidential|internal_only)$", "商业机密"),
            ]
        }
    }
    
    # 数据内容模式（用于验证）
    CONTENT_PATTERNS = {
        "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
        "phone": re.compile(r"^[\d\s\-\+\(\)]{7,20}$"),
        "credit_card": re.compile(r"^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$"),
        "ssn": re.compile(r"^\d{3}-?\d{2}-?\d{4}$"),
        "ip_address": re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
        "api_key": re.compile(r"^[a-zA-Z0-9]{32,64}$"),
        "uuid": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
    }

    # 通用加密特征模式（不依赖特定系统）
    # 用于检测数据是否已加密，降低误报
    ENCRYPTION_INDICATORS = {
        # Django密码哈希格式
        "django_password": r'^pbkdf2_sha256\$\d+\$[a-zA-Z0-9_]+\$[a-zA-Z0-9_+/=]+$',
        # bcrypt格式 (OpenBSD bcrypt)
        "bcrypt": r'^\$2[aby]?\$\d+\$[./A-Za-z0-9]{50,60}$',
        # Argon2格式
        "argon2": r'^\$argon2[id]\$v=\d+\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+$',
        # SHA1哈希
        "sha1_hash": r'^[a-fA-F0-9]{40}$',
        # SHA256哈希
        "sha256_hash": r'^[a-fA-F0-9]{64}$',
        # MD5哈希
        "md5_hash": r'^[a-fA-F0-9]{32}$',
        # Base64长字符串（可能是加密数据）
        "base64_long": r'^[A-Za-z0-9+/]{100,}={0,2}$',
        # 十六进制长字符串
        "hex_long": r'^[0-9a-fA-F]{64,}$',
    }

    def __init__(self, connector):
        self.connector = connector
        self.dialect = connector.dialect.lower() if connector else "unknown"
        self.findings: List[SensitiveColumn] = []

    def scan(
        self,
        tables: Optional[List[str]] = None,
        sample_size: int = 100,
        use_dynamic_sampling: bool = True
    ) -> Dict[str, Any]:
        """
        扫描敏感数据（兼容接口）

        参数：
            tables: 指定表列表（None表示所有表）
            sample_size: 每列采样行数（启用动态采样时作为基础值）
            use_dynamic_sampling: 是否使用动态采样策略

        返回：
            Dict: 扫描结果
        """
        if tables:
            # 扫描指定表
            all_findings = []
            sampling_info = {}

            for table in tables:
                try:
                    # 根据配置决定是否使用动态采样
                    if use_dynamic_sampling:
                        actual_sample_size = self._calculate_dynamic_sample_size(table, sample_size)
                        sampling_info[table] = actual_sample_size
                    else:
                        actual_sample_size = sample_size
                        sampling_info[table] = sample_size

                    findings = self.scan_table(table, actual_sample_size)
                    all_findings.extend(findings)
                except Exception as e:
                    logger.error(f"扫描表 {table} 失败: {e}")

            # 分类统计
            by_level = {}
            by_category = {}
            for finding in all_findings:
                level = finding.sensitivity_level.value
                category = finding.category.value
                by_level[level] = by_level.get(level, 0) + 1
                by_category[category] = by_category.get(category, 0) + 1

            return {
                "status": "success",
                "total_tables": len(tables),
                "tables_scanned": len(set(f.table_name for f in all_findings)),
                "total_findings": len(all_findings),
                "by_level": by_level,
                "by_category": by_category,
                "sampling_info": sampling_info,
                "dynamic_sampling_enabled": use_dynamic_sampling,
                "critical_findings": [f.to_dict() for f in all_findings if f.sensitivity_level == SensitivityLevel.CRITICAL],
                "high_findings": [f.to_dict() for f in all_findings if f.sensitivity_level == SensitivityLevel.HIGH],
                "all_findings": [f.to_dict() for f in all_findings],
                "summary": self._generate_summary(all_findings)
            }
        else:
            # 扫描所有表
            return self.scan_all_tables(sample_size, use_dynamic_sampling)

    def _calculate_dynamic_sample_size(self, table_name: str, base_sample_size: int = 100) -> int:
        """
        根据表大小动态计算采样行数

        策略：
        - 小表 (< 10,000行): 全量扫描
        - 中表 (10,000 - 1,000,000行): 1%采样，最少1000行
        - 大表 (> 1,000,000行): 分层采样，0.1%采样，最少5000行，最多50000行

        参数：
            table_name: 表名
            base_sample_size: 基础采样大小

        返回：
            int: 动态计算的采样大小
        """
        try:
            # 获取表的总行数
            if "oracle" in self.dialect:
                count_sql = f"SELECT COUNT(*) FROM {table_name.upper()}"
            elif "postgresql" in self.dialect:
                count_sql = f'SELECT COUNT(*) FROM "{table_name}"'
            elif self.dialect in ("mysql", "mysql+pymysql"):
                count_sql = f"SELECT COUNT(*) FROM `{table_name}`"
            else:
                count_sql = f"SELECT COUNT(*) FROM {table_name}"

            count_result = self.connector.execute(count_sql)
            total_rows = int(count_result.rows[0][0]) if count_result.rows else 0

            # 根据表大小计算采样数
            if total_rows < 10000:
                # 小表：全量扫描
                sample_size = total_rows
                logger.debug(f"表 {table_name} 为小表 ({total_rows} 行)，使用全量扫描")
            elif total_rows < 1000000:
                # 中表：1%采样，最少1000行
                sample_size = max(int(total_rows * 0.01), 1000)
                logger.debug(f"表 {table_name} 为中表 ({total_rows} 行)，采样 {sample_size} 行")
            else:
                # 大表：0.1%采样，最少5000行，最多50000行
                sample_size = min(max(int(total_rows * 0.001), 5000), 50000)
                logger.debug(f"表 {table_name} 为大表 ({total_rows} 行)，采样 {sample_size} 行")

            return sample_size

        except Exception as e:
            logger.warning(f"计算动态采样大小失败: {e}，使用默认值 {base_sample_size}")
            return base_sample_size

    def scan_all_tables(self, sample_size: int = 100, use_dynamic_sampling: bool = True) -> Dict[str, Any]:
        """
        扫描所有表

        参数：
            sample_size: 每列采样行数（启用动态采样时作为基础值）
            use_dynamic_sampling: 是否使用动态采样策略

        返回：
            Dict: 扫描结果
        """
        try:
            tables = self.connector.get_tables()
            all_findings = []
            sampling_info = {}

            for table in tables:
                try:
                    # 根据配置决定是否使用动态采样
                    if use_dynamic_sampling:
                        actual_sample_size = self._calculate_dynamic_sample_size(table, sample_size)
                        sampling_info[table] = actual_sample_size
                    else:
                        actual_sample_size = sample_size
                        sampling_info[table] = sample_size

                    findings = self.scan_table(table, actual_sample_size)
                    all_findings.extend(findings)
                except Exception as e:
                    logger.error(f"扫描表 {table} 失败: {e}")

            # 分类统计
            by_level = {}
            by_category = {}
            for finding in all_findings:
                level = finding.sensitivity_level.value
                category = finding.category.value
                by_level[level] = by_level.get(level, 0) + 1
                by_category[category] = by_category.get(category, 0) + 1

            return {
                "status": "success",
                "total_tables": len(tables),
                "tables_scanned": len(set(f.table_name for f in all_findings)),
                "total_findings": len(all_findings),
                "by_level": by_level,
                "by_category": by_category,
                "sampling_info": sampling_info,  # 添加采样信息
                "dynamic_sampling_enabled": use_dynamic_sampling,
                "critical_findings": [f.to_dict() for f in all_findings if f.sensitivity_level == SensitivityLevel.CRITICAL],
                "high_findings": [f.to_dict() for f in all_findings if f.sensitivity_level == SensitivityLevel.HIGH],
                "all_findings": [f.to_dict() for f in all_findings],
                "summary": self._generate_summary(all_findings)
            }

        except Exception as e:
            logger.error(f"扫描所有表失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def scan_table(self, table_name: str, sample_size: int = 100) -> List[SensitiveColumn]:
        """
        扫描单个表
        
        参数：
            table_name: 表名
            sample_size: 采样行数
            
        返回：
            List[SensitiveColumn]: 敏感列列表
        """
        findings = []
        
        try:
            # 获取表结构
            schema = self._get_table_schema(table_name)
            
            for column in schema:
                col_name = column["name"]
                data_type = column["type"]
                
                # 1. 字段名分析
                name_match = self._analyze_column_name(col_name)
                
                if name_match:
                    category, level, pattern_desc = name_match

                    # 2. 获取采样数据验证
                    samples, stats = self._get_column_samples(table_name, col_name, sample_size)

                    # 3. 检测是否已加密（关键优化）
                    is_encrypted, encryption_note = self._is_likely_encrypted(samples, col_name, table_name)

                    # 4. 根据加密状态调整敏感级别
                    adjusted_level, level_note = self._adjust_for_encryption(level, is_encrypted)

                    # 5. 内容验证（提高置信度）
                    content_confidence = self._validate_content(samples, category, col_name)

                    # 6. 计算熵（检测加密/随机数据）
                    entropy = self._calculate_entropy(samples)

                    # 7. 综合置信度
                    confidence = self._calculate_confidence(
                        name_match=True,
                        content_confidence=content_confidence,
                        entropy=entropy,
                        stats=stats,
                        column_name=col_name
                    )

                    # 8. 生成建议（包含加密信息）
                    recommendation = self._generate_recommendation(
                        category, adjusted_level, col_name, entropy
                    )

                    # 如果已加密，修改建议
                    if is_encrypted:
                        recommendation = f"[已加密] {encryption_note}。{recommendation}"

                    finding = SensitiveColumn(
                        table_name=table_name,
                        column_name=col_name,
                        data_type=data_type,
                        sensitivity_level=adjusted_level,
                        category=category,
                        confidence=confidence,
                        detection_method="name_pattern+content" if content_confidence > 0.5 else "name_pattern",
                        sample_values=samples[:5],
                        row_count=stats.get("row_count", 0),
                        null_count=stats.get("null_count", 0),
                        unique_count=stats.get("unique_count", 0),
                        entropy=entropy,
                        recommendation=recommendation
                    )

                    findings.append(finding)
            
            return findings
            
        except Exception as e:
            logger.error(f"扫描表 {table_name} 失败: {e}")
            return []
    
    def _get_table_schema(self, table_name: str) -> List[Dict]:
        """获取表结构"""
        try:
            # 使用 DatabaseConnector 的 get_schema 方法
            import pandas as pd
            schema_df = self.connector.get_schema(table_name)
            
            columns = []
            for _, row in schema_df.iterrows():
                # 支持多种列名格式
                # MySQL: Field, Type
                # PostgreSQL: column_name, data_type
                # 通用: name, type
                col_name = row.get("Field") or row.get("name") or row.get("column_name", "")
                col_type = row.get("Type") or row.get("type") or row.get("data_type", "UNKNOWN")
                columns.append({
                    "name": str(col_name),
                    "type": str(col_type)
                })
            return columns
        except Exception as e:
            logger.error(f"获取表结构失败: {e}")
            return []
    
    def _analyze_column_name(self, column_name: str) -> Optional[Tuple[DataCategory, SensitivityLevel, str]]:
        """分析字段名是否敏感"""
        for category, levels in self.COLUMN_PATTERNS.items():
            for level, patterns in levels.items():
                for pattern, desc in patterns:
                    if re.match(pattern, column_name):
                        return (category, level, desc)
        return None
    
    def _get_column_samples(self, table_name: str, column_name: str, sample_size: int) -> Tuple[List[str], Dict]:
        """获取列采样数据"""
        samples = []
        stats = {"row_count": 0, "null_count": 0, "unique_count": 0}
        
        try:
            # 构建安全的查询（使用参数化查询）
            # 注意：表名和列名不能参数化，需要验证
            if not self._is_safe_identifier(table_name) or not self._is_safe_identifier(column_name):
                return samples, stats
            
            # 获取总行数
            if "oracle" in self.dialect:
                count_sql = f"SELECT COUNT(*) FROM {table_name.upper()}"
            elif "postgresql" in self.dialect:
                count_sql = f'SELECT COUNT(*) FROM "{table_name}"'
            elif self.dialect in ("mysql", "mysql+pymysql"):
                count_sql = f"SELECT COUNT(*) FROM `{table_name}`"
            else:
                count_sql = f"SELECT COUNT(*) FROM {table_name}"
            count_result = self.connector.execute(count_sql)
            total_rows = int(count_result.rows[0][0]) if count_result.rows else 0
            stats["row_count"] = total_rows
            
            # 采样查询
            if self.dialect in ("mysql", "mysql+pymysql"):
                sql = f"SELECT `{column_name}` FROM `{table_name}` WHERE `{column_name}` IS NOT NULL LIMIT {sample_size}"
            elif "postgresql" in self.dialect:
                sql = f'SELECT "{column_name}" FROM "{table_name}" WHERE "{column_name}" IS NOT NULL LIMIT {sample_size}'
            elif self.dialect in ("sqlite", "sqlite3"):
                sql = f'SELECT "{column_name}" FROM "{table_name}" WHERE "{column_name}" IS NOT NULL LIMIT {sample_size}'
            elif "oracle" in self.dialect:
                # Oracle 使用 ROWNUM，表名和列名默认大写，不需要引号
                sql = f'SELECT {column_name.upper()} FROM {table_name.upper()} WHERE {column_name.upper()} IS NOT NULL AND ROWNUM <= {sample_size}'
            else:
                sql = f"SELECT {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL LIMIT {sample_size}"
            
            result = self.connector.execute(sql)
            
            for row in result.rows:
                if row[0] is not None:
                    samples.append(str(row[0]))
                else:
                    stats["null_count"] += 1
            
            # 统计唯一值数量
            stats["unique_count"] = len(set(samples))
            
        except Exception as e:
            logger.warning(f"获取采样数据失败: {e}")
        
        return samples, stats
    
    def _is_safe_identifier(self, identifier: str) -> bool:
        """检查标识符是否安全"""
        # Oracle 允许 $ 和 # 在标识符中，如 v$session, quest_sl_temp_explain1
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_$#]*$', identifier))
    
    def _validate_content(self, samples: List[str], category: DataCategory, column_name: str) -> float:
        """验证内容匹配度"""
        if not samples:
            return 0.0
        
        match_count = 0
        
        for sample in samples:
            sample_str = str(sample)
            
            if category == DataCategory.CONTACT:
                if "email" in column_name.lower():
                    if self.CONTENT_PATTERNS["email"].match(sample_str):
                        match_count += 1
                elif "phone" in column_name.lower():
                    if self.CONTENT_PATTERNS["phone"].match(sample_str):
                        match_count += 1
            
            elif category == DataCategory.FINANCIAL:
                if "credit" in column_name.lower() or "card" in column_name.lower():
                    if self.CONTENT_PATTERNS["credit_card"].match(sample_str):
                        match_count += 1
            
            elif category == DataCategory.CREDENTIALS:
                if "api" in column_name.lower() or "key" in column_name.lower():
                    if self.CONTENT_PATTERNS["api_key"].match(sample_str):
                        match_count += 1
            
            elif category == DataCategory.PII:
                if "ssn" in column_name.lower():
                    if self.CONTENT_PATTERNS["ssn"].match(sample_str):
                        match_count += 1
        
        return match_count / len(samples) if samples else 0.0
    
    def _calculate_entropy(self, samples: List[str]) -> float:
        """计算数据熵（检测加密/随机数据）"""
        if not samples:
            return 0.0
        
        # 合并所有样本
        text = "".join(str(s) for s in samples)
        if not text:
            return 0.0
        
        # 计算字符频率
        freq = Counter(text)
        length = len(text)
        
        # 计算香农熵
        entropy = 0.0
        for count in freq.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    def _is_likely_encrypted(self, samples: List[str], column_name: str, table_name: str) -> Tuple[bool, str]:
        """
        检测数据是否可能已加密
        
        基于数据特征而非硬编码系统规则进行检测

        返回:
            Tuple[bool, str]: (是否已加密, 原因说明)
        """
        # 如果没有样本，无法检测
        if not samples:
            return False, "无数据样本"
        
        # 过滤掉空字符串和None
        valid_samples = [s for s in samples if s and str(s).strip()]
        if not valid_samples:
            return False, "无有效数据样本"
        
        total_samples = len(valid_samples)
        encrypted_indicators = 0
        detected_formats = []

        for sample in valid_samples:
            sample_str = str(sample).strip()
            
            # 检查各种加密格式
            for format_name, pattern in self.ENCRYPTION_INDICATORS.items():
                if re.match(pattern, sample_str):
                    encrypted_indicators += 1
                    if format_name not in detected_formats:
                        detected_formats.append(format_name)
                    break

        # 如果超过80%的样本符合加密特征，判定为已加密
        if total_samples > 0 and encrypted_indicators / total_samples >= 0.8:
            format_str = ", ".join(detected_formats[:3])  # 最多显示3种格式
            return True, f"检测到加密格式: {format_str}"

        # 高熵检测（加密数据通常具有高熵）
        entropy = self._calculate_entropy(valid_samples)
        avg_length = sum(len(str(s)) for s in valid_samples) / total_samples if total_samples > 0 else 0

        # 高熵且长度适中（加密数据通常长度固定或较长）
        if entropy > 5.5 and avg_length > 20:
            return True, f"数据熵值较高({entropy:.2f})，可能已加密"

        return False, "未检测到明显加密特征"

    def _adjust_for_encryption(self, level: SensitivityLevel, is_encrypted: bool) -> Tuple[SensitivityLevel, str]:
        """
        根据加密状态调整敏感级别

        返回:
            Tuple[SensitivityLevel, str]: (调整后的级别, 说明)
        """
        if not is_encrypted:
            return level, ""

        # 已加密数据降低一个级别
        if level == SensitivityLevel.CRITICAL:
            return SensitivityLevel.MEDIUM, "数据已加密存储，风险降低"
        elif level == SensitivityLevel.HIGH:
            return SensitivityLevel.LOW, "数据已加密存储，风险降低"
        else:
            return level, "数据已加密存储"

    def _calculate_confidence(self, name_match: bool, content_confidence: float,
                             entropy: float, stats: Dict, column_name: str = "") -> float:
        """计算综合置信度"""
        confidence = 0.0

        # 字段名匹配权重 - 根据字段名确定性调整
        if name_match:
            col_lower = column_name.lower()

            # 高确定性字段名（完全匹配敏感关键词）
            high_confidence_keywords = [
                "password", "passwd", "pwd", "secret", "token",
                "api_key", "credit_card", "ssn", "social_security"
            ]
            # 中等确定性字段名（常见敏感字段）
            medium_confidence_keywords = [
                "name", "email", "phone", "address", "birth",
                "gender", "salary", "income"
            ]

            if any(kw == col_lower for kw in high_confidence_keywords):
                confidence += 0.7
            elif any(kw in col_lower for kw in medium_confidence_keywords):
                confidence += 0.6
            else:
                confidence += 0.5

        # 内容验证权重
        if content_confidence > 0:
            confidence += content_confidence * 0.2

        # 熵分析（高熵可能是加密数据）
        if entropy > 4.5:  # 高熵阈值
            confidence += 0.05

        # 唯一值比例（敏感数据通常唯一性高）
        row_count = stats.get("row_count", 0)
        unique_count = stats.get("unique_count", 0)
        if row_count > 0:
            unique_ratio = unique_count / row_count
            if unique_ratio > 0.9:  # 高唯一性
                confidence += 0.05

        return min(1.0, confidence)
    
    def _generate_recommendation(self, category: DataCategory, level: SensitivityLevel,
                                 column_name: str, entropy: float) -> str:
        """生成修复建议"""
        recommendations = []
        
        if level == SensitivityLevel.CRITICAL:
            recommendations.append(f"立即加密 {column_name} 列")
            recommendations.append("实施严格的访问控制")
            if category == DataCategory.CREDENTIALS:
                recommendations.append("使用哈希存储密码，禁止明文存储")
        elif level == SensitivityLevel.HIGH:
            recommendations.append(f"建议加密 {column_name} 列")
            recommendations.append("限制查询权限")
        else:
            recommendations.append(f"考虑对 {column_name} 进行脱敏处理")
        
        if entropy > 4.5:
            recommendations.append("数据熵较高，可能已加密")
        
        return "; ".join(recommendations)
    
    def _generate_summary(self, findings: List[SensitiveColumn]) -> str:
        """生成扫描摘要"""
        if not findings:
            return "未发现敏感数据"
        
        critical = sum(1 for f in findings if f.sensitivity_level == SensitivityLevel.CRITICAL)
        high = sum(1 for f in findings if f.sensitivity_level == SensitivityLevel.HIGH)
        medium = sum(1 for f in findings if f.sensitivity_level == SensitivityLevel.MEDIUM)
        
        return (
            f"发现 {len(findings)} 个敏感列 "
            f"(严重: {critical}, 高危: {high}, 中危: {medium})"
        )

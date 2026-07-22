"""HTML/CSS templates for report generator."""
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据库巡检报告 - {instance_name}</title>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --bg-card-hover: #263348;
            --bg-input: #0f172a;
            --border-color: #334155;
            --border-hover: #475569;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --critical: #ef476f;
            --high: #fd7e14;
            --medium: #ffd166;
            --low: #06d6a0;
            --info: #4cc9f0;
            --pass: #06d6a0;
            --warning: #ffd166;
            --fail: #ef476f;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
            --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
            --shadow-lg: 0 8px 30px rgba(0,0,0,0.5);
            --radius: 12px;
            --radius-sm: 8px;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
                         'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }}

        /* ========== Header ========== */
        .report-header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 50%, #1a1a3e 100%);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 40px;
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
        }}

        .report-header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent), #8b5cf6, var(--critical));
        }}

        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 30px;
        }}

        .header-title {{
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}

        .header-subtitle {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 6px;
        }}

        .header-badge {{
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
            color: var(--accent);
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }}

        .header-meta {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
        }}

        .meta-item {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: var(--radius-sm);
            padding: 14px 16px;
        }}

        .meta-label {{
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }}

        .meta-value {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
        }}

        /* ========== Stats Row ========== */
        .stats-row {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}

        @media (max-width: 900px) {{
            .stats-row {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}

        @media (max-width: 600px) {{
            .stats-row {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}

        .stat-card::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
        }}

        .stat-card.critical::after {{ background: var(--critical); }}
        .stat-card.high::after {{ background: var(--high); }}
        .stat-card.medium::after {{ background: var(--medium); }}
        .stat-card.low::after {{ background: var(--low); }}
        .stat-card.info::after {{ background: var(--info); }}

        .stat-card:hover {{
            transform: translateY(-3px);
            border-color: var(--border-hover);
            box-shadow: var(--shadow-md);
        }}

        .stat-num {{
            font-size: 36px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 6px;
        }}

        .stat-card.critical .stat-num {{ color: var(--critical); }}
        .stat-card.high .stat-num {{ color: var(--high); }}
        .stat-card.medium .stat-num {{ color: var(--medium); }}
        .stat-card.low .stat-num {{ color: var(--low); }}
        .stat-card.info .stat-num {{ color: var(--info); }}

        .stat-label {{
            font-size: 13px;
            color: var(--text-secondary);
        }}

        /* ========== Card ========== */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }}

        .card-title {{
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .card-title::before {{
            content: '';
            display: inline-block;
            width: 4px;
            height: 20px;
            background: var(--accent);
            border-radius: 2px;
        }}

        /* ========== Charts Grid ========== */
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }}

        @media (max-width: 900px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* ========== Donut Chart ========== */
        .donut-chart {{
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 10px 0;
        }}

        .donut-svg {{
            width: 200px;
            height: 200px;
        }}

        .donut-progress {{
            transition: stroke-dashoffset 1.5s ease;
        }}

        .donut-score {{
            font-size: 42px;
            font-weight: 700;
        }}

        .donut-grade {{
            font-size: 16px;
            font-weight: 500;
        }}

        /* ========== Risk Bar Chart ========== */
        .risk-chart {{
            padding: 8px 0;
        }}

        .bar-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 14px;
        }}

        .bar-label {{
            width: 48px;
            font-size: 13px;
            color: var(--text-secondary);
            text-align: right;
            flex-shrink: 0;
        }}

        .bar-track {{
            flex: 1;
            height: 22px;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
            overflow: hidden;
        }}

        .bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 1s ease;
            min-width: 2px;
        }}

        .bar-num {{
            width: 32px;
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            text-align: right;
            flex-shrink: 0;
        }}

        .bar-pct {{
            width: 52px;
            font-size: 12px;
            color: var(--text-muted);
            text-align: right;
            flex-shrink: 0;
        }}

        /* ========== Status Vertical Bar Chart ========== */
        .status-chart {{
            display: flex;
            justify-content: space-around;
            align-items: flex-end;
            height: 220px;
            padding: 20px 10px 0;
        }}

        .vbar-item {{
            text-align: center;
            flex: 1;
            max-width: 80px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .vbar-val {{
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 8px;
        }}

        .vbar-track {{
            width: 44px;
            height: 120px;
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
            display: flex;
            align-items: flex-end;
            overflow: hidden;
        }}

        .vbar-fill {{
            width: 100%;
            border-radius: 6px 6px 0 0;
            transition: height 1s ease;
            min-height: 4px;
        }}

        .vbar-label {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 10px;
        }}

        .vbar-pct {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        /* ========== High Risk Section ========== */
        .high-risk-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
            border-left: 4px solid var(--critical);
        }}

        .risk-count-badge {{
            background: rgba(239, 71, 111, 0.15);
            color: var(--critical);
            padding: 4px 14px;
            border-radius: 16px;
            font-size: 13px;
            font-weight: 600;
        }}

        .risk-item {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 20px;
            margin-bottom: 12px;
            border-left: 4px solid;
            transition: all 0.25s ease;
        }}

        .risk-item:hover {{
            background: var(--bg-card-hover);
            border-color: var(--border-hover);
        }}

        .risk-item.critical {{ border-left-color: var(--critical); }}
        .risk-item.high {{ border-left-color: var(--high); }}
        .risk-item.medium {{ border-left-color: var(--medium); }}
        .risk-item.low {{ border-left-color: var(--low); }}

        .risk-item-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}

        .risk-item-name {{
            font-size: 15px;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .level-tag {{
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .level-tag.critical {{ background: rgba(239,71,111,0.2); color: var(--critical); }}
        .level-tag.high {{ background: rgba(253,126,20,0.2); color: var(--high); }}
        .level-tag.medium {{ background: rgba(255,209,102,0.2); color: var(--medium); }}
        .level-tag.low {{ background: rgba(6,214,160,0.2); color: var(--low); }}

        .risk-item-desc {{
            color: var(--text-secondary);
            font-size: 14px;
            margin-bottom: 10px;
            line-height: 1.5;
        }}

        .risk-item-meta {{
            display: flex;
            gap: 16px;
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}

        .risk-item-suggestion {{
            background: rgba(59, 130, 246, 0.08);
            border: 1px solid rgba(59, 130, 246, 0.15);
            border-radius: 6px;
            padding: 12px 14px;
            font-size: 13px;
            color: #93c5fd;
            line-height: 1.5;
        }}

        .empty-state {{
            text-align: center;
            padding: 50px 20px;
            color: var(--text-muted);
        }}

        .empty-icon {{
            font-size: 40px;
            margin-bottom: 12px;
            color: var(--pass);
        }}

        .show-more {{
            text-align: center;
            color: var(--accent);
            margin-top: 16px;
            font-size: 13px;
            cursor: pointer;
            padding: 10px;
            border-radius: var(--radius-sm);
            transition: all 0.25s ease;
        }}

        .show-more:hover {{
            background: rgba(59, 130, 246, 0.08);
        }}

        /* ========== Details Section ========== */
        .details-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }}

        .toggle-btn {{
            background: rgba(59, 130, 246, 0.12);
            color: var(--accent);
            border: 1px solid rgba(59, 130, 246, 0.25);
            padding: 10px 22px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.25s ease;
        }}

        .toggle-btn:hover {{
            background: rgba(59, 130, 246, 0.2);
            border-color: rgba(59, 130, 246, 0.4);
        }}

        .collapsed {{
            display: none;
        }}

        .details-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 13px;
        }}

        .details-table th {{
            background: rgba(255,255,255,0.04);
            padding: 12px 14px;
            text-align: left;
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-color);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            position: sticky;
            top: 0;
        }}

        .details-table td {{
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            color: var(--text-primary);
        }}

        .details-table tr:hover td {{
            background: rgba(255,255,255,0.02);
        }}

        /* ========== Pagination ========== */
        .pagination {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
        }}

        .page-numbers {{
            display: flex;
            gap: 6px;
        }}

        .page-btn {{
            background: rgba(255,255,255,0.04);
            color: var(--text-secondary);
            border: 1px solid var(--border-color);
            padding: 8px 14px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s ease;
            min-width: 36px;
        }}

        .page-btn:hover:not(:disabled) {{
            background: rgba(59, 130, 246, 0.12);
            color: var(--accent);
            border-color: rgba(59, 130, 246, 0.3);
        }}

        .page-btn.active {{
            background: rgba(59, 130, 246, 0.2);
            color: var(--accent);
            border-color: var(--accent);
        }}

        .page-btn:disabled {{
            opacity: 0.4;
            cursor: not-allowed;
        }}

        .page-info {{
            color: var(--text-muted);
            font-size: 13px;
            margin-left: 12px;
        }}

        .status-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}

        .status-tag.pass {{ background: rgba(6,214,160,0.15); color: var(--pass); }}
        .status-tag.warning {{ background: rgba(255,209,102,0.15); color: var(--warning); }}
        .status-tag.fail {{ background: rgba(239,71,111,0.15); color: var(--fail); }}

        /* ========== Footer ========== */
        .report-footer {{
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 12px;
            border-top: 1px solid var(--border-color);
            margin-top: 10px;
        }}

        .chart-empty {{
            text-align: center;
            padding: 50px 20px;
            color: var(--text-muted);
            font-size: 14px;
        }}

        /* ========== Nav ========== */
        .report-nav {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 16px 24px;
            margin-bottom: 24px;
            position: sticky;
            top: 12px;
            z-index: 100;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .nav-label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-right: 8px;
        }}

        .nav-link {{
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-secondary);
            text-decoration: none;
            transition: all 0.2s ease;
            border: 1px solid transparent;
        }}

        .nav-link:hover {{
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent);
            border-color: rgba(59, 130, 246, 0.2);
        }}

        /* ========== Executive Summary ========== */
        .executive-summary {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }}

        .summary-text {{
            font-size: 15px;
            color: var(--text-secondary);
            line-height: 1.8;
            margin-bottom: 20px;
        }}

        .summary-text strong {{
            color: var(--text-primary);
        }}

        .summary-highlights {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }}

        .highlight-item {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 16px;
            display: flex;
            align-items: center;
            gap: 14px;
        }}

        .highlight-icon {{
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: 700;
            flex-shrink: 0;
        }}

        .highlight-icon.score {{ background: rgba(59,130,246,0.15); color: var(--accent); }}
        .highlight-icon.critical {{ background: rgba(239,71,111,0.15); color: var(--critical); }}
        .highlight-icon.warning {{ background: rgba(255,209,102,0.15); color: var(--warning); }}
        .highlight-icon.pass {{ background: rgba(6,214,160,0.15); color: var(--pass); }}

        .highlight-content {{
            flex: 1;
        }}

        .highlight-value {{
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .highlight-label {{
            font-size: 12px;
            color: var(--text-muted);
        }}

        /* ========== Category Pass Rate Chart ========== */
        .category-chart {{
            padding: 8px 0;
        }}

        .cat-bar-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}

        .cat-bar-label {{
            width: 72px;
            font-size: 13px;
            font-weight: 600;
            text-align: right;
            flex-shrink: 0;
        }}

        .cat-bar-track {{
            flex: 1;
            height: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
            overflow: hidden;
        }}

        .cat-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 1s ease;
            min-width: 2px;
        }}

        .cat-bar-info {{
            width: 80px;
            display: flex;
            align-items: center;
            gap: 6px;
            flex-shrink: 0;
        }}

        .cat-bar-rate {{
            font-size: 14px;
            font-weight: 700;
        }}

        .cat-bar-detail {{
            font-size: 11px;
            color: var(--text-muted);
        }}

        /* ========== Category Section ========== */
        .category-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }}

        .category-section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }}

        .category-title {{
            font-size: 17px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .category-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }}

        .category-desc {{
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 20px;
        }}

        .category-stats-bar {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}

        .cat-stat {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
        }}

        .cat-stat-label {{
            color: var(--text-muted);
        }}

        .cat-stat-value {{
            font-weight: 600;
        }}

        .cat-stat-value.pass {{ color: var(--pass); }}
        .cat-stat-value.warning {{ color: var(--warning); }}
        .cat-stat-value.fail {{ color: var(--fail); }}

        .category-pass-bar {{
            height: 6px;
            background: rgba(255,255,255,0.05);
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 20px;
        }}

        .category-pass-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 1s ease;
        }}

        .category-items {{
            display: grid;
            gap: 10px;
        }}

        .cat-item {{
            display: grid;
            grid-template-columns: 1fr auto auto auto;
            gap: 16px;
            align-items: center;
            padding: 14px 16px;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: var(--radius-sm);
            font-size: 13px;
            transition: all 0.2s ease;
        }}

        .cat-item:hover {{
            background: rgba(255,255,255,0.04);
            border-color: var(--border-color);
        }}

        .cat-item-name {{
            font-weight: 500;
            color: var(--text-primary);
        }}

        .cat-item-desc {{
            color: var(--text-muted);
            font-size: 12px;
            margin-top: 4px;
        }}

        .cat-item-value {{
            color: var(--text-secondary);
            font-size: 12px;
            text-align: right;
            max-width: 160px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .cat-item-suggestion {{
            color: #93c5fd;
            font-size: 12px;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        /* ========== Recommendations Section ========== */
        .recommendations-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
            border-left: 4px solid var(--accent);
        }}

        .rec-item {{
            display: flex;
            gap: 16px;
            padding: 16px;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: var(--radius-sm);
            margin-bottom: 10px;
            transition: all 0.2s ease;
        }}

        .rec-item:hover {{
            background: rgba(255,255,255,0.04);
            border-color: var(--border-color);
        }}

        .rec-priority {{
            width: 32px;
            height: 32px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            flex-shrink: 0;
        }}

        .rec-priority.p1 {{ background: rgba(239,71,111,0.2); color: var(--critical); }}
        .rec-priority.p2 {{ background: rgba(253,126,20,0.2); color: var(--high); }}
        .rec-priority.p3 {{ background: rgba(255,209,102,0.2); color: var(--medium); }}

        .rec-content {{
            flex: 1;
        }}

        .rec-title {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 4px;
        }}

        .rec-detail {{
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.5;
        }}

        .rec-meta {{
            display: flex;
            gap: 12px;
            margin-top: 6px;
            font-size: 11px;
            color: var(--text-muted);
        }}

        /* ========== Section Anchor Offset ========== */
        .section-anchor {{
            scroll-margin-top: 80px;
        }}

        /* ========== Animations ========== */
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(16px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .animate-in {{
            animation: fadeInUp 0.5s ease forwards;
            opacity: 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>

    <script>
        function toggleDetails() {{
            var details = document.getElementById('full-details');
            var btn = document.getElementById('toggle-btn');
            if (details.classList.contains('collapsed')) {{
                details.classList.remove('collapsed');
                btn.textContent = '收起详细列表';
            }} else {{
                details.classList.add('collapsed');
                btn.textContent = '展开详细列表';
            }}
        }}

        function toggleCategory(catId) {{
            var items = document.getElementById(catId);
            var btn = document.getElementById(catId + '-btn');
            if (items.classList.contains('collapsed')) {{
                items.classList.remove('collapsed');
                btn.textContent = '收起';
            }} else {{
                items.classList.add('collapsed');
                btn.textContent = '展开全部';
            }}
        }}

        // 分页功能
        var currentPage = 0;
        var totalPages = document.querySelectorAll('.page-content').length;

        function goToPage(page) {{
            if (page < 0 || page >= totalPages) return;

            // 隐藏所有页面
            var pages = document.querySelectorAll('.page-content');
            pages.forEach(function(p) {{
                p.style.display = 'none';
            }});

            // 显示目标页面
            var targetPage = document.getElementById('page-' + page);
            if (targetPage) {{
                targetPage.style.display = 'table-row-group';
            }}

            // 更新页码按钮状态
            var pageBtns = document.querySelectorAll('.page-numbers .page-btn');
            pageBtns.forEach(function(btn) {{
                btn.classList.remove('active');
                if (parseInt(btn.getAttribute('data-page')) === page) {{
                    btn.classList.add('active');
                }}
            }});

            // 更新上一页/下一页按钮状态
            var prevBtn = document.getElementById('prev-btn');
            var nextBtn = document.getElementById('next-btn');
            if (prevBtn) prevBtn.disabled = page === 0;
            if (nextBtn) nextBtn.disabled = page === totalPages - 1;

            // 更新当前页显示
            var currentPageSpan = document.getElementById('current-page');
            if (currentPageSpan) currentPageSpan.textContent = page + 1;

            currentPage = page;
        }}

        function prevPage() {{
            goToPage(currentPage - 1);
        }}

        function nextPage() {{
            goToPage(currentPage + 1);
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            var cards = document.querySelectorAll('.stat-card, .risk-item, .rec-item');
            cards.forEach(function(card, index) {{
                card.classList.add('animate-in');
                card.style.animationDelay = (index * 60) + 'ms';
            }});

            var bars = document.querySelectorAll('.bar-fill, .cat-bar-fill');
            bars.forEach(function(bar) {{
                var finalWidth = bar.style.width;
                bar.style.width = '0';
                setTimeout(function() {{
                    bar.style.width = finalWidth;
                }}, 400);
            }});

            var vbars = document.querySelectorAll('.vbar-fill');
            vbars.forEach(function(vbar) {{
                var finalHeight = vbar.style.height;
                vbar.style.height = '0';
                setTimeout(function() {{
                    vbar.style.height = finalHeight;
                }}, 400);
            }});

            var progress = document.querySelector('.donut-progress');
            if (progress) {{
                var finalOffset = progress.getAttribute('stroke-dashoffset');
                var circumference = progress.getAttribute('stroke-dasharray');
                progress.setAttribute('stroke-dashoffset', circumference);
                setTimeout(function() {{
                    progress.setAttribute('stroke-dashoffset', finalOffset);
                }}, 400);
            }}

            var passFills = document.querySelectorAll('.category-pass-fill');
            passFills.forEach(function(fill) {{
                var finalWidth = fill.style.width;
                fill.style.width = '0';
                setTimeout(function() {{
                    fill.style.width = finalWidth;
                }}, 500);
            }});
        }});
    </script>
</body>
</html>'''

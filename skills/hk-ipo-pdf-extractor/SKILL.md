# HK IPO PDF Structured Extraction Skill

## 1. Skill 名称

`hk_ipo_pdf_extractor`

## 2. Skill 目标

本 Skill 专门用于处理港股打新场景下的 HKEXnews PDF 文件，将港股新股相关 PDF 抽取为 Agent 可用的结构化数据。

本 Skill 的目标不是做投资建议，而是解决以下问题：

1. 这是什么新股？
2. 股票代码是多少？
3. 什么时候开始申购？
4. 什么时候截止申购？
5. 一手多少股？
6. 一手入场费是多少？
7. 招股价区间是多少？
8. 全球发售、香港公开发售、国际发售分别是多少股？
9. 是否有回拨机制？
10. 是否有超额配售权？
11. 什么时候公布中签结果？
12. 什么时候退款？
13. 什么时候上市交易？
14. 配发结果出来后，中签率、认购倍数、最终发售价是多少？
15. 招股书中是否有基本面、财务、募资用途、基石投资人、风险因素等分析所需字段？

本 Skill 输出结构化 JSON，供后续新股日历 Agent、打新提醒 Agent、IPO 分析 Agent、数据库入库系统使用。

---

## 3. 适用 PDF 类型

本 Skill 主要处理以下港股新股 PDF：

```text
1. Prospectus / 招股书
2. Global Offering Announcement / 全球发售公告
3. Allotment Results Announcement / 配发结果公告
4. Price Determination Announcement / 定价公告
5. Stabilization Announcement / 稳定价格行动公告
6. Supplemental Announcement / 补充公告
7. Post Hearing Information Pack / 聆讯后资料集
8. Application Proof / 申请版本
```

不同 PDF 的抽取重点不同：

| PDF 类型                           | 主要用途                         |
| -------------------------------- | ---------------------------- |
| Prospectus                       | 公司基本面、财务、募资用途、风险因素、基石投资人、保荐人 |
| Global Offering Announcement     | 申购时间、招股价、一手入场费、发售结构、上市时间     |
| Allotment Results Announcement   | 最终发售价、认购倍数、配发基准、中签率、回拨结果     |
| Price Determination Announcement | 最终发售价                        |
| Stabilization Announcement       | 绿鞋、稳定价格行动、超额配售情况             |
| Supplemental Announcement        | 时间表、发售条款、风险提示等修正信息           |

---

## 4. 输入格式

### 4.1 PDF URL 输入

```json
{
  "input_type": "url",
  "pdf_url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0630/2026063000121.pdf",
  "source": "hkexnews",
  "market": "HK",
  "language_hint": "auto"
}
```

### 4.2 本地 PDF 输入

```json
{
  "input_type": "file",
  "file_path": "/data/hk_ipo/2026063000121.pdf",
  "source": "local",
  "market": "HK",
  "language_hint": "auto"
}
```

---

## 5. 输出总结构

本 Skill 必须输出 JSON。

```json
{
  "success": true,
  "meta": {},
  "document_type": {},
  "company": {},
  "ipo_basic": {},
  "offering_structure": {},
  "pricing": {},
  "application": {},
  "application_money_table": [],
  "timetable": {},
  "allotment_result": {},
  "reallocation": {},
  "over_allotment": {},
  "cornerstone_investors": [],
  "sponsors_underwriters": {},
  "financial_snapshot": {},
  "business_snapshot": {},
  "use_of_proceeds": [],
  "risk_factors": [],
  "result_publication": {},
  "trading": {},
  "derived": {},
  "raw_evidence": [],
  "quality_check": {},
  "warnings": []
}
```

字段缺失时必须填 `null` 或空数组，不允许凭经验补全。

---

## 6. PDF 解析流程

```text
PDF URL / PDF 文件
    ↓
下载或读取 PDF
    ↓
记录 PDF 元数据
    ↓
判断 PDF 类型
    ↓
提取文本层
    ↓
提取表格
    ↓
必要时 OCR
    ↓
清理页眉、页脚、乱码
    ↓
按页、章节、表格切块
    ↓
根据港股打新关键词定位候选内容
    ↓
将候选文本块和表格传给大模型
    ↓
大模型抽取结构化 JSON
    ↓
程序规则校验
    ↓
生成 Agent 可用的派生字段
    ↓
输出最终 JSON
```

---

## 7. PDF 元数据

每次解析必须记录：

```json
{
  "meta": {
    "source_url": null,
    "file_path": null,
    "file_name": null,
    "file_sha256": null,
    "file_size_bytes": null,
    "downloaded_at": null,
    "page_count": null,
    "parser_version": "hk_ipo_pdf_extractor_v1"
  }
}
```

---

## 8. 文档类型识别

### 8.1 全球发售公告

识别关键词：

```text
Global Offering
Hong Kong Public Offering
International Offering
Maximum Offer Price
Expected Timetable
Application lists close
Dealings in the Shares expected to commence
White Form eIPO
HKSCC EIPO
FINI
```

输出：

```json
{
  "document_type": {
    "type": "global_offering_announcement",
    "title": null,
    "is_prospectus": false,
    "announcement_date": null,
    "language": null,
    "confidence": null
  }
}
```

### 8.2 招股书

识别关键词：

```text
Prospectus
Summary
Risk Factors
Business
Financial Information
Future Plans and Use of Proceeds
Cornerstone Investors
Underwriting
Directors and Parties Involved
```

输出：

```json
{
  "document_type": {
    "type": "prospectus",
    "title": null,
    "is_prospectus": true,
    "announcement_date": null,
    "language": null,
    "confidence": null
  }
}
```

### 8.3 配发结果公告

识别关键词：

```text
Allotment Results
Basis of Allocation
Valid Applications
Oversubscription
Reallocation
Final Offer Price
Number of valid applications
One-lot success rate
```

输出：

```json
{
  "document_type": {
    "type": "allotment_results_announcement",
    "title": null,
    "is_prospectus": false,
    "announcement_date": null,
    "language": null,
    "confidence": null
  }
}
```

### 8.4 定价公告

识别关键词：

```text
Offer Price
Final Offer Price
Price Determination
```

输出：

```json
{
  "document_type": {
    "type": "price_determination_announcement",
    "title": null,
    "is_prospectus": false,
    "announcement_date": null,
    "language": null,
    "confidence": null
  }
}
```

### 8.5 稳定价格行动公告

识别关键词：

```text
Stabilization Actions
Over-allotment Option
Stabilizing Manager
Lapse of Over-allotment Option
```

输出：

```json
{
  "document_type": {
    "type": "stabilization_announcement",
    "title": null,
    "is_prospectus": false,
    "announcement_date": null,
    "language": null,
    "confidence": null
  }
}
```

---

## 9. 港股打新必须抽取的信息

### 9.1 公司基础信息

用于识别新股。

必须抽取：

```json
{
  "company": {
    "english_name": null,
    "chinese_name": null,
    "stock_code": null,
    "share_type": null,
    "listing_board": null,
    "company_website": null,
    "incorporation_place": null,
    "industry": null
  }
}
```

字段说明：

| 字段                  | 说明                          |
| ------------------- | --------------------------- |
| english_name        | 公司英文名                       |
| chinese_name        | 公司中文名，保留 PDF 原文             |
| stock_code          | 股票代码                        |
| share_type          | H Shares / Shares / Units 等 |
| listing_board       | Main Board / GEM            |
| company_website     | 公司官网                        |
| incorporation_place | 注册地                         |
| industry            | 行业分类，优先从招股书摘要抽取             |

---

### 9.2 新股基础参数

用于打新日历和申购页面展示。

```json
{
  "ipo_basic": {
    "market": "HK",
    "exchange": "HKEX",
    "stock_code": null,
    "board_lot": null,
    "minimum_application_shares": null,
    "application_multiple": null,
    "currency": "HKD"
  }
}
```

重点字段：

| 字段                         | 说明           |
| -------------------------- | ------------ |
| board_lot                  | 每手股数         |
| minimum_application_shares | 最低申购股数       |
| application_multiple       | 申购递增单位       |
| currency                   | 申购币种，通常为 HKD |

---

### 9.3 发售结构

用于判断发行规模和香港公开发售比例。

```json
{
  "offering_structure": {
    "global_offering_shares": null,
    "hong_kong_offer_shares": null,
    "international_offer_shares": null,
    "hk_public_initial_ratio": null,
    "international_initial_ratio": null,
    "offer_shares_before_over_allotment": null,
    "offer_shares_after_over_allotment": null
  }
}
```

重点抽取关键词：

```text
Number of Offer Shares under the Global Offering
Number of Hong Kong Offer Shares
Number of International Offer Shares
Global Offering
Hong Kong Public Offering
International Offering
```

校验规则：

```text
global_offering_shares ≈ hong_kong_offer_shares + international_offer_shares
```

---

### 9.4 招股价与最终发售价

用于计算一手入场费、估值、募资规模。

```json
{
  "pricing": {
    "offer_price_min": null,
    "offer_price_max": null,
    "maximum_offer_price": null,
    "final_offer_price": null,
    "currency": "HKD",
    "nominal_value": null
  }
}
```

不同 PDF 的处理规则：

| PDF 类型                           | 字段                                                  |
| -------------------------------- | --------------------------------------------------- |
| Global Offering Announcement     | offer_price_min、offer_price_max、maximum_offer_price |
| Prospectus                       | offer_price_min、offer_price_max                     |
| Allotment Results Announcement   | final_offer_price                                   |
| Price Determination Announcement | final_offer_price                                   |

---

### 9.5 费用率

用于复核一手入场费。

```json
{
  "fees": {
    "brokerage_rate": null,
    "sfc_transaction_levy_rate": null,
    "hkex_trading_fee_rate": null,
    "afrc_transaction_levy_rate": null,
    "total_fee_rate": null,
    "raw_fee_text": null
  }
}
```

抽取规则：

```text
百分比需要同时保留原文和 decimal。
例如：
1.0% -> 0.01
0.0027% -> 0.000027
```

---

### 9.6 申购渠道

用于告诉用户怎么申购、截止时间是什么。

```json
{
  "application": {
    "channels": [
      {
        "name": null,
        "platform": null,
        "target_investors": null,
        "start_time": null,
        "latest_application_time": null,
        "latest_payment_time": null,
        "notes": null
      }
    ],
    "minimum_application_shares": null,
    "application_multiple": null,
    "max_public_application_shares": null
  }
}
```

重点关键词：

```text
White Form eIPO
HKSCC EIPO
FINI
CCASS
Nominee
Application lists
electronic application instructions
```

---

### 9.7 申购金额表

这是港股打新最核心的表格之一，用于一手、多手申购金额展示。

输出：

```json
{
  "application_money_table": [
    {
      "shares": null,
      "amount_payable_hkd": null,
      "source_page": null,
      "raw_text": null
    }
  ]
}
```

必须抽取的表格标题关键词：

```text
No. of Hong Kong Offer Shares applied for
Amount payable on application
Application Money
```

处理规则：

1. 表格通常是多列布局。
2. 必须按“申购股数 -> 应缴金额”配对。
3. 不能简单按行拼接。
4. 金额去除逗号，转为 number。
5. 股数去除逗号，转为 integer。
6. 第一行通常是一手入场费来源。
7. 一手入场费应写入 `derived.one_lot_entry_fee_hkd`。

---

### 9.8 时间表

用于新股日历、提醒、状态机。

```json
{
  "timetable": {
    "public_offering_start": null,
    "white_form_eipo_deadline": null,
    "hkscc_eipo_deadline": null,
    "application_list_open": null,
    "application_payment_deadline": null,
    "application_list_close": null,
    "price_determination_date": null,
    "allotment_result_announcement": null,
    "refund_date": null,
    "share_certificate_dispatch_date": null,
    "share_certificate_valid_time": null,
    "dealing_start": null,
    "timezone": "Asia/Hong_Kong"
  }
}
```

重点关键词：

```text
Expected Timetable
Hong Kong Public Offering commences
Latest time for completing electronic applications
Application lists open
Application lists close
Price Determination Date
Announcement of final Offer Price
Announcement of allotment results
Despatch of share certificates
Despatch of refund cheques
Dealings in the Shares expected to commence
```

时间标准化规则：

```text
9:00 a.m. -> 09:00:00
12:00 noon -> 12:00:00
11:00 p.m. -> 23:00:00
Hong Kong time -> Asia/Hong_Kong
```

输出日期时间必须使用 ISO 8601：

```json
{
  "dealing_start": "2026-07-10T09:00:00+08:00"
}
```

---

### 9.9 回拨机制

用于判断香港公开发售比例是否可能提高。

```json
{
  "reallocation": {
    "is_reallocation_possible": null,
    "initial_hk_public_ratio": null,
    "max_hk_public_offer_shares_after_reallocation": null,
    "max_hk_public_ratio_after_reallocation": null,
    "trigger_conditions": [],
    "condition_summary": null
  }
}
```

重点关键词：

```text
Reallocation
Clawback
Hong Kong Public Offering
oversubscribed
subscription
```

处理规则：

1. 抽取初始香港公开发售比例。
2. 抽取最高可回拨比例。
3. 抽取触发条件。
4. 如果 PDF 没有明确说明，不要猜测。

---

### 9.10 超额配售权 / 绿鞋

用于判断发行规模是否可能扩大，以及后续稳定价格行动。

```json
{
  "over_allotment": {
    "has_over_allotment_option": null,
    "max_additional_shares": null,
    "percentage_of_global_offering": null,
    "exercise_deadline": null,
    "stabilization_end_date": null,
    "stabilizing_manager": null,
    "status": null
  }
}
```

重点关键词：

```text
Over-allotment Option
Stabilizing Manager
stabilization period
additional Shares
15%
lapse
exercised
partially exercised
fully exercised
```

---

### 9.11 配发结果

只在 Allotment Results Announcement 中重点抽取。

```json
{
  "allotment_result": {
    "final_offer_price": null,
    "net_proceeds": null,
    "hong_kong_public_offer_subscription_times": null,
    "international_offer_subscription_times": null,
    "valid_applications_count": null,
    "valid_application_shares": null,
    "one_lot_success_rate": null,
    "reallocation_triggered": null,
    "final_hk_public_offer_shares": null,
    "final_international_offer_shares": null,
    "basis_of_allocation": []
  }
}
```

`basis_of_allocation` 输出：

```json
{
  "basis_of_allocation": [
    {
      "applied_shares": null,
      "valid_applications": null,
      "basis": null,
      "allotment_shares": null,
      "success_rate": null,
      "source_page": null
    }
  ]
}
```

重点关键词：

```text
Basis of Allocation
Valid Applications
Number of valid applications
Approximate percentage allotted
One-lot success rate
Final Offer Price
Hong Kong Public Offering has been over-subscribed
International Offering has been over-subscribed
```

---

### 9.12 基石投资人

主要从招股书或全球发售公告抽取。

```json
{
  "cornerstone_investors": [
    {
      "name": null,
      "investment_amount": null,
      "currency": null,
      "shares_subscribed": null,
      "lockup_period_months": null,
      "raw_text": null,
      "source_page": null
    }
  ]
}
```

重点关键词：

```text
Cornerstone Investors
Cornerstone Investment Agreements
lock-up
investment amount
```

---

### 9.13 保荐人、整体协调人、账簿管理人、承销商

用于新股质量分析。

```json
{
  "sponsors_underwriters": {
    "sole_sponsor": [],
    "joint_sponsors": [],
    "overall_coordinators": [],
    "joint_global_coordinators": [],
    "joint_bookrunners": [],
    "joint_lead_managers": [],
    "underwriters": [],
    "needs_ocr_for_logos": false
  }
}
```

处理规则：

1. 首页机构名称可能是 logo 图片。
2. 如果文本层无法识别，要 OCR 首页和相关页面。
3. 不允许凭经验补充机构名称。
4. 如果只能识别角色，不能识别机构，设置 `needs_ocr_for_logos = true`。

---

### 9.14 财务快照

主要从招股书中抽取，用于后续 IPO 分析。

```json
{
  "financial_snapshot": {
    "reporting_periods": [],
    "revenue": [],
    "gross_profit": [],
    "gross_margin": [],
    "net_profit": [],
    "adjusted_net_profit": [],
    "operating_cash_flow": [],
    "cash_and_cash_equivalents": [],
    "total_assets": [],
    "total_liabilities": []
  }
}
```

字段格式：

```json
{
  "revenue": [
    {
      "period": "2023",
      "value": null,
      "currency": null,
      "unit": null,
      "raw_text": null,
      "source_page": null
    }
  ]
}
```

重点章节：

```text
Summary
Financial Information
Selected Consolidated Financial Information
Revenue
Gross Profit
Profit for the Year
Non-IFRS Measures
```

---

### 9.15 业务摘要

主要从招股书中抽取，供用户快速理解公司做什么。

```json
{
  "business_snapshot": {
    "business_description": null,
    "main_products_services": [],
    "business_model": null,
    "major_customers": [],
    "major_suppliers": [],
    "market_position": null,
    "industry": null
  }
}
```

重点章节：

```text
Summary
Business
Overview
Our Products
Our Services
Customers
Suppliers
Competitive Strengths
```

---

### 9.16 募资用途

主要从招股书中抽取。

```json
{
  "use_of_proceeds": [
    {
      "purpose": null,
      "percentage": null,
      "amount": null,
      "currency": null,
      "raw_text": null,
      "source_page": null
    }
  ]
}
```

重点关键词：

```text
Use of Proceeds
Future Plans and Use of Proceeds
Net Proceeds
```

---

### 9.17 风险因素

主要从招股书中抽取。

```json
{
  "risk_factors": [
    {
      "risk_title": null,
      "risk_summary": null,
      "category": null,
      "source_page": null,
      "raw_text": null
    }
  ]
}
```

风险分类建议：

```text
business_risk
financial_risk
customer_concentration_risk
supplier_risk
regulatory_risk
industry_risk
technology_risk
competition_risk
litigation_risk
macro_risk
```

要求：

1. 不要抽取整章全文。
2. 抽取风险标题和简短摘要。
3. 保留原文证据。
4. 不做投资建议。

---

### 9.18 结果公布渠道

用于提醒用户在哪里查中签。

```json
{
  "result_publication": {
    "final_offer_price_announcement_time": null,
    "allocation_results_announcement_time": null,
    "channels": [
      {
        "name": null,
        "url": null,
        "method": null
      }
    ]
  }
}
```

重点关键词：

```text
results of allocations
final Offer Price
Hong Kong Stock Exchange website
Company website
iporesults
eIPO
telephone enquiry
```

---

### 9.19 交易安排

用于上市日提醒。

```json
{
  "trading": {
    "stock_code": null,
    "board_lot": null,
    "dealing_start": null,
    "ccass_eligible": null,
    "trading_currency": "HKD"
  }
}
```

重点关键词：

```text
Dealings in the Shares
Stock code
board lot
CCASS
eligible securities
```

---

## 10. 派生字段

Skill 需要生成适合 Agent 使用的派生字段。

```json
{
  "derived": {
    "one_lot_entry_fee_hkd": null,
    "subscription_window": {
      "start": null,
      "end": null
    },
    "ipo_status": null,
    "important_reminders": [],
    "is_result_announced": false,
    "is_listed": false,
    "has_prospectus_data": false,
    "has_allotment_data": false
  }
}
```

### 10.1 IPO 状态机

```text
当前时间 < 申购开始时间:
    upcoming

申购开始时间 <= 当前时间 < 申购截止时间:
    open_for_subscription

申购截止时间 <= 当前时间 < 公布结果时间:
    closed_waiting_result

公布结果时间 <= 当前时间 < 上市交易时间:
    result_announced_waiting_listing

当前时间 >= 上市交易时间:
    listed
```

### 10.2 重要提醒

```json
{
  "important_reminders": [
    {
      "type": "application_deadline",
      "time": null,
      "message": "申购截止"
    },
    {
      "type": "allotment_result",
      "time": null,
      "message": "公布配发结果"
    },
    {
      "type": "listing",
      "time": null,
      "message": "上市交易"
    }
  ]
}
```

---

## 11. 传给大模型的数据

不要直接把完整 PDF 原文件传给大模型。

应先由程序抽取文本、表格和候选字段，再传给大模型。

```json
{
  "task": "extract_hk_ipo_structured_data",
  "document_type_hint": "global_offering_announcement",
  "source_url": null,
  "candidate_chunks": [
    {
      "chunk_id": "page_2_block_1",
      "page_no": 2,
      "chunk_type": "text",
      "section_title": null,
      "text": null
    }
  ],
  "tables": [
    {
      "table_id": "page_5_table_1",
      "page_no": 5,
      "table_name": "Expected Timetable",
      "headers": [],
      "rows": []
    }
  ],
  "target_schema": {}
}
```

---

## 12. 字段定位关键词

程序应优先搜索以下关键词附近内容。

### 12.1 基础信息关键词

```text
Stock code
Company
Company Limited
股份有限公司
H Shares
Main Board
GEM
```

### 12.2 申购关键词

```text
Hong Kong Public Offering
White Form eIPO
HKSCC EIPO
Application lists
Latest time for completing
Application monies
Amount payable
```

### 12.3 价格关键词

```text
Offer Price
Maximum Offer Price
Final Offer Price
HK$
```

### 12.4 时间表关键词

```text
Expected Timetable
commences
closes
Price Determination Date
Allotment Results
refund
share certificates
Dealings
```

### 12.5 配发结果关键词

```text
Allotment Results
Basis of Allocation
Valid Applications
Oversubscribed
One-lot success rate
Reallocation
```

### 12.6 招股书分析关键词

```text
Summary
Risk Factors
Business
Financial Information
Use of Proceeds
Cornerstone Investors
Underwriting
```

---

## 13. 大模型抽取 Prompt

```text
你是港股新股 PDF 结构化抽取助手。

请根据输入的 HKEX PDF 文本块、表格和 OCR 内容，抽取港股打新相关字段。

要求：
1. 只能根据输入内容抽取，不要使用外部知识。
2. 不要猜测，缺失字段填 null。
3. 日期统一转换为 ISO 8601 格式。
4. 港股时间默认使用 Asia/Hong_Kong 时区。
5. 金额去除千分位逗号，并转为 number。
6. 股数去除千分位逗号，并转为 integer。
7. 百分比同时保留原文和 decimal 数值。
8. 表格数据必须保持原始行列关系。
9. 每个关键字段必须给出 evidence，包括 page_no、chunk_id、原文片段。
10. 如果字段来自计算，需要说明计算来源。
11. 输出严格 JSON，不要输出解释性文字。
12. 不要给出是否值得申购的投资建议。

重点抽取：
- 公司名称
- 股票代码
- 一手股数
- 招股价区间
- 最终发售价
- 一手入场费
- 申购开始时间
- 申购截止时间
- 公布结果时间
- 上市交易时间
- 全球发售股份数
- 香港公开发售股份数
- 国际发售股份数
- 回拨机制
- 超额配售权
- 配发结果
- 认购倍数
- 中签率
- 基石投资人
- 保荐人和承销商
- 财务快照
- 募资用途
- 风险因素
```

---

## 14. Evidence 证据格式

所有关键字段必须保留证据。

```json
{
  "raw_evidence": [
    {
      "field_path": "company.stock_code",
      "page_no": 2,
      "chunk_id": "page_2_block_1",
      "source_type": "text",
      "text": "Stock code : 2249"
    },
    {
      "field_path": "application_money_table[0].amount_payable_hkd",
      "page_no": 12,
      "chunk_id": "page_12_table_1",
      "source_type": "table",
      "text": "100 shares HK$3,262.57"
    }
  ]
}
```

要求：

1. evidence 必须来自 PDF 原文。
2. 不能把模型总结当作 evidence。
3. 表格字段必须记录 table_id。
4. OCR 字段必须记录 OCR 置信度。
5. 派生字段必须记录计算来源字段。

---

## 15. 数据标准化规则

### 15.1 日期时间

原文：

```text
9:00 a.m. on Tuesday, June 30, 2026
12:00 noon on Tuesday, July 7, 2026
no later than 11:00 p.m. on Thursday, July 9, 2026
```

标准化：

```json
{
  "time": "2026-06-30T09:00:00+08:00",
  "timezone": "Asia/Hong_Kong",
  "raw_text": "9:00 a.m. on Tuesday, June 30, 2026"
}
```

### 15.2 金额

原文：

```text
HK$3,262.57
HK$30.00
RMB1.00
```

标准化：

```json
{
  "value": 3262.57,
  "currency": "HKD",
  "raw_text": "HK$3,262.57"
}
```

### 15.3 股数

原文：

```text
216,167,000 H Shares
```

标准化：

```json
{
  "value": 216167000,
  "unit": "shares",
  "raw_text": "216,167,000 H Shares"
}
```

### 15.4 百分比

原文：

```text
15%
```

标准化：

```json
{
  "raw_text": "15%",
  "decimal": 0.15
}
```

---

## 16. 质量校验规则

输出前必须执行质量校验。

```json
{
  "quality_check": {
    "is_valid_json": true,
    "has_company_name": false,
    "has_stock_code": false,
    "has_offer_price": false,
    "has_board_lot": false,
    "has_application_deadline": false,
    "has_listing_time": false,
    "has_application_money_table": false,
    "has_evidence": false,
    "needs_ocr": false,
    "confidence": 0.0,
    "warnings": []
  }
}
```

必须校验：

1. 股票代码必须是 4 位或 5 位数字。
2. 上市时间不能早于申购截止时间。
3. 公布结果时间通常不能早于申购截止时间。
4. 一手入场费应大于 `最高招股价 × 每手股数`。
5. 全球发售股份数应接近等于香港公开发售股份数 + 国际发售股份数。
6. 百分比 decimal 应在 0 到 1 之间。
7. 如果文档声明不是招股书，则 `is_prospectus = false`。
8. 如果保荐人或承销商是图片但 OCR 未识别，应提示 `needs_ocr_for_logos = true`。
9. 如果没有配发结果公告，不允许输出中签率。
10. 如果没有最终发售价公告，不允许把最高招股价当作最终发售价。

---

## 17. 错误处理

### 17.1 PDF 下载失败

```json
{
  "success": false,
  "error_type": "download_failed",
  "message": "PDF download failed"
}
```

### 17.2 PDF 无法解析

```json
{
  "success": false,
  "error_type": "pdf_parse_failed",
  "message": "Unable to extract text, table, or OCR content from PDF"
}
```

### 17.3 大模型输出非法 JSON

```json
{
  "success": false,
  "error_type": "llm_json_invalid",
  "message": "LLM output is not valid JSON"
}
```

### 17.4 关键字段缺失

```json
{
  "success": true,
  "warning_type": "missing_required_fields",
  "missing_fields": [
    "stock_code",
    "application_deadline",
    "board_lot"
  ]
}
```

---

## 18. Agent 使用原则

调用本 Skill 的上层 Agent 应遵守：

1. 本 Skill 只负责抽取数据，不直接判断是否值得打新。
2. 如果只有全球发售公告，不能声称已经完成基本面分析。
3. 如果没有招股书，不能输出财务质量结论。
4. 如果没有配发结果公告，不能输出中签率。
5. 如果没有暗盘数据，不能推测上市首日涨跌。
6. 如果字段缺失，应提示需要补充对应 PDF。
7. 如果用户问“值得打吗”，应交给 IPO 分析 Skill，而不是本 Skill 直接回答。

---

## 19. 推荐数据库表设计

### 19.1 `hk_ipo_master`

存储每只新股的基础信息。

```json
{
  "stock_code": null,
  "company_name_en": null,
  "company_name_cn": null,
  "listing_board": null,
  "industry": null,
  "source_url": null
}
```

### 19.2 `hk_ipo_offering`

存储发售结构和定价。

```json
{
  "stock_code": null,
  "offer_price_min": null,
  "offer_price_max": null,
  "final_offer_price": null,
  "global_offering_shares": null,
  "hong_kong_offer_shares": null,
  "international_offer_shares": null,
  "board_lot": null,
  "one_lot_entry_fee_hkd": null
}
```

### 19.3 `hk_ipo_timetable`

存储关键时间。

```json
{
  "stock_code": null,
  "application_start": null,
  "application_deadline": null,
  "allotment_result_time": null,
  "refund_date": null,
  "listing_time": null
}
```

### 19.4 `hk_ipo_allotment`

存储配发结果。

```json
{
  "stock_code": null,
  "final_offer_price": null,
  "public_subscription_times": null,
  "international_subscription_times": null,
  "one_lot_success_rate": null,
  "basis_of_allocation": []
}
```

### 19.5 `hk_ipo_prospectus_snapshot`

存储招股书基本面快照。

```json
{
  "stock_code": null,
  "business_description": null,
  "revenue": [],
  "net_profit": [],
  "gross_margin": [],
  "use_of_proceeds": [],
  "cornerstone_investors": [],
  "risk_factors": []
}
```

---

## 20. 最小可用版本 MVP

MVP 至少稳定抽取以下字段：

```json
{
  "stock_code": null,
  "company_name_en": null,
  "company_name_cn": null,
  "document_type": null,
  "offer_price_min": null,
  "offer_price_max": null,
  "final_offer_price": null,
  "board_lot": null,
  "one_lot_entry_fee_hkd": null,
  "application_start": null,
  "application_deadline": null,
  "allotment_result_time": null,
  "listing_time": null,
  "source_url": null
}
```

MVP 支持的 Agent 功能：

```text
1. 新股日历
2. 申购提醒
3. 一手入场费展示
4. 公布结果提醒
5. 上市交易提醒
6. PDF 字段问答
```

---

## 21. 后续增强方向

后续版本可以增加：

```text
1. 招股书财务数据抽取
2. 基石投资人抽取
3. 保荐人评分数据接入
4. 中签率计算和展示
5. 暗盘数据接入
6. 上市首日表现跟踪
7. 同行业估值对比
8. 认购热度跟踪
9. 多 PDF 合并更新同一只新股
10. 自动发现 HKEXnews 新 PDF
```

---

## 22. Skill 边界

本 Skill 不负责：

```text
投资建议
买卖推荐
盈利预测
中签率预测
暗盘价格预测
上市首日涨跌预测
自动申购
自动下单
舆情判断
估值结论
```

本 Skill 只负责：

```text
读取港股新股 PDF
抽取文本和表格
识别文档类型
抽取港股打新字段
标准化日期、金额、股数、百分比
保留证据
输出结构化 JSON
```

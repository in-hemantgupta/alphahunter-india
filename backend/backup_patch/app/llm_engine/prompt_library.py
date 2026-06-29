REPORT_PROMPT = """

Analyze this annual report.

Find:

1 Revenue growth drivers

2 New capex plans

3 Management confidence level

4 Expansion initiatives

5 Future guidance

6 Business risks

7 Any warning signals

Return structured JSON.

"""


COMPARE_PROMPT = """

Compare previous quarter transcript

with current quarter transcript.

Detect:

Management confidence increase

Margin commentary change

Demand commentary change

Capex guidance changes

Tone change

"""


SHIFT_PROMPT = """

Compare old report vs new report.

Detect narrative shift.

Is management more optimistic?

Has guidance improved?

Any material changes?

"""


GOVERNANCE_PROMPT = """

Analyze governance quality.

Detect:

Accounting red flags

Auditor concerns

Promoter issues

Related party risks

Capital allocation concerns

"""


RISK_PROMPT = """

Find hidden risks management is not emphasizing.

Detect:

Supply chain risk

Customer concentration

Regulatory risk

Margin pressure

Working capital issues

"""

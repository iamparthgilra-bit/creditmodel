
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Credit Decisioning Engine",
    page_icon="💳",
    layout="wide"
)

st.title("💳 Credit Decisioning Engine")
st.caption("Eligibility + Account Aggregator enrichment + Basel risk + IFRS 9 ECL")

# -----------------------------
# Core calculations
# -----------------------------

def calculate_emi(principal, annual_rate, months):
    r = annual_rate / 12
    if r == 0:
        return principal / months
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def estimate_pd(cibil, foir, aa_bounce_count=0):
    pd = 0.02

    if cibil < 650:
        pd += 0.15
    elif cibil < 700:
        pd += 0.08
    elif cibil < 750:
        pd += 0.03

    if foir > 0.60:
        pd += 0.10
    elif foir > 0.40:
        pd += 0.05

    if aa_bounce_count >= 3:
        pd += 0.05
    elif aa_bounce_count >= 1:
        pd += 0.02

    return min(pd, 0.99)


def estimate_lgd(ltv):
    if ltv <= 0.70:
        return 0.20
    elif ltv <= 0.80:
        return 0.30
    elif ltv <= 0.90:
        return 0.40
    return 0.55


def determine_stage(dpd, cibil):
    if dpd >= 90:
        return 3
    elif dpd >= 30 or cibil < 650:
        return 2
    return 1


def calculate_ecl(loan_amount, tenure, annual_rate, pd, lgd, stage):
    monthly_rate = annual_rate / 12
    emi = calculate_emi(loan_amount, annual_rate, tenure)

    horizon = min(12, tenure) if stage == 1 else tenure

    annual_pd = pd
    if stage == 2:
        annual_pd = min(pd * 1.75, 0.99)
    elif stage == 3:
        annual_pd = min(pd * 2.50, 0.99)

    monthly_pd = 1 - (1 - annual_pd) ** (1 / 12)

    balance = loan_amount
    total_ecl = 0
    schedule = []

    for month in range(1, horizon + 1):
        interest = balance * monthly_rate
        principal = min(max(emi - interest, 0), balance)
        balance = max(balance - principal, 0)

        ead = balance + principal
        adjusted_lgd = max(
            0.15,
            lgd - (month / tenure) * 0.05
        )
        discount_factor = 1 / ((1 + monthly_rate) ** month)

        monthly_ecl = (
            monthly_pd
            * adjusted_lgd
            * ead
            * discount_factor
        )

        total_ecl += monthly_ecl

        schedule.append({
            "Month": month,
            "PD": monthly_pd,
            "LGD": adjusted_lgd,
            "EAD": ead,
            "Monthly ECL": monthly_ecl
        })

        if balance <= 0:
            break

    return total_ecl, emi, pd * lgd * loan_amount, pd, schedule


def run_underwriting(
    income,
    existing_emi,
    loan_amount,
    vehicle_value,
    tenure,
    cibil,
    dpd,
    age,
    employment_months,
    aa_used,
    aa_bounce_count
):
    new_emi = calculate_emi(loan_amount, 0.15, tenure)
    total_emi = existing_emi + new_emi
    foir = total_emi / income
    ltv = loan_amount / vehicle_value

    pd = estimate_pd(cibil, foir, aa_bounce_count if aa_used else 0)
    lgd = estimate_lgd(ltv)
    stage = determine_stage(dpd, cibil)

    ecl, emi, basel_el, pd, schedule = calculate_ecl(
        loan_amount,
        tenure,
        0.15,
        pd,
        lgd,
        stage
    )

    failures = []

    if age < 21 or age > 60:
        failures.append("Age outside 21–60")
    if employment_months < 12:
        failures.append("Employment tenure below 12 months")
    if cibil < 650:
        failures.append("CIBIL below 650")
    if foir > 0.60:
        failures.append("FOIR above 60%")
    if ltv > 0.90:
        failures.append("LTV above 90%")

    # AA is designed to resolve information/affordability uncertainty,
    # not override hard policy failures.
    hard_failure = (
        age < 21 or age > 60 or
        employment_months < 12 or
        cibil < 650 or
        ltv > 0.90
    )

    if hard_failure:
        decision = "REJECT"
    elif ecl <= 3000:
        decision = "APPROVE"
    elif ecl <= 8000:
        decision = "MANUAL REVIEW"
    else:
        decision = "REJECT"

    return {
        "income": income,
        "existing_emi": existing_emi,
        "new_emi": emi,
        "total_emi": total_emi,
        "foir": foir,
        "ltv": ltv,
        "pd": pd,
        "lgd": lgd,
        "ead": loan_amount,
        "basel_el": basel_el,
        "stage": stage,
        "ecl": ecl,
        "decision": decision,
        "failures": failures,
        "schedule": schedule
    }


# -----------------------------
# Sidebar: Application data
# -----------------------------

st.sidebar.header("Application Data")

income = st.sidebar.number_input(
    "Monthly income (₹)", 10000, 1000000, 40000, 1000
)

existing_emi = st.sidebar.number_input(
    "Existing EMI (₹)", 0, 500000, 18000, 1000
)

loan_amount = st.sidebar.number_input(
    "Loan amount (₹)", 10000, 5000000, 100000, 5000
)

vehicle_value = st.sidebar.number_input(
    "Vehicle value (₹)", 10000, 5000000, 125000, 5000
)

tenure = st.sidebar.slider(
    "Tenure (months)", 6, 84, 36
)

cibil = st.sidebar.slider(
    "CIBIL score", 300, 900, 720
)

dpd = st.sidebar.slider(
    "Current DPD", 0, 180, 0
)

age = st.sidebar.slider(
    "Age", 18, 70, 30
)

employment_months = st.sidebar.slider(
    "Employment tenure (months)", 0, 240, 24
)

st.sidebar.divider()

st.sidebar.header("Account Aggregator")

aa_used = st.sidebar.checkbox(
    "Customer provided AA consent/data"
)

if aa_used:
    st.sidebar.success("AA data available")

    aa_income = st.sidebar.number_input(
        "AA verified monthly income (₹)",
        0, 1000000, 55000, 1000
    )

    aa_existing_emi = st.sidebar.number_input(
        "AA verified existing EMI (₹)",
        0, 500000, 10000, 1000
    )

    aa_bounce_count = st.sidebar.number_input(
        "Bank bounces in last 6 months",
        0, 20, 0
    )

    aa_salary_credits = st.sidebar.number_input(
        "Salary credits in last 6 months",
        0, 6, 6
    )

else:
    aa_income = income
    aa_existing_emi = existing_emi
    aa_bounce_count = 0
    aa_salary_credits = 0


# -----------------------------
# Main screen
# -----------------------------

st.markdown("### 1. Initial Underwriting")

initial = run_underwriting(
    income,
    existing_emi,
    loan_amount,
    vehicle_value,
    tenure,
    cibil,
    dpd,
    age,
    employment_months,
    False,
    0
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("FOIR", f"{initial['foir']*100:.1f}%")
col2.metric("LTV", f"{initial['ltv']*100:.1f}%")
col3.metric("PD", f"{initial['pd']*100:.1f}%")
col4.metric("Decision", initial["decision"])

if initial["failures"]:
    st.warning("Initial policy exceptions:")
    for x in initial["failures"]:
        st.write("• " + x)

st.divider()

# -----------------------------
# AA reassessment
# -----------------------------

st.markdown("### 2. Account Aggregator Reassessment")

if initial["decision"] == "REJECT" and not aa_used:
    st.info(
        "Customer is rejected based on the initial information. "
        "AA can be offered for financial-data enrichment where appropriate."
    )

if aa_used:

    consolidated_income = max(income, aa_income)
    consolidated_emi = aa_existing_emi

    st.write("### Consolidated Financial Profile")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Application Income",
        f"₹{income:,.0f}"
    )

    c2.metric(
        "AA Verified Income",
        f"₹{aa_income:,.0f}"
    )

    c3.metric(
        "Consolidated Income",
        f"₹{consolidated_income:,.0f}"
    )

    c4.metric(
        "Verified Existing EMI",
        f"₹{consolidated_emi:,.0f}"
    )

    reassessed = run_underwriting(
        consolidated_income,
        consolidated_emi,
        loan_amount,
        vehicle_value,
        tenure,
        cibil,
        dpd,
        age,
        employment_months,
        True,
        aa_bounce_count
    )

    st.markdown("### 3. Final Decision After AA")

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Consolidated FOIR",
        f"{reassessed['foir']*100:.1f}%"
    )

    col2.metric(
        "PD",
        f"{reassessed['pd']*100:.1f}%"
    )

    col3.metric(
        "Basel EL",
        f"₹{reassessed['basel_el']:,.0f}"
    )

    col4.metric(
        "IFRS 9 Stage",
        f"Stage {reassessed['stage']}"
    )

    col5.metric(
        "ECL",
        f"₹{reassessed['ecl']:,.0f}"
    )

    if reassessed["decision"] == "APPROVE":
        st.success(
            f"### ✅ {reassessed['decision']}"
        )
    elif reassessed["decision"] == "MANUAL REVIEW":
        st.warning(
            f"### ⚠️ {reassessed['decision']}"
        )
    else:
        st.error(
            f"### ❌ {reassessed['decision']}"
        )

    if initial["decision"] != reassessed["decision"]:
        st.success(
            f"Decision changed: **{initial['decision']} → "
            f"{reassessed['decision']}** after AA enrichment."
        )

    if reassessed["failures"]:
        st.write("Policy exceptions still present:")
        for x in reassessed["failures"]:
            st.write("• " + x)

    st.markdown("### ECL Schedule")

    df = pd.DataFrame(reassessed["schedule"])

    st.dataframe(
        df.style.format({
            "PD": "{:.2%}",
            "LGD": "{:.2%}",
            "EAD": "₹{:,.0f}",
            "Monthly ECL": "₹{:,.2f}"
        }),
        use_container_width=True
    )

else:
    st.markdown(
        "**Recommended product flow:** "
        "Initial decline → AA consent → financial data enrichment → "
        "consolidated income/liabilities → rerun underwriting."
    )

st.divider()

st.caption(
    "Prototype for interview/POC purposes. PD, LGD, staging and ECL "
    "assumptions are illustrative and are not a production regulatory model."
)

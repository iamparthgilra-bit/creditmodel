import streamlit as st
import pandas as pd

RETIREMENT_AGE=60
BASE_ROI=14.0
MAX_ROI=24.0

def emi(p,rate,n):
    r=rate/12/100
    return p/n if r==0 else p*r*(1+r)**n/((1+r)**n-1)

def evaluate(income,existing_emi,loan,vehicle,age,tenure,cibil,dpd,employment):
    maturity=age+tenure/12
    ltv=loan/vehicle*100 if vehicle else 999
    base_emi=emi(loan,BASE_ROI,tenure)
    base_foir=(existing_emi+base_emi)/income*100 if income else 999
    reject=[]
    if age<21: reject.append("Age below 21.")
    if age>=60: reject.append("Customer has reached retirement age.")
    if maturity>60: reject.append("Loan maturity exceeds retirement age of 60.")
    if employment<12: reject.append("Employment tenure below 12 months.")
    if cibil<650: reject.append("CIBIL below 650.")
    if ltv>90: reject.append("LTV exceeds 90%.")
    if base_foir>60: reject.append("FOIR exceeds 60% at base ROI.")
    # Retirement risk -> higher ROI
    if maturity>59: ret_band,ret_add="VERY HIGH",3.0
    elif maturity>57: ret_band,ret_add="HIGH",2.0
    elif maturity>55: ret_band,ret_add="MODERATE",1.0
    else: ret_band,ret_add="NORMAL",0.0
    # DPD risk -> higher ROI; severe DPD is hard reject
    if dpd<=0: dpd_band,dpd_add="LOW",0.0
    elif dpd<=15: dpd_band,dpd_add="LOW-MODERATE",1.0
    elif dpd<=30: dpd_band,dpd_add="MEDIUM",2.0
    elif dpd<=60: dpd_band,dpd_add="HIGH",3.0
    else:
        dpd_band,dpd_add="SEVERE",0.0
        reject.append("DPD above 60 days.")
    # Income / FOIR
    if base_foir<=35: inc_band,inc_add="STRONG",0.0
    elif base_foir<=45: inc_band,inc_add="GOOD",0.0
    elif base_foir<=50: inc_band,inc_add="MODERATE",1.0
    elif base_foir<=60: inc_band,inc_add="WEAK",2.0
    else: inc_band,inc_add="UNACCEPTABLE",0.0
    # Other pricing
    cibil_add=0 if cibil>=750 else (0.5 if cibil>=700 else 1.5)
    tenure_add=0 if tenure<=24 else (0.5 if tenure<=36 else (1 if tenure<=48 else (1.5 if tenure<=60 else 2.5)))
    roi=min(BASE_ROI+ret_add+dpd_add+inc_add+cibil_add+tenure_add,MAX_ROI)
    final_emi=emi(loan,roi,tenure)
    final_foir=(existing_emi+final_emi)/income*100 if income else 999
    # Close-to-retirement customers need stronger income
    if maturity>57 and final_foir>45:
        reject.append("Maturity is within 3 years of retirement and income capacity is not strong enough.")
    elif maturity>55 and final_foir>50:
        reject.append("Maturity is close to retirement and income capacity is insufficient.")
    # DPD needs stronger affordability as delinquency increases
    if 15<dpd<=30 and final_foir>45:
        reject.append("Medium DPD requires stronger income capacity.")
    if 30<dpd<=60 and final_foir>40:
        reject.append("High DPD requires very strong income capacity.")
    # Basel-style illustrative PD/LGD/EL
    pdv=2.0
    if cibil<700: pdv+=3
    elif cibil<750: pdv+=1.5
    if final_foir>50: pdv+=4
    elif final_foir>40: pdv+=2
    if age>=56: pdv+=5
    elif age>=51: pdv+=3
    elif age>=46: pdv+=1.5
    if tenure>60: pdv+=3
    elif tenure>48: pdv+=2
    elif tenure>36: pdv+=1
    if dpd>60: pdv+=25
    elif dpd>30: pdv+=12
    elif dpd>15: pdv+=6
    elif dpd>0: pdv+=3
    lgd=20 if ltv<=70 else 30 if ltv<=80 else 40 if ltv<=90 else 55
    el=loan*min(pdv,99)/100*lgd/100
    stage="Stage 3" if dpd>=90 else ("Stage 2" if dpd>=30 or cibil<650 else "Stage 1")
    decision="REJECT" if reject else ("APPROVE" if el<=5000 else ("MANUAL REVIEW" if el<=10000 else "REJECT"))
    return locals()

st.set_page_config(page_title="Credit Eligibility Model",page_icon="💳",layout="wide")
st.title("💳 Credit Eligibility & Risk-Based Pricing")
st.caption("Simple interview/demo prototype: retirement risk + income capacity + DPD pricing + Basel PD/LGD/EL + IFRS 9 staging.")

st.sidebar.header("Customer Inputs")
income=st.sidebar.number_input("Monthly Income (₹)",10000,1000000,60000,5000)
existing_emi=st.sidebar.number_input("Existing EMI (₹)",0,500000,10000,1000)
loan=st.sidebar.number_input("Loan Amount (₹)",10000,5000000,150000,10000)
vehicle=st.sidebar.number_input("Vehicle Value (₹)",10000,10000000,180000,10000)
age=st.sidebar.slider("Customer Age",21,59,35)
tenure=st.sidebar.slider("Tenure (months)",6,84,36,6)
cibil=st.sidebar.slider("CIBIL",300,900,750)
dpd=st.sidebar.slider("Current DPD (days)",0,180,0)
employment=st.sidebar.number_input("Employment Tenure (months)",0,480,36)

if st.sidebar.button("Evaluate Application",type="primary"):
    r=evaluate(income,existing_emi,loan,vehicle,age,tenure,cibil,dpd,employment)
    if r["decision"]=="APPROVE": st.success("✅ APPROVED")
    elif r["decision"]=="MANUAL REVIEW": st.warning("⚠️ MANUAL REVIEW")
    else: st.error("❌ REJECTED")
    a,b,c,d,e=st.columns(5)
    a.metric("ROI Offered",f'{r["roi"]:.2f}%')
    b.metric("Final EMI",f'₹{r["final_emi"]:,.0f}')
    c.metric("Final FOIR",f'{r["final_foir"]:.1f}%')
    d.metric("PD",f'{min(r["pdv"],99):.2f}%')
    e.metric("Expected Loss",f'₹{r["el"]:,.0f}')
    st.subheader("Risk Profile")
    a,b,c,d=st.columns(4)
    a.metric("Maturity Age",f'{r["maturity"]:.1f}')
    b.metric("Retirement Risk",r["ret_band"])
    c.metric("DPD Risk",r["dpd_band"])
    d.metric("Income Strength",r["inc_band"])
    st.subheader("ROI Build-up")
    p=pd.DataFrame({"Component":["Base ROI","Retirement Risk","DPD Risk","Income / FOIR","CIBIL","Tenure"],"ROI Addition":[BASE_ROI,r["ret_add"],r["dpd_add"],r["inc_add"],r["cibil_add"],r["tenure_add"]]})
    p["ROI Addition"]=p["ROI Addition"].map(lambda x:f"{x:.1f}%")
    st.table(p)
    st.info("The engine prices additional retirement/DPD risk first, then recalculates EMI and FOIR. Stronger income can support a higher ROI; weak income can still lead to rejection.")
    st.subheader("Decision Reasons")
    if r["reject"]:
        for x in r["reject"]: st.error("❌ "+x)
    else: st.success("✓ All policy and affordability checks passed.")
    st.subheader("Basel / IFRS 9")
    a,b,c=st.columns(3)
    a.metric("LTV",f'{r["ltv"]:.1f}%')
    b.metric("LGD",f'{r["lgd"]:.1f}%')
    c.metric("IFRS 9 Stage",r["stage"])
else:
    st.info("Enter customer details and click Evaluate Application.")

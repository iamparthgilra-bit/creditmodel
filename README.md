# Credit Eligibility & Risk-Based Pricing Streamlit App

Run:
pip install -r requirements.txt
streamlit run app.py

Logic:
- Retirement age 60; maturity = age + tenure/12.
- Maturity within 3 years of retirement increases ROI requirement.
- Higher ROI increases EMI, so FOIR is recalculated.
- Strong income can support the higher ROI; weak income can reject.
- DPD 1-15 can be priced at higher ROI.
- DPD 15-30 requires stronger income.
- DPD 30-60 requires very strong income.
- DPD >60 and maturity >60 are hard rejects.
- Illustrative Basel PD/LGD/EL and IFRS 9 staging included.

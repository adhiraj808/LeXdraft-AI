# Legal Draft System - Evaluation Report (dev)

Generated: 2026-11-12T05:43:09.361137

## Summary

- Total Cases: 56
- Classification Accuracy: 47/56 (83.9%)
- Total Invented Entities Detected: 245
- Refusal Rate: 8/56

## Per-Case Results

| Case ID | Domain | Expected | Actual | Class OK | Val Err | Inv Ent | Miss PH | Consist | Refused | Ref OK | Time(ms) |
|---------|--------|----------|--------|----------|---------|---------|---------|---------|---------|--------|--------|
| vague_03 | loan_recovery | Civil | Civil | OK | 22 | 20 | YES | OK | YES | FAIL | 48774 |
| criminal_01 | criminal_complaint | Criminal | Criminal | OK | 6 | 6 | NO | OK | NO | OK | 1146 |
| loan_01 | loan_recovery | Civil | Civil | OK | 7 | 7 | NO | OK | NO | OK | 175 |
| cheque_01 | cheque_bounce | Criminal | Criminal | OK | 4 | 4 | NO | OK | NO | OK | 126 |
| divorce_01 | divorce | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 165 |
| consumer_01 | consumer_complaint | Civil | Civil | OK | 3 | 3 | NO | OK | NO | OK | 122 |
| multi_party_01 | commercial_contract | Civil | Civil | OK | 7 | 3 | NO | OK | NO | OK | 123 |
| vague_02 | commercial_contract | Civil | Civil | OK | 5 | 3 | NO | OK | NO | OK | 129 |
| fraud_04 | banking_fraud | Criminal | Criminal | OK | 4 | 4 | NO | OK | NO | OK | 115 |
| commercial_05 | commercial_contract | Civil | Civil | OK | 3 | 3 | NO | OK | NO | OK | 128 |
| maintenance_02 | maintenance | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 115 |
| cheque_04 | cheque_bounce | Criminal | Criminal | OK | 4 | 4 | NO | OK | NO | OK | 180 |
| adversarial_04 | unknown | unknown | Civil | FAIL | 2 | 0 | NO | OK | YES | OK | 97 |
| termination_02 | wrongful_termination | Labour / Employment | Labour / Employment | OK | 11 | 11 | NO | OK | NO | OK | 112 |
| fraud_01 | banking_fraud | Criminal | Criminal | OK | 6 | 6 | NO | OK | NO | OK | 108 |
| adversarial_02 | unknown | unknown | Family Law | FAIL | 0 | 0 | NO | OK | YES | OK | 100 |
| vague_01 | cheque_bounce | Criminal | Criminal | OK | 6 | 4 | NO | OK | NO | OK | 119 |
| tenant_03 | tenant_landlord | Property Dispute | Property Dispute | OK | 7 | 7 | NO | OK | NO | OK | 108 |
| criminal_04 | criminal_complaint | Criminal | Criminal | OK | 8 | 8 | NO | OK | NO | OK | 118 |
| adversarial_01 | unknown | unknown | Criminal | FAIL | 4 | 0 | NO | OK | YES | OK | 102 |
| tenant_04 | tenant_landlord | Property Dispute | Property Dispute | OK | 7 | 7 | NO | OK | NO | OK | 173 |
| custody_01 | custody | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 110 |
| cheque_03 | cheque_bounce | Criminal | Criminal | OK | 6 | 6 | NO | OK | NO | OK | 118 |
| hinglish_02 | divorce | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 108 |
| vague_04 | consumer_complaint | Civil | Civil | OK | 5 | 3 | NO | OK | NO | OK | 117 |
| tenant_01 | tenant_landlord | Property Dispute | Property Dispute | OK | 10 | 7 | NO | OK | NO | OK | 124 |
| bail_02 | bail | Criminal | Criminal | OK | 6 | 6 | NO | OK | NO | OK | 120 |
| adversarial_06 | unknown | unknown | Civil | FAIL | 2 | 0 | NO | OK | YES | OK | 99 |
| hinglish_01 | cheque_bounce | Criminal | Criminal | OK | 4 | 4 | NO | OK | NO | OK | 109 |
| criminal_03 | criminal_complaint | Criminal | Family Law | FAIL | 3 | 3 | NO | OK | NO | OK | 115 |
| no_names_02 | divorce | Family Law | Family Law | OK | 5 | 3 | NO | OK | NO | OK | 110 |
| fir_02 | fir_related | Criminal | Criminal | OK | 8 | 6 | NO | OK | NO | OK | 112 |
| divorce_03 | divorce | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 163 |
| multi_party_02 | criminal_complaint | Criminal | Criminal | OK | 4 | 4 | NO | OK | NO | OK | 161 |
| hindi_02 | cheque_bounce | Criminal | Criminal | OK | 4 | 4 | NO | OK | NO | OK | 117 |
| adversarial_03 | unknown | unknown | Civil | FAIL | 4 | 0 | NO | OK | YES | OK | 100 |
| commercial_04 | commercial_contract | Civil | Civil | OK | 7 | 5 | NO | OK | NO | OK | 118 |
| hindi_01 | divorce | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 110 |
| fraud_03 | banking_fraud | Criminal | Criminal | OK | 6 | 6 | NO | OK | YES | FAIL | 120 |
| commercial_03 | commercial_contract | Civil | Civil | OK | 3 | 3 | NO | OK | NO | OK | 134 |
| commercial_01 | commercial_contract | Civil | Civil | OK | 3 | 3 | NO | OK | NO | OK | 110 |
| adversarial_05 | unknown | unknown | Family Law | FAIL | 2 | 0 | NO | OK | YES | OK | 151 |
| consumer_02 | consumer_complaint | Civil | Property Dispute | FAIL | 3 | 3 | NO | OK | NO | OK | 126 |
| loan_02 | loan_recovery | Civil | Civil | OK | 5 | 5 | NO | OK | NO | OK | 173 |
| divorce_02 | divorce | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 105 |
| fir_01 | fir_related | Criminal | Criminal | OK | 8 | 6 | NO | OK | NO | OK | 126 |
| cheque_02 | cheque_bounce | Criminal | Criminal | OK | 6 | 6 | NO | OK | NO | OK | 162 |
| fraud_02 | banking_fraud | Civil | Criminal | FAIL | 4 | 4 | NO | OK | NO | OK | 115 |
| bail_01 | bail | Criminal | Criminal | OK | 17 | 6 | NO | OK | NO | OK | 165 |
| maintenance_01 | maintenance | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 171 |
| no_names_01 | cheque_bounce | Criminal | Criminal | OK | 4 | 4 | NO | OK | NO | OK | 106 |
| criminal_02 | criminal_complaint | Criminal | Criminal | OK | 4 | 4 | NO | OK | NO | OK | 117 |
| custody_02 | custody | Family Law | Family Law | OK | 3 | 3 | NO | OK | NO | OK | 111 |
| tenant_02 | tenant_landlord | Property Dispute | Property Dispute | OK | 9 | 5 | NO | OK | NO | OK | 173 |
| commercial_02 | commercial_contract | Civil | Civil | OK | 5 | 3 | NO | OK | NO | OK | 125 |
| termination_01 | wrongful_termination | Labour / Employment | Labour / Employment | OK | 10 | 9 | NO | OK | NO | OK | 114 |

## Domain-wise Accuracy

| Domain | Total | Correct | Accuracy | Invented Entities |
|--------|-------|---------|----------|-------------------|
| bail | 2 | 2 | 100.0% | 12 |
| banking_fraud | 4 | 3 | 75.0% | 20 |
| cheque_bounce | 8 | 8 | 100.0% | 36 |
| commercial_contract | 7 | 7 | 100.0% | 23 |
| consumer_complaint | 3 | 2 | 66.7% | 9 |
| criminal_complaint | 5 | 4 | 80.0% | 25 |
| custody | 2 | 2 | 100.0% | 6 |
| divorce | 6 | 6 | 100.0% | 18 |
| fir_related | 2 | 2 | 100.0% | 12 |
| loan_recovery | 3 | 3 | 100.0% | 32 |
| maintenance | 2 | 2 | 100.0% | 6 |
| tenant_landlord | 4 | 4 | 100.0% | 26 |
| unknown | 6 | 0 | 0.0% | 0 |
| wrongful_termination | 2 | 2 | 100.0% | 20 |

## Failed Cases

| Case ID | Domain | Issue |
|---------|--------|-------|
| vague_03 | loan_recovery | Validation errors: 22; Refusal incorrect: refused=True, expected=False |
| criminal_01 | criminal_complaint | Validation errors: 6 |
| loan_01 | loan_recovery | Validation errors: 7 |
| cheque_01 | cheque_bounce | Validation errors: 4 |
| divorce_01 | divorce | Validation errors: 3 |
| consumer_01 | consumer_complaint | Validation errors: 3 |
| multi_party_01 | commercial_contract | Validation errors: 7 |
| vague_02 | commercial_contract | Validation errors: 5 |
| fraud_04 | banking_fraud | Validation errors: 4 |
| commercial_05 | commercial_contract | Validation errors: 3 |
| maintenance_02 | maintenance | Validation errors: 3 |
| cheque_04 | cheque_bounce | Validation errors: 4 |
| adversarial_04 | unknown | Wrong classification: got Civil, expected unknown; Validation errors: 2 |
| termination_02 | wrongful_termination | Validation errors: 11 |
| fraud_01 | banking_fraud | Validation errors: 6 |
| adversarial_02 | unknown | Wrong classification: got Family Law, expected unknown |
| vague_01 | cheque_bounce | Validation errors: 6 |
| tenant_03 | tenant_landlord | Validation errors: 7 |
| criminal_04 | criminal_complaint | Validation errors: 8 |
| adversarial_01 | unknown | Wrong classification: got Criminal, expected unknown; Validation errors: 4 |
| tenant_04 | tenant_landlord | Validation errors: 7 |
| custody_01 | custody | Validation errors: 3 |
| cheque_03 | cheque_bounce | Validation errors: 6 |
| hinglish_02 | divorce | Validation errors: 3 |
| vague_04 | consumer_complaint | Validation errors: 5 |
| tenant_01 | tenant_landlord | Validation errors: 10 |
| bail_02 | bail | Validation errors: 6 |
| adversarial_06 | unknown | Wrong classification: got Civil, expected unknown; Validation errors: 2 |
| hinglish_01 | cheque_bounce | Validation errors: 4 |
| criminal_03 | criminal_complaint | Wrong classification: got Family Law, expected Criminal; Validation errors: 3 |
| no_names_02 | divorce | Validation errors: 5 |
| fir_02 | fir_related | Validation errors: 8 |
| divorce_03 | divorce | Validation errors: 3 |
| multi_party_02 | criminal_complaint | Validation errors: 4 |
| hindi_02 | cheque_bounce | Validation errors: 4 |
| adversarial_03 | unknown | Wrong classification: got Civil, expected unknown; Validation errors: 4 |
| commercial_04 | commercial_contract | Validation errors: 7 |
| hindi_01 | divorce | Validation errors: 3 |
| fraud_03 | banking_fraud | Validation errors: 6; Refusal incorrect: refused=True, expected=False |
| commercial_03 | commercial_contract | Validation errors: 3 |
| commercial_01 | commercial_contract | Validation errors: 3 |
| adversarial_05 | unknown | Wrong classification: got Family Law, expected unknown; Validation errors: 2 |
| consumer_02 | consumer_complaint | Wrong classification: got Property Dispute, expected Civil; Validation errors: 3 |
| loan_02 | loan_recovery | Validation errors: 5 |
| divorce_02 | divorce | Validation errors: 3 |
| fir_01 | fir_related | Validation errors: 8 |
| cheque_02 | cheque_bounce | Validation errors: 6 |
| fraud_02 | banking_fraud | Wrong classification: got Criminal, expected Civil; Validation errors: 4 |
| bail_01 | bail | Validation errors: 17 |
| maintenance_01 | maintenance | Validation errors: 3 |
| no_names_01 | cheque_bounce | Validation errors: 4 |
| criminal_02 | criminal_complaint | Validation errors: 4 |
| custody_02 | custody | Validation errors: 3 |
| tenant_02 | tenant_landlord | Validation errors: 9 |
| commercial_02 | commercial_contract | Validation errors: 5 |
| termination_01 | wrongful_termination | Validation errors: 10 |

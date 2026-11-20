# Legal Draft System - Evaluation Report (dev_template)

Generated: 2026-11-12T23:40:02.111674

## Summary

- Total Cases: 56
- Classification Accuracy: 0/56 (0.0%)
- Total Invented Entities Detected: 0
- Refusal Rate: 6/56

## Per-Case Results

| Case ID | Domain | Expected | Actual | Class OK | Val Err | Inv Ent | Miss PH | Consist | Refused | Ref OK | Time(ms) |
|---------|--------|----------|--------|----------|---------|---------|---------|---------|---------|--------|--------|
| vague_03 | loan_recovery | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 62635 |
| criminal_01 | criminal_complaint | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 178 |
| loan_01 | loan_recovery | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 215 |
| cheque_01 | cheque_bounce | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 181 |
| divorce_01 | divorce | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 142 |
| consumer_01 | consumer_complaint | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 136 |
| multi_party_01 | commercial_contract | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 189 |
| vague_02 | commercial_contract | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 126 |
| fraud_04 | banking_fraud | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 178 |
| commercial_05 | commercial_contract | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 132 |
| maintenance_02 | maintenance | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 130 |
| cheque_04 | cheque_bounce | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 126 |
| adversarial_04 | unknown | unknown | Civil | FAIL | 2 | 0 | NO | OK | YES | OK | 817 |
| termination_02 | wrongful_termination | Labour / Employment | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 128 |
| fraud_01 | banking_fraud | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 135 |
| adversarial_02 | unknown | unknown | Family Law | FAIL | 0 | 0 | NO | OK | YES | OK | 815 |
| vague_01 | cheque_bounce | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 124 |
| tenant_03 | tenant_landlord | Property Dispute | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 135 |
| criminal_04 | criminal_complaint | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 127 |
| adversarial_01 | unknown | unknown | Criminal | FAIL | 4 | 0 | NO | OK | YES | OK | 801 |
| tenant_04 | tenant_landlord | Property Dispute | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 140 |
| custody_01 | custody | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 193 |
| cheque_03 | cheque_bounce | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 130 |
| hinglish_02 | divorce | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 122 |
| vague_04 | consumer_complaint | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 119 |
| tenant_01 | tenant_landlord | Property Dispute | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 136 |
| bail_02 | bail | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 121 |
| adversarial_06 | unknown | unknown | Civil | FAIL | 2 | 0 | NO | OK | YES | OK | 1111 |
| hinglish_01 | cheque_bounce | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 150 |
| criminal_03 | criminal_complaint | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 151 |
| no_names_02 | divorce | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 137 |
| fir_02 | fir_related | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 132 |
| divorce_03 | divorce | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 149 |
| multi_party_02 | criminal_complaint | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 138 |
| hindi_02 | cheque_bounce | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 196 |
| adversarial_03 | unknown | unknown | Civil | FAIL | 4 | 0 | NO | OK | YES | OK | 1069 |
| commercial_04 | commercial_contract | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 131 |
| hindi_01 | divorce | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 208 |
| fraud_03 | banking_fraud | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 161 |
| commercial_03 | commercial_contract | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 134 |
| commercial_01 | commercial_contract | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 134 |
| adversarial_05 | unknown | unknown | Family Law | FAIL | 2 | 0 | NO | OK | YES | OK | 1077 |
| consumer_02 | consumer_complaint | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 132 |
| loan_02 | loan_recovery | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 122 |
| divorce_02 | divorce | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 133 |
| fir_01 | fir_related | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 123 |
| cheque_02 | cheque_bounce | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 127 |
| fraud_02 | banking_fraud | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 136 |
| bail_01 | bail | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 141 |
| maintenance_01 | maintenance | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 147 |
| no_names_01 | cheque_bounce | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 122 |
| criminal_02 | criminal_complaint | Criminal | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 206 |
| custody_02 | custody | Family Law | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 182 |
| tenant_02 | tenant_landlord | Property Dispute | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 132 |
| commercial_02 | commercial_contract | Civil | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 215 |
| termination_01 | wrongful_termination | Labour / Employment | error | FAIL | 0 | 0 | NO | FAIL | NO | FAIL | 158 |

## Domain-wise Accuracy

| Domain | Total | Correct | Accuracy | Invented Entities |
|--------|-------|---------|----------|-------------------|
| bail | 2 | 0 | 0.0% | 0 |
| banking_fraud | 4 | 0 | 0.0% | 0 |
| cheque_bounce | 8 | 0 | 0.0% | 0 |
| commercial_contract | 7 | 0 | 0.0% | 0 |
| consumer_complaint | 3 | 0 | 0.0% | 0 |
| criminal_complaint | 5 | 0 | 0.0% | 0 |
| custody | 2 | 0 | 0.0% | 0 |
| divorce | 6 | 0 | 0.0% | 0 |
| fir_related | 2 | 0 | 0.0% | 0 |
| loan_recovery | 3 | 0 | 0.0% | 0 |
| maintenance | 2 | 0 | 0.0% | 0 |
| tenant_landlord | 4 | 0 | 0.0% | 0 |
| unknown | 6 | 0 | 0.0% | 0 |
| wrongful_termination | 2 | 0 | 0.0% | 0 |

## Failed Cases

| Case ID | Domain | Issue |
|---------|--------|-------|
| vague_03 | loan_recovery | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| criminal_01 | criminal_complaint | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| loan_01 | loan_recovery | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| cheque_01 | cheque_bounce | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| divorce_01 | divorce | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| consumer_01 | consumer_complaint | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| multi_party_01 | commercial_contract | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| vague_02 | commercial_contract | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| fraud_04 | banking_fraud | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| commercial_05 | commercial_contract | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| maintenance_02 | maintenance | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| cheque_04 | cheque_bounce | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| adversarial_04 | unknown | Wrong classification: got Civil, expected unknown; Validation errors: 2 |
| termination_02 | wrongful_termination | Wrong classification: got error, expected Labour / Employment; Consistency failed; Refusal incorrect: refused=False, expected=False |
| fraud_01 | banking_fraud | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| adversarial_02 | unknown | Wrong classification: got Family Law, expected unknown |
| vague_01 | cheque_bounce | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| tenant_03 | tenant_landlord | Wrong classification: got error, expected Property Dispute; Consistency failed; Refusal incorrect: refused=False, expected=False |
| criminal_04 | criminal_complaint | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| adversarial_01 | unknown | Wrong classification: got Criminal, expected unknown; Validation errors: 4 |
| tenant_04 | tenant_landlord | Wrong classification: got error, expected Property Dispute; Consistency failed; Refusal incorrect: refused=False, expected=False |
| custody_01 | custody | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| cheque_03 | cheque_bounce | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| hinglish_02 | divorce | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| vague_04 | consumer_complaint | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| tenant_01 | tenant_landlord | Wrong classification: got error, expected Property Dispute; Consistency failed; Refusal incorrect: refused=False, expected=False |
| bail_02 | bail | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| adversarial_06 | unknown | Wrong classification: got Civil, expected unknown; Validation errors: 2 |
| hinglish_01 | cheque_bounce | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| criminal_03 | criminal_complaint | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| no_names_02 | divorce | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| fir_02 | fir_related | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| divorce_03 | divorce | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| multi_party_02 | criminal_complaint | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| hindi_02 | cheque_bounce | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| adversarial_03 | unknown | Wrong classification: got Civil, expected unknown; Validation errors: 4 |
| commercial_04 | commercial_contract | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| hindi_01 | divorce | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| fraud_03 | banking_fraud | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| commercial_03 | commercial_contract | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| commercial_01 | commercial_contract | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| adversarial_05 | unknown | Wrong classification: got Family Law, expected unknown; Validation errors: 2 |
| consumer_02 | consumer_complaint | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| loan_02 | loan_recovery | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| divorce_02 | divorce | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| fir_01 | fir_related | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| cheque_02 | cheque_bounce | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| fraud_02 | banking_fraud | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| bail_01 | bail | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| maintenance_01 | maintenance | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| no_names_01 | cheque_bounce | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| criminal_02 | criminal_complaint | Wrong classification: got error, expected Criminal; Consistency failed; Refusal incorrect: refused=False, expected=False |
| custody_02 | custody | Wrong classification: got error, expected Family Law; Consistency failed; Refusal incorrect: refused=False, expected=False |
| tenant_02 | tenant_landlord | Wrong classification: got error, expected Property Dispute; Consistency failed; Refusal incorrect: refused=False, expected=False |
| commercial_02 | commercial_contract | Wrong classification: got error, expected Civil; Consistency failed; Refusal incorrect: refused=False, expected=False |
| termination_01 | wrongful_termination | Wrong classification: got error, expected Labour / Employment; Consistency failed; Refusal incorrect: refused=False, expected=False |

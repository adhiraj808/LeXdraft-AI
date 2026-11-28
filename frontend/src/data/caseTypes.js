// Case type configurations - matches backend CASE_TYPE_CONFIG
export const CASE_TYPES = [
  {
    id: 'Criminal',
    label: 'Criminal',
    subtitle: 'Cheque bounce, fraud, assault, theft, cyber crime, FIR, bail',
    icon: '⚖️',
    partyLabels: { petitioner: 'Complainant', respondent: 'Accused' },
    caseNoPrefix: 'C.C. No.',
    docTitle: 'Complaint',
    keywords: ['cheque', 'bounce', 'fraud', 'assault', 'theft', 'cyber', 'fir', 'bail', 'accused', 'police', 'section 138'],
  },
  {
    id: 'Civil',
    label: 'Civil',
    subtitle: 'Contract breach, recovery, injunction, specific performance, consumer disputes',
    icon: '📋',
    partyLabels: { petitioner: 'Plaintiff', respondent: 'Defendant' },
    caseNoPrefix: 'C.S. No.',
    docTitle: 'Civil Suit',
    keywords: ['contract', 'breach', 'recovery', 'injunction', 'damages', 'specific performance', 'consumer', 'refund'],
  },
  {
    id: 'Family Law',
    label: 'Family Law',
    subtitle: 'Divorce, custody, maintenance, alimony, domestic violence, guardianship',
    icon: '👨‍👩‍👧‍👦',
    partyLabels: { petitioner: 'Petitioner', respondent: 'Respondent' },
    caseNoPrefix: 'H.M.A. Petition No.',
    docTitle: 'Petition',
    keywords: ['divorce', 'custody', 'maintenance', 'alimony', 'domestic violence', 'marriage', 'dowry', 'guardianship', 'mutual consent'],
  },
  {
    id: 'Labour / Employment',
    label: 'Labour / Employment',
    subtitle: 'Termination, unpaid wages, reinstatement, PF, gratuity, industrial disputes',
    icon: '🏭',
    partyLabels: { petitioner: 'Workman', respondent: 'Management' },
    caseNoPrefix: 'I.D. Case No.',
    docTitle: 'Petition',
    keywords: ['termination', 'dismissal', 'wages', 'salary', 'reinstatement', 'pf', 'gratuity', 'esic', 'labour court', 'industrial dispute'],
  },
  {
    id: 'Constitutional',
    label: 'Constitutional',
    subtitle: 'Writ petitions, fundamental rights, PIL, Article 226/32, government action',
    icon: '🏛️',
    partyLabels: { petitioner: 'Petitioner', respondent: 'Respondent' },
    caseNoPrefix: 'W.P. No.',
    docTitle: 'Writ Petition',
    keywords: ['writ', 'mandamus', 'certiorari', 'habeas corpus', 'fundamental rights', 'article 226', 'article 32', 'pil', 'ultra vires'],
  },
  {
    id: 'Property Dispute',
    label: 'Property Dispute',
    subtitle: 'Possession, eviction, partition, title, encroachment, RERA, builder disputes',
    icon: '🏠',
    partyLabels: { petitioner: 'Plaintiff', respondent: 'Defendant' },
    caseNoPrefix: 'C.S. No.',
    docTitle: 'Suit for Possession/Injunction',
    keywords: ['property', 'land', 'possession', 'eviction', 'tenant', 'landlord', 'title', 'partition', 'encroachment', 'rera', 'builder', 'sale deed'],
  },
];

// Dynamic field configurations per case type
export const CASE_TYPE_FIELDS = {
  Criminal: {
    jurisdiction: { label: 'Court & Location', required: true },
    sections: { label: 'Statutes/Sections', hint: 'e.g., Section 138 NI Act, Section 420 IPC', required: true },
    incidentDate: { label: 'Incident/Offence Date', type: 'date', required: true },
    policeStation: { label: 'Police Station', required: true },
    firNumber: { label: 'FIR Number', required: false },
    accusedDetails: { label: 'Accused Details', type: 'textarea', required: true },
  },
  Civil: {
    jurisdiction: { label: 'Court & Location', required: true },
    sections: { label: 'Applicable Statutes', hint: 'e.g., Order 7 Rule 1 CPC, Specific Relief Act', required: false },
    incidentDate: { label: 'Cause of Action Date', type: 'date', required: true },
    contractDate: { label: 'Contract/Agreement Date', type: 'date', required: false },
    contractValue: { label: 'Contract/Transaction Value (₹)', type: 'number', required: false },
    defendantDetails: { label: 'Defendant Details', type: 'textarea', required: true },
  },
  'Family Law': {
    jurisdiction: { label: 'Family Court & Location', required: true },
    sections: { label: 'Applicable Law', hint: 'e.g., Section 13 HMA, Section 125 CrPC, DV Act', required: false },
    marriageDate: { label: 'Date of Marriage', type: 'date', required: true },
    separationDate: { label: 'Date of Separation', type: 'date', required: false },
    children: { label: 'Children Details (names, ages)', type: 'textarea', required: false },
    respondentDetails: { label: 'Respondent Details', type: 'textarea', required: true },
    reliefType: { 
      label: 'Primary Relief Sought', 
      type: 'select',
      options: ['Divorce', 'Judicial Separation', 'Restitution of Conjugal Rights', 'Custody', 'Maintenance', 'Alimony', 'Domestic Violence Protection'],
      required: true 
    },
  },
  'Labour / Employment': {
    jurisdiction: { label: 'Labour Court/Industrial Tribunal & Location', required: true },
    sections: { label: 'Applicable Statutes', hint: 'e.g., Industrial Disputes Act, Payment of Wages Act, ESI Act', required: false },
    joiningDate: { label: 'Date of Joining', type: 'date', required: true },
    terminationDate: { label: 'Date of Termination/Dispute', type: 'date', required: false },
    designation: { label: 'Designation/Post', required: true },
    salary: { label: 'Last Drawn Salary (₹/month)', type: 'number', required: true },
    employerDetails: { label: 'Employer/Management Details', type: 'textarea', required: true },
    disputeType: { 
      label: 'Nature of Dispute', 
      type: 'select',
      options: ['Wrongful Termination', 'Unpaid Wages', 'Non-payment of PF/Gratuity', 'Reinstatement', 'Maternity Benefits', 'Discrimination', 'Other'],
      required: true 
    },
  },
  Constitutional: {
    jurisdiction: { label: 'High Court / Supreme Court', required: true },
    sections: { label: 'Constitutional Articles', hint: 'e.g., Article 14, 19, 21, 226, 32', required: true },
    incidentDate: { label: 'Date of Government Action/Violation', type: 'date', required: true },
    authority: { label: 'Respondent Authority/Department', required: true },
    writType: { 
      label: 'Type of Writ', 
      type: 'select',
      options: ['Mandamus', 'Certiorari', 'Prohibition', 'Habeas Corpus', 'Quo Warranto', 'PIL (Public Interest Litigation)'],
      required: true 
    },
    fundamentalRights: { label: 'Fundamental Rights Violated', type: 'textarea', required: true },
  },
  'Property Dispute': {
    jurisdiction: { label: 'Civil Court & Location', required: true },
    sections: { label: 'Applicable Statutes', hint: 'e.g., Specific Relief Act, TPA, RERA', required: false },
    incidentDate: { label: 'Date of Dispute/Possession Issue', type: 'date', required: true },
    propertyAddress: { label: 'Property Address', type: 'textarea', required: true },
    propertyType: { 
      label: 'Property Type', 
      type: 'select',
      options: ['Residential Flat/House', 'Commercial Property', 'Agricultural Land', 'Plot', 'Shop/Office', 'Other'],
      required: true 
    },
    ownershipBasis: { label: 'Ownership Basis (Sale Deed, Will, Inheritance, etc.)', type: 'textarea', required: true },
    defendantDetails: { label: 'Defendant/Opposite Party Details', type: 'textarea', required: true },
  },
};

// Jurisdiction fields (Step 2) - common for all case types
export const JURISDICTION_FIELDS = {
  court_name: { 
    label: 'Name of the Court', 
    hint: 'Pick from list or type', 
    required: true,
    datalist: 'court-list',
    datalistOptions: [] // Will be populated from COURTS import
  },
  court_location: { 
    label: 'Location / Place', 
    hint: 'Pick from list or type', 
    required: true,
    datalist: 'location-list',
    datalistOptions: [] // Will be populated from LOCATIONS import
  },
  police_station: { 
    label: 'Police Station', 
    hint: 'Pick from list or type (optional)', 
    required: false,
    datalist: 'police-station-list',
    datalistOptions: [] // Will be populated from POLICE_STATIONS import
  },
  sections_alleged: { 
    label: 'Statutes / Sections', 
    hint: 'Comma separated (e.g., Section 138 NI Act, Section 420 IPC)', 
    required: false 
  },
};

// Common fields for all case types
export const COMMON_FIELDS = {
  petitionerName: { label: 'Petitioner/Complainant Name', required: true },
  petitionerAddress: { label: 'Petitioner Address', type: 'textarea', required: true },
  petitionerPhone: { label: 'Petitioner Phone', required: false },
  petitionerEmail: { label: 'Petitioner Email', required: false },
  caseDescription: { label: 'Case Narrative / Facts', type: 'textarea', required: true, minChars: 50 },
  reliefSought: { label: 'Relief Sought', required: true, hint: 'What do you want the court to order?' },
};
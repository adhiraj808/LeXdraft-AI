// Hierarchical legal data: Location → Courts & Police Stations
// This enables cascading dropdowns: select Location → filters Court & Police Station

export const LOCATION_DATA = [
  {
    location: "New Delhi",
    state: "Delhi",
    courts: [
      "Saket District Court, Delhi",
      "Tis Hazari District Court, Delhi",
      "Patiala House District Court, Delhi",
      "Rohini District Court, Delhi",
      "Dwarka District Court, Delhi",
      "Karkardooma District Court, Delhi",
    ],
    policeStations: [
      "Connaught Place, Delhi",
      "Karol Bagh, Delhi",
      "Saket, Delhi",
      "Lajpat Nagar, Delhi",
      "Rohini, Delhi",
      "Dwarka, Delhi",
      "Shahdara, Delhi",
      "Civil Lines, Delhi",
    ],
  },
  {
    location: "Noida",
    state: "Uttar Pradesh",
    courts: [
      "District Court, Gautam Buddh Nagar (Noida)",
    ],
    policeStations: [
      "Noida Sector 20, Noida",
      "Noida Sector 63, Noida",
      "Greater Noida, Noida",
    ],
  },
  {
    location: "Gurugram",
    state: "Haryana",
    courts: [
      "District Court, Gurugram",
    ],
    policeStations: [
      "DLF Phase 1, Gurugram",
      "Sector 14, Gurugram",
      "Sadar, Gurugram",
    ],
  },
  {
    location: "Ghaziabad",
    state: "Uttar Pradesh",
    courts: [
      "District Court, Ghaziabad",
    ],
    policeStations: [
      "Kavi Nagar, Ghaziabad",
      "Sahibabad, Ghaziabad",
      "Indirapuram, Ghaziabad",
    ],
  },
  {
    location: "Faridabad",
    state: "Haryana",
    courts: [
      "District Court, Faridabad",
    ],
    policeStations: [
      "Sector 21, Faridabad",
      "Ballabgarh, Faridabad",
      "NIT, Faridabad",
    ],
  },
  {
    location: "Mumbai",
    state: "Maharashtra",
    courts: [
      "City Civil & Sessions Court, Mumbai",
      "Bandra District Court, Mumbai",
      "Andheri District Court, Mumbai",
      "Borivali District Court, Mumbai",
      "Dadar District Court, Mumbai",
    ],
    policeStations: [
      "Colaba, Mumbai",
      "Andheri, Mumbai",
      "Bandra, Mumbai",
      "Juhu, Mumbai",
      "Dadar, Mumbai",
      "Worli, Mumbai",
      "Powai, Mumbai",
    ],
  },
  {
    location: "Thane",
    state: "Maharashtra",
    courts: [
      "Thane District Court, Thane",
    ],
    policeStations: [
      "Thane Nagar, Thane",
      "Kasarvadavali, Thane",
      "Mumbra, Thane",
    ],
  },
  {
    location: "Pune",
    state: "Maharashtra",
    courts: [
      "Shivajinagar District Court, Pune",
      "Pimpri-Chinchwad District Court, Pune",
    ],
    policeStations: [
      "Koregaon Park, Pune",
      "Kothrud, Pune",
      "Hinjewadi, Pune",
      "Yerwada, Pune",
    ],
  },
  {
    location: "Nagpur",
    state: "Maharashtra",
    courts: [
      "District Court, Nagpur",
    ],
    policeStations: [
      "Sitabuldi, Nagpur",
      "Dharampeth, Nagpur",
      "Sadar, Nagpur",
    ],
  },
  {
    location: "Nashik",
    state: "Maharashtra",
    courts: [
      "District Court, Nashik",
    ],
    policeStations: [
      "Nashik Road, Nashik",
      "Panchavati, Nashik",
      "CIDCO, Nashik",
    ],
  },
  {
    location: "Chennai",
    state: "Tamil Nadu",
    courts: [
      "City Civil Court, Chennai",
      "Chengalpattu District Court, Chennai",
      "Madras High Court, Chennai",
    ],
    policeStations: [
      "T. Nagar, Chennai",
      "Anna Nagar, Chennai",
      "Mylapore, Chennai",
      "Adyar, Chennai",
      "Egmore, Chennai",
    ],
  },
  {
    location: "Coimbatore",
    state: "Tamil Nadu",
    courts: [
      "District Court, Coimbatore",
    ],
    policeStations: [
      "Coimbatore Central, Coimbatore",
      "Peelamedu, Coimbatore",
      "R.S. Puram, Coimbatore",
    ],
  },
  {
    location: "Madurai",
    state: "Tamil Nadu",
    courts: [
      "District Court, Madurai",
    ],
    policeStations: [
      "Madurai Central, Madurai",
      "Tallakulam, Madurai",
      "K.K. Nagar, Madurai",
    ],
  },
  {
    location: "Kolkata",
    state: "West Bengal",
    courts: [
      "City Civil Court, Kolkata",
      "Alipore District Court, Kolkata",
      "Barasat District Court, Kolkata",
      "Calcutta High Court, Kolkata",
    ],
    policeStations: [
      "Park Street, Kolkata",
      "Ballygunge, Kolkata",
      "Salt Lake, Kolkata",
      "New Market, Kolkata",
    ],
  },
  {
    location: "Bengaluru",
    state: "Karnataka",
    courts: [
      "City Civil Court, Bengaluru",
      "Karnataka High Court, Bengaluru",
    ],
    policeStations: [
      "Cubbon Park, Bengaluru",
      "Whitefield, Bengaluru",
      "Koramangala, Bengaluru",
      "Jayanagar, Bengaluru",
      "Electronic City, Bengaluru",
    ],
  },
  {
    location: "Mysuru",
    state: "Karnataka",
    courts: [
      "District Court, Mysuru",
    ],
    policeStations: [
      "Mysuru Central, Mysuru",
      "VV Mohalla, Mysuru",
      "Nazarbad, Mysuru",
    ],
  },
  {
    location: "Hyderabad",
    state: "Telangana",
    courts: [
      "City Civil Court, Hyderabad",
      "Ranga Reddy District Court, Hyderabad",
      "Telangana High Court, Hyderabad",
    ],
    policeStations: [
      "Banjara Hills, Hyderabad",
      "Begumpet, Hyderabad",
      "Jubilee Hills, Hyderabad",
      "Gachibowli, Hyderabad",
      "Secunderabad, Hyderabad",
    ],
  },
  {
    location: "Ahmedabad",
    state: "Gujarat",
    courts: [
      "City Civil Court, Ahmedabad",
      "Gujarat High Court, Ahmedabad",
    ],
    policeStations: [
      "Navrangpura, Ahmedabad",
      "Vastrapur, Ahmedabad",
      "Satellite, Ahmedabad",
      "Maninagar, Ahmedabad",
    ],
  },
  {
    location: "Surat",
    state: "Gujarat",
    courts: [
      "District Court, Surat",
    ],
    policeStations: [
      "Athwa, Surat",
      "Katargam, Surat",
      "Varachha, Surat",
    ],
  },
  {
    location: "Vadodara",
    state: "Gujarat",
    courts: [
      "District Court, Vadodara",
    ],
    policeStations: [
      "Sayajigunj, Vadodara",
      "Manjalpur, Vadodara",
      "Gotri, Vadodara",
    ],
  },
  {
    location: "Jaipur",
    state: "Rajasthan",
    courts: [
      "Jaipur District Court, Jaipur",
      "Rajasthan High Court, Jaipur",
    ],
    policeStations: [
      "Malviya Nagar, Jaipur",
      "Vaishali Nagar, Jaipur",
      "Mansarovar, Jaipur",
      "Sanganer, Jaipur",
    ],
  },
  {
    location: "Jodhpur",
    state: "Rajasthan",
    courts: [
      "District Court, Jodhpur",
      "Rajasthan High Court, Jodhpur",
    ],
    policeStations: [
      "Jodhpur Central, Jodhpur",
      "Sardarpura, Jodhpur",
      "Ratanada, Jodhpur",
    ],
  },
  {
    location: "Udaipur",
    state: "Rajasthan",
    courts: [
      "District Court, Udaipur",
    ],
    policeStations: [
      "Udaipur Central, Udaipur",
      "Hiran Magri, Udaipur",
    ],
  },
  {
    location: "Lucknow",
    state: "Uttar Pradesh",
    courts: [
      "Lucknow District Court, Lucknow",
      "Allahabad High Court (Lucknow Bench), Lucknow",
    ],
    policeStations: [
      "Hazratganj, Lucknow",
      "Gomti Nagar, Lucknow",
      "Aliganj, Lucknow",
      "Maharajganj, Lucknow",
    ],
  },
  {
    location: "Kanpur",
    state: "Uttar Pradesh",
    courts: [
      "Kanpur District Court, Kanpur",
    ],
    policeStations: [
      "Swaroop Nagar, Kanpur",
      "Kidwai Nagar, Kanpur",
      "Kakadeo, Kanpur",
    ],
  },
  {
    location: "Agra",
    state: "Uttar Pradesh",
    courts: [
      "Agra District Court, Agra",
    ],
    policeStations: [
      "Agra Central, Agra",
      "Sadar, Agra",
    ],
  },
  {
    location: "Varanasi",
    state: "Uttar Pradesh",
    courts: [
      "Varanasi District Court, Varanasi",
    ],
    policeStations: [
      "Varanasi Central, Varanasi",
      "Sigra, Varanasi",
      "Lanka, Varanasi",
    ],
  },
  {
    location: "Meerut",
    state: "Uttar Pradesh",
    courts: [
      "Meerut District Court, Meerut",
    ],
    policeStations: [
      "Meerut Central, Meerut",
      "Sadar Bazar, Meerut",
    ],
  },
  {
    location: "Patna",
    state: "Bihar",
    courts: [
      "Patna District Court, Patna",
      "Patna High Court, Patna",
    ],
    policeStations: [
      "Boring Road, Patna",
      "Kankarbagh, Patna",
      "Gandhi Maidan, Patna",
    ],
  },
  {
    location: "Bhopal",
    state: "Madhya Pradesh",
    courts: [
      "Bhopal District Court, Bhopal",
      "Madhya Pradesh High Court, Bhopal",
    ],
    policeStations: [
      "Arera Hills, Bhopal",
      "MP Nagar, Bhopal",
      "Habibganj, Bhopal",
    ],
  },
  {
    location: "Indore",
    state: "Madhya Pradesh",
    courts: [
      "Indore District Court, Indore",
    ],
    policeStations: [
      "Indore Central, Indore",
      "Vijay Nagar, Indore",
      "Palasia, Indore",
    ],
  },
  {
    location: "Chandigarh",
    state: "Chandigarh",
    courts: [
      "Chandigarh District Court, Chandigarh",
      "Punjab & Haryana High Court, Chandigarh",
    ],
    policeStations: [
      "Sector 17, Chandigarh",
      "Sector 26, Chandigarh",
      "Sector 34, Chandigarh",
    ],
  },
  {
    location: "Ludhiana",
    state: "Punjab",
    courts: [
      "Ludhiana District Court, Ludhiana",
    ],
    policeStations: [
      "Ludhiana Central, Ludhiana",
      "Model Town, Ludhiana",
    ],
  },
  {
    location: "Amritsar",
    state: "Punjab",
    courts: [
      "Amritsar District Court, Amritsar",
    ],
    policeStations: [
      "Amritsar Central, Amritsar",
      "Civil Lines, Amritsar",
    ],
  },
  {
    location: "Kochi",
    state: "Kerala",
    courts: [
      "Ernakulam District Court, Kochi",
      "Kerala High Court, Kochi",
    ],
    policeStations: [
      "Marine Drive, Kochi",
      "Kaloor, Kochi",
      "Edappally, Kochi",
    ],
  },
  {
    location: "Thiruvananthapuram",
    state: "Kerala",
    courts: [
      "District Court, Thiruvananthapuram",
    ],
    policeStations: [
      "Thiruvananthapuram Central, Thiruvananthapuram",
      "Kazhakootam, Thiruvananthapuram",
    ],
  },
  {
    location: "Bhubaneswar",
    state: "Odisha",
    courts: [
      "Bhubaneswar District Court, Bhubaneswar",
      "Orissa High Court, Cuttack",
    ],
    policeStations: [
      "Saheed Nagar, Bhubaneswar",
      "Nayapalli, Bhubaneswar",
      "Khandagiri, Bhubaneswar",
    ],
  },
  {
    location: "Guwahati",
    state: "Assam",
    courts: [
      "Guwahati District Court, Guwahati",
      "Gauhati High Court, Guwahati",
    ],
    policeStations: [
      "Guwahati Central, Guwahati",
      "Paltan Bazar, Guwahati",
      "Dispur, Guwahati",
    ],
  },
  {
    location: "Dehradun",
    state: "Uttarakhand",
    courts: [
      "Dehradun District Court, Dehradun",
    ],
    policeStations: [
      "Dehradun Central, Dehradun",
      "Rajpur, Dehradun",
    ],
  },
  {
    location: "Shimla",
    state: "Himachal Pradesh",
    courts: [
      "Shimla District Court, Shimla",
      "Himachal Pradesh High Court, Shimla",
    ],
    policeStations: [
      "Shimla Central, Shimla",
      "New Shimla, Shimla",
    ],
  },
  {
    location: "Ranchi",
    state: "Jharkhand",
    courts: [
      "Ranchi District Court, Ranchi",
      "Jharkhand High Court, Ranchi",
    ],
    policeStations: [
      "Ranchi Central, Ranchi",
      "Lalpur, Ranchi",
    ],
  },
  {
    location: "Raipur",
    state: "Chhattisgarh",
    courts: [
      "Raipur District Court, Raipur",
    ],
    policeStations: [
      "Raipur Central, Raipur",
      "Civil Lines, Raipur",
    ],
  },
  {
    location: "Visakhapatnam",
    state: "Andhra Pradesh",
    courts: [
      "Visakhapatnam District Court, Visakhapatnam",
    ],
    policeStations: [
      "Visakhapatnam Central, Visakhapatnam",
      "Dwaraka Nagar, Visakhapatnam",
    ],
  },
  {
    location: "Vijayawada",
    state: "Andhra Pradesh",
    courts: [
      "Vijayawada District Court, Vijayawada",
    ],
    policeStations: [
      "Vijayawada Central, Vijayawada",
      "Governorpet, Vijayawada",
    ],
  },
  {
    location: "Srinagar",
    state: "Jammu & Kashmir",
    courts: [
      "Srinagar District Court, Srinagar",
    ],
    policeStations: [
      "Srinagar Central, Srinagar",
      "Rajbagh, Srinagar",
    ],
  },
  {
    location: "Jammu",
    state: "Jammu & Kashmir",
    courts: [
      "Jammu District Court, Jammu",
    ],
    policeStations: [
      "Jammu Central, Jammu",
      "Gandhi Nagar, Jammu",
    ],
  },
];

// Helper functions for cascading dropdowns
export function getLocations() {
  return LOCATION_DATA.map(d => d.location);
}

export function getCourtsForLocation(location) {
  const found = LOCATION_DATA.find(d => d.location === location);
  return found?.courts || [];
}

export function getPoliceStationsForLocation(location) {
  const found = LOCATION_DATA.find(d => d.location === location);
  return found?.policeStations || [];
}

export function getStateForLocation(location) {
  const found = LOCATION_DATA.find(d => d.location === location);
  return found?.state || '';
}

// All unique courts/police stations (for fallback/free typing)
export const ALL_COURTS = [...new Set(LOCATION_DATA.flatMap(d => d.courts))];
export const ALL_POLICE_STATIONS = [...new Set(LOCATION_DATA.flatMap(d => d.policeStations))];

// Case-type specific statutes/sections for dropdown suggestions
export const CASE_TYPE_STATUTES = {
  Criminal: [
    "Section 138 NI Act (Cheque Bounce)",
    "Section 420 IPC (Cheating)",
    "Section 406 IPC (Criminal Breach of Trust)",
    "Section 379 IPC (Theft)",
    "Section 302 IPC (Murder)",
    "Section 307 IPC (Attempt to Murder)",
    "Section 354 IPC (Assault on Woman)",
    "Section 506 IPC (Criminal Intimidation)",
    "Section 34 IPC (Common Intention)",
    "Section 120B IPC (Criminal Conspiracy)",
    "Section 66 IT Act (Cyber Crime)",
    "Section 67 IT Act (Obscene Content)",
    "CrPC Section 438 (Anticipatory Bail)",
    "CrPC Section 439 (Regular Bail)",
    "CrPC Section 154 (FIR Registration)",
    "CrPC Section 173 (Charge Sheet)",
  ],
  Civil: [
    "Order 7 Rule 1 CPC (Plaint Particulars)",
    "Order 39 CPC (Temporary Injunction)",
    "Section 9 CPC (Civil Court Jurisdiction)",
    "Section 11 CPC (Res Judicata)",
    "Specific Relief Act, Section 10 (Specific Performance)",
    "Specific Relief Act, Section 38 (Perpetual Injunction)",
    "Indian Contract Act, Section 73 (Damages)",
    "Indian Contract Act, Section 74 (Liquidated Damages)",
    "Transfer of Property Act, Section 53A (Part Performance)",
    "Consumer Protection Act, Section 35 (Compensation)",
    "Limitation Act, Section 5 (Extension of Time)",
    "Arbitration Act, Section 9 (Interim Measures)",
    "Arbitration Act, Section 34 (Setting Aside Award)",
  ],
  "Family Law": [
    "Hindu Marriage Act, Section 13 (Divorce Grounds)",
    "Hindu Marriage Act, Section 13B (Mutual Consent Divorce)",
    "Hindu Marriage Act, Section 9 (Restitution of Conjugal Rights)",
    "Hindu Marriage Act, Section 24 (Maintenance Pendente Lite)",
    "Hindu Marriage Act, Section 25 (Permanent Alimony)",
    "Hindu Adoption & Maintenance Act, Section 18 (Wife's Maintenance)",
    "Guardian and Wards Act, Section 7 (Guardianship)",
    "Guardian and Wards Act, Section 17 (Custody)",
    "Protection of Women from DV Act, Section 18 (Protection Order)",
    "Protection of Women from DV Act, Section 20 (Monetary Relief)",
    "Special Marriage Act, Section 27 (Divorce)",
    "CrPC Section 125 (Maintenance)",
    "CrPC Section 127 (Alteration of Allowance)",
  ],
  "Labour / Employment": [
    "Industrial Disputes Act, Section 25F (Retrenchment Compensation)",
    "Industrial Disputes Act, Section 25N (Permission for Layoff)",
    "Industrial Disputes Act, Section 33 (Protected Workmen)",
    "Payment of Wages Act, Section 5 (Time of Payment)",
    "Payment of Wages Act, Section 7 (Deductions)",
    "Employees' Provident Funds Act, Section 6 (Contributions)",
    "Employees' State Insurance Act, Section 46 (Benefits)",
    "Maternity Benefit Act, Section 5 (Maternity Leave)",
    "Payment of Gratuity Act, Section 4 (Gratuity)",
    "Equal Remuneration Act, Section 4 (Equal Pay)",
    "Shops & Establishments Act (State-specific)",
    "Trade Unions Act, Section 2(h) (Registration)",
  ],
  Constitutional: [
    "Article 14 (Equality Before Law)",
    "Article 19(1)(a) (Freedom of Speech)",
    "Article 19(1)(g) (Right to Profession)",
    "Article 21 (Right to Life & Liberty)",
    "Article 22 (Protection Against Arrest)",
    "Article 32 (Supreme Court Writ Jurisdiction)",
    "Article 226 (High Court Writ Jurisdiction)",
    "Article 300A (Right to Property)",
    "Article 21A (Right to Education)",
    "Article 15 (Prohibition of Discrimination)",
    "Article 16 (Equality of Opportunity)",
    "Administrative Law - Principles of Natural Justice",
  ],
  "Property Dispute": [
    "Specific Relief Act, Section 5 (Recovery of Possession)",
    "Specific Relief Act, Section 6 (Possession of Immovable Property)",
    "Specific Relief Act, Section 38 (Perpetual Injunction)",
    "Transfer of Property Act, Section 53 (Fraudulent Transfer)",
    "Transfer of Property Act, Section 53A (Part Performance)",
    "Indian Easements Act, Section 4 (Easement Definition)",
    "Registration Act, Section 17 (Compulsory Registration)",
    "RERA, Section 12 (Project Registration)",
    "RERA, Section 18 (Return of Money with Interest)",
    "Limitation Act, Article 65 (Possession Suit - 12 Years)",
    "Hindu Succession Act, Section 6 (Coparcenary Rights)",
    "Partition Act, Section 2 (Partition Suit)",
  ],
};
/* Data dari mesin simulasi tervalidasi. Jangan diedit manual —
   di-generate oleh build_mockup.py. */
const ROLE_HOME = {
  "admin": "admin/dashboard.html",
  "teknisi": "teknisi/dashboard.html",
  "pelapor": "pelapor/dashboard.html"
};
const DB = {
 "users": [
  {
   "username": "admin",
   "nama": "Admin Helpdesk",
   "role": "admin",
   "tech_id": null
  },
  {
   "username": "t01",
   "nama": "Teknisi A",
   "role": "teknisi",
   "tech_id": "T01"
  },
  {
   "username": "pelapor",
   "nama": "Mahasiswa Contoh",
   "role": "pelapor",
   "tech_id": null
  }
 ],
 "techs": [
  {
   "id": "T01",
   "name": "Teknisi A",
   "status": "Available"
  },
  {
   "id": "T02",
   "name": "Teknisi B",
   "status": "Available"
  },
  {
   "id": "T03",
   "name": "Teknisi C",
   "status": "Available"
  },
  {
   "id": "T04",
   "name": "Teknisi D",
   "status": "Available"
  }
 ],
 "scen": {
  "S1": {
   "name": "S1 Baseline",
   "rule": "Lowest Active Workload (Available; tie-breaker ID)",
   "purpose": "Distribusi dasar (rule V2 setelah koreksi)",
   "max": 245,
   "min": 125,
   "gap": 120,
   "balance": 0.5102,
   "stdev": 54.47,
   "jains": 0.925,
   "gapw": 350,
   "jainsw": 0.9083,
   "avgw": 0.23,
   "maxw": 5,
   "last": "13:05",
   "total": 22,
   "cases": 20,
   "dur": 765,
   "ideal": 191.25,
   "loads": {
    "T01": {
     "dur": 245,
     "w": 570,
     "n": 7
    },
    "T02": {
     "dur": 245,
     "w": 600,
     "n": 7
    },
    "T03": {
     "dur": 125,
     "w": 250,
     "n": 4
    },
    "T04": {
     "dur": 150,
     "w": 380,
     "n": 4
    }
   }
  },
  "S2": {
   "name": "S2 Cumulative",
   "rule": "Lowest Cumulative Workload",
   "purpose": "Pemerataan berdasarkan total menit yang sudah ditugaskan (termasuk tiket Technician Request)",
   "max": 205,
   "min": 180,
   "gap": 25,
   "balance": 0.878,
   "stdev": 9.6,
   "jains": 0.9975,
   "gapw": 190,
   "jainsw": 0.9693,
   "avgw": 0.23,
   "maxw": 5,
   "last": "13:05",
   "total": 22,
   "cases": 20,
   "dur": 765,
   "ideal": 191.25,
   "loads": {
    "T01": {
     "dur": 185,
     "w": 520,
     "n": 4
    },
    "T02": {
     "dur": 180,
     "w": 345,
     "n": 6
    },
    "T03": {
     "dur": 195,
     "w": 535,
     "n": 5
    },
    "T04": {
     "dur": 205,
     "w": 400,
     "n": 7
    }
   }
  },
  "S3": {
   "name": "S3 Priority-aware",
   "rule": "Lowest Cumulative Weighted Workload",
   "purpose": "Priority ikut memengaruhi pemilihan",
   "max": 225,
   "min": 175,
   "gap": 50,
   "balance": 0.7778,
   "stdev": 19.8,
   "jains": 0.9894,
   "gapw": 100,
   "jainsw": 0.9927,
   "avgw": 0.23,
   "maxw": 5,
   "last": "13:05",
   "total": 22,
   "cases": 20,
   "dur": 765,
   "ideal": 191.25,
   "loads": {
    "T01": {
     "dur": 180,
     "w": 385,
     "n": 6
    },
    "T02": {
     "dur": 185,
     "w": 485,
     "n": 4
    },
    "T03": {
     "dur": 175,
     "w": 470,
     "n": 5
    },
    "T04": {
     "dur": 225,
     "w": 460,
     "n": 7
    }
   }
  },
  "S4": {
   "name": "S4 Redistribution",
   "rule": "Highest → Lowest",
   "purpose": "Menguji dampak redistribusi tiket antrean",
   "max": 210,
   "min": 180,
   "gap": 30,
   "balance": 0.8571,
   "stdev": 12.44,
   "jains": 0.9958,
   "gapw": 170,
   "jainsw": 0.9787,
   "avgw": 0.23,
   "maxw": 5,
   "last": "13:05",
   "total": 22,
   "cases": 20,
   "dur": 765,
   "ideal": 191.25,
   "loads": {
    "T01": {
     "dur": 210,
     "w": 490,
     "n": 6
    },
    "T02": {
     "dur": 180,
     "w": 410,
     "n": 5
    },
    "T03": {
     "dur": 195,
     "w": 535,
     "n": 5
    },
    "T04": {
     "dur": 180,
     "w": 365,
     "n": 6
    }
   }
  }
 },
 "tickets": [
  {
   "id": "T-001",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 08:00",
   "category": "Network",
   "detail": "Tidak bisa akses internet kampus dari lab",
   "priority": "High",
   "weight": 3,
   "duration": 60,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T01",
   "start": "08:00",
   "finish": "09:00",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T01",
    "start": "08:00",
    "finish": "09:00",
    "waiting": 0,
    "weighted_load": 180,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "08:00 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T01",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-002",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 08:10",
   "category": "Hardware",
   "detail": "Monitor tidak menyala saat dinyalakan",
   "priority": "Medium",
   "weight": 2,
   "duration": 30,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T02",
   "start": "08:10",
   "finish": "08:40",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T02",
    "start": "08:10",
    "finish": "08:40",
    "waiting": 0,
    "weighted_load": 60,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "08:10 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T02",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-003",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 08:15",
   "category": "Account",
   "detail": "Lupa password akun SIA, butuh reset",
   "priority": "High",
   "weight": 3,
   "duration": 45,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T03",
   "start": "08:15",
   "finish": "09:00",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T03",
    "start": "08:15",
    "finish": "09:00",
    "waiting": 0,
    "weighted_load": 135,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "08:15 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T03",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-004",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 08:20",
   "category": "Multimedia",
   "detail": "Proyektor ruang kelas tidak muncul gambar",
   "priority": "Low",
   "weight": 1,
   "duration": 20,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T04",
   "start": "08:20",
   "finish": "08:40",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T04",
    "start": "08:20",
    "finish": "08:40",
    "waiting": 0,
    "weighted_load": 20,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "08:20 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T04",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-005",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 08:35",
   "category": "Software",
   "detail": "Aplikasi akademik error saat login",
   "priority": "Medium",
   "weight": 2,
   "duration": 40,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T02",
   "start": "08:40",
   "finish": "09:20",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T02",
    "start": "08:40",
    "finish": "09:20",
    "waiting": 5,
    "weighted_load": 80,
    "rule_note": "Semua Busy → teknisi dengan waktu selesai paling cepat"
   },
   "history": [
    [
     "Tiket dibuat",
     "08:35 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T02",
     "mesin S2 · Semua Busy → teknisi dengan waktu selesai paling cepat",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-006",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 08:45",
   "category": "Network",
   "detail": "Koneksi WiFi putus-putus di gedung B",
   "priority": "High",
   "weight": 3,
   "duration": 50,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T04",
   "start": "08:45",
   "finish": "09:35",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T04",
    "start": "08:45",
    "finish": "09:35",
    "waiting": 0,
    "weighted_load": 150,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "08:45 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T04",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-007",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 09:00",
   "category": "Printer",
   "detail": "Printer macet, kertas tersangkut",
   "priority": "Low",
   "weight": 1,
   "duration": 15,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T03",
   "start": "09:00",
   "finish": "09:15",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T03",
    "start": "09:00",
    "finish": "09:15",
    "waiting": 0,
    "weighted_load": 15,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "09:00 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T03",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-008",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 09:05",
   "category": "Hardware",
   "detail": "Laptop tidak bisa connect ke proyektor",
   "priority": "Medium",
   "weight": 2,
   "duration": 35,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T01",
   "start": "09:05",
   "finish": "09:40",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T01",
    "start": "09:05",
    "finish": "09:40",
    "waiting": 0,
    "weighted_load": 70,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "09:05 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T01",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-009",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 09:20",
   "category": "Academic System",
   "detail": "Nilai mahasiswa tidak muncul di sistem akademik",
   "priority": "High",
   "weight": 3,
   "duration": 55,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T03",
   "start": "09:20",
   "finish": "10:15",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T03",
    "start": "09:20",
    "finish": "10:15",
    "waiting": 0,
    "weighted_load": 165,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "09:20 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T03",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-010",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 09:30",
   "category": "Network",
   "detail": "Kabel LAN longgar, koneksi hilang timbul",
   "priority": "Medium",
   "weight": 2,
   "duration": 25,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T02",
   "start": "09:30",
   "finish": "09:55",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T02",
    "start": "09:30",
    "finish": "09:55",
    "waiting": 0,
    "weighted_load": 50,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "09:30 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T02",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-011",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 09:45",
   "category": "CCTV/Infrastructure",
   "detail": "CCTV lantai 2 tidak merekam",
   "priority": "Low",
   "weight": 1,
   "duration": 30,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T04",
   "start": "09:45",
   "finish": "10:15",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T04",
    "start": "09:45",
    "finish": "10:15",
    "waiting": 0,
    "weighted_load": 30,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "09:45 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T04",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-012",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 10:00",
   "category": "Account",
   "detail": "Akun tidak bisa login, kemungkinan terkunci",
   "priority": "High",
   "weight": 3,
   "duration": 40,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T01",
   "start": "10:00",
   "finish": "10:40",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T01",
    "start": "10:00",
    "finish": "10:40",
    "waiting": 0,
    "weighted_load": 120,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "10:00 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T01",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-013",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 10:10",
   "category": "Software",
   "detail": "Update software menyebabkan aplikasi crash",
   "priority": "Medium",
   "weight": 2,
   "duration": 30,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T02",
   "start": "10:10",
   "finish": "10:40",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T02",
    "start": "10:10",
    "finish": "10:40",
    "waiting": 0,
    "weighted_load": 60,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "10:10 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T02",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-014",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 10:25",
   "category": "Multimedia",
   "detail": "Speaker ruang multimedia tidak berbunyi",
   "priority": "Low",
   "weight": 1,
   "duration": 20,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T04",
   "start": "10:25",
   "finish": "10:45",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T04",
    "start": "10:25",
    "finish": "10:45",
    "waiting": 0,
    "weighted_load": 20,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "10:25 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T04",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-015",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 10:40",
   "category": "Network",
   "detail": "Jaringan lambat saat jam sibuk",
   "priority": "High",
   "weight": 3,
   "duration": 60,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T03",
   "start": "10:40",
   "finish": "11:40",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T03",
    "start": "10:40",
    "finish": "11:40",
    "waiting": 0,
    "weighted_load": 180,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "10:40 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T03",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-016",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 10:55",
   "category": "Hardware",
   "detail": "Hardisk laptop bermasalah, sering hang",
   "priority": "Medium",
   "weight": 2,
   "duration": 35,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T04",
   "start": "10:55",
   "finish": "11:30",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T04",
    "start": "10:55",
    "finish": "11:30",
    "waiting": 0,
    "weighted_load": 70,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "10:55 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T04",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-017",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 11:10",
   "category": "Printer",
   "detail": "Tinta printer habis dan tidak terdeteksi",
   "priority": "Low",
   "weight": 1,
   "duration": 15,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T02",
   "start": "11:10",
   "finish": "11:25",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T02",
    "start": "11:10",
    "finish": "11:25",
    "waiting": 0,
    "weighted_load": 15,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "11:10 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T02",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-018",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 11:20",
   "category": "Academic System",
   "detail": "Sistem akademik tidak bisa diakses dari luar kampus",
   "priority": "High",
   "weight": 3,
   "duration": 50,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T01",
   "start": "11:20",
   "finish": "12:10",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T01",
    "start": "11:20",
    "finish": "12:10",
    "waiting": 0,
    "weighted_load": 150,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "11:20 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T01",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-019",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 11:35",
   "category": "Software",
   "detail": "Software lisensi expired",
   "priority": "Medium",
   "weight": 2,
   "duration": 40,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T02",
   "start": "11:35",
   "finish": "12:15",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T02",
    "start": "11:35",
    "finish": "12:15",
    "waiting": 0,
    "weighted_load": 80,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "11:35 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T02",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "T-020",
   "ticket_type": "User Report",
   "created_by": "User",
   "time": "2026-09-23 11:50",
   "category": "Network",
   "detail": "Jaringan mati total di satu ruangan",
   "priority": "Low",
   "weight": 1,
   "duration": 20,
   "related_id": null,
   "requested_by": null,
   "assigned_tech": "T04",
   "start": "11:50",
   "finish": "12:10",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T04",
    "start": "11:50",
    "finish": "12:10",
    "waiting": 0,
    "weighted_load": 20,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "11:50 oleh User",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T04",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "TK-001",
   "ticket_type": "Technician Request",
   "created_by": "Admin",
   "time": "2026-09-23 12:20",
   "category": "Network",
   "detail": "T04 minta bantuan konfigurasi switch tambahan untuk kasus T-006 (WiFi gedung B)",
   "priority": "Medium",
   "weight": 2,
   "duration": 20,
   "related_id": "T-006",
   "requested_by": "T04",
   "assigned_tech": "T03",
   "start": "12:20",
   "finish": "12:40",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T03",
    "start": "12:20",
    "finish": "12:40",
    "waiting": 0,
    "weighted_load": 40,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "12:20 oleh Admin",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T03",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  },
  {
   "id": "TK-002",
   "ticket_type": "Technician Request",
   "created_by": "Admin",
   "time": "2026-09-23 12:35",
   "category": "Network",
   "detail": "T02 minta bantuan cek beban server untuk kasus T-015 (jaringan lambat)",
   "priority": "High",
   "weight": 3,
   "duration": 30,
   "related_id": "T-015",
   "requested_by": "T02",
   "assigned_tech": "T04",
   "start": "12:35",
   "finish": "13:05",
   "lifecycle": "Open",
   "assignment": {
    "tech_id": "T04",
    "start": "12:35",
    "finish": "13:05",
    "waiting": 0,
    "weighted_load": 90,
    "rule_note": "Available + beban kumulatif (menit) terendah; tie-breaker ID"
   },
   "history": [
    [
     "Tiket dibuat",
     "12:35 oleh Admin",
     "bg-accent"
    ],
    [
     "Ditugaskan ke T04",
     "mesin S2 · Available + beban kumulatif (menit) terendah; tie-breaker ID",
     "bg-warn"
    ],
    [
     "Dikerjakan",
     "status alur kerja (usulan)",
     "bg-good"
    ]
   ]
  }
 ],
 "recent": [
  {
   "id": "T-018",
   "time": "11:20",
   "category": "Academic System",
   "detail": "Sistem akademik tidak bisa diakses dari luar kampus",
   "priority": "High",
   "duration": 50
  },
  {
   "id": "T-019",
   "time": "11:35",
   "category": "Software",
   "detail": "Software lisensi expired",
   "priority": "Medium",
   "duration": 40
  },
  {
   "id": "T-020",
   "time": "11:50",
   "category": "Network",
   "detail": "Jaringan mati total di satu ruangan",
   "priority": "Low",
   "duration": 20
  },
  {
   "id": "TK-001",
   "time": "12:20",
   "category": "Network",
   "detail": "T04 minta bantuan konfigurasi switch tambahan untuk kasus T-006 (WiFi gedung B)",
   "priority": "Medium",
   "duration": 20
  },
  {
   "id": "TK-002",
   "time": "12:35",
   "category": "Network",
   "detail": "T02 minta bantuan cek beban server untuk kasus T-015 (jaringan lambat)",
   "priority": "High",
   "duration": 30
  }
 ],
 "best_gap": "S2",
 "best_gapw": "S3"
};

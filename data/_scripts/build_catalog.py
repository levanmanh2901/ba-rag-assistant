import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)

catalog = [
    # ---- BRD ----
    ("BRD-001", "BRD/BRD_NapTien_v1.2.md", "BRD", "Nap_Tien", "1.2", "Approved", "2026-03-01", "Product Team"),
    ("BRD-002", "BRD/BRD_ChuyenTienP2P_v2.0.md", "BRD", "Chuyen_Tien_P2P", "2.0", "Approved", "2026-01-15", "Product Team"),
    ("BRD-003", "BRD/BRD_ThanhToanQR_v1.0.md", "BRD", "Thanh_Toan_QR", "1.0", "Approved", "2025-08-01", "Product Team"),
    ("BRD-004", "BRD/BRD_RutTien_v1.1.md", "BRD", "Rut_Tien", "1.1", "Approved", "2026-03-20", "Product Team"),
    # ---- SOP ----
    ("SOP-002", "SOP/SOP_KYC_v2.1.docx", "SOP", "KYC", "2.1", "Approved", "2026-02-15", "Compliance Team"),
    ("SOP-003", "SOP/SOP_XuLyKhieuNai_v1.5.md", "SOP", "Khieu_Nai", "1.5", "Approved", "2026-01-10", "Customer Support & Risk Team"),
    ("SOP-005", "SOP/SOP_DoiSoat_v2.0.docx", "SOP", "Doi_Soat", "2.0", "Approved", "2026-03-01", "Finance & Operations Team"),
    # ---- Business Rules ----
    ("BR-002", "BusinessRules/BusinessRules_HanMucGiaoDich_v3.0.md", "BusinessRules", "Han_Muc_Giao_Dich", "3.0", "Approved", "2026-02-01", "Compliance & Product Team"),
    ("BR-004", "BusinessRules/BusinessRules_PhongChongGianLan_v2.0.md", "BusinessRules", "Phong_Chong_Gian_Lan", "2.0", "Approved", "2026-01-05", "Risk & Compliance Team"),
    # ---- Deprecated ----
    ("BR-002-v1", "Deprecated/BusinessRules_HanMucGiaoDich_v1.0_DEPRECATED.md", "BusinessRules", "Han_Muc_Giao_Dich", "1.0", "Deprecated", "2024-10-01", "Compliance & Product Team"),
    # ---- User Stories ----
    ("US-EPIC-014", "UserStories/UserStories_Epic_QRPay.md", "UserStory", "Thanh_Toan_QR", "1.0", "In Progress", "2026-04-10", "PO"),
    ("US-EPIC-021", "UserStories/UserStories_Epic_NapTien.md", "UserStory", "Nap_Tien", "1.0", "In Progress", "2026-05-05", "PO"),
    # ---- FAQ ----
    ("FAQ-001", "FAQ/FAQ_HoTroKhachHang.md", "FAQ", "General", "2.3", "Approved", "2026-05-01", "Customer Support Team"),
    ("FAQ-002", "FAQ/FAQ_Merchant.md", "FAQ", "Merchant", "1.2", "Approved", "2026-04-20", "Business Development Team"),
    # ---- Glossary ----
    ("GL-001", "Glossary/Glossary_DataDictionary.md", "Glossary", "General", "1.4", "Approved", "2026-04-01", "Product & Data Team"),
    # ---- Fees / Limits (Excel) ----
    ("FEE-001", "Fees/BangPhi_ManhPay_v2.4.xlsx", "Fee_Pricing_Table", "General", "2.4", "Approved", "2026-04-01", "Finance & Product Team"),
    ("LIMIT-001", "Limits/MaTran_HanMuc_SLA_ManhPay_v1.2.xlsx", "Limit_SLA_Matrix", "General", "1.2", "Approved", "2026-02-01", "Compliance & Product Team"),
    # ---- Incident / Change / Integration ----
    ("INC-001", "IncidentReports/INC_001_LoiDoiSoatNapTien.md", "IncidentReport", "Nap_Tien", "1.0", "Closed", "2026-02-08", "Engineering & Operations Team"),
    ("CR-LOG-001", "ChangeRequests/CR_LichSuThayDoiPhi.md", "ChangeRequest", "General", "1.0", "Approved", "2026-04-15", "Product & Finance Team"),
    ("INT-001", "Integration/IntegrationSpec_Napas247.md", "IntegrationSpec", "Tich_Hop_Ngan_Hang", "1.3", "Approved", "2026-02-01", "Engineering & Product Team"),
]

records = []
missing = []
for doc_id, path, dtype, module, version, status, eff, owner in catalog:
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        missing.append(path)
    records.append({
        "doc_id": doc_id,
        "file_path": path,
        "doc_type": dtype,
        "module": module,
        "version": version,
        "status": status,
        "effective_date": eff,
        "owner": owner,
        "file_format": os.path.splitext(path)[1].lstrip("."),
    })

if missing:
    print("THIẾU FILE:", missing)
    sys.exit(1)

out = os.path.join(ROOT, "metadata_catalog.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

# --- Thống kê ---
from collections import Counter
print(f"Tổng số tài liệu: {len(records)}")
print("Theo doc_type:", dict(Counter(r["doc_type"] for r in records)))
print("Theo định dạng:", dict(Counter(r["file_format"] for r in records)))
print("Theo status:", dict(Counter(r["status"] for r in records)))
print("Số module:", len(set(r["module"] for r in records)))

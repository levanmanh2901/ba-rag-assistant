const { Document, Packer, Paragraph, TextRun, HeadingLevel } = require("docx");

const metaLine = (label, value) => new Paragraph({
  children: [
    new TextRun({ text: `${label}: `, bold: true }),
    new TextRun({ text: value }),
  ],
});

const heading = (text, level) => new Paragraph({ text, heading: level });
const bullet = (text) => new Paragraph({ text, bullet: { level: 0 } });
const numbered = (text) => new Paragraph({
  text,
  numbering: { reference: "sop-numbering", level: 0 },
});

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "sop-numbering",
        levels: [
          { level: 0, format: "decimal", text: "%1.", alignment: "start" },
        ],
      },
    ],
  },
  sections: [
    {
      properties: { page: { size: { width: 12240, height: 15840 } } },
      children: [
        new Paragraph({ text: "SOP - Quy trình xác thực định danh khách hàng (eKYC)", heading: HeadingLevel.TITLE }),
        metaLine("Mã tài liệu", "SOP-002"),
        metaLine("Loại tài liệu", "SOP"),
        metaLine("Module", "KYC"),
        metaLine("Phiên bản", "2.1"),
        metaLine("Trạng thái", "Approved"),
        metaLine("Ngày hiệu lực", "2026-02-15"),
        metaLine("Chủ sở hữu", "Compliance Team"),
        new Paragraph({ text: "" }),

        heading("1. Mục đích", HeadingLevel.HEADING_1),
        new Paragraph("Quy định quy trình chuẩn để xác thực danh tính khách hàng (eKYC) khi đăng ký hoặc nâng cấp Tier tài khoản ManhPay, đảm bảo tuân thủ quy định của Ngân hàng Nhà nước (NHNN) về phòng chống rửa tiền."),

        heading("2. Phạm vi áp dụng", HeadingLevel.HEADING_1),
        bullet("Áp dụng cho toàn bộ khách hàng cá nhân đăng ký mới hoặc nâng Tier tài khoản."),
        bullet("Không áp dụng cho tài khoản doanh nghiệp (xem SOP-007 riêng)."),

        heading("3. Quy trình xác thực Tier 1 lên Tier 2 (eKYC cơ bản)", HeadingLevel.HEADING_1),
        numbered("Khách hàng vào mục Tài khoản > Xác thực danh tính."),
        numbered("Chụp ảnh mặt trước và mặt sau CCCD/CMND."),
        numbered("Hệ thống OCR tự động trích xuất thông tin (họ tên, số CCCD, ngày sinh, địa chỉ)."),
        numbered("Khách hàng thực hiện selfie kèm chuyển động khuôn mặt (liveness detection) để chống giả mạo."),
        numbered("Hệ thống đối chiếu khuôn mặt selfie với ảnh trên giấy tờ (face matching), ngưỡng chấp nhận tối thiểu 85% độ tương đồng."),
        numbered("Nếu đạt yêu cầu, tài khoản tự động được nâng lên Tier 2 trong vòng 5 phút."),
        numbered("Nếu không đạt (độ tương đồng dưới 85% hoặc giấy tờ không rõ nét), hệ thống yêu cầu chụp lại tối đa 3 lần, sau đó chuyển sang xét duyệt thủ công bởi nhân viên Compliance trong vòng 4 giờ làm việc."),

        heading("4. Quy trình xác thực Tier 2 lên Tier 3 (eKYC nâng cao)", HeadingLevel.HEADING_1),
        numbered("Khách hàng yêu cầu nâng Tier 3 từ mục Tài khoản > Nâng cấp hạn mức."),
        numbered("Hệ thống gửi yêu cầu đối chiếu thông tin với Cơ sở dữ liệu quốc gia về dân cư qua kênh VNeID hoặc đối tác định danh được NHNN cấp phép."),
        numbered("Khách hàng xác nhận đồng ý chia sẻ thông tin qua ứng dụng VNeID (nếu dùng kênh này)."),
        numbered("Kết quả đối chiếu trả về trong vòng tối đa 24 giờ làm việc."),
        numbered("Nếu khớp thông tin, tài khoản được nâng lên Tier 3; nếu không khớp, hệ thống thông báo lý do cụ thể (VD: thông tin CCCD đã thay đổi, cần cập nhật lại)."),

        heading("5. Các trường hợp từ chối và xử lý", HeadingLevel.HEADING_1),
        bullet("Giấy tờ tùy thân đã hết hạn: từ chối, yêu cầu khách hàng cập nhật giấy tờ mới."),
        bullet("Nghi ngờ giấy tờ giả mạo (phát hiện qua thuật toán chống giả mạo): tài khoản bị đánh dấu review, chuyển sang đội Compliance điều tra, tạm khóa chức năng nâng Tier trong thời gian chờ."),
        bullet("Khách hàng dưới 18 tuổi: từ chối xác thực, theo quy định NHNN về độ tuổi mở ví điện tử."),

        heading("6. Chỉ số vận hành (SLA)", HeadingLevel.HEADING_1),
        bullet("Xử lý tự động (automated): dưới 5 phút, tỷ lệ xử lý tự động thành công mục tiêu > 80%."),
        bullet("Xử lý thủ công (manual review): dưới 4 giờ làm việc trong ngày, dưới 24 giờ nếu phát sinh ngoài giờ hành chính."),

        heading("7. Lịch sử thay đổi", HeadingLevel.HEADING_1),
        bullet("v1.0 (2025-05-01): Khởi tạo quy trình."),
        bullet("v2.0 (2025-10-01): Bổ sung kênh xác thực qua VNeID cho Tier 3."),
        bullet("v2.1 (2026-02-15): Điều chỉnh ngưỡng face matching từ 80% lên 85% theo khuyến nghị audit bảo mật."),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => require("fs").writeFileSync("SOP_KYC_v2.1.docx", buf));
